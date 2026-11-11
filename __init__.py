"""PatchReview: route recognized file writes through Hermes' native human approval gate."""
from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import Any

_WRITE_TOOL_NAMES = frozenset({
    "write_file", "create_file", "edit_file", "str_replace",
    "search_replace", "patch", "apply_patch",
})
_PATH_KEYS = ("path", "file_path", "filename", "file", "target")
_CONTENT_KEYS = ("content", "new_content", "text", "body")


def _is_write_tool(name: str) -> bool:
    normalized = str(name or "").lower().rsplit(".", 1)[-1]
    return any(normalized == item or normalized.endswith("_" + item)
               for item in _WRITE_TOOL_NAMES)


def _first_string(args: dict, keys: tuple[str, ...]):
    for key in keys:
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _extract_change(tool_name: str, args: dict):
    path = _first_string(args, _PATH_KEYS)
    if not path:
        return None
    target = Path(os.path.abspath(os.path.expanduser(path)))
    if target.is_symlink() or (target.exists() and not target.is_file()):
        return None
    try:
        old = target.read_text(encoding="utf-8") if target.exists() else ""
    except (OSError, UnicodeError):
        return None

    old_string, new_string = args.get("old_string"), args.get("new_string")
    if isinstance(old_string, str) and isinstance(new_string, str) and old_string:
        # Hermes' patch tool and string-replacement tools share this shape.
        # Use an exact match for the preview; Hermes remains responsible for
        # applying the original call with its own matching semantics.
        if old_string not in old:
            return None
        replace_all = bool(args.get("replace_all", False))
        new = old.replace(old_string, new_string) if replace_all else old.replace(old_string, new_string, 1)
    else:
        # Multi-file/opaque patch payloads cannot be represented safely as a
        # single-file diff, so fail closed.
        if str(args.get("mode", "")).lower() == "patch" or "patch" in tool_name.lower():
            return None
        new = None
        for key in _CONTENT_KEYS:
            if key in args:
                new = args[key] if isinstance(args[key], str) else None
                break
        if new is None:
            return None

    diff = "".join(difflib.unified_diff(
        old.splitlines(keepends=True), new.splitlines(keepends=True),
        fromfile="a/" + str(target), tofile="b/" + str(target), lineterm="\n"
    ))
    if not diff:
        diff = "(No textual changes.)"
    return str(target), diff


def register(ctx: Any):
    def pre_tool_call(tool_name="", args=None, task_id="", **kwargs):
        del task_id, kwargs
        name = str(tool_name or "")
        if not _is_write_tool(name):
            return None
        parsed = _extract_change(name, args if isinstance(args, dict) else {})
        if parsed is None:
            return {
                "action": "block",
                "message": (
                    "PatchReview cannot safely summarize this write request "
                    "(unsupported arguments, unreadable/non-text file, or invalid target). "
                    "No write was performed."
                ),
            }
        path, diff = parsed
        preview = diff[:6000]
        if len(diff) > 6000:
            preview += "\n... diff truncated ..."
        return {
            "action": "approve",
            "message": (
                "PatchReview human review required. Hermes will execute the original "
                "write tool only if you approve it. PatchReview does not write files.\n"
                f"Tool: {name}\nTarget: {path}\n\nProposed diff:\n{preview}"
            ),
        }

    ctx.register_hook("pre_tool_call", pre_tool_call)

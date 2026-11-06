"""PatchReview: stage file changes until a human explicitly accepts them."""
from __future__ import annotations
import difflib, hashlib, json, os, tempfile, threading, uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_WRITE_MARKERS = ("write_file", "patch", "apply_patch", "create_file", "edit_file", "str_replace", "search_replace")
_PATH_KEYS = ("path", "file_path", "filename", "file", "target")
_CONTENT_KEYS = ("content", "new_content", "new_string", "text", "body")
_LOCK = threading.RLock()

def _now():
    return datetime.now(timezone.utc).isoformat()

def _json(data):
    return json.dumps(data, ensure_ascii=False, indent=2)

def _data_dir(ctx):
    candidate = None
    getter = getattr(ctx, "plugin_data_dir", None)
    if callable(getter):
        try: candidate = getter()
        except Exception: candidate = None
    if candidate:
        root = Path(candidate).expanduser()
    else:
        home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()
        root = home / "plugin-data" / "patchreview"
    root.mkdir(parents=True, exist_ok=True)
    return root

def _load(queue_file):
    try:
        value = json.loads(queue_file.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError("Cannot read PatchReview queue: " + str(exc))

def _save(queue_file, proposals):
    queue_file.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="pending-", suffix=".json", dir=str(queue_file.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(proposals, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, queue_file)
    finally:
        try: os.unlink(temp_name)
        except FileNotFoundError: pass

def _hash(value):
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()

def _diff(path, old, new):
    before = (old or "").splitlines(keepends=True)
    after = new.splitlines(keepends=True)
    result = "".join(difflib.unified_diff(before, after, fromfile="a/" + path, tofile="b/" + path, lineterm="\n"))
    return result or "--- a/" + path + "\n+++ b/" + path + "\n(no textual changes)\n"

def _first_string(args, keys):
    for key in keys:
        value = args.get(key)
        if isinstance(value, str) and value.strip(): return value
    return None

def _extract_proposal(tool_name, args):
    path = _first_string(args, _PATH_KEYS)
    if not path: return None
    path = os.path.expanduser(path)
    lowered = tool_name.lower()
    if "str_replace" in lowered or "search_replace" in lowered:
        old_string, new_string = args.get("old_string"), args.get("new_string")
        if not isinstance(old_string, str) or not isinstance(new_string, str): return None
        try: old_content = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
        except (OSError, UnicodeError): return None
        if old_string not in old_content: return None
        return path, old_content.replace(old_string, new_string, 1), old_content
    content = _first_string(args, _CONTENT_KEYS)
    if content is None: return None
    try: old_content = Path(path).read_text(encoding="utf-8") if Path(path).exists() else None
    except (OSError, UnicodeError): return None
    return path, content, old_content

def _summary(item):
    return {key: item.get(key) for key in ("id", "path", "tool", "status", "old_hash", "new_hash", "created_at")} | {"diff_preview": item.get("diff", "")[:5000]}

def register(ctx: Any):
    queue_file = _data_dir(ctx) / "pending.json"

    def mutate(fn):
        with _LOCK:
            proposals = _load(queue_file)
            result = fn(proposals)
            _save(queue_file, proposals)
            return result

    def pre_tool_call(tool_name="", args=None, task_id="", **kwargs):
        del task_id, kwargs
        name = str(tool_name or "")
        if not any(marker in name.lower() for marker in _WRITE_MARKERS): return None
        parsed = _extract_proposal(name, args if isinstance(args, dict) else {})
        if parsed is None: return None
        path, new_content, old_content = parsed
        pid = uuid.uuid4().hex[:8]
        item = {
            "id": pid, "path": path, "tool": name, "old_content": old_content,
            "new_content": new_content, "diff": _diff(path, old_content, new_content),
            "old_hash": _hash(old_content), "new_hash": _hash(new_content),
            "status": "pending", "created_at": _now(), "updated_at": _now(), "reason": None
        }
        try:
            mutate(lambda proposals: proposals.append(item))
        except Exception as exc:
            return {"action": "block", "message": "PatchReview could not persist the proposal; write blocked: " + str(exc)}
        return {"action": "block", "message": "PatchReview blocked " + name + ". Proposal " + pid + " for " + path + " is pending human review. Call patchreview_list, then patchreview_accept with id " + pid + ", or patchreview_reject."}

    def handle_list(params, **kwargs):
        del kwargs
        status = str(params.get("status", "pending")).lower()
        if status not in ("pending", "accepted", "rejected", "all"):
            return _json({"success": False, "error": "status must be pending, accepted, rejected, or all"})
        with _LOCK: proposals = _load(queue_file)
        chosen = proposals if status == "all" else [p for p in proposals if p.get("status") == status]
        return _json({"success": True, "count": len(chosen), "proposals": [_summary(p) for p in chosen]})

    def accept_one(proposals, pid):
        item = next((p for p in proposals if p.get("id") == pid), None)
        if item is None: raise KeyError("Proposal " + repr(pid) + " not found")
        if item.get("status") != "pending": raise ValueError("Proposal " + pid + " is not pending")
        target = Path(item["path"]).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix="." + target.name + ".patchreview-", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                handle.write(item["new_content"])
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            try: os.unlink(temp_name)
            except FileNotFoundError: pass
        item["status"], item["updated_at"] = "accepted", _now()
        return {"id": pid, "path": str(target), "status": "accepted", "new_hash": item["new_hash"]}

    def handle_accept(params, **kwargs):
        del kwargs
        pid = str(params.get("id", "")).strip()
        if not pid: return _json({"success": False, "error": "id is required"})
        try: return _json({"success": True, **mutate(lambda proposals: accept_one(proposals, pid))})
        except Exception as exc: return _json({"success": False, "error": str(exc)})

    def handle_reject(params, **kwargs):
        del kwargs
        pid, reason = str(params.get("id", "")).strip(), str(params.get("reason", "")).strip() or None
        if not pid: return _json({"success": False, "error": "id is required"})
        def reject(proposals):
            item = next((p for p in proposals if p.get("id") == pid), None)
            if item is None: raise KeyError("Proposal " + repr(pid) + " not found")
            if item.get("status") != "pending": raise ValueError("Proposal " + pid + " is not pending")
            item.update(status="rejected", reason=reason, updated_at=_now())
            return {"id": pid, "path": item["path"], "status": "rejected", "reason": reason}
        try: return _json({"success": True, **mutate(reject)})
        except Exception as exc: return _json({"success": False, "error": str(exc)})

    def handle_accept_all(params, **kwargs):
        del params, kwargs
        try:
            accepted = mutate(lambda proposals: [accept_one(proposals, p["id"]) for p in list(proposals) if p.get("status") == "pending"])
            return _json({"success": True, "accepted_count": len(accepted), "accepted": accepted})
        except Exception as exc: return _json({"success": False, "error": str(exc)})

    def handle_status(params, **kwargs):
        del params, kwargs
        with _LOCK: proposals = _load(queue_file)
        counts = {s: sum(1 for p in proposals if p.get("status") == s) for s in ("pending", "accepted", "rejected")}
        return _json({"success": True, **counts, "total": len(proposals)})

    def add_tool(name, description, properties, required, handler):
        schema = {"name": name, "description": description, "parameters": {"type": "object", "properties": properties, "required": required}}
        ctx.register_tool(name=name, toolset="patchreview", schema=schema, handler=handler)

    add_tool("patchreview_list", "List staged file changes for human review.", {"status": {"type": "string", "enum": ["pending", "accepted", "rejected", "all"], "description": "Filter; defaults to pending."}}, [], handle_list)
    add_tool("patchreview_accept", "Accept one staged proposal and write its new content to disk.", {"id": {"type": "string", "description": "Proposal id to accept."}}, ["id"], handle_accept)
    add_tool("patchreview_reject", "Reject one staged proposal without changing the file on disk.", {"id": {"type": "string", "description": "Proposal id to reject."}, "reason": {"type": "string", "description": "Optional rejection reason."}}, ["id"], handle_reject)
    add_tool("patchreview_accept_all", "Accept every pending proposal and write them to disk.", {}, [], handle_accept_all)
    add_tool("patchreview_status", "Return pending, accepted, rejected, and total proposal counts.", {}, [], handle_status)
    ctx.register_hook("pre_tool_call", pre_tool_call)
    ctx.patchreview_queue_file = queue_file

# PatchReview

**A human approval layer for Hermes file-writing tools.**

PatchReview hooks recognized file-write calls and escalates them to Hermes' native human-approval gate with a proposed diff. If the user approves, Hermes continues with the original tool call. If the user denies, the write does not proceed.

## How it works

1. Hermes is about to execute a recognized file-writing tool.
2. PatchReview reads the target text file and prepares a diff preview. It does not modify the file.
3. PatchReview returns Hermes' `{"action": "approve", "message": "..."}` directive.
4. Hermes presents its own approval prompt. The user decides.
5. On approval, Hermes executes the original tool through its normal write path and protections.

PatchReview does not expose accept/approve tools to the model, maintain a separate approval queue, or write files itself. This avoids model self-approval and preserves Hermes' native write guards.

## Install

```bash
hermes plugins install Bilalsnz/plugin --no-deps --no-enable
hermes plugins doctor patchreview --ci
hermes plugins enable patchreview
```

Restart Hermes if the current process was already running.

## Coverage and limitations

The hook recognizes `write_file`, `create_file`, `edit_file`, `str_replace`, `search_replace`, `patch`, and `apply_patch` tool names. For full-content writes it reads a UTF-8 target and previews the proposed content. For string replacements, including Hermes' core `patch` tool when it supplies `old_string` and `new_string`, it computes a preview using those fields and the optional `replace_all` flag. Replacement previews preserve the surrounding file content. Matching is exact for preview generation, so some edits that Hermes' fuzzy matcher could apply may be blocked if the exact `old_string` is not present.

If PatchReview cannot safely parse the request, read the target, or produce a preview, it blocks that recognized call rather than silently allowing an unreviewed write. Opaque or multi-file patch payloads are currently unsupported and are blocked.

PatchReview is a plugin-level tool-call guardrail, not an operating-system sandbox. It cannot intercept shell commands, arbitrary scripts, unrelated processes, or write tools whose names are not recognized. Hermes' native approval behavior and platform/session policy determine whether an approval prompt is available; unattended or unsupported contexts may deny the call.

The plugin itself does not write target files, invoke shell commands, make network requests, send telemetry, store credentials, or run background processes.

## Validation

```bash
python -m unittest discover -s tests -v
hermes plugins doctor . --ci
hermes plugins validate . --install-deps
```

## Demo

Demonstrate a normal Hermes file-write request, show the native Hermes approval prompt with PatchReview's diff summary, approve one operation, then deny another. Verify the resulting files using Hermes' normal tools. The bundled HTML page, if shown, is an offline visual mockup and is not connected to the live approval flow.

## License

MIT. See [LICENSE](LICENSE).

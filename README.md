# PatchReview

**Review the diff before a supported Hermes file-write tool can change a file.**

PatchReview is a Hermes Agent Python plugin. Its `pre_tool_call` hook intercepts recognized file-writing tools, stages the proposed UTF-8 content in a persistent review queue, and blocks the original tool call. A human must explicitly accept or reject the proposal through PatchReview's tools.

## What it does

1. Recognizes supported write-tool names before the tool executes.
2. Extracts the target path and proposed content, or computes an exact string replacement.
3. Stores the old/new content, SHA-256 hashes, timestamps, and unified diff in Hermes plugin data.
4. Blocks the original write after the proposal is safely queued.
5. Allows a human to inspect, accept, or reject the staged proposal.

If a recognized write tool is called with an unsupported or invalid argument shape, PatchReview now blocks it instead of silently allowing it through. If queue persistence fails, the original write is also blocked.

## Install

Install the repository through Hermes' plugin manager:

```bash
hermes plugins install Bilalsnz/plugin --no-deps --no-enable
hermes plugins doctor patchreview --ci
hermes plugins enable patchreview
```

Restart Hermes after activation if the current process was already running. Plugin activation may trigger Hermes environment synchronization; on resource-constrained Android/Termux devices, review the installer's proposed work before approving it.

The plugin declares no third-party Python dependencies. The repository is flat: `__init__.py`, `plugin.yaml`, and the supporting files live at its root.
PatchReview itself makes no network requests, sends no telemetry, and does not require API keys.

## Tools

| Tool | Purpose |
| --- | --- |
| `patchreview_status` | Count pending, accepted, and rejected proposals. |
| `patchreview_list` | List proposals, defaulting to pending; supports status filters. |
| `patchreview_accept` | Apply one pending proposal by ID. |
| `patchreview_reject` | Reject one pending proposal without writing it. |
| `patchreview_accept_all` | Apply every pending proposal. Use only when you intend to approve the entire queue. |

## Architecture

```text
Hermes write tool call
        |
        v
pre_tool_call hook
        |
        +-- unrelated tool name ----------> continue normally
        |
        v
recognized write tool
        |
        +-- unsupported/invalid arguments -> BLOCK
        |
        v
read current UTF-8 file (if present)
        |
        v
build proposal + unified diff + hashes
        |
        v
persist proposal in plugin-data/pending.json
        |
        +-- persistence error -------------> BLOCK
        |
        v
BLOCK original write; return proposal ID
        |
        v
Human reviews proposal
        |
        +----------+-------------+
        |                        |
      ACCEPT                   REJECT
        |                        |
 verify original file         mark rejected
 has not changed                 |
        |                        v
 atomically replace file      disk unchanged
        |
 mark accepted
```

The queue is stored in the profile-scoped directory returned by Hermes' `plugin_data_dir("patchreview")`. Queue updates use a temporary file and `os.replace`. Accepted file content is written to a temporary file in the target directory and then atomically replaced into place.

## Supported write calls and fail-closed behavior

The hook recognizes these tool-name patterns (case-insensitive): `write_file`, `create_file`, `edit_file`, `str_replace`, `search_replace`, `patch`, and `apply_patch`.

For full-content writes, it accepts a string path from `path`, `file_path`, `filename`, `file`, or `target`, and a string body from `content`, `new_content`, `new_string`, `text`, or `body`. Empty string content is valid.

For `str_replace` and `search_replace`, it requires `old_string` and `new_string`, reads the current UTF-8 file, and stages the first exact occurrence replacement. If the target cannot be read, the old text is absent, or arguments cannot be parsed, the recognized call is blocked. Opaque patch/diff formats that cannot be safely converted to complete file content are blocked rather than passed through.

Symbolic-link targets and non-regular-file targets are refused. Before acceptance, PatchReview checks that the target's existence state and content hash still match the staged baseline. A changed file must be reviewed again through a fresh proposal.

## Security boundaries and limitations

PatchReview is a **tool-call guardrail**, not an operating-system sandbox or a complete filesystem security boundary.

- It intercepts only the recognized Hermes tool names above. A different write tool, shell command, terminal command, script, or unrelated process can still write files without passing through this hook.
- A recognized tool call with an unsupported argument shape is blocked. However, an unrecognized tool name is outside the hook's coverage.
- The hook handles UTF-8 text files, not binary files.
- String replacement stages only the first exact match.
- Symlink targets are refused, but this is not a general defense against every filesystem race or hostile concurrent process. Another process with access to the same files may still race the final check and replacement.
- The proposal queue is local plugin data. Anyone with sufficient access to the same OS account and files may be able to inspect or alter it.
- The queue and target file cannot be committed as one cross-filesystem transaction. A process crash or storage failure at the wrong moment can leave recovery work to the operator.
- `patchreview_accept_all` approves every currently pending proposal. Review the queue before using it.
- The bundled HTML UI is an offline visual demo with sample data. Its buttons do not connect to Hermes' live queue and do not perform filesystem writes.

Do not describe PatchReview as preventing all filesystem writes. Its guarantee is narrower: it blocks recognized, parseable write-tool calls until a proposal is queued, and it blocks recognized calls it cannot safely parse.

## Review UI

Open `ui/review.html` directly in a browser. It runs offline with sample proposals. The UI is for presentation only and is not a live queue client.

## Validation

Run the plugin checks from the repository root:

```bash
hermes plugins doctor . --ci
hermes plugins validate . --install-deps
```

The project CI workflow runs the same Hermes Doctor and catalog validator checks on pushes and pull requests.

## 90-second demo outline

1. Show PatchReview loaded in Hermes.
2. Ask Hermes to create a harmless file using its normal `write_file` tool.
3. Show the blocked write and proposal ID.
4. Inspect the pending proposal and diff with `patchreview_list`.
5. Accept it and verify the file content on disk.
6. Stage a second harmless write, reject it, and verify that the file was not created.
7. Briefly show the offline review UI, clearly identifying it as a visual demo.

Use actual plugin behavior in the recording, not a scripted mock.

## Catalog submission

1. Run the validation commands and confirm CI passes.
2. Pin the catalog entry to the exact commit containing the reviewed plugin version.
3. Keep the catalog PR description aligned with the security boundaries above.
4. Publish the demo video under 90 seconds and tag `@NousResearch`.
5. Submit the catalog PR URL and video URL through the organizer's submission form before the official deadline.

## Why a plugin instead of a prompt?

A prompt can ask an agent to request permission, but it cannot enforce that request at the tool-call boundary. PatchReview uses Hermes' `pre_tool_call` hook to block recognized write calls before execution, persist a proposal, and expose explicit review tools. Its protection remains limited to the tools and argument shapes it recognizes.

## License

MIT. See [LICENSE](LICENSE).

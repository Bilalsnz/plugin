# PatchReview

**Nothing writes to disk until the human accepts the diff.**

PatchReview is a Hermes Agent Python plugin that intercepts supported file-writing tools before execution, stores each proposed change in a durable review queue, and exposes tools to inspect, accept, or reject proposals. The original write is blocked while a reviewable proposal is pending. Only patchreview_accept and patchreview_accept_all apply queued content.

## Features

- Intercepts supported write-like tool names in pre_tool_call.
- Persists proposals in pending.json under Hermes plugin data.
- Captures old/new content, SHA-256 hashes, timestamps, and a unified diff.
- Provides list, accept, reject, accept-all, and status tools.
- Includes an offline glass-card UI with sample proposals.
- No network calls, telemetry, API keys, or third-party Python dependencies.

## Install

~~~bash
cp -r patchreview ~/.hermes/plugins/patchreview
hermes plugins doctor ~/.hermes/plugins/patchreview
hermes plugins enable patchreview
hermes plugins validate ./patchreview --install-deps
~~~

Restart Hermes after enabling if the current process has already loaded its plugin registry.

## Tools

| Tool | Purpose |
| --- | --- |
| patchreview_list | List proposals; filter pending, accepted, rejected, or all. |
| patchreview_accept | Apply one pending proposal by id. |
| patchreview_reject | Reject one proposal; disk remains unchanged. |
| patchreview_accept_all | Apply every pending proposal. |
| patchreview_status | Return proposal counts. |

The hook watches tool names containing write_file, patch, apply_patch, create_file, edit_file, str_replace, or search_replace (case-insensitive). It extracts paths and content from common argument keys. Replacement tools read the current UTF-8 file and stage the result of the first exact replacement.

If a supported call cannot be parsed, the hook leaves it alone as specified by the MVP contract. If queue persistence fails after parsing, it blocks the write rather than allowing an unreviewed change.

## Review UI

Open ui/review.html directly in a browser. It runs offline with realistic sample proposals. A live integration can inject window.PATCHREVIEW_DATA before review.js loads. The static UI is a demo surface; its sample accept/reject buttons update browser presentation only. Actual filesystem writes are performed by Hermes tools.

## 90-second demo script

1. 0–10s: Show hermes plugins list with PatchReview enabled.
2. 10–25s: Ask Hermes: “Create file /tmp/patchreview-demo.txt with hello v1”.
3. 25–35s: Show the blocked response and proposal id.
4. 35–48s: Call patchreview_list and show the pending proposal and diff.
5. 48–65s: Call patchreview_accept with that id.
6. 65–78s: Run cat /tmp/patchreview-demo.txt and show hello v1 on disk.
7. 78–90s: Optionally stage another write, reject it, and show that the file remains unchanged. End on the review UI.

Keep the recording under 90 seconds, use a human voice, and show actual plugin behavior rather than a scripted mock.

## Catalog submission

1. Push the finished repository to GitHub.
2. Run Hermes plugin doctor and validator; resolve every error.
3. Copy the exact 40-character commit SHA for the release commit.
4. Open a PR to NousResearch/hermes-agent adding plugin-catalog/patchreview.yaml. Include the public repository URL and pinned commit SHA, following the current catalog schema.
5. Publish the demo video on X, tag @NousResearch, and keep it under 90 seconds.
6. Submit the organizer's form with both the catalog PR URL and X video URL before the stated deadline.

## Why this is more than a skill

A skill can tell an agent to ask before writing, but it cannot reliably intercept a tool call at the execution boundary. PatchReview registers a real pre_tool_call policy hook that vetoes supported writes, persists proposed content outside the conversation, and exposes explicit tools that control when disk writes occur. Enforcement lives in the plugin runtime rather than relying only on model instructions.

## MVP boundaries

- Intercepts named write-like tools, not arbitrary shell commands or writes by unrelated processes.
- Supports common path/content keys and exact string-replacement arguments. Unknown argument shapes are not intercepted.
- The HTML UI is an offline demo surface; it does not directly mutate Hermes' queue or filesystem.
- File contents are treated as UTF-8 text.

## License

MIT. See LICENSE.

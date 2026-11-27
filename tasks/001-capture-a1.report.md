# Report 001 — Capture pipeline and first recording (A1)
Status: done

## Done
- `pyproject.toml` + `uv.lock`: mitmproxy 12.3.1 as a project dependency (Python ≥ 3.12), pytest in the dev group. All tools run as `uv run tools/<name>`.
- `tools/tee_sse.py`: tees `text/event-stream` bodies to `streams/<flow.id>.sse` plus a `<flow.id>.chunks.jsonl` sidecar (start / chunk: t_ns, offset, len / end: total, sha256, reason). Shuts mitmdump down if `tee_dir` is not set.
- `tools/viamitm`: `viamitm [-p PORT] [-c CA] -- cmd…`; sets `HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS` for that command only.
- `tools/run_case`: one prompt per step, `--resume` from step 1's session id, `--model`, `--port`, `--pass-env`; writes `logs/<run-id>/` with manifest, flow dump, streams, mitmdump log, per-step stdout/stderr.
- `tools/inventory`: flows table, totals per host/path/class, header names (+ safelisted values), `/v1/messages` request/response summary, CLI cross-check, notes, problems.
- Two A1 recordings (2 of the 3 allowed runs): `logs/20261127T144857Z-A1` is the valid one; `…144452Z-A1` has the repo `CLAUDE.md` leak (F-012) and is kept locally as its evidence.

## Verified
- Tests: 12 pass offline (`uv run pytest`): tee sha256 = client sha256 = server sha256; first event reaches the client before the server sends the second one; non-SSE body stays in the flow and stream files are named by flow id; inventory classifies a synthetic run, fails on unknown host / unknown SSE event / unknown block type / truncated tee file, prints no header values or body text; `run_case` end to end with a fake `claude` (environment, argv, `--resume`, manifest).
- A1 run: exit code 0, result text 32 characters, stderr empty, no retry event, one inference request answered 200, stream ended cleanly, mitmdump exit 0 with no warnings in its log.
- Inventory of the A1 run: 16 flows, all classified, `UNKNOWN` empty, exit 0. Classes: inference 1, telemetry 3, feature_flags 1, client_config 2, plugin_registry 2, mcp_registry 2, mcp 5. One note: a telemetry flow without response (F-014). CLI message id found in SSE: yes; per-message usage equals final SSE usage: no (equals `message_start` usage); result usage equals final SSE usage: yes.
- `git status` shows nothing from `logs/`; secret check on the staged diff: no match.
- Environment given to `claude`: `HOME`, `PATH` (rebuilt: claude's directory + `/usr/local/bin:/usr/bin:/bin`); `viamitm` adds `HTTPS_PROXY`, `NODE_EXTRA_CA_CERTS`; bash adds `PWD`, `SHLVL`. Nothing else was needed.

## Deviations
- `claude` runs in `<scratch-root>/<run-id>` (default under the system temp dir), not inside the run directory: a directory under `logs/` inherits this repo's `CLAUDE.md` (F-012), which the same task forbids. `run_case` refuses a working directory that has instruction files above it; the path is in the manifest and the empty directory is removed afterwards.
- Inventory has more classes than the task's examples, taken from the observed endpoints (F-001). A response-less flow is a problem only for inference/count_tokens/UNKNOWN, otherwise a note. It also prints message roles, request content-block types and the response content-encoding, and exits non-zero on tee size/sha256 mismatch.
- Hint checked on mitmproxy 12.3.1: `flow.response.stream` as a callable works; the body is not kept in the flow by default, but an option `store_streamed_bodies` (off by default) now exists.

## Findings
F-001 16 requests / 4 hosts, one inference · F-002 single `main` inference request (E-1, E-3) · F-003 `x-claude-code-*` headers (E-2) · F-004 oauth and `anthropic-beta` (E-6) · F-005 body keys, `thinking` · F-006 `cache_control` placement (E-4, E-5) · F-007 role `system` message and `tool_addition` blocks · F-008 gzip SSE · F-009 SSE types · F-010 CLI id/usage vs SSE · F-011 stream-json event types · F-012 ancestor `CLAUDE.md` · F-013 user-level config via `HOME` · F-014 telemetry cut off at exit

## Open questions
1. F-013: the user-level `CLAUDE.md`, plugins and MCP servers are part of the recorded session, and 9 of 16 requests come from them. Keep `HOME` as is, or isolate the configuration (which interacts with the login)? Assumed: keep `HOME`, record what leaks.
2. MCP hosts depend on the user's configuration; `api.githubcopilot.com` is in the class table only because this machine has that plugin. Should P1 treat MCP hosts as a per-machine list, or should recordings exclude MCP?
3. F-007 and the 18 beta values (F-004): the recorded body uses a `system` role message and `tool_addition` blocks. Whether an API key accepts this body unchanged decides D1; not testable here.

## Suggestions
- Turn on `store_streamed_bodies` to get a second, independent copy of each stream for T1.
- `viamitm` sets only `HTTPS_PROXY` as specified; a plain-HTTP request would bypass the proxy unseen. Also set `HTTP_PROXY`, and record TLS handshake failures (clients that reject the CA) in the addon, so P1 can see uncaptured hosts.
- README has no owner in the table and has no usage section yet.

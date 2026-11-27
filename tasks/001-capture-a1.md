# Task 001 — Capture pipeline and first recording (A1)

Read `CLAUDE.md` and `docs/PLAN.md` first.

## Goal

Record one `claude -p "Say hello."` run through mitmproxy without buffering the
stream, keep the raw data, and produce a sanitized inventory of what was
captured. No parsing into chains, no verification, no replay yet — those are
later tasks, and their design depends on what this task finds.

## Deliverables

1. **Project skeleton**: `pyproject.toml` (uv), `tools/`, `tests/`.

2. **`tools/tee_sse.py`** — mitmproxy addon.
   - For responses with `content-type: text/event-stream`: pass the body
     through to the client as it arrives, and write the same bytes to a file.
   - For each chunk also record a monotonic timestamp, byte offset and length
     (sidecar file).
   - Never modify the bytes. Leave non-SSE responses alone.
   - Each stream file must be traceable to its flow in the `-w` dump.
   - Hint, to be checked against the installed mitmproxy version: set
     `flow.response.stream` to a callable in the `responseheaders` hook. With
     streaming on, mitmproxy does not keep the response body in the flow, so
     the tee file is the only copy.

3. **`tools/viamitm`** — runs one command with `HTTPS_PROXY` and
   `NODE_EXTRA_CA_CERTS` set for that command only. Port configurable.

4. **`tools/run_case`** — runs a case and leaves one run directory
   `logs/<run-id>/`.
   - Starts `mitmdump` with the addon and `-w`, waits until it accepts
     connections, stops it cleanly at the end.
   - Runs each step as
     `claude -p "<prompt>" --output-format stream-json --verbose`;
     step 1 fresh, later steps with `--resume <session_id>` taken from step 1.
     Optional `--model`. Only a single-step case has to be exercised in this
     task, but do not design multi-step out.
   - Runs `claude` in an empty scratch directory inside the run directory and
     with a minimal environment (start from `env -i`, add back only what is
     needed), so that neither this repo's `CLAUDE.md` nor your own session's
     environment leaks into the recorded session. List the variables you had
     to keep in the report.
   - Saves the CLI stdout and stderr of each step, unmodified.
   - Writes `manifest.json`: Claude Code version, mitmproxy version, flags,
     prompts, start/end times, exit codes, and the auth kind (`api_key` or
     `oauth`, decided from which auth header name is present — never the value).

5. **`tools/inventory`** — prints a sanitized overview of one run directory.
   - Per flow: method, host, path with query, status, request body size,
     response content type, response size, streamed or not, chunk count,
     duration.
   - Request header **names**; values only for the safelist in `CLAUDE.md`.
   - Totals per host and path. Every flow belongs to a named class
     (`inference`, `count_tokens`, `telemetry`, ...) or to an explicit
     `UNKNOWN` class; exit non-zero if `UNKNOWN` is not empty.
   - For `/v1/messages` requests: model, `stream`, top-level body keys, number
     of `system` blocks, `messages`, `tools`; for their responses: SSE event
     type counts, message id, `stop_reason`, usage numbers.
   - Cross-check against the CLI output of the same run: are the assistant
     message ids from `stream-json` present in the SSE streams, and do the
     usage numbers agree? Print yes/no per message; do not fail on "no".

6. **Tests** (offline, synthetic):
   - bytes written by the tee equal bytes delivered to the client (sha256);
   - the stream is not buffered: with a local test server that emits SSE
     events with pauses, the client receives the first event before the server
     has sent the last one;
   - inventory classifies a synthetic run and fails on an unknown host.

7. **One recording of A1** made with `run_case`, and the inventory output of
   that run, sanitized, summarized in the report.

## Allowed API usage

At most 3 runs of `claude -p "Say hello."`, with whatever login the machine
already has. Nothing else. If running `claude` from inside your own session does
not work, do not work around it: write the exact command for the owner to run
by hand into the report and mark the task `partial`.

## Acceptance criteria

- All tests pass offline.
- The A1 run exits with code 0, the CLI result text is non-empty, and Claude
  Code reports no retries or stream errors.
- The inventory lists every flow of the A1 run with a class; `UNKNOWN` is empty
  or each unknown is named in the report.
- `git status` shows nothing from `logs/`; the secret check from `CLAUDE.md`
  passes on the commit.

## Record in docs/FINDINGS.md

For the A1 run, as `F-NNN` entries, confirming or refuting `E-1 … E-6` where
they apply:

- how many HTTP requests one prompt produces, to which hosts and paths;
- how many of them are `/v1/messages`, with which models and which
  `x-claude-code-request-class` values;
- which `x-claude-code-*` request headers are present (names);
- whether CLI message ids and usage match the SSE streams;
- top-level keys of the inference request body, and whether `cache_control`
  markers and a `thinking` field are present;
- auth kind.

## Out of scope

Chain extraction, T2 consistency check, replay, multi-step recordings, any
group other than A, viewers or UIs.

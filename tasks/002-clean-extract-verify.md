# Task 002 — Clean profile, extract, verify (A1)

Read `docs/DECISIONS.md` (top section) and the changed rows of `docs/PLAN.md`
first. Report 001 is accepted; its three suggestions about capture are adopted
below.

## Goal

Finish stage 1 of the plan: a clean A1 recording that passes P1, P2, T1 and T3.

## Part A — capture changes and the `clean` profile

1. `viamitm` also sets `HTTP_PROXY`.
2. The addon records TLS handshake failures (host, time) into the run
   directory. Inventory lists them.
3. Turn on mitmproxy's `store_streamed_bodies`, so each stream exists twice:
   our tee file and mitmproxy's own copy in the flow.
4. `run_case --profile clean|as-is`, default `clean`. The manifest records the
   profile and the exact flags and environment variables that implement it.

`clean` means: no user-level `CLAUDE.md`, plugins, MCP servers, hooks, skills
or auto memory reach the session, while Claude Code's default system prompt and
built-in tools stay as they are, and the machine's existing login still works.

How to get there is yours to find out from `claude --help` and the official
docs at code.claude.com/docs. Candidates: `--setting-sources`,
`--strict-mcp-config`, plugin-related flags or settings, environment variables.
Rules:

- Prefer the least invasive combination. `--bare` only as a fallback, and then
  say so under "Open questions", because it changes the built-in tools.
- Do not copy, move, edit or delete anything under the user's real config,
  and never copy credential files anywhere. If `clean` cannot be reached under
  the current login without that, stop Part A, report what is missing, and
  continue with Parts B and C on the existing `as-is` recording.
- Do not switch off telemetry or other default traffic for the sake of a
  shorter log; `clean` removes the user's configuration, nothing else.

## Part B — `tools/extract <run-dir>`

Derived, deterministic, safe to re-run. Output goes under the run directory.

For every inference flow, in order:

- raw request body, byte-for-byte, with sha256;
- request metadata: method, path with query, header names, values of
  safelisted and `x-claude-code-*` headers; credential values redacted;
- the response stream decompressed (derived copy), the parsed events in order,
  and the assistant message assembled from them: id, model, content blocks,
  `stop_reason`, final usage, and separately the `message_start` usage;
- a flag for an incomplete stream (no `message_stop`).

Plus an index of all inference records with their chain key (session id, agent
id if any, request class) and hashes.

The assembler knows an explicit list of event, block and delta types; anything
else is an error with the type name. Request-side roles and block types are
listed the same way (F-007).

## Part C — `tools/verify <run-dir>`

Prints one row per check — PASS, FAIL or SKIP with a one-line reason — writes
the same as JSON into the run directory, exits non-zero on any FAIL.

- **P1** — every flow classified, `UNKNOWN` empty; no TLS handshake failures;
  response-less flows only in `telemetry`; under `clean`, no flows of the
  classes that `clean` is supposed to remove.
- **P2** — CLI assistant message ids = logged inference message ids, both
  directions; CLI `result` usage = final usage summed over those responses,
  field by field. Per-message CLI usage vs `message_start` usage: report, do
  not fail.
- **T1** — tee sha256 = sidecar sha256 = sha256 of mitmproxy's stored copy;
  stream decompresses and parses to the end; request body is valid JSON; only
  known types.
- **T3** — text assembled from the last `main` inference response equals the
  CLI `result` string exactly. On mismatch print lengths and the first
  differing offset, never the text.

Checks that need several steps or several requests (T2) are out of scope; do
not stub them.

## Tests (offline, synthetic)

- Assembler: text; `tool_use` with `input_json_delta` split over several
  deltas and with empty input; thinking with `thinking_delta` and
  `signature_delta`; several blocks; `ping`; an `error` event mid-stream; a
  truncated stream; an unknown event, block and delta type.
- Verify must FAIL on a synthetic run after each of these mutations: an
  inference stream file removed; one byte flipped in a tee file; one SSE event
  dropped; the CLI result text edited; a CLI assistant event removed; an
  unknown host added. This is the offline part of check K.

## Allowed API usage

At most 4 runs of `claude -p "Say hello."`. Nothing else.

## Acceptance criteria

- All tests pass offline.
- A `clean` A1 recording exists where: `system/init` lists no MCP servers and
  no plugins; the user-level `CLAUDE.md` text is absent from the inference
  request body (check locally with a marker string; never write the string
  anywhere); inventory shows no `mcp` flows.
- `verify` on the `clean` A1 recording: P1, P2, T1, T3 all PASS.
- `verify` also runs on the existing `as-is` recording from task 001; report
  its table too (FAILs there are acceptable if explained).
- Secret check passes; nothing from `logs/` is committed.

## Record in docs/FINDINGS.md

- What implements `clean` (flags, variables) and what each one removes.
- `clean` vs `as-is` for A1: request count per class, request body size,
  number of `system` blocks, `messages` entries and `tools`, input-side usage.
- Which non-inference classes remain under `clean`.
- Anything in the stream or the CLI output that the assembler or verify had to
  treat specially.

## Out of scope

T2, multi-step recordings, replay, groups other than A.

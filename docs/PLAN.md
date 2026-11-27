# Plan

Owner of this file: planning chat. Last updated: 2026-11-27.

## Goal

Show that our recording of `claude -p` traffic is correct, by three separate claims:

- **Complete** — no request that Claude Code sent is missing from the log.
- **Exact** — what we stored is byte-for-byte what was sent and received.
- **Sufficient** — replaying a logged request, using nothing but the log,
  makes the model behave the way it did in the original run.

"The final answer looks similar" alone is weak evidence (model output varies
from run to run), so most checks below are deterministic.

## Checks

| Id | Claim | Check | Needs API key |
|---|---|---|---|
| P1 | Complete | Every host and path in the recording is classified; no unknowns | no |
| P2 | Complete | Every assistant `message.id` in the CLI `stream-json` output is found in the log (SSE `message_start`), and the usage summed over the log equals the usage reported by the CLI result | no |
| T1 | Exact | Request bodies and SSE streams are stored as raw bytes with sha256; unknown event/block types are errors | no |
| T2 | Exact | Chain consistency: request N+1 = messages of request N + assistant message assembled from response N + new user/tool_result content, after normalization. Every other difference is printed as a diff | no |
| T3 | Exact | Final text assembled from the last SSE response equals `result` in the CLI output | no |
| D1 | Sufficient | The API accepts the replayed request (HTTP 200, no validation error, thinking signatures accepted) | yes |
| D2 | Sufficient | Total input tokens (`input_tokens + cache_creation_input_tokens + cache_read_input_tokens`) of the replay equal the original | yes |
| D3 | Sufficient | Replaying every request of the main chain yields the same decision as recorded (same tool, same arguments, or text) | yes |
| D4 | Sufficient | 3–5 replays of the final request: the original answer lies within the spread of the replays | yes |
| K  | Control | Deliberately damaged logs (drop a message, truncate a tool_result, drop a system block) make T2 fail and D2 change | partly |

T2 normalization starts with an empty allow-list. Each allowed difference
(for example moving `cache_control` markers, history rebuilt on `--resume`,
compaction) is added only after it has been observed and written to
`docs/FINDINGS.md`.

## Scope now: group A only (plain dialogue, no tools)

| Id | Prompt | Looks at |
|---|---|---|
| A1 | Say hello. | shortest possible exchange |
| A2 | Explain the Sieve of Eratosthenes. | long answer |
| A3 | Explain the Sieve of Eratosthenes in three sentences. | format constraint |
| A4 | Translate the previous answer into Russian. | uses previous turn |
| A5 | Now explain it in more detail. | continues the dialogue |

A multi-step case is one session: step 1 is a fresh `claude -p`, later steps use
`--resume <session_id>`.

Stages:

1. **A1 alone** — debug capture, parsing, P1, P2, T1, T3.
2. **A1 → A2** — first `--resume` boundary; build the T2 allow-list.
3. **A1 → A5** — whole chain, token growth, cache behaviour.
4. **With API key** — re-record group A with the key, replay within minutes: D1–D4, K.

Groups B–I (search, OS tools, project work, agents, errors, permissions, MCP,
subagents) come later and are out of scope until this file says otherwise.

## Components

| Tool | Purpose |
|---|---|
| `tools/tee_sse.py` | mitmproxy addon: pass SSE through as a stream and tee the raw bytes to disk |
| `tools/viamitm` | run one command with proxy env vars set, without touching the shell env |
| `tools/run_case` | start capture, run the steps of a case, save CLI output and a manifest |
| `tools/inventory` | sanitized overview of a recorded run (P1) |
| `tools/extract` | recording → one record per `/v1/messages` call, grouped into chains |
| `tools/verify` | P1, P2, T1, T2, T3 and the K mutations |
| `tools/replay` | D1–D4 |

## Recording rules

- Proxy must not buffer streaming responses: Claude Code reads SSE event by
  event and aborts a stream that stays silent too long.
- Each recorded session runs in an empty scratch directory with a minimal
  environment, so that this repository's own `CLAUDE.md` and the parent
  session's environment do not leak into the recorded context.
- Each run has a manifest: tool versions, flags, timestamps, exit codes, and the
  kind of authentication used (`api_key` or `oauth` — the kind only).
- Recordings made under a subscription login are for tool debugging only.
  Evidence for D1–D4 uses recordings made with an API key, replayed with the
  same key.

## Replay rules

- Send the raw recorded body to the same path and query string.
- Send only these recorded headers: `anthropic-version`, `anthropic-beta`
  (minus any OAuth-only value), `content-type`. Use our own `user-agent`.
- Authenticate only with `ANTHROPIC_API_KEY` from the environment.
- Replay never executes tools; it only compares what the model asks for.

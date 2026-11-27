# Findings

Owner of this file: implementing agent.

Observed facts about how Claude Code talks to the API. Facts only — no guesses.
Structure and counts only — no captured content, no identifiers, no credentials
(see `CLAUDE.md`).

Entry format:

```
## F-NNN — <one-line statement of the fact>
- Observed: <date>, Claude Code <version>, auth kind <api_key|oauth>
- Evidence: logs/<run-id>/<file>  (local path; logs are not in git)
- Detail: <2–5 lines>
- Affects: <which check in docs/PLAN.md, if any>
```

## Expected from documentation — to be confirmed or refuted by observation

Source: https://code.claude.com/docs/en/llm-gateway-protocol

- E-1. Inference requests go to `POST /v1/messages?beta=true`; token counting
  may use `/v1/messages/count_tokens`.
- E-2. Requests carry `x-claude-code-session-id`; subagent requests also carry
  `x-claude-code-agent-id`.
- E-3. On a direct connection to the Anthropic API, requests carry
  `x-claude-code-request-class` (`main`, `subagent`, `workflow`, `compaction`,
  `auxiliary`).
- E-4. Claude Code puts `cache_control` markers on `system` blocks and on
  `messages` entries.
- E-5. The first `system` block is a short attribution block (client version
  plus a fingerprint).
- E-6. With a subscription login, `anthropic-beta` carries an extra OAuth value.

When an expectation is confirmed or refuted, add a normal `F-NNN` entry that
refers to it (for example "confirms E-3").

## Observed

All entries below come from case A1 (`claude -p "Say hello."`, one step).
Class names in backticks are the labels used by `tools/inventory`.

## F-001 — One A1 run produces 16 HTTP requests to 4 hosts; exactly one is inference
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm (same counts in logs/20261127T144452Z-A1)
- Detail: `api.anthropic.com` 10: `inference` 1 (`POST /v1/messages`), `telemetry` 2
  (`POST /api/event_logging/v2/batch`), `feature_flags` 1 (`POST /api/eval/sdk-<key>`),
  `client_config` 2 (`GET /api/claude_cli/bootstrap`, `GET /api/claude_code_penguin_mode`),
  `plugin_registry` 2 (`GET /api/oauth/organizations/<uuid>/plugins/list-plugins`, `.../marketplaces`),
  `mcp_registry` 2 (`GET /v1/mcp_servers`, `GET /api/directory/server-urls`).
  `mcp-proxy.anthropic.com` 2 (`POST /v1/mcp/<id>`, SSE responses). `api.githubcopilot.com` 3
  (`/mcp/`, all answered 400). `http-intake.logs.us5.datadoghq.com` 1 (`POST /api/v2/logs`).
  No `count_tokens` request. All requests are HTTP/1.1.
- Affects: P1

## F-002 — The single inference request is `POST /v1/messages?beta=true` with request class `main` (confirms E-1, E-3)
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm
- Detail: model `claude-fable-5-2`, `stream: true`, `x-claude-code-request-class: main`,
  `anthropic-version: 2023-06-01`. No auxiliary or second inference request in a
  one-prompt `-p` run. Request body about 70 kB.
- Affects: P1, P2, D1

## F-003 — `x-claude-code-*` request headers on the inference request (confirms E-2 for the session id)
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm
- Detail: `x-claude-code-prompt-id`, `x-claude-code-request-class`,
  `x-claude-code-sandy-plover`, `x-claude-code-session-id`. No `x-claude-code-agent-id`
  (no subagents in A1). Other request-scoped headers on the same request:
  `x-claude-1p-request-class`, `anthropic-dispatch-id`, `x-client-request-id`, `x-app`,
  `x-stainless-*`. `x-claude-code-session-id` is also sent to `mcp-proxy.anthropic.com`;
  no other non-inference request carries an `x-claude-code-*` header.
- Affects: chain grouping (DECISIONS), T2

## F-004 — Auth kind is oauth; `anthropic-beta` carries `oauth-2025-04-20` (consistent with E-6)
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm, manifest.json
- Detail: inference `anthropic-beta` has 18 values:
  `claude-code-20250219,oauth-2025-04-20,interleaved-thinking-2025-05-14,context-management-2025-06-27,prompt-caching-scope-2026-01-05,per-turn-control-2026-07-01,mid-conversation-tool-changes-2026-07-01,inline-tools-2026-09-15,advisor-tool-2026-03-01,thinking-token-count-2026-05-13,advanced-tool-use-2025-11-20,mid-conversation-system-clear-at-2026-08-21,effort-2025-11-24,thinking-binding-controls-2026-08-01,thinking-display-updates-2026-08-18,extended-cache-ttl-2025-04-11,cache-diagnosis-2026-04-07,message-threads-2026-08-12`.
  `feature_flags`, `client_config` and `telemetry` requests to `api.anthropic.com` send
  `anthropic-beta: oauth-2025-04-20` alone. Whether the value is absent with an API
  key is not observed yet.
- Affects: D1 (replay header filter)

## F-005 — Top-level keys of the inference request body; `thinking` is present
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm
- Detail: keys in order: `model messages system tools metadata max_tokens thinking
  context_management data_flow output_config thread diagnostics stream`.
  `thinking` is `{"type": "adaptive", "display": "updates"}`. `system` has 4 blocks,
  `messages` 2 entries, `tools` 12 entries (2 with `defer_loading`, one of type
  `advisor_20260301`). `metadata` has the single key `user_id`.
- Affects: T2, D1, D2

## F-006 — `cache_control` markers are on system blocks 3 and 4 and on the last block of the last message (confirms E-4; consistent with E-5)
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm
- Detail: system block 3: `{"type": "ephemeral", "ttl": "1h", "scope": "global"}`; system
  block 4 and the last content block of the last message: `{"type": "ephemeral", "ttl": "1h"}`.
  No marker on `tools` entries. System block 1 is short (under 200 characters), has no
  marker and contains the client version string; a fingerprint was not verified.
- Affects: T2 normalization, D2

## F-007 — `messages` contains a message with role `system` and content blocks of type `tool_addition`
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm
- Detail: `messages` is [`user`: 4 `text` blocks; `system`: 1 `text` block and 3
  `tool_addition` blocks]. A `tool_addition` block has the keys `type`, `tool` and
  optionally `cache_control`. So the role set is not just user/assistant and the
  request-side block types are not just text/tool_use/tool_result.
- Affects: T2, D1, known-type lists of `tools/extract`

## F-008 — The inference response is a gzip-encoded SSE stream; other responses are br-encoded or plain
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/streams/*.chunks.jsonl, flows.mitm
- Detail: inference response: `content-type: text/event-stream; charset=utf-8`,
  `content-encoding: gzip`, 763 body bytes delivered in 3 chunks (823 bytes / 4 chunks
  in the other run). The tee file therefore holds compressed bytes and must be
  decompressed before parsing. JSON responses of `api.anthropic.com` are `br`-encoded;
  the MCP SSE responses are not encoded.
- Affects: T1, T3

## F-009 — SSE event, block and delta types seen in A1
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/streams/
- Detail: events `message_start` 1, `content_block_start` 1, `content_block_delta` 2–5,
  `content_block_stop` 1, `message_delta` 1, `message_stop` 1, `ping` 1. One content
  block of type `text`, deltas of type `text_delta` only; no thinking block although
  `thinking` is adaptive. `stop_reason` is `end_turn`.
- Affects: T1, T3

## F-010 — CLI message id is in the SSE stream; CLI per-message usage equals `message_start` usage, CLI result usage equals final SSE usage
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/steps/01/stdout.jsonl, streams/ (same result in logs/20261127T144452Z-A1)
- Detail: the one `assistant` event's `message.id` equals the id in SSE `message_start`.
  Its `usage` equals the usage in `message_start` (`output_tokens` 4), not the final
  one (`output_tokens` 13 from `message_delta`). The `result` event's usage equals the
  final SSE usage in all four fields (input 2, cache creation 14243, cache read 9444,
  output 13).
- Affects: P2 (compare per-message usage on input-side fields or against `message_start`)

## F-011 — `stream-json` event types in A1: `system/init`, `assistant`, `rate_limit_event`, `result/success`
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/steps/01/stdout.jsonl
- Detail: one of each. No retry event, `is_error` false, `num_turns` 1, stderr empty;
  on the wire a single inference request, answered 200, stream ended cleanly.
- Affects: P2

## F-012 — Claude Code loads `CLAUDE.md` from the ancestors of its working directory
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144452Z-A1 (working directory inside this repo) vs logs/20261127T144857Z-A1 (outside)
- Detail: with the working directory at `logs/<run-id>/scratch`, text of this repo's
  `CLAUDE.md` is in the inference request body; with a directory outside the repo it
  is not. Request body 75,505 vs 70,444 bytes, `cache_creation_input_tokens` 16,117 vs
  14,243. An empty directory inside the repo does not isolate the session.
- Affects: recording rules in PLAN, D2

## F-013 — User-level configuration reaches the recorded session through `HOME`
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm, steps/01/stdout.jsonl
- Detail: with only `HOME` and `PATH` kept, text of the user-level `CLAUDE.md` is in the
  inference request body; `system/init` lists 3 MCP servers and 5 plugins; 9 of the 16
  requests are `plugin_registry`, `mcp_registry` or `mcp` traffic. The `mcp` hosts
  depend on the user's configuration, not on Claude Code itself.
- Affects: recording rules in PLAN, P1

## F-014 — A telemetry request is cut off when the CLI exits
- Observed: 2026-11-27, Claude Code 2.1.332, auth kind oauth
- Evidence: logs/20261127T144857Z-A1/flows.mitm (same in logs/20261127T144452Z-A1)
- Detail: the `POST /api/v2/logs` request to the Datadog intake is fully sent (about
  72 kB) but the flow ends with "Client disconnected" and has no response. A complete
  log can therefore contain response-less flows of class `telemetry`.
- Affects: P1

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

(none yet)

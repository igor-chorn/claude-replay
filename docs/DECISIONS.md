# Decisions

Owner of this file: planning chat. Newest first. One entry = date, decision, reason.

## 2026-11-27

- **Work split.** Planning in a separate chat; implementation by Claude Code on
  the owner's Ubuntu VM; hand-off through `tasks/` and reports in this repo.
  Reason: keep planning free of implementation detail.
- **Start with group A only**, in three stages (A1; A1→A2; A1→A5).
  Reason: each stage adds exactly one new thing, so a failure is easy to locate.
- **Correctness = complete + exact + sufficient**, checked by P/T/D/K checks in
  `docs/PLAN.md`. Reason: similarity of the final answer alone cannot
  distinguish a correct log from an incomplete one.
- **Capture with mitmproxy as a forward proxy plus a streaming tee addon**, not
  `-w` alone. Reason: a buffering proxy stalls Claude Code on long responses;
  with pass-through streaming mitmproxy does not keep the body, so we must tee it.
- **Group requests into chains by `x-claude-code-*` request headers** where
  present, not by guessing from the system prompt. Reason: documented and exact.
- **Independent reference for completeness is the CLI's own `stream-json`
  output** (per-message ids and usage). Reason: documented, and produced by a
  different code path than the proxy.
- **Replay only with an API key; never with a subscription token.**
  Reason: subscription OAuth is permitted only inside Anthropic's own apps.
- **Subscription recordings are for debugging; evidence uses API-key recordings.**
  Reason: the two kinds of traffic differ (beta header values, model used for
  auxiliary requests).
- **Public repository, so no recorded content in git.** Reason: logs contain
  credentials, account identifiers and full prompts.

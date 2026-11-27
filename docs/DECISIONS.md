# Decisions

Owner of this file: planning chat. Newest first. One entry = date, decision, reason.

## 2026-11-27 (after report 001)

- **Recordings use a `clean` profile by default** (answers report 001, open
  questions 1 and 2). No user-level `CLAUDE.md`, plugins or MCP servers in the
  recorded session; the default system prompt and built-in tools stay.
  Reason: 9 of 16 requests and part of the prompt came from this machine's
  personal configuration (F-013); evidence must not depend on it, and P1 needs
  a host list that is the same on any machine. MCP comes back later (group H)
  through an explicit, controlled MCP config, not through the user's setup.
- **Isolation must not touch credential files.** Reason: copying an OAuth
  credential into a second config directory risks token-refresh rotation
  logging the owner out. If `clean` is impossible under the subscription login,
  it waits for the API key.
- **`--bare` is a fallback only.** Reason: it changes the built-in tool set, so
  the session would no longer be ordinary Claude Code.
- **P2 compares ids both ways and result usage against summed final usage**
  (F-010). Reason: the CLI's per-message usage is the `message_start` snapshot.
- **T1 keeps the stream as received (gzip) and gets a second copy** via
  mitmproxy's `store_streamed_bodies`. Reason: two independent copies make the
  byte-exactness claim checkable.
- **Proxy env also sets `HTTP_PROXY`; TLS handshake failures are recorded.**
  Reason: both are ways traffic could escape the log unnoticed.
- **Report 001, open question 3** (role `system` message, `tool_addition`
  blocks, 18 beta values): no action now. Decided by D1 on the first
  recording made with an API key.

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

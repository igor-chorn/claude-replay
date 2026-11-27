# claude-replay

Record the API traffic of `claude -p` through mitmproxy, verify that the
recording is complete and exact, and replay recorded requests with an API key to
check that the log alone reproduces the model's behaviour.

- `docs/PLAN.md` — what is being proven and how
- `docs/DECISIONS.md` — decision log
- `docs/FINDINGS.md` — observed protocol facts
- `tasks/` — task briefs and reports
- `CLAUDE.md` — rules for the implementing agent

Recorded traffic lives in `logs/` and is never committed.

# claude-replay — rules for the implementing agent

You are the implementer. Planning happens elsewhere (a separate planning chat with
the project owner). You receive work as task files in `tasks/` and answer with a
report file. Read `docs/PLAN.md` before your first task in a session.

## What this project is

We record the HTTP traffic of `claude -p` through mitmproxy, verify that the
recording is complete and exact, and then replay recorded requests against the
Claude API to show that the log alone is sufficient to reproduce the model's
behaviour. See `docs/PLAN.md` for what "complete / exact / sufficient" means.

## THIS REPOSITORY IS PUBLIC

- Never commit anything from `logs/`. It holds credentials, account identifiers
  and full request/response bodies.
- Never put into code, commits, reports or `docs/FINDINGS.md`:
  - values of `authorization`, `x-api-key`, `cookie`, `set-cookie` or any token;
  - `metadata.user_id`, e-mail addresses, account or organization ids;
  - captured request or response bodies, including system-prompt text.
- Reports and findings contain structure only: counts, sizes, names of headers
  and fields, event types, and values of the safelisted headers
  (`anthropic-version`, `anthropic-beta`, `content-type`, `x-claude-code-request-class`).
- Before every commit run a secret check over the staged diff (at least:
  `sk-ant-`, `Bearer `, `authorization:`), and stop if anything matches.

## Hard rules

1. **Stay inside the task.** Do what the task file says. Ideas, extras and
   refactors go into the report under "Suggestions", not into the code.
2. **Plan-level questions are not yours to decide.** Technical details are yours.
   Anything that changes what we prove or how (see `docs/PLAN.md`) goes into the
   report under "Open questions". Make the smallest reasonable assumption, say so,
   and continue.
3. **No API spend without permission.** Do not run `claude -p`, call the Claude
   API, or run replay unless the task explicitly allows it, and never more runs
   than it allows.
4. **Replay credentials.** Replay may only ever authenticate with
   `ANTHROPIC_API_KEY` from the environment. Never reuse a credential found in
   recorded traffic. Never send a subscription/OAuth token from our own code.
5. **Raw bytes are the source of truth.** Captured request bodies and response
   streams are stored byte-for-byte. Parsed forms are derived and can be
   regenerated. Never "fix up" raw data.
6. **Unknown means error.** An SSE event type, content-block type, delta type,
   host or endpoint the code does not know must be reported loudly (non-zero
   exit or an explicit "unknown" bucket in the output). Never skip silently.
7. **Do not edit** `docs/PLAN.md`, `docs/DECISIONS.md`, or `tasks/*.md` (except
   your own `*.report.md`). If they are wrong, say so in the report.

## Who writes what

| Path | Owner |
|---|---|
| `CLAUDE.md`, `docs/PLAN.md`, `docs/DECISIONS.md`, `tasks/NNN-*.md` | planning chat |
| `tools/`, `tests/`, `pyproject.toml`, `docs/FINDINGS.md`, `tasks/NNN-*.report.md` | you |

Both sides commit to `main`. Run `git pull --rebase` before you start and before
you push.

## Workflow for one task

1. `git pull --rebase`, read `tasks/NNN-name.md`.
2. Implement. Add tests. Run them.
3. Record observed protocol facts in `docs/FINDINGS.md` (format is in that file).
4. Write `tasks/NNN-name.report.md` (format below).
5. One commit per task: `NNN: short summary`. Push.

## Report format (max ~40 lines)

```
# Report NNN — <title>
Status: done | partial | blocked
## Done            — what exists now, one line per deliverable
## Verified        — how each acceptance criterion was checked, with the result
## Deviations      — where you departed from the task and why
## Findings        — new entries added to docs/FINDINGS.md (titles only)
## Open questions  — plan-level questions for the planning chat
## Suggestions     — optional, short
```

No code in reports. No log excerpts beyond sanitized counts and names.

## Tooling

- Python via `uv`; mitmproxy via `uv tool run --from mitmproxy ...` or as a
  project dependency, your choice (state it in the report).
- Tests with `pytest`. Tests must run offline, on synthetic data.
- Code, comments, docs and reports are in English.

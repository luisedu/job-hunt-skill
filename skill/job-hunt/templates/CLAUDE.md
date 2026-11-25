# Job hunt workspace: {{name}}

Created {{today}} with the `job-hunt` skill. Claude finds jobs, tailors CVs and cover letters, preps interviews and tracks applications.
**{{name}} submits every application. Claude never applies, emails or messages anyone on their behalf.**

## Read first, every session
1. `memory.md`: hard rules. Change only when {{name}} asks.
2. `applications.md`: the tracker. See "Response follow-up".
3. `curriculum/profile.md`: the only facts allowed in documents and answers, plus "Do NOT claim".
4. `search/filters.md`: tunable filters (its JSON block is read by the skill scripts).

## File map
| Path | What |
|---|---|
| `memory.md` | Hard rules: location, pay floor, role type, document rules, excluded companies |
| `applications.md` | Every application and lead, with status and next step |
| `curriculum/` | Master CV PDF(s) + `profile.md` (extracted facts) |
| `search/filters.md` | Thresholds, keywords, sources (JSON) + tuning log |
| `search/sources.md` | Which job boards work, quirks, manual-only boards |
| `search/scan-log.md` | One entry per scan |
| `search/scans/` | Raw/filtered JSON per scan (machine data) |
| `interview/` | Reusable stories + numbers bank, AI-interview rules, salary notes, per-company prep |
| `outcomes/` | Append-only event log (`outcomes.jsonl`, schema in `outcomes/README.md`) + saved postings |
| `<company>/` | Final tailored PDFs only |

## Workflow
Follow the `job-hunt` skill (SKILL.md): scan → filter → vet by hand → tailor → track → follow up.

## Response follow-up
At the start of a session, check `applications.md`. For active rows whose "Last update" is ≥ 5 days old, ask once, briefly, whether there's any news. Record answers. Move finished ones to "Closed".

## Outcome log (always, alongside `applications.md`)
Every tracker change also gets an event: `python3 SKILL_DIR/scripts/outcomes.py --workspace . event --company … --title … --event … --value … [--reason codes] [--data JSON]`.
- Applied → `decision applied` + `stage submitted`. Skipped a kept job → `decision skipped` with a reason. **Always ask why if it's unclear: it's the most useful label.**
- A correction that sounds general → `rule proposed`. Only after {{name}} confirms it and it's in `filters.md` or `memory.md` → `rule approved` with `--reply` (their words, verbatim). **A single skip is not a rule:** don't generalize one case without asking.
- After a hire: ask for check-ins at 30/90/180/365 days (`checkin`: satisfaction, whether the job matched the posting, would stay).

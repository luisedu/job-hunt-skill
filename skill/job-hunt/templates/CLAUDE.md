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
| `interview/` | Reusable stories, salary notes, per-company prep |
| `<company>/` | Final tailored PDFs only |

## Workflow
Follow the `job-hunt` skill (SKILL.md): scan → filter → vet by hand → tailor → track → follow up.

## Response follow-up
At the start of a session, check `applications.md`. For active rows whose "Last update" is ≥ 5 days old, ask once, briefly, whether there's any news. Record answers. Move finished ones to "Closed".

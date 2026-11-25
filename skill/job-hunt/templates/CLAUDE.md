# Job hunt workspace: {{name}}

**{{name}} submits every application. Claude never applies, emails or messages anyone on their behalf.**

Follow the `job-hunt` skill: `{{skillDir}}/SKILL.md` (scripts in `{{skillDir}}/scripts/`, always with `--workspace {{workspace}}`).

- Every session: read `memory.md` (hard rules) and `applications.md` (tracker), then skill §2.
- `curriculum/profile.md` holds the only facts allowed in documents and answers ("Do NOT claim" included).
- `search/filters.md` is the config the scripts read: open it when scanning or tuning.
- `<company>/` folders hold final PDFs only. `outcomes/outcomes.jsonl` is append-only: every tracker change gets an event (skill `reference/outcomes.md`).

---
name: job-hunt
description: Run a personal job search from a local workspace. Scan 10+ public job boards and companies' own job boards, filter out ghost jobs, reposts, location-restricted remote roles, below-floor pay and scams, rank by fit against the user's CV, tailor CV and cover-letter PDFs, prep interviews (including AI-scored ones), and track applications and outcomes (funnel, calibration, retention check-ins) with periodic follow-up questions. Use when the user wants to set up a job hunt, find jobs, check for new jobs, tailor a CV or cover letter, prep an interview, or update application status.
---

# Job hunt

A workspace-based job search. Everything personal lives in the user's **workspace** folder (markdown + PDFs). This skill holds the method, scripts and templates.

`SKILL_DIR` = the directory containing this file. Scripts: `SKILL_DIR/scripts/`. Templates: `SKILL_DIR/templates/` (workspace files) and `SKILL_DIR/assets/` (CV and letter HTML).

## Ground rules (always)
- **The user applies.** Never submit applications, send emails or messages, or fill forms on the user's behalf. Draft text for them to send.
- **Honesty:** CVs, letters and answers use only facts in `curriculum/profile.md`. Never invent metrics, tools or experience. Respect its "Do NOT claim" list.
- **Privacy:** the workspace holds personal data. Never publish or commit it, and never send the CV, salary or contact details to third-party services unless the user asks.
- **Scams:** never advise sharing ID documents or bank details, or paying fees, before a signed contract with a named legal entity.
- Don't scrape login-walled sites (LinkedIn, Indeed, Glassdoor, Wellfound). Suggest the user search those manually.

## 1. First run: create the workspace
Trigger: no `CLAUDE.md` + `search/filters.md` in the chosen folder.
1. Ask where the workspace should live (default: `~/JobHunt`). Ask for the CV PDF path.
2. Read the CV (`pdftotext -layout <cv.pdf> -`). Then ask only what the CV can't answer, one short round:
   - target roles and seniority
   - home country/city, and whether remote only (hybrid OK in which cities?)
   - which regions may hire them (citizenships/work permits matter)
   - pay floor (monthly, in their currency) and target rate
   - companies to exclude, and the document language(s)
3. Build `answers.json` (schema in `scripts/init_workspace.py` docstring). Derive `queries` (3–8 broad terms), `titleKeywords`, `textKeywords` and `fit` weights from the CV and target role. Enable region-specific sources (e.g. `gupy` for Brazil, `getonbrd` for LATAM, `arbeitnow` for EU).
4. Run `python3 SKILL_DIR/scripts/init_workspace.py --workspace <ws> --answers answers.json`.
5. Copy the CV into `<ws>/curriculum/` and fill `curriculum/profile.md` from it (all roles, dates, skills, publications, references). Leave "Confirmed in conversation" and "Do NOT claim" for later.
6. Show the user the created files and the filter config, and offer a first scan.

## 2. Every session
1. Read `<ws>/CLAUDE.md`, `memory.md`, `applications.md`.
2. **Follow-up:** for active rows in `applications.md` whose "Last update" is ≥ 5 days old, ask once, briefly, whether there's news. Example: "Any reply from Acme or Globex?". Update rows with the answer and today's date. Move closed ones to "Closed". Don't ask again in the same session.
3. **Curriculum check:** if a PDF in `curriculum/` is newer than the date on `profile.md`'s "Source" line, re-extract it, update `profile.md` (keep the confirmed and do-not-claim sections), and tell the user what changed.

## 3. Finding jobs
- **Full scan:**
  ```bash
  python3 SKILL_DIR/scripts/scan.py --workspace <ws>      # writes search/scans/raw-DATE.json
  python3 SKILL_DIR/scripts/filter.py --workspace <ws>    # writes results-DATE.json, prints ranked list
  ```
  `--only remotive,himalayas` limits sources.
- **Vet every kept job by hand before showing it:** read the description. Is it really the target role? Can they hire in the user's country? Mixed or adjacent roles → "borderline". Unknown company → check website, domain age (RDAP), MX and recruiter email domain.
- **Report:** counts (raw → relevant → kept → vetted), exclusions grouped by reason, then the jobs best fit first. For each: title, company, location rule, pay or "not listed", age, why it fits, flags, apply link. Mention notable jobs dropped only for repost/age, so the user can override.
- Append a dated entry to `search/scan-log.md`. Add good unapplied jobs to "Candidates found" in `applications.md`.
- Quick checks may use the Remote Rocketship API if the user has a key (`sources.remoterocketship`).
- **Company job boards** (`ats` source): suggest 10–30 companies that do the user's kind of work, find their slugs with `scan.py --workspace <ws> --probe-ats a,b,c`, and add the ones found to `filters.md` → `atsBoards`. This catches openings the day they're posted, before the aggregators pick them up.

## 4. Tailoring documents
1. Read the posting and map each requirement to evidence in `profile.md`. Note gaps and ask before claiming anything new. Record confirmed facts in `profile.md` → "Confirmed in conversation".
2. Copy `SKILL_DIR/assets/cv.html` / `letter.html` into the session scratchpad (never into the workspace). Fill them in the posting's language and order skills by the posting's keywords. **Never drop sections such as References without asking.**
3. Convert: `soffice --headless --convert-to pdf:writer_web_pdf_Export --outdir <ws>/<company> file.html`. Check `pdfinfo` pages (CV ≤ 2, letter 1) and a preview (`pdftoppm -r 50 -png`).
4. **Only PDFs go in `<ws>/<company>/`.** Put paste-ready letter text in chat, and check ATS character limits if given.
5. Add or update the row in `applications.md` (`prepared`). Set it to `submitted` when the user confirms.

## 5. Interviews and offers
- **AI-scored or async interviews** (audio bots, one-way video): follow `interview/ai-interviews.md`. Offer a mock first: ask the likely questions one at a time and score each answer against its rules.
- Keep a **numbers bank** in `interview/stories.md`: confirmed baseline → result figures. Interviewers, and especially bots, ask for comparisons. Never invent a number: ask the user, and record what they confirm in `profile.md`.
- Create `interview/<company>.md` from `templates/interview/_company-template.md`: company facts with sources, role → evidence map, gaps and honest answers, questions to ask, pay plan.
- Build reusable stories in `interview/stories.md` from what the user tells you (confirmed facts only).
- Pay: convert everything to the user's monthly currency. Compare to the floor and target in `memory.md`. Suggest letting the employer name the number first, and quoting a stated hours basis for contractor rates.

## 6. Outcome log and learning
Every change to `applications.md` also gets an event in `outcomes/outcomes.jsonl` (`scripts/outcomes.py`; schema in the workspace's `outcomes/README.md`). `filter.py` logs scan decisions automatically.
```bash
python3 SKILL_DIR/scripts/outcomes.py --workspace <ws> event --company C --title T --event decision --value applied --data '{"channel": "greenhouse"}'
python3 SKILL_DIR/scripts/outcomes.py --workspace <ws> event --company C --title T --event stage --value interview --data '{"format": "video-call", "round": 1}'
python3 SKILL_DIR/scripts/outcomes.py --workspace <ws> stats       # funnel
python3 SKILL_DIR/scripts/outcomes.py --workspace <ws> calibrate   # does the fit score predict interviews? (advisory)
```
- **Skips are the most useful labels.** When the user passes on a kept job, log `decision skipped` with a reason code, and ask why if it isn't clear.
- **A single skip is not a rule.** Don't turn one case into a filter. If a correction sounds general, ask: "Should this apply to all X, or only this job?" Log `rule proposed`. Only after the user confirms it and it's in `filters.md`/`memory.md`, log `rule approved` with `--reply` holding their words verbatim. To drop one role but not the company, use `excludedRoles`.
- **Calibration is advisory.** Report `calibrate` as it prints it. With few outcomes it says "n too small" or "insufficient": say so, and never turn 2 of 3 into a percentage. Never retune the fit weights automatically. Suggest changes and let the user decide.
- **Retention.** After a hire, ask for short check-ins at 30, 90, 180 and 365 days (`checkin`: satisfaction 1–5, did the job match the posting 1–5, would stay). The posting saved at apply time (`outcomes/postings/`) is the reference. This tells the user, and the search, which kinds of job actually last.

## 7. Tuning
- The user changes a hard rule → edit `memory.md` **and** the matching `search/filters.md` JSON value, and add a line to the tuning log.
- A source breaks → note it in `search/sources.md`, and disable it in `filters.md` or fix `scan.py`.
- Too much noise or too few jobs → adjust `queries`, `titleKeywords`, `textKeywords`, `minTextHits`, `allowed`, and log the change.

## Files reference
| Workspace file | Purpose |
|---|---|
| `CLAUDE.md` | Loads the workspace context every session |
| `memory.md` | Hard rules (location, pay floor, role, documents, exclusions) |
| `applications.md` | Tracker; its table rows are read by `filter.py` to flag already-applied companies |
| `curriculum/profile.md` | Allowed facts + do-not-claim |
| `search/filters.md` | JSON config for the scripts + field guide + tuning log |
| `search/sources.md`, `search/scan-log.md` | Source notes, scan history |
| `interview/*.md` | Stories + numbers bank, AI-interview rules, salary notes, company prep |
| `outcomes/` | Event log (`outcomes.jsonl`), saved postings, schema README |

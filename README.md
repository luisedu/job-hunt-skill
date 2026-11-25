# job-hunt: a Claude Code skill for an honest, low-noise job search

[![tests](https://github.com/luisedu/job-hunt-skill/actions/workflows/tests.yml/badge.svg)](https://github.com/luisedu/job-hunt-skill/actions/workflows/tests.yml)

A [Claude Code](https://claude.com/claude-code) skill that runs your job search from a local folder of Markdown files:

- **Scans 11 public job boards** (RemoteOK, Remotive, Himalayas, Jobicy, We Work Remotely, Working Nomads, HN "Who is hiring", Arbeitnow, GetOnBoard, Gupy, and optionally Remote Rocketship).
- **Watches companies' own job boards** (Greenhouse, Ashby, Lever, Workable) for the companies you list, so you see openings the day they are posted. `--probe-ats` finds each company's board.
- **Answers "can they hire me, and what will I take home?"** Each job gets an eligibility verdict that tells *residence* apart from *right to work* (a passport isn't an address), detects the contract type (local payroll, PJ, contractor, employer of record) and time-zone overlap, and estimates **net monthly pay** per contract. Brazil (CLT, PJ, export of services) is the first country module; other countries use your own flat rates.
- **Checks whether a company is real:** domain age, mail setup, website, public job board, recruiter email, LEI and the Brazilian CNPJ registry, combined into an explainable trust score. It never says "safe".
- **Turns your history into decisions:** which employers keep posting jobs you can take (and their job boards), each company's reply rate and interview format, the most-requested skills you lack and which ones come with better pay, and a weekly search-health check with one concrete suggestion.
- **Compares offers** (local employee vs. PJ vs. foreign contract) on net pay, benefits and **currency risk**: net if the currency moves ±10–20% and over the last 12 months' real range, plus the local salary that would match each contract.
- **Filters out the noise** most job tools ignore:
  - "remote" jobs that only hire in another country
  - ghost jobs (stale, reposted, talent pools)
  - pay below your floor (converted from any currency)
  - duplicates across boards
- **Flags likely scams:** free-mail recruiters, fees, Telegram/WhatsApp-only contact, implausible pay, unnamed companies.
- **Ranks by fit** against your profile, then Claude vets every job by reading it.
- **Tailors CV and cover-letter PDFs** using only facts from your CV, with a "do not claim" list to keep it honest.
- **Checks each CV the way an ATS reads it:**
  - parsing: selectable text, contact details, headings, dates, glued lines, fonts
  - the posting's keywords, split into already in the CV / missing but true / not yours
  - title match with the posting
  - the screening questions where most automatic rejections happen
  It never suggests hidden text or claiming skills you don't have.
- **Tracks applications** and asks you, now and then, whether you've heard back.
- **Logs outcomes** in an append-only event log: every filter decision, every skip (with your reason), every stage, and check-ins at 30/90/180/365 days after a hire. It saves each posting when you apply, so you can later check whether the job matched what was advertised.
- **Learns carefully:** a correction becomes a rule only after you approve it (your words are stored verbatim). `calibrate` checks whether the fit score predicts interviews, and shows "n too small" instead of a fake percentage.
- **Preps AI-scored interviews** (audio bots, one-way video): answer rules, a numbers bank and mock runs.

It **never applies, emails or messages anyone for you.** You stay in control of every application.

![Demo: scan and filter for a frontend engineer in Portugal](docs/demo.svg)

<sub>Real run with the example profile in `examples/`: 3,381 postings from 8 boards → 48 kept. Onsite jobs and "remote" roles restricted to the US, India and elsewhere were removed automatically.</sub>

## Install

```bash
git clone https://github.com/luisedu/job-hunt-skill
ln -s "$PWD/job-hunt-skill/skill/job-hunt" ~/.claude/skills/job-hunt
```

Requirements: Python 3.11+, `curl`, `pdftotext` (poppler-utils) and LibreOffice (`soffice`) for PDF output.

## Use

Open Claude Code in an empty folder (e.g. `~/JobHunt`) and say:

> Set up my job hunt. My CV is at ~/Downloads/cv.pdf

Claude reads your CV and asks a few questions: target role, where you live, which regions can hire you, and your pay floor. It then creates the workspace:

```
JobHunt/
├── CLAUDE.md              loads the context every session
├── memory.md              hard rules (remote only, pay floor, exclusions…)
├── applications.md        tracker
├── curriculum/            your CV + profile.md (allowed facts, do-not-claim list)
├── search/filters.md      tunable filters (a JSON block the scripts read)
├── search/sources.md      job-board notes
├── search/scan-log.md     scan history
├── interview/             stories + numbers bank, AI-interview rules, salary notes, company prep
├── outcomes/              event log (outcomes.jsonl) + postings saved when you apply
└── <company>/             tailored PDFs
```

After that:

| Say | What happens |
|---|---|
| "Any new jobs?" | Full scan → filter → Claude vets → ranked list with reasons for every exclusion |
| "Tailor my CV for <link>" | Maps requirements to your facts, asks about gaps, writes PDFs |
| "I applied to X" / "X replied" | Tracker and outcome log updated; the posting is saved |
| "Skip X, the pay is too low" | Logged with your reason. Claude asks before turning it into a rule |
| "Prep me for the X interview" | Company research, role → evidence map, honest answers for gaps, questions to ask |
| "Mock my AI interview for X" | Likely questions one at a time, each answer scored against the AI-interview rules |
| "Also watch Acme and Globex" | Finds their job boards (`--probe-ats`) and adds them to the scan |
| "How is my search going?" | Funnel (`stats`) and whether the fit score predicts interviews (`calibrate`) |
| "Is Acme legit? The recruiter wrote from gmail" | `verify_company.py`: trust score, reasons and next steps |
| "Compare this CLT offer with that USD contract" | `netpay.py`: net monthly pay for each, with assumptions |
| "Will my CV pass the ATS for <link>?" | `ats_check.py`: parsing problems, keyword gaps (only true ones to add), title, screening questions |
| "Compare my offers" | `offers.py`: net, benefits, currency scenarios, local-salary equivalent |
| "Which companies hire from my country?" | `insights.py employers --suggest-ats` |
| "What should I learn next?" | `insights.py skills`: gaps across every relevant job, and pay linked to skills |
| "How did this week go?" | `insights.py weekly`: funnel by channel, follow-ups due, one suggestion |
| "Only show EU jobs above €4k" | Rules + filters updated, change logged |

Scripts also run on their own:

```bash
python3 skill/job-hunt/scripts/scan.py   --workspace ~/JobHunt
python3 skill/job-hunt/scripts/filter.py --workspace ~/JobHunt     # also logs filter decisions
python3 skill/job-hunt/scripts/scan.py   --workspace ~/JobHunt --probe-ats acme,globex
python3 skill/job-hunt/scripts/outcomes.py --workspace ~/JobHunt stats       # or: calibrate
python3 skill/job-hunt/scripts/netpay.py   --workspace ~/JobHunt --gross 25000 --contract employee_local
python3 skill/job-hunt/scripts/verify_company.py --workspace ~/JobHunt --company Acme --domain acme.com
python3 skill/job-hunt/scripts/insights.py --workspace ~/JobHunt weekly        # or: employers, companies, skills
python3 skill/job-hunt/scripts/offers.py   --workspace ~/JobHunt               # reads interview/offers.json
python3 skill/job-hunt/scripts/ats_check.py --cv CV.pdf --posting posting.txt --workspace ~/JobHunt
```

## Configuration

All tuning lives in `search/filters.md` in your workspace (see its field guide): queries, title/description keywords, allowed regions, pay floor, ghost-job limits, fit weights, enabled sources, company job boards to watch (`atsBoards`), and single roles to drop without excluding the company (`excludedRoles`). An example: `examples/answers-frontend-portugal.json`.

## Privacy

Your workspace contains your CV, salary expectations, application history and outcome log. The workspace `.gitignore` ignores everything by default. **Don't commit it.** The scripts only call public job-board APIs, an FX-rate API (frankfurter.app) and, for company checks, public registries and DNS (rdap.org, dns.google, api.gleif.org, brasilapi.com.br), plus frankfurter.app for exchange-rate history in offer comparisons. Only company names, domains and currency codes are sent. Nothing about you is sent anywhere.

## Sources and terms

Only public APIs and RSS feeds are used, including the public job-board APIs of Greenhouse, Ashby, Lever and Workable for the companies you list. LinkedIn, Indeed, Glassdoor and Wellfound are intentionally not scraped: search those manually. Remote Rocketship needs your own API key (`~/.config/remoterocketship/api-key`). Job-board endpoints change, so the notes are in `templates/search/sources.md` and PRs are welcome.

## Tests

```bash
python3 -m unittest discover -s tests -v    # offline: filters, outcome log, calibration, job-board parsers, net pay, eligibility, company check, insights, offers, ATS check
```

## License

MIT

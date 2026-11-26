# Changelog

## 0.2.4 (2026-11-26)
- **Filter, pay in the text:** when a job has no salary field, pay stated after a pay word in the posting (e.g. "Compensation $15-$25", "Salary: USD 120,000 – 150,000 per year") now counts for the pay floor and net estimate. Budgets and stipends next to "salary" are ignored.
- **Filter, location:** "hiring for someone in <country>" in the posting text is a restriction, like "must be located in".
- **Docs:** Portuguese (Brazil) README, `README.pt-BR.md`, with a language switch at the top of both READMEs.

## 0.2.3 (2026-11-25)
Beta readiness, from a clean install of the plugin and a live first run.
- **Plugin installs:** the workspace `CLAUDE.md` names the installed skill instead of its versioned cache folder, which changes on every `/plugin update`.
- **ATS check on a URL:** script, style, navigation and footer blocks are dropped before reading, so page CSS no longer shows up as keywords or screening topics; the report notes that a saved posting text gives exact results.
- **Scan:** the company-boards source is skipped while `atsBoards` is empty, instead of a false "0 jobs" warning.
- **Wording:** `offers.py` says "local-employee gross" (not the Brazil-only "CLT"); posting-text restrictions are grouped in the exclusion summary.
- **README:** beta status and known limitations. **GitHub:** issue templates for broken sources, country net-pay modules and bugs, each with a public-data warning.

## 0.2.2 (2026-11-25)
- **Security:**
  - The Remote Rocketship API key never follows a redirect (urllib would have copied it to the new host).
  - The company check and `ats_check --posting URL` only fetch public hosts, check every redirect hop and pin it to the checked address; `--domain` goes through the same host check.
  - Job links from boards keep only http(s); downloads are capped at 20 MB.
  - Workspace files and folders are owner-only (0700/0600); caches, scans, results and `filters.md` edits are written atomically.
  - `redact` no longer keeps a backup with the erased data, and removes old ones.
  - New `render_pdf.py` refuses HTML that loads remote resources and puts PDFs in a safe company-slug folder; SKILL.md says to HTML-escape filled values.
  - CI actions are pinned to commits, with a read-only token.
- **Wrong results fixed:**
  - A bare "Remote" location no longer excludes a job (it's treated as unstated).
  - Remote-only workspaces now exclude hybrid jobs outside `hybridOkCities` (they slipped through when the city was in `allowed`).
  - "Must be located in a time zone…" with no country is a flag, not an exclusion.
  - "Works for us" no longer reads as the USA.
  - Salary text: "50-60k", "4.000" and yearly ranges with dots now parse correctly; day and week rates are recognised.
  - ATS check: "bonus" or "preferred" inside a sentence no longer turns every requirement into "nice to have".
  - "Already applied" and duplicate grouping no longer confuse "The X" with "The Y".
  - `offers.py` handles day and week rates and rejects unknown periods.
- **Usefulness:**
  - An invalid timezone warns instead of crashing, and `init` rejects it up front.
  - `scan.py --only` rejects unknown source names.
  - `stage followed_up` stops `due` repeating the same follow-up for 7 days.
  - Clean errors for missing poppler tools, unreadable posting URLs, bad `--data` JSON, and an apply event with no matching scanned posting.
  - The workspace `CLAUDE.md` holds the real skill path.
- **Less verbose:**
  - The workspace `CLAUDE.md` is a short pointer to the skill (about 1,000 fewer tokens every session).
  - Duplicated rules removed from `memory.md`, `sources.md`, the outcomes README and the reference docs.
  - `filter.py` groups "restricted to …" exclusions and drops repeated flags; small-sample notes print once per report.
- **Docs:** correct plugin install commands; the `answers.json` schema lists the `person` fields.

## 0.2.1 (2026-11-25)
- **Source terms:** Gupy's candidate terms forbid aggregating postings. The source is no longer recommended, stays off by default and warns on every scan if enabled. PerfectRole: terms not found, so check them before enabling.
- **Policy wording:** net pay is an AI-assisted estimate from a fixed formula; the tax regime and what to report are for an accountant; eligibility reads the posting, not legal advice; company verdicts are private signals, never published.
- **README:** "Disclaimer and acceptable use" (for job seekers, not for screening candidates).
- **Security (sharp-edges review):**
  - The company check only trusts domains whose name matches the company, never local or IP hosts, and keys its cache by domain.
  - `init --force` backs files up first; the workspace `.gitignore` always denies everything.
  - `redact` is value-only, backed up, atomic and covers saved postings; `export` drops free text.
  - Exchange-rate fallback warns; invalid `fit` regexes match literally; results never overwrite the input; source errors are reported; a small same-day scan no longer replaces a good one; control and bidi characters are stripped from untrusted text; saved postings are labelled untrusted.
- **CI:** bandit security lint, with the known items documented in `.bandit.yml`.

## 0.2.0 (2026-11-25)
- **Install as a plugin:** `.claude-plugin/` manifest and marketplace.
- **Sources:** companies' own job boards (Greenhouse, Ashby, Lever, Workable) with `--probe-ats`; PerfectRole (sitemaps + JSON-LD, robots-compliant); HN "Who is hiring" thread found automatically; Remotive cached and capped at 4 requests a day (their terms).
- **Filter:** `excludedRoles`; `pay.unlisted` (flag/keep/hide); `pay.floorBasis` (gross/net); salary read from the posting text in the home currency (R$, €, £); Portuguese/Spanish seniority words and "(Remote)" variants in deduplication.
- **Eligibility:** residence vs right to work, EU free movement, contract type, time-zone overlap.
- **Net pay:** country modules (Brazil 2026: CLT, PJ, export of services, dividend rules), flat rates elsewhere.
- **Company check:** domain age, mail, website, job board, recruiter email, LEI, CNPJ, with an explainable trust score.
- **ATS check:** parsing, keyword buckets (only true terms to add), title match, screening topics.
- **Insights:** `due`, `weekly`, `employers`, `companies`, `skills`; offer comparison with currency risk.
- **Outcome log:** events, posting snapshots, calibration, retention check-ins, `redact`, anonymised `export`.
- **Security and privacy:** API key only in an HTTP header, hardened curl, an untrusted-text rule, referee consent, an accurate privacy section.
- **SKILL.md** slimmed to the core steps; details moved to `reference/` (loaded on demand).
- CI: tests on 3.11/3.13 plus `ruff` (pyflakes errors).

## 0.1.0
- Initial release: multi-board scan, ghost/location/pay/scam filter, honest CV and letter tailoring, tracker and follow-ups.

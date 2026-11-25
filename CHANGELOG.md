# Changelog

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

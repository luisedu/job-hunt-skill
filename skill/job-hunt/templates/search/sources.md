# Job sources

Implemented in the skill's `scripts/scan.py`. Turn on/off in `search/filters.md` → `sources`.

| Key | Board | Coverage | Notes |
|---|---|---|---|
| `remoteok` | RemoteOK API | global remote, tech | Full feed (~100). Location often "US Only" |
| `remotive` | Remotive API | global remote | Per query. Salary as free text |
| `himalayas` | Himalayas API | global remote | Per query, `locationRestrictions` list (empty = unrestricted) |
| `jobicy` | Jobicy API | global remote | Per query as tag. `jobGeo` |
| `weworkremotely` | WWR RSS | global remote | Category feeds. `region` tag |
| `workingnomads` | Working Nomads API | global remote | Small feed |
| `hn` | HN "Who is hiring" | startups, many remote | Latest monthly thread found automatically |
| `arbeitnow` | Arbeitnow API | Europe (mostly DE) | Mostly onsite. Enable for EU candidates |
| `getonbrd` | GetOnBoard API | LATAM | Never add `expand=` (returns 0) |
| `gupy` | Gupy portal | Brazil | Parses `__NEXT_DATA__` from portal.gupy.io/job-search. Use `gupyTerms` in Portuguese |
| `remoterocketship` | Remote Rocketship API | 100k+ company career pages | **Needs a paid API key** at `~/.config/remoterocketship/api-key`. Location only in the URL slug |

## Manual-only (login walls / anti-bot, don't scrape)
LinkedIn, Indeed, Glassdoor, Wellfound. Search them yourself with filters: role · Remote · your country/region · past week.

## Verifying a single job or company
- Ashby `api.ashbyhq.com/posting-api/job-board/<co>` · Greenhouse `boards-api.greenhouse.io/v1/boards/<co>/jobs` · SmartRecruiters `api.smartrecruiters.com/v1/companies/<co>/postings/<id>`
- Unknown company: domain age `rdap.verisign.com/com/v1/domain/<domain>`, MX via `dns.google/resolve?name=<domain>&type=MX`, website content, recruiter email domain.

## Notes
_(add quirks, broken endpoints and yield observations here)_

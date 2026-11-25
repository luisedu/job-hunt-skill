# Job sources

Implemented in the skill's `scripts/scan.py`. Turn on/off in `search/filters.md` → `sources`.

| Key | Board | Coverage | Notes |
|---|---|---|---|
| `remoteok` | RemoteOK API | global remote, tech | Full feed (~100). Location often "US Only" |
| `remotive` | Remotive API | global remote | Free API returns only ~15 recent jobs per request (Nov 2026). One request, cached 6 h, max 4/day (their terms); queries matched locally. Salary as free text |
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

## Company job boards (`ats` source)
Public JSON APIs, no key: Greenhouse, Ashby, Lever, Workable. List target companies in `filters.md` → `atsBoards`. Most companies hire locally, so the value is catching a remote opening for your region the day it's posted. Many large companies use Workday or their own site instead: check those by hand.

## Pages that block plain HTTP
If a page needs JavaScript or blocks scripts (some LinkedIn posts, some career sites), a scraping MCP such as Firecrawl can read it. Use it only as a fallback for single pages; free tiers have small credit budgets.

## Terms of use
- Always show the source name and the original job link (RemoteOK, Remotive and Jobicy require attribution and a link back).
- Never republish job data on other sites or use it to collect sign-ups. This workspace is for your personal search.
- Respect each source's rate limits. Don't run full scans more than a couple of times a day.

# Search filters (tunable)

The skill scripts read the JSON block below. Edit values here. Hard rules live in `memory.md`.

```json
{{filtersJson}}
```

## Field guide
- `queries`: search terms sent to every board (keep 3–8, broad).
- `roles.titleKeywords`: a title containing one of these is on-target. `roles.titleRoleWords` (default engineer/developer/…) must also appear, unless the description has keyword hits.
- `roles.textKeywords` + `minTextHits`: a generic title (e.g. "Software Engineer") counts if the description has ≥ N distinct keywords.
- `roles.excludeTitle`: words that drop a title. `excludeTitleUnlessKeyword` drops a title unless it also has a target keyword.
- `location.allowed`: regions/countries that may hire you (worldwide/anywhere are always allowed). Any other named location → excluded.
- `location.hybridOkCities`: onsite/hybrid allowed here. `acceptUnstated`: keep jobs with no location, flagged.
- `pay.floorMonthly`: in `profile.currency`. Jobs whose top of range is below it are dropped. `maxPlausibleMonthly` triggers a scam flag.
- `ghost`: age limits and repost window (days).
- `fit`: regex → weight, for ranking. `penalizeKeywords`: −2 each.
- `excludedRoles`: `[{"company": "…", "title": "…"}]` drops one role (and its reposts) without excluding the whole company. Titles are compared without seniority words, so "Senior X" also drops a repost titled "X".
- `atsBoards`: company job boards to scan directly, by system: `{"greenhouse": [...], "ashby": [...], "lever": [...], "workable": [...]}`. Find slugs with `scan.py --probe-ats name1,name2`.
- `sources`: turn boards on/off (see `search/sources.md`). `gupyTerms`: Portuguese terms for Gupy (Brazil).

## Tuning log
- {{today}}: initial setup.

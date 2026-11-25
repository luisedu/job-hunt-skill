# Outcome log

`outcomes.jsonl` records what happened to every job: filtered, skipped, applied, interviewed, hired, and how the job went afterwards. It's the evidence the search learns from. It's append-only, with one JSON object per line. Never edit old lines: to correct one, append a new event.

- `filter.py` logs every scan automatically.
- Claude logs your decisions, stages, rules and check-ins with `outcomes.py event`.
- `outcomes.py stats` prints the funnel. `outcomes.py calibrate` checks whether the fit score predicts interviews. It is advisory and shows counts, not percentages, while samples are small.
- Applying (`decision applied`) saves the posting text to `postings/`, so later you can check whether the job matched what was advertised.

## Common fields
| Field | Meaning |
|---|---|
| `v` | schema version (1) |
| `date` | YYYY-MM-DD the event happened |
| `event` | `filter` · `decision` · `stage` · `rule` · `checkin` |
| `job` | `<first word of company>/<title slug>`. It joins events for the same job. Pass `--job` to reuse the scan's id when the tracker title differs |
| `value` | see below |
| `reason` | list of reason codes |
| `data` | structured details (format, scores, pay asked, channel…) |
| `note` | short free text. `[backfilled …]` marks reconstructed events |
| `reply` | for `rule` events: the user's words, verbatim |
| `posting` | for `decision applied`: path of the saved posting snapshot |

## Events
| event | values | written when |
|---|---|---|
| `filter` | `keep`, `excluded` | every scan (automatic). Also carries `features` and `reasons_text` |
| `decision` | `applied`, `skipped`, `saved` | you act on a job, or pass on a kept one (log `skipped` with a reason) |
| `stage` | `submitted`, `screening`, `interview`, `offer`, `hired`, `rejected`, `ghosted`, `withdrawn` | every tracker status change |
| `rule` | `proposed`, `approved`, `rejected` | a correction from you becomes a candidate filter rule |
| `checkin` | `30d`, `90d`, `180d`, `365d`, `left` | after a hire: did the job match the posting, and are you staying? |

## Reason codes
- **filter** (automatic): `location_restricted`, `location_unstated`, `onsite`, `stale`, `talent_pool`, `repost`, `pay_below_floor`, `company_excluded`, `role_excluded`, `other`
- **decision** (yours), for example: `pay_below_floor_user`, `level`, `location`, `wrong_role`, `company_reputation`, `scam`, `low_fit`, `inbound`, `other`
- **stage end**, for example: `interview_score`, `no_reply`, `pay_mismatch`, `location_mismatch`, `role_mismatch`, `withdrew_better_offer`, `other`

Add new codes freely, but list them here.

## Useful `data` keys
- **interview:** `format` (`ai-audio`, `ai-interview`, `video-call`, `take-home`, `email-questions`, `onsite`), `vendor`, `round`, `minutes`, `scores`
- **application:** `channel` (`greenhouse`, `ashby`, `lever`, `linkedin`, `referral`, `inbound-recruiter`…), `docs` (language), `contract`, `ask`
- **offer / hire:** `pay`, `currency`, `contract`, `start`
- **checkin:** `satisfaction` (1–5), `role_matches_posting` (1–5), `would_stay` (y/n), `issues`

## Privacy
Personal data. Never publish it. Any future sharing must be opt-in and anonymized (drop company names, notes and URLs; keep codes and features).

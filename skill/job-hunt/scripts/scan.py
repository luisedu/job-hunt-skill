#!/usr/bin/env python3
"""Multi-source job scan driven by the workspace config.

Usage:
    python3 scan.py --workspace PATH            # all enabled sources
    python3 scan.py --workspace PATH --only remotive,himalayas

Reads  PATH/search/filters.md  (JSON block: "queries", "sources", "gupyTerms", "remoteRocketship")
Writes PATH/search/scans/raw-YYYY-MM-DD.json  (list of normalized jobs)

Normalized job: {source, sid, title, company, loc, url, text, posted (ISO-8601 UTC), sal, extra}
sal: {min, max, cur, per} | {text} | null
Only public APIs / RSS feeds are used. No login-walled sites are scraped.
"""
import argparse, datetime as dt, html, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402

UA = "Mozilla/5.0 (X11; Linux x86_64) job-hunt-skill/1.0"


def get(url, timeout=40):
    return subprocess.run(["curl", "-s", "-L", "-m", str(timeout), "-A", UA, url], capture_output=True, text=True).stdout


def getj(url, **kw):
    try:
        return json.loads(get(url, **kw))
    except Exception:
        return None


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(s or "")))).strip()


def pdate(s):
    if not s:
        return None
    try:
        if isinstance(s, (int, float)) or (isinstance(s, str) and s.isdigit()):
            return dt.datetime.fromtimestamp(int(s), dt.timezone.utc)
        s = str(s).replace("Z", "+00:00")
        if re.match(r"\d{4}-\d{2}-\d{2}", s):
            t = s[11:19] if len(s) > 10 else "00:00:00"
            return dt.datetime.fromisoformat(s[:10] + "T" + t).replace(tzinfo=dt.timezone.utc)
        return dt.datetime.strptime(s[:25].strip(), "%a, %d %b %Y %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def job(source, sid, title, company, loc, url, text, posted, sal=None, extra=None):
    return dict(source=source, sid=str(sid), title=strip(title), company=strip(company or ""), loc=strip(loc or ""),
                url=url, text=strip(text)[:20000], posted=posted.isoformat() if posted else None, sal=sal, extra=extra or {})


# ---------------------------------------------------------------- sources
def src_remoterocketship(cfg):
    rr = cfg.get("remoteRocketship") or {}
    keyf = os.path.expanduser(rr.get("apiKeyFile", "~/.config/remoterocketship/api-key"))
    if not os.path.exists(keyf):
        print("remoterocketship: no API key file, skipped", file=sys.stderr)
        return []
    out = []
    for kw in cfg["queries"]:
        for page in range(1, rr.get("maxPages", 3) + 1):
            f = {"keywordFilters": [kw], "showRemoteJobs": True, "itemsPerPage": 50, "page": page}
            if rr.get("seniority"):
                f["seniorityFilters"] = rr["seniority"]
            body = json.dumps({"filters": f, "includeJobDescription": True})
            # the key is read by the shell from the file; it is never printed or put in this script's args
            r = subprocess.run(["sh", "-c", 'curl -s -m 60 -X POST https://www.remoterocketship.com/api/openclaw/jobs/ '
                                '-H "Authorization: Bearer $(cat "$1")" -H "Content-Type: application/json" --data-binary @-', "_", keyf],
                               input=body, capture_output=True, text=True)
            try:
                jobs = json.loads(r.stdout).get("jobOpenings") or []
            except Exception:
                time.sleep(3)
                continue
            for j in jobs:
                s = j.get("salaryRange")
                sal = dict(min=s.get("min"), max=s.get("max"), cur=s.get("currencyCode"),
                           per=s.get("salaryType") or s.get("salaryHumanReadableText")) if s else None
                txt = " ".join(str(j.get(k) or "") for k in ("roleDescription", "roleRequirements", "benefits"))
                # RR has no location field; the slug ends with "<location>-remote"
                out.append(job("RemoteRocketship", j["id"], j.get("roleTitle"), (j.get("company") or {}).get("name"),
                               "slug: " + (j.get("slug") or "").replace("-", " "), j.get("url"), txt, pdate(j.get("created_at")), sal))
            if len(jobs) < 50:
                break
            time.sleep(1)
    return out


def src_remoteok(cfg):
    d = getj("https://remoteok.com/api") or []
    return [job("RemoteOK", j.get("id"), j.get("position"), j.get("company"), j.get("location"), j.get("apply_url") or j.get("url"),
                (j.get("description") or "") + " tags: " + " ".join(j.get("tags") or []), pdate(j.get("date")),
                dict(min=j.get("salary_min"), max=j.get("salary_max"), cur="USD", per="year") if j.get("salary_max") else None)
            for j in d[1:] if isinstance(j, dict)]


def src_remotive(cfg):
    out = []
    for t in cfg["queries"]:
        for j in (getj("https://remotive.com/api/remote-jobs?search=" + quote(t)) or {}).get("jobs", []):
            out.append(job("Remotive", j["id"], j.get("title"), j.get("company_name"), j.get("candidate_required_location"), j.get("url"),
                           j.get("description"), pdate(j.get("publication_date")), {"text": j["salary"]} if j.get("salary") else None))
    return out


def src_himalayas(cfg):
    out = []
    for t in cfg["queries"]:
        for page in range(1, 4):
            jobs = (getj(f"https://himalayas.app/jobs/api/search?q={quote(t)}&page={page}") or {}).get("jobs") or []
            for j in jobs:
                loc = ", ".join(j.get("locationRestrictions") or []) or "unrestricted"
                sal = dict(min=j.get("minSalary"), max=j.get("maxSalary"), cur=j.get("currency") or "USD",
                           per=j.get("salaryPeriod") or "year") if j.get("maxSalary") else None
                out.append(job("Himalayas", j.get("guid") or j.get("applicationLink"), j.get("title"), j.get("companyName"), loc,
                               j.get("applicationLink"), (j.get("description") or "") + " " + (j.get("excerpt") or ""), pdate(j.get("pubDate")), sal))
            if len(jobs) < 20:
                break
    return out


def src_jobicy(cfg):
    out = []
    for t in cfg["queries"]:
        for j in (getj("https://jobicy.com/api/v2/remote-jobs?count=50&tag=" + quote(t)) or {}).get("jobs", []):
            mx = j.get("annualSalaryMax") or j.get("salaryMax")
            sal = dict(min=j.get("annualSalaryMin") or j.get("salaryMin"), max=mx, cur=j.get("salaryCurrency") or "USD",
                       per=j.get("salaryPeriod") or "year") if mx else None
            out.append(job("Jobicy", j["id"], j.get("jobTitle"), j.get("companyName"), j.get("jobGeo"), j.get("url"),
                           j.get("jobDescription") or j.get("jobExcerpt"), pdate(j.get("pubDate")), sal))
    return out


def src_arbeitnow(cfg):
    out = []
    for page in range(1, 8):
        d = getj(f"https://www.arbeitnow.com/api/job-board-api?page={page}") or {}
        for j in d.get("data", []):
            out.append(job("Arbeitnow", j.get("slug"), j.get("title"), j.get("company_name"),
                           (j.get("location") or "") + (" remote" if j.get("remote") else " onsite"), j.get("url"),
                           (j.get("description") or "") + " tags: " + " ".join(j.get("tags") or []), pdate(j.get("created_at"))))
        if not d.get("data"):
            break
    return out


def src_weworkremotely(cfg):
    out = []
    for feed in ["remote-jobs.rss", "categories/remote-programming-jobs.rss", "categories/remote-back-end-programming-jobs.rss",
                 "categories/remote-front-end-programming-jobs.rss", "categories/remote-full-stack-programming-jobs.rss",
                 "categories/remote-design-jobs.rss", "categories/remote-devops-sysadmin-jobs.rss", "categories/all-other-remote-jobs.rss"]:
        x = get("https://weworkremotely.com/" + feed)
        for it in re.findall(r"<item>(.*?)</item>", x, re.S):
            def g(t):
                m = re.search(rf"<{t}>(.*?)</{t}>", it, re.S)
                return (m.group(1) if m else "").replace("<![CDATA[", "").replace("]]>", "")
            comp, _, ttl = strip(g("title")).partition(":")
            out.append(job("WeWorkRemotely", strip(g("guid") or g("link")), ttl or comp, comp, strip(g("region")), strip(g("link")),
                           g("description"), pdate(strip(g("pubDate")))))
    return out


def src_workingnomads(cfg):
    d = getj("https://www.workingnomads.com/api/exposed_jobs/") or []
    return [job("WorkingNomads", j.get("url"), j.get("title"), j.get("company_name"), j.get("location"), j.get("url"),
                (j.get("description") or "") + " tags: " + str(j.get("tags")), pdate(j.get("pub_date"))) for j in d]


def src_getonbrd(cfg):
    out = []
    for t in cfg["queries"]:
        # note: adding expand=... makes this endpoint return nothing
        for j in (getj("https://www.getonbrd.com/api/v0/search/jobs?per_page=100&query=" + quote(t)) or {}).get("data", []):
            a = j.get("attributes", {})
            sal = dict(min=a.get("min_salary"), max=a.get("max_salary"), cur="USD", per="month") if a.get("max_salary") else None
            loc = ("remote " + str(a.get("remote_modality") or "")) if a.get("remote") else "onsite"
            loc += " countries: " + ",".join(a.get("countries") or [])
            out.append(job("GetOnBoard", j.get("id"), a.get("title"), "", loc,
                           (j.get("links") or {}).get("public_url") or f"https://www.getonbrd.com/jobs/{j.get('id')}",
                           " ".join(str(a.get(k) or "") for k in ("description", "functions", "desirable", "benefits")),
                           pdate(a.get("published_at")), sal))
    return out


def src_gupy(cfg):
    """Brazil only. Parses __NEXT_DATA__ from the public search page (the JSON APIs return 404)."""
    out = []
    for t in cfg.get("gupyTerms") or cfg["queries"]:
        for off in range(0, 120, 12):
            url = f"https://portal.gupy.io/job-search/term={quote(t)}" + (f"&offset={off}" if off else "")
            m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', get(url), re.S)
            if not m:
                break
            try:
                d = json.loads(m.group(1))["props"]["pageProps"]["initialJobList"]
            except Exception:
                break
            data = d.get("data") or []
            for j in data:
                out.append(job("Gupy", j["id"], j.get("name"), j.get("careerPageName"),
                               f"{j.get('workplaceType')} {j.get('city') or ''} {j.get('state') or ''} Brazil",
                               j.get("jobUrl"), j.get("description"), pdate(j.get("publishedDate")), None, {"type": j.get("type")}))
            if not data or off + 12 >= (d.get("pagination") or {}).get("total", 0):
                break
    return out


def src_hn(cfg):
    """Latest 'Ask HN: Who is hiring?' thread, found automatically."""
    s = getj("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=who%20is%20hiring") or {}
    tid = next((h["objectID"] for h in s.get("hits", []) if h.get("title", "").lower().startswith("ask hn: who is hiring")), None)
    if not tid:
        return []
    out = []
    for c in (getj(f"https://hn.algolia.com/api/v1/items/{tid}") or {}).get("children", []):
        t = strip(c.get("text"))
        if not t or re.match(r"\s*(seeking|looking for|available for)\b", t, re.I):
            continue  # candidates advertising themselves, not jobs
        parts = [p.strip() for p in t.split("|")]
        out.append(job("HN WhoIsHiring", c.get("id"), " | ".join(parts[1:3])[:150] or t[:100], parts[0][:60], " | ".join(parts[:6])[:300],
                       f"https://news.ycombinator.com/item?id={c.get('id')}", t, pdate(c.get("created_at"))))
    return out


SOURCES = {name[4:]: fn for name, fn in list(globals().items()) if name.startswith("src_")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--only", help="comma-separated source names: " + ",".join(SOURCES))
    a = ap.parse_args()
    ws = os.path.abspath(os.path.expanduser(a.workspace))
    cfg = load_config(ws)
    enabled = [s for s, on in cfg["sources"].items() if on and s in SOURCES]
    if a.only:
        enabled = [s for s in a.only.split(",") if s in SOURCES]
    allj, stats = [], {}
    with ThreadPoolExecutor(6) as ex:
        futs = {s: ex.submit(SOURCES[s], cfg) for s in enabled}
        for s, fu in futs.items():
            try:
                r = fu.result()
            except Exception as e:
                print("ERR", s, repr(e), file=sys.stderr)
                r = []
            stats[s] = len(r)
            allj += r
    out = os.path.join(ws, "search", "scans")
    os.makedirs(out, exist_ok=True)
    fn = os.path.join(out, f"raw-{dt.date.today().isoformat()}.json")
    json.dump(allj, open(fn, "w"))
    print(json.dumps(stats), "total", len(allj))
    print("saved", fn)


if __name__ == "__main__":
    main()

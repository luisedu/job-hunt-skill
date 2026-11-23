#!/usr/bin/env python3
"""Apply the workspace rules to a raw scan.

Usage:
    python3 filter.py --workspace PATH [--raw PATH/search/scans/raw-YYYY-MM-DD.json] [--today YYYY-MM-DD]

Rules (all configured in PATH/search/filters.md):
  relevance  -> title keywords + role words, or role words + enough description keywords
  location   -> remote only (optional), allowed regions, drop remote jobs restricted elsewhere
  ghost      -> too old, reposted over a long span, talent-pool / evergreen listings
  pay        -> monthly pay converted to home currency must reach the floor
  dedupe     -> same company + normalized title across boards
  scams      -> free-mail contacts, fees, messenger-only contact, missing company, implausible pay
Writes PATH/search/scans/results-YYYY-MM-DD.json and prints a ranked summary.
"""
import argparse, collections, datetime as dt, glob, json, os, re, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load_config  # noqa: E402

GLOBAL = re.compile(r"worldwide|anywhere|global|unrestricted|all countries|any (location|country|timezone)|work from anywhere", re.I)
COUNTRY_WORDS = re.compile(
    r"united states|\busa?\b|u\.s\.|canada|united kingdom|\buk\b|europe|\beu\b|emea|apac|latam|latin america|americas|"
    r"germany|deutschland|france|spain|portugal|netherlands|poland|india|israel|australia|ireland|italy|sweden|switzerland|"
    r"austria|belgium|denmark|norway|finland|czech|romania|ukraine|singapore|japan|china|korea|mexico|argentina|colombia|"
    r"chile|peru|brazil|brasil|philippines|vietnam|pakistan|turkey|egypt|nigeria|kenya|south africa|new zealand|"
    r"new york|california|texas|london|berlin|munich|toronto", re.I)
RESTRICT = re.compile(
    r"(?:must|need to|required to|should)\s+(?:be\s+)?(?:currently\s+)?(?:be\s+)?(?:based|located|reside|residing|live|living)\s+in\s+(?:the\s+)?([a-z .]{2,30})"
    r"|authori[sz]ed to work in (?:the\s+)?([a-z .]{2,20})"
    r"|only (?:open to |accepting )?(?:candidates|applicants) (?:based |located |residing )?in (?:the\s+)?([a-z .]{2,20})"
    r"|\b(us|usa|u\.s\.|uk|eu|europe|canada)[- ]only\b"
    r"|((?:us|u\.s\.) citizen|green card|security clearance|ts/sci|\bitar\b)", re.I)
GHOST = re.compile(r"talent pool|banco de talentos|future opportunit|evergreen|always (be )?hiring|pipeline for future|"
                   r"not an active (opening|role)|general application|expression of interest|cadastro reserva", re.I)
SCAM = re.compile(r"telegram|whatsapp|wire transfer|western union|check deposit|purchase (your own |the )?equipment|training fee|"
                  r"registration fee|application fee|pay (a|the) fee|\busdt\b|bitcoin|crypto(currency)? payment|no experience (required|needed)|"
                  r"earn up to \$|guaranteed (income|earnings)|unlimited earning|text (us|me) at", re.I)
FREEMAIL = re.compile(r"[\w.+-]+@(gmail|yahoo|hotmail|outlook|proton(mail)?|icloud|aol)\.(com|me)", re.I)


def words_re(words):
    words = [w for w in words if w]
    if not words:
        return re.compile(r"(?!x)x")
    return re.compile(r"(?:" + "|".join(r"\b" + re.escape(w).replace(r"\ ", r"[\s-]?") + r"\b" for w in words) + r")", re.I)


def norm_title(s):
    s = (s or "").lower()
    s = re.sub(r"job id:?\s*\S+|\b[a-z]{2}\d{4,}\b", " ", s)
    s = re.sub(r"\b(senior|sr\.?|mid[- ]level|staff|principal|lead|ii+|iv|remote)\b", " ", s)
    return re.sub(r"[^a-z0-9à-ú]+", " ", s).strip()


def fx_table(cfg):
    home = cfg["profile"]["currency"].upper()
    try:
        if os.environ.get("JOB_HUNT_OFFLINE"):
            raise RuntimeError("offline")
        out = subprocess.run(["curl", "-s", "-L", "-m", "15", f"https://api.frankfurter.app/latest?from={home}"], capture_output=True, text=True).stdout
        rates = json.loads(out)["rates"]
    except Exception:
        rates = cfg["fallbackFxPerCurrency"]
    tbl = {k.upper(): 1 / v for k, v in rates.items() if v}
    tbl[home] = 1.0
    return tbl


def monthly_pay(j, cfg, fx):
    """Return (low, high) monthly pay in home currency, or None."""
    s, hours = j.get("sal"), cfg["pay"]["hoursPerMonth"]
    vals, cur, per = [], None, ""
    if s and "text" in s:
        txt = s["text"]
        cur = "EUR" if "€" in txt else "GBP" if "£" in txt else "BRL" if "R$" in txt else "USD"
        for n, k in re.findall(r"(\d[\d,.]*)\s*(k)?", txt, re.I):
            try:
                v = float(n.replace(",", "")) * (1000 if k else 1)
            except ValueError:
                continue
            if v > 5:
                vals.append(v)
        per = "hour" if re.search(r"hour|/h\b|hr", txt, re.I) else "month" if re.search(r"month|/mo", txt, re.I) else ""
    elif s:
        for x in (s.get("min"), s.get("max")):
            try:
                if x and float(x) > 0:
                    vals.append(float(x))
            except (TypeError, ValueError):
                pass
        cur, per = (s.get("cur") or "USD").upper(), str(s.get("per") or "").lower()
    if not vals or cur not in fx:
        return None
    lo, hi = min(vals), max(vals)
    if "hour" in per or "hr" in per:
        f = hours
    elif "day" in per:
        f = hours / 8
    elif "week" in per:
        f = 4.33
    elif "month" in per:
        f = 1
    elif "year" in per or "annual" in per:
        f = 1 / 12
    else:  # guess from magnitude (in USD terms)
        usd = hi * fx[cur] / fx.get("USD", 1)
        f = 1 / 12 if usd > 20000 else hours if usd < 300 else 1
    return round(lo * f * fx[cur]), round(hi * f * fx[cur])


def classify(j, cfg, R, fx, today):
    title, text, loc = j["title"], j["text"], j["loc"]
    head = text[:3000]
    reasons, flags = [], []
    roles = cfg["roles"]

    # ---- relevance
    if R["excl_title"].search(title):
        return "irrelevant", ["excluded title word"], flags
    kw_title = bool(R["title_kw"].search(title))
    role_title = bool(R["role"].search(title))
    hits = len({m.group(0).lower() for m in R["text_kw"].finditer(text)})
    if not ((kw_title and (role_title or hits >= 1)) or (role_title and hits >= roles["minTextHits"])):
        return "irrelevant", ["not target role"], flags
    if R["excl_unless"].search(title) and not kw_title:
        return "irrelevant", ["excluded specialisation"], flags

    # ---- location
    L = cfg["location"]
    locl = loc.lower()
    if j["source"] == "RemoteRocketship":
        tw = set(re.sub(r"[^a-z0-9 ]", " ", title.lower()).split())
        locl = " ".join(w for w in locl.replace("slug:", "").split() if w not in tw and w != "remote" and not w.isdigit())
        j["loc"] = "location: " + (locl or "?")
    remote_signal = re.search(r"remote|remoto|anywhere|worldwide|unrestricted", loc + " " + head[:600], re.I)
    if j["source"] == "Gupy":
        wp = loc.split(" ")[0]
        if wp != "remote" and L["remoteOnly"] and not R["hybrid_city"].search(loc):
            reasons.append(f"{wp}, not remote")
    elif L["remoteOnly"] and re.search(r"\bonsite\b|on-site only|in[- ]office", loc, re.I) and not re.search("remote", loc, re.I):
        reasons.append("onsite")
    elif L["remoteOnly"] and j["source"].startswith("HN") and not re.search("remote", loc, re.I):
        reasons.append("not remote")
    stated = locl.strip(" ,;-") not in ("", "?", "unrestricted") and j["source"] not in ("HN WhoIsHiring", "Gupy")
    if stated and not GLOBAL.search(locl) and not R["allowed"].search(locl):
        reasons.append("restricted to " + locl.strip()[:40])
    m = RESTRICT.search(text)
    if m and not GLOBAL.search(locl) and not R["allowed"].search(locl):
        target = next((g for g in m.groups() if g), m.group(0))
        if not R["allowed"].search(target):
            reasons.append("restricted: " + m.group(0)[:50])
    if not stated and not GLOBAL.search(loc + " " + head) and not R["allowed"].search(loc + " " + head):
        if L["acceptUnstated"]:
            flags.append("location not stated: verify eligibility")
        else:
            reasons.append("location not stated")

    # ---- ghost
    G = cfg["ghost"]
    if j["posted"]:
        age = (today - dt.datetime.fromisoformat(j["posted"])).days
        j["age_days"] = age
        if age > G["maxAgeDays"]:
            reasons.append(f"open {age} days (stale)")
        elif age > G["warnAgeDays"]:
            flags.append(f"{age} days old")
    else:
        flags.append("no post date")
    gm = GHOST.search(text)
    if gm:
        reasons.append(f'talent pool / ghost ("{gm.group(0)}")')

    # ---- pay
    P = cfg["pay"]
    pay = monthly_pay(j, cfg, fx)
    j["pay_monthly"] = pay
    cur = cfg["profile"]["currency"]
    if pay and P["floorMonthly"]:
        if pay[1] < P["floorMonthly"]:
            reasons.append(f"pay max ~{cur} {pay[1]:,}/mo < floor {P['floorMonthly']:,}")
        elif pay[0] < P["floorMonthly"]:
            flags.append(f"range starts below floor ({cur} {pay[0]:,}–{pay[1]:,}/mo)")
    elif not pay:
        flags.append("salary not listed")

    # ---- companies
    co = j["company"].lower()
    if co and any(c.lower() in co for c in cfg["excludedCompanies"] if c):
        reasons.append("company excluded")
    if co and R["applied"] and any(a and a.split()[0] in co.split()[:2] for a in R["applied"]):
        flags.append("ALREADY APPLIED / in pipeline")

    # ---- scams
    sc = []
    fm = FREEMAIL.search(text)
    if fm:
        sc.append("free-mail contact (@" + fm.group(0).split("@")[1] + ")")
    sm = SCAM.search(text)
    if sm:
        sc.append(f'keyword "{sm.group(0)}"')
    if not j["company"] or re.search(r"confidential|stealth|undisclosed|^n/?a$", j["company"], re.I):
        sc.append("company not named")
    if len(text) < 400:
        sc.append("very short description")
    if pay and P["maxPlausibleMonthly"] and pay[1] > P["maxPlausibleMonthly"]:
        sc.append("implausibly high pay")
    if sc:
        flags.append("SCAM CHECK: " + "; ".join(sc))
    return ("excluded" if reasons else "keep"), reasons, flags


def fit_score(j, cfg, R):
    t = (j["title"] + " " + j["text"]).lower()
    s = sum(w for p, w in cfg["fit"].items() if re.search(p, t, re.I))
    if R["title_kw"].search(j["title"]):
        s += 4
    if R["allowed"].search(j["loc"] + " " + j["text"][:3000]):
        s += 3
    if j.get("pay_monthly") and cfg["pay"]["floorMonthly"] and j["pay_monthly"][1] >= cfg["pay"]["floorMonthly"]:
        s += 2
    s -= 2 * sum(1 for p in cfg["penalizeKeywords"] if re.search(p, t, re.I))
    return s


def run(ws, raw_path=None, today=None):
    cfg = load_config(ws)
    scans = os.path.join(ws, "search", "scans")
    raw_path = raw_path or sorted(glob.glob(os.path.join(scans, "raw-*.json")))[-1]
    with open(raw_path) as fh:
        raw = json.load(fh)
    today = today or dt.datetime.now(dt.timezone.utc)
    apps_md = os.path.join(ws, "applications.md")
    applied = set()
    if os.path.exists(apps_md):
        with open(apps_md, encoding="utf-8") as fh:
            applied = {m.strip().lower() for m in re.findall(r"^\|\s*\d{4}-\d{2}(?:-\d{2})?\s*\|\s*([^|]+)\|", fh.read(), re.M)}
    R = {
        "title_kw": words_re(cfg["roles"]["titleKeywords"]),
        "role": words_re(cfg["roles"]["titleRoleWords"]),
        "text_kw": words_re(cfg["roles"]["textKeywords"]),
        "excl_title": words_re(cfg["roles"]["excludeTitle"]),
        "excl_unless": words_re(cfg["roles"]["excludeTitleUnlessKeyword"]),
        "allowed": words_re(cfg["location"]["allowed"]),
        "hybrid_city": words_re(cfg["location"]["hybridOkCities"]),
        "applied": applied,
    }
    fx = fx_table(cfg)
    for j in raw:
        j["status"], j["reasons"], j["flags"] = classify(j, cfg, R, fx, today)

    groups = collections.defaultdict(list)
    for j in raw:
        if j["status"] != "irrelevant":
            groups[((norm_title(j["company"]).split() or [""])[0], norm_title(j["title"]))].append(j)
    final = []
    for g in groups.values():
        g.sort(key=lambda x: x["posted"] or "")
        dates = sorted({x["posted"][:10] for x in g if x["posted"]})
        best = dict(g[-1])
        if not best.get("pay_monthly"):  # keep salary info from any duplicate
            withpay = [x for x in g if x.get("pay_monthly")]
            if withpay:
                best["pay_monthly"], best["sal"] = withpay[-1]["pay_monthly"], withpay[-1]["sal"]
                best["flags"] = [f for f in best["flags"] if f != "salary not listed"]
        best["sources"] = sorted({x["source"] for x in g})
        best["urls"] = list(dict.fromkeys(x["url"] for x in g if x["url"]))[:3]
        if len(dates) >= 2 and (dt.date.fromisoformat(dates[-1]) - dt.date.fromisoformat(dates[0])).days > cfg["ghost"]["repostSpanDays"]:
            best["status"] = "excluded"
            best["reasons"] = best["reasons"] + [f"reposted ({len(g)} postings, {dates[0]} → {dates[-1]})"]
        inherited = [r for x in g for r in x["reasons"] if r.startswith(("restricted", "onsite", "pay max", "open "))]
        if best["status"] == "keep" and inherited:
            best["status"], best["reasons"] = "excluded", inherited[:1]
        best["fit"] = fit_score(best, cfg, R)
        final.append(best)

    keep = sorted([j for j in final if j["status"] == "keep"], key=lambda x: -x["fit"])
    exc = [j for j in final if j["status"] == "excluded"]
    res_path = raw_path.replace("raw-", "results-")
    with open(res_path, "w") as fh:
        json.dump({"keep": keep, "excluded": exc}, fh, ensure_ascii=False, indent=1)
    summary = collections.Counter(re.sub(r"\d[\d,]*|\(.*|:.*", "#", j["reasons"][0])[:40] for j in exc)
    return dict(raw=len(raw), irrelevant=sum(j["status"] == "irrelevant" for j in raw), unique=len(final),
                keep=keep, excluded=exc, reasons=summary.most_common(), path=res_path, currency=cfg["profile"]["currency"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--raw")
    ap.add_argument("--today", help="YYYY-MM-DD (for reproducible runs)")
    a = ap.parse_args()
    today = dt.datetime.fromisoformat(a.today).replace(tzinfo=dt.timezone.utc) if a.today else None
    r = run(os.path.abspath(os.path.expanduser(a.workspace)), a.raw, today)
    print(f"raw {r['raw']} | irrelevant {r['irrelevant']} | unique relevant {r['unique']} | keep {len(r['keep'])} | excluded {len(r['excluded'])}")
    print("excluded by reason:", r["reasons"][:12])
    for j in r["keep"]:
        pay = f"{r['currency']} {j['pay_monthly'][0]:,}–{j['pay_monthly'][1]:,}/mo" if j.get("pay_monthly") else "no salary"
        print(f"\n[{j['fit']}] {j['title']} — {j['company']} | {'+'.join(j['sources'])} | {j.get('age_days')}d | {pay}")
        print("   loc:", j["loc"][:110])
        if j["flags"]:
            print("   flags:", "; ".join(j["flags"]))
        print("  ", j["urls"][0] if j["urls"] else "")
    print("\nsaved", r["path"])


if __name__ == "__main__":
    main()

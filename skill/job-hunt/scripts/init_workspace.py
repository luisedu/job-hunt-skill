#!/usr/bin/env python3
"""Create a job-hunt workspace from templates.

Usage:
    python3 init_workspace.py --workspace PATH --answers answers.json [--force]

answers.json (Claude collects these from the user first; see SKILL.md "First run"):
{
  "name": "Ana Silva",
  "headline": "Frontend Engineer",
  "homeCountry": "Portugal",
  "homeCity": "Lisbon",
  "currency": "EUR",
  "languages": "Portuguese (native), English (fluent)",
  "targetRoles": "Senior Frontend / React engineer",
  "seniority": ["mid", "senior"],
  "queries": ["frontend", "react", "typescript"],
  "titleKeywords": ["frontend", "front-end", "react", "ui engineer"],
  "textKeywords": ["react", "typescript", "next.js", "css"],
  "excludeTitleUnlessKeyword": ["backend", "mobile"],
  "allowedRegions": ["portugal", "europe", "eu", "emea"],
  "hybridOkCities": ["lisbon"],
  "remoteOnly": true,
  "floorMonthly": 3500,
  "targetRate": "EUR 45/h as contractor or EUR 60k/yr employee",
  "excludedCompanies": [],
  "fit": {"react": 2, "typescript": 2, "next\\.js": 1},
  "sources": {"gupy": false, "getonbrd": false, "arbeitnow": true, "remoterocketship": false},
  "gupyTerms": []
}
"""
import argparse, json, os, re, shutil, sys, datetime as dt

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(SKILL, "templates")


def render(text, a):
    def rep(m):
        v = a.get(m.group(1), "")
        if isinstance(v, (list, dict)):
            return ", ".join(v) if isinstance(v, list) else json.dumps(v)
        return str(v)
    return re.sub(r"\{\{(\w+)\}\}", rep, text)


def filters_json(a):
    cfg = {
        "profile": {"homeCountry": a["homeCountry"], "currency": a["currency"].upper()},
        "queries": a["queries"],
        "gupyTerms": a.get("gupyTerms", []),
        "sources": a.get("sources", {}),
        "remoteRocketship": {"apiKeyFile": "~/.config/remoterocketship/api-key", "seniority": a.get("seniority", ["mid", "senior"]), "maxPages": 3},
        "roles": {
            "titleKeywords": a["titleKeywords"],
            "textKeywords": a["textKeywords"],
            "minTextHits": a.get("minTextHits", 2),
            "excludeTitleUnlessKeyword": a.get("excludeTitleUnlessKeyword", ["llm", "genai", "agentic", "prompt"]),
        },
        "location": {"remoteOnly": a.get("remoteOnly", True), "allowed": a["allowedRegions"],
                     "hybridOkCities": a.get("hybridOkCities", []), "acceptUnstated": True},
        "pay": {"floorMonthly": a["floorMonthly"], "hoursPerMonth": 160, "maxPlausibleMonthly": a["floorMonthly"] * 12},
        "ghost": {"maxAgeDays": 60, "warnAgeDays": 35, "repostSpanDays": 21},
        "fit": a.get("fit", {}),
        "penalizeKeywords": a.get("penalizeKeywords", []),
        "excludedCompanies": a.get("excludedCompanies", []),
        "excludedRoles": a.get("excludedRoles", []),
        "atsBoards": a.get("atsBoards", {"greenhouse": [], "ashby": [], "lever": [], "workable": []}),
    }
    return json.dumps(cfg, indent=2, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--answers", required=True)
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    o = ap.parse_args()
    ws = os.path.abspath(os.path.expanduser(o.workspace))
    a = json.load(open(o.answers))
    missing = [k for k in ("name", "homeCountry", "currency", "queries", "titleKeywords", "textKeywords", "allowedRegions", "floorMonthly") if k not in a]
    if missing:
        sys.exit("answers.json missing: " + ", ".join(missing))
    a.setdefault("today", dt.date.today().isoformat())
    a.setdefault("excludedCompaniesList", "\n".join(f"- {c}" for c in a.get("excludedCompanies", [])) or "- (none yet)")
    a["filtersJson"] = filters_json(a)

    created, skipped = [], []
    for root, _, files in os.walk(TPL):
        for f in files:
            if f.endswith(".html"):
                continue  # document templates stay in the skill
            src = os.path.join(root, f)
            rel = os.path.relpath(src, TPL)
            dst = os.path.join(ws, rel)
            if os.path.exists(dst) and not o.force:
                skipped.append(rel)
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "w", encoding="utf-8").write(render(open(src, encoding="utf-8").read(), a))
            created.append(rel)
    for d in ("curriculum", "search/scans", "outcomes/postings"):
        os.makedirs(os.path.join(ws, d), exist_ok=True)
    gi = os.path.join(ws, ".gitignore")
    if not os.path.exists(gi):
        open(gi, "w").write("# personal data: never publish\n*\n")
    print("workspace:", ws)
    print("created:", *created, sep="\n  ")
    if skipped:
        print("kept existing (use --force to overwrite):", *skipped, sep="\n  ")
    print("next: put your CV PDF in", os.path.join(ws, "curriculum"), "and ask Claude to fill curriculum/profile.md")


if __name__ == "__main__":
    main()

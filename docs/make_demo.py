#!/usr/bin/env python3
"""Rebuild docs/demo.svg from a real run with an example profile.

    W=$(mktemp -d); rmdir $W
    python3 skill/job-hunt/scripts/init_workspace.py --workspace $W --answers examples/answers-frontend-portugal.json
    python3 skill/job-hunt/scripts/scan.py --workspace $W && python3 skill/job-hunt/scripts/filter.py --workspace $W
    python3 docs/make_demo.py $W
"""
import collections, glob, html, json, os, re, sys

ws = sys.argv[1]
res_path = sorted(glob.glob(os.path.join(ws, "search", "scans", "results-*.json")))[-1]
raw = json.load(open(res_path.replace("results-", "raw-")))
res = json.load(open(res_path))
sources = collections.Counter(j["source"] for j in raw)
reasons = collections.Counter(re.sub(r"\(.*|:.*|\d[\d,]*", "", j["reasons"][0]).strip()[:28] for j in res["excluded"])
relevant = len(res["keep"]) + len(res["excluded"])

lines = [("#7ee787", "$ python3 scan.py --workspace ~/JobHunt && python3 filter.py --workspace ~/JobHunt"),
         ("#c9d1d9", f"{len(raw):,} postings from {len(sources)} boards → {relevant} relevant → {len(res['keep'])} kept"),
         ("#8b949e", "excluded: " + ", ".join(f"{r} {n}" for r, n in reasons.most_common(4))),
         ("#c9d1d9", "")]
for j in res["keep"][:5]:
    pay = f"€{j['pay_monthly'][0]:,}–{j['pay_monthly'][1]:,}/mo" if j.get("pay_monthly") else "salary not listed"
    lines.append(("#79c0ff", f"[{j['fit']}] {j['title'][:58]} — {j['company'][:22]}"))
    lines.append(("#8b949e", f"     {'+'.join(j['sources'])} · eligibility: {j.get('eligibility')} · {pay} · {j.get('age_days')}d"))
lines.append(("#c9d1d9", ""))
lines.append(("#d2a8ff", "Claude reads each kept job, checks the company, tailors an ATS-checked CV. You apply."))

h = 40 + 21 * len(lines) + 16
out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="980" height="{h}" viewBox="0 0 980 {h}">',
       f'<rect width="980" height="{h}" rx="10" fill="#0d1117"/>',
       '<circle cx="20" cy="18" r="6" fill="#ff5f56"/><circle cx="40" cy="18" r="6" fill="#ffbd2e"/><circle cx="60" cy="18" r="6" fill="#27c93f"/>',
       '<text x="490" y="22" fill="#8b949e" font-family="monospace" font-size="12" text-anchor="middle">job-hunt · example profile: frontend engineer in Portugal, floor EUR 3,500/mo</text>',
       '<g font-family="ui-monospace,SFMono-Regular,Menlo,Consolas,monospace" font-size="13">']
for i, (color, text) in enumerate(lines):
    out.append(f'<text x="16" y="{52 + 21 * i}" fill="{color}" xml:space="preserve">{html.escape(text)}</text>')
out.append("</g></svg>")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo.svg"), "w").write("\n".join(out) + "\n")
print(f"demo.svg: {len(raw)} postings, {len(sources)} boards, {relevant} relevant, {len(res['keep'])} kept")

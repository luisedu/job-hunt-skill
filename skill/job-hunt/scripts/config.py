"""Load the workspace config: the first ```json block in <workspace>/search/filters.md, merged over defaults."""
import copy, json, os, re

DEFAULTS = {
    "profile": {"homeCountry": "", "currency": "USD"},
    "queries": [],
    "gupyTerms": [],
    "sources": {
        "remoterocketship": False, "remoteok": True, "remotive": True, "himalayas": True, "jobicy": True,
        "arbeitnow": False, "weworkremotely": True, "workingnomads": True, "getonbrd": False, "gupy": False, "hn": True,
    },
    "remoteRocketship": {"apiKeyFile": "~/.config/remoterocketship/api-key", "seniority": ["mid", "senior"], "maxPages": 3},
    "roles": {
        "titleKeywords": [],
        "titleRoleWords": ["engineer", "developer", "scientist", "researcher", "specialist", "architect", "programmer"],
        "textKeywords": [],
        "minTextHits": 2,
        "excludeTitle": ["sales", "account exec", "account manager", "marketing", "recruit", "talent", "intern", "trainee",
                         "junior", "jr", "director", "vp", "head of", "teacher", "instructor", "tutor", "support",
                         "counsel", "lawyer", "nurse", "physician", "ai trainer", "annotator", "writer"],
        "excludeTitleUnlessKeyword": ["llm", "genai", "generative", "agentic", "agent", "nlp", "prompt"],
    },
    "location": {"remoteOnly": True, "allowed": [], "hybridOkCities": [], "acceptUnstated": True},
    "pay": {"floorMonthly": 0, "hoursPerMonth": 160, "maxPlausibleMonthly": 0},
    "ghost": {"maxAgeDays": 60, "warnAgeDays": 35, "repostSpanDays": 21},
    "fit": {},
    "penalizeKeywords": [],
    "excludedCompanies": [],
    "fallbackFxPerCurrency": {},
}


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load_config(workspace):
    path = os.path.join(workspace, "search", "filters.md")
    with open(path, encoding="utf-8") as fh:
        md = fh.read()
    m = re.search(r"```json\s*(\{.*?\})\s*```", md, re.S)
    if not m:
        raise SystemExit(f"No ```json block found in {path}")
    cfg = _merge(DEFAULTS, json.loads(m.group(1)))
    if not cfg["queries"]:
        raise SystemExit("filters.md: 'queries' is empty: add the search terms for your target role")
    return cfg

"""End-to-end first run for every example profile (offline), region-specific filtering, and country-module checks.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, glob, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
os.environ["JOB_HUNT_OFFLINE"] = "1"
import config  # noqa: E402
import filter as F  # noqa: E402
import insights as I  # noqa: E402
import netpay as N  # noqa: E402

TODAY = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
EXAMPLES = sorted(glob.glob(os.path.join(ROOT, "examples", "answers-*.json")))


def J(title, loc, text, company="Co", sal=None, days=3):
    return dict(source="Himalayas", sid=f"{company}-{title}-{loc}", title=title, company=company, loc=loc, url=f"https://example.com/{company}",
                text=text * 8, posted=(TODAY - dt.timedelta(days=days)).isoformat(), sal=sal, extra={})


def init(answers):
    ws = tempfile.mkdtemp(prefix="jh-ex-")
    shutil.rmtree(ws)  # start from a folder that doesn't exist yet, like a real first run
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", ws, "--answers", answers],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return ws


def run(ws, jobs, fx=None):
    if fx:
        fm = os.path.join(ws, "search", "filters.md")
        with open(fm) as f:
            md = f.read()
        with open(fm, "w") as f:
            f.write(md.replace('"excludedCompanies"', f'"fallbackFxPerCurrency": {json.dumps(fx)},\n  "excludedCompanies"', 1))
    raw = os.path.join(ws, "search", "scans", "raw-2026-06-15.json")
    with open(raw, "w") as f:
        json.dump(jobs, f)
    r = F.run(ws, raw, TODAY)
    return {j["company"]: j for j in r["keep"]}, {j["company"]: j for j in r["excluded"]}


class FirstRun(unittest.TestCase):
    def test_every_example_creates_a_clean_workspace(self):
        self.assertGreaterEqual(len(EXAMPLES), 3)
        for ex in EXAMPLES:
            with self.subTest(example=os.path.basename(ex)):
                ws = init(ex)
                try:
                    for f in ("CLAUDE.md", "memory.md", "applications.md", "curriculum/profile.md", "search/filters.md", "search/sources.md",
                              "interview/stories.md", "interview/ai-interviews.md", "interview/offers.json", "outcomes/README.md", ".gitignore"):
                        self.assertTrue(os.path.exists(os.path.join(ws, f)), f)
                    for path in glob.glob(os.path.join(ws, "**", "*.md"), recursive=True):
                        with open(path) as fh:
                            self.assertNotIn("{{", fh.read(), path)
                    cfg = config.load_config(ws)
                    self.assertTrue(cfg["person"]["residence"])
                    self.assertEqual(I.due(ws), {"follow_up": [], "ghost_risk": [], "interviews": [], "checkins": []})
                    with open(os.path.join(ws, ".gitignore")) as fh:
                        self.assertIn("*", fh.read())
                finally:
                    shutil.rmtree(ws)


class Regions(unittest.TestCase):
    def test_argentina_data_engineer(self):
        ws = init(os.path.join(ROOT, "examples", "answers-data-engineer-argentina.json"))
        try:
            txt = " Build pipelines with Spark, Airflow, dbt and Kafka in Python and SQL."
            keep, exc = run(ws, [J("Senior Data Engineer", "LATAM", txt, "Latam Co", {"min": 6000, "max": 7000, "cur": "USD", "per": "month"}),
                                 J("Data Engineer", "USA", txt, "US Co")])
            self.assertIn("Latam Co", keep)
            self.assertEqual(keep["Latam Co"]["eligibility"], "eligible")
            self.assertEqual(keep["Latam Co"]["pay_net"], (round(6000 * 11 / 12 * 0.82), round(7000 * 11 / 12 * 0.82)))  # flat rate, 11 months
            self.assertIn("restricted", " ".join(exc["US Co"]["reasons"]))
        finally:
            shutil.rmtree(ws)

    def test_spain_designer_hybrid_and_eu(self):
        ws = init(os.path.join(ROOT, "examples", "answers-designer-spain.json"))
        try:
            txt = " Own the design system in Figma, run user research and prototyping with accessibility in mind."
            keep, exc = run(ws, [J("Senior Product Designer", "Hybrid, Madrid", txt, "Madrid Co"),
                                 J("Product Designer", "Remote, Europe", txt, "EU Co"),
                                 J("Product Designer", "Remote, USA", txt, "US Co"),
                                 J("Graphic Designer", "Remote, Europe", txt, "Graphic Co")])
            self.assertTrue({"Madrid Co", "EU Co"} <= set(keep))
            self.assertIn("US Co", exc)
            self.assertNotIn("Graphic Co", set(keep) | set(exc))  # excluded title word -> irrelevant
        finally:
            shutil.rmtree(ws)


class TitleNormalisation(unittest.TestCase):
    def test_dedupe_keys(self):
        n = F.norm_title
        self.assertEqual(n("AI Senior Engineer (Vision)"), n("AI Senior Engineer - Vision"))                       # keep meaningful words
        self.assertEqual(n("ML Engineer - Computer Vision (Remote Position)"), n("ML Engineer – Computer Vision"))  # drop markers
        self.assertEqual(n("Engenheiro de Visão Computacional Sênior (Remoto)"), n("Engenheiro de Visão Computacional Pleno"))
        self.assertNotEqual(n("Vision Engineer (3D)"), n("Vision Engineer (2D)"))


class CountryModules(unittest.TestCase):
    def test_modules_have_required_keys_and_rules(self):
        files = glob.glob(os.path.join(SCRIPTS, "netpay", "*.json"))
        self.assertTrue(files)
        for p in files:
            with open(p) as f:
                m = json.load(f)
            for k in ("country", "currency", "validFrom", "validUntil", "note", "sources"):
                self.assertIn(k, m, p)
            self.assertEqual(os.path.basename(p)[:-5], m["country"])
            self.assertIn(m["country"], N.COUNTRIES, "register the rules in netpay.COUNTRIES (docs/netpay-countries.md)")
            self.assertTrue(set(N.COUNTRIES[m["country"]]) & {"employee", "company"})
            self.assertTrue(all(str(v).startswith(("http", "LC ", "Lei ", "Portaria")) for v in m["sources"].values()), m["sources"])


if __name__ == "__main__":
    unittest.main()

"""Offline tests: init a fake workspace, feed synthetic jobs, check every filter rule.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
os.environ["JOB_HUNT_OFFLINE"] = "1"
import filter as F  # noqa: E402

TODAY = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
LONG = " We build web apps with React and TypeScript, Next.js, CSS and a design system. " * 10


def J(title, company="Acme", loc="Europe", days=3, sal=None, text=LONG, source="Remotive", sid=None):
    posted = (TODAY - dt.timedelta(days=days)).isoformat()
    return dict(source=source, sid=sid or f"{company}-{title}-{days}", title=title, company=company, loc=loc,
                url=f"https://example.com/{company}/{days}", text=text, posted=posted, sal=sal, extra={})


class FilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws = tempfile.mkdtemp(prefix="jh-test-")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", cls.ws,
                        "--answers", os.path.join(ROOT, "examples", "answers-frontend-portugal.json")], check=True, capture_output=True)
        # fallback FX for offline runs: units of currency per 1 EUR
        fm = os.path.join(cls.ws, "search", "filters.md")
        md = open(fm).read().replace('"excludedCompanies"', '"fallbackFxPerCurrency": {"USD": 1.1, "GBP": 0.85},\n  "excludedCompanies"', 1)
        open(fm, "w").write(md)
        with open(os.path.join(cls.ws, "applications.md"), "a") as f:
            f.write("\n| 2026-06-01 | Applied Co | Frontend Engineer | link | submitted | 2026-06-01 | — | — |\n")
        jobs = [
            J("Senior Frontend Engineer", "GoodCo", "Europe", sal={"min": 70000, "max": 90000, "cur": "EUR", "per": "year"}),
            J("Senior Frontend Engineer", "GoodCo", "EMEA", source="Himalayas"),                 # duplicate
            J("React Developer", "UsOnly", "USA"),                                                 # restricted
            J("Frontend Engineer", "TextRestrict", "", text=LONG + " Candidates must be located in the United States."),
            J("Frontend Engineer", "OldCo", "Worldwide", days=90),                                 # stale
            J("Frontend Engineer", "Repost", "Worldwide", days=50, sid="r1"),
            J("Frontend Engineer", "Repost", "Worldwide", days=2, sid="r2"),                       # reposted
            J("Frontend Engineer", "CheapCo", "Worldwide", sal={"min": 15, "max": 18, "cur": "USD", "per": "hour"}),
            J("Frontend Engineer", "Pool", "Worldwide", text=LONG + " Join our talent pool for future opportunities."),
            J("Account Executive", "SalesCo", "Worldwide"),                                        # irrelevant
            J("Backend Engineer (Go)", "BackCo", "Worldwide", text="Go, Kafka, Postgres " * 40),  # irrelevant
            J("Frontend Developer", "", "Worldwide", text=LONG + " Contact us on Telegram, send CV to hr.jobs@gmail.com"),
            J("Frontend Engineer", "Example Bad Corp", "Worldwide"),                               # excluded company
            J("Frontend Engineer", "Applied Co", "Portugal"),                                      # already applied
            J("Software Engineer", "GenericCo", "Anywhere"),                                       # generic title + text hits
        ]
        raw = os.path.join(cls.ws, "search", "scans", "raw-2026-06-15.json")
        json.dump(jobs, open(raw, "w"))
        cls.r = F.run(cls.ws, raw, TODAY)
        cls.keep = {j["company"]: j for j in cls.r["keep"]}
        cls.exc = {j["company"]: j for j in cls.r["excluded"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.ws)

    def reason(self, co):
        return " ".join(self.exc[co]["reasons"])

    def test_good_job_kept_and_deduped(self):
        self.assertIn("GoodCo", self.keep)
        self.assertEqual(sorted(self.keep["GoodCo"]["sources"]), ["Himalayas", "Remotive"])
        self.assertEqual(self.keep["GoodCo"]["pay_monthly"], (5833, 7500))

    def test_location_restricted(self):
        self.assertIn("restricted", self.reason("UsOnly"))
        self.assertIn("restricted", self.reason("TextRestrict"))

    def test_stale_and_repost(self):
        self.assertIn("open 90 days", self.reason("OldCo"))
        self.assertIn("reposted", self.reason("Repost"))

    def test_pay_floor(self):
        self.assertIn("pay max", self.reason("CheapCo"))   # USD 18/h * 160 / 1.1 = EUR 2,618 < 3,500

    def test_talent_pool(self):
        self.assertIn("talent pool", self.reason("Pool"))

    def test_irrelevant_dropped(self):
        allco = set(self.keep) | set(self.exc)
        self.assertNotIn("SalesCo", allco)
        self.assertNotIn("BackCo", allco)

    def test_scam_flags(self):
        flags = " ".join(self.keep[""]["flags"])
        self.assertIn("SCAM CHECK", flags)
        self.assertIn("telegram", flags.lower())
        self.assertIn("gmail", flags)

    def test_excluded_company(self):
        self.assertIn("company excluded", self.reason("Example Bad Corp"))

    def test_already_applied_flag(self):
        self.assertIn("ALREADY APPLIED", " ".join(self.keep["Applied Co"]["flags"]))

    def test_generic_title_with_keywords(self):
        self.assertIn("GenericCo", self.keep)

    def test_ranking(self):
        self.assertEqual(self.r["keep"][0]["company"], "GoodCo")

    def test_workspace_files(self):
        for f in ("CLAUDE.md", "memory.md", "applications.md", "curriculum/profile.md", "search/filters.md",
                  "search/sources.md", "search/scan-log.md", "interview/stories.md", "interview/salary.md", ".gitignore"):
            self.assertTrue(os.path.exists(os.path.join(self.ws, f)), f)
        mem = open(os.path.join(self.ws, "memory.md")).read()
        self.assertIn("EUR 3500/month", mem)
        self.assertNotIn("{{", mem)


if __name__ == "__main__":
    unittest.main()

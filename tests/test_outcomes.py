"""Offline tests for the outcome log, role exclusion and the company job-board source.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
os.environ["JOB_HUNT_OFFLINE"] = "1"
import filter as F  # noqa: E402
import outcomes as O  # noqa: E402
import scan as S  # noqa: E402

TODAY = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
LONG = " We build web apps with React and TypeScript, Next.js, CSS and a design system. " * 10


def J(title, company, loc="Worldwide", days=3):
    return dict(source="Remotive", sid=f"{company}-{title}", title=title, company=company, loc=loc,
                url=f"https://example.com/{company}", text=LONG, posted=(TODAY - dt.timedelta(days=days)).isoformat(), sal=None, extra={})


class OutcomesTest(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="jh-out-")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", self.ws,
                        "--answers", os.path.join(ROOT, "examples", "answers-frontend-portugal.json")], check=True, capture_output=True)
        fm = os.path.join(self.ws, "search", "filters.md")
        md = open(fm).read().replace('"excludedRoles": []', '"excludedRoles": [{"company": "Mixed Co", "title": "Senior Frontend Engineer"}]', 1)
        open(fm, "w").write(md)
        jobs = [J("Senior Frontend Engineer", "Mixed Co"), J("Frontend Developer", "Mixed Co"),
                J("Frontend Engineer", "GoodCo"), J("Frontend Engineer", "UsOnly", "USA")]
        self.raw = os.path.join(self.ws, "search", "scans", "raw-2026-06-15.json")
        json.dump(jobs, open(self.raw, "w"))
        self.r = F.run(self.ws, self.raw, TODAY)

    def tearDown(self):
        shutil.rmtree(self.ws)

    def test_excluded_role_only_that_role(self):
        exc = {(j["company"], j["title"]): j for j in self.r["excluded"]}
        keep = {(j["company"], j["title"]) for j in self.r["keep"]}
        self.assertIn("role excluded", exc[("Mixed Co", "Senior Frontend Engineer")]["reasons"])
        self.assertIn(("Mixed Co", "Frontend Developer"), keep)

    def test_scan_log_codes_and_idempotent(self):
        n = O.log_scan(self.ws, self.r["path"])
        self.assertEqual(n, 4)
        self.assertEqual(O.log_scan(self.ws, self.r["path"]), 0)  # same date, same decisions: nothing new
        rows = {r["job"]: r for r in O.Log(self.ws).load()}
        self.assertEqual(rows["mixed/senior-frontend-engineer"]["reason"], ["role_excluded"])
        self.assertEqual(rows["usonly/frontend-engineer"]["reason"], ["location_restricted"])
        self.assertEqual(rows["goodco/frontend-engineer"]["value"], "keep")
        self.assertEqual(rows["goodco/frontend-engineer"]["date"], "2026-06-15")

    def test_applied_saves_posting_snapshot(self):
        row = O.log_event(self.ws, "GoodCo", "Frontend Engineer", "decision", "applied")
        self.assertTrue(row.get("posting", "").startswith("outcomes/postings/"))
        snap = open(os.path.join(self.ws, row["posting"])).read()
        self.assertIn("React and TypeScript", snap)

    def test_bad_value_rejected(self):
        with self.assertRaises(SystemExit):
            O.log_event(self.ws, "GoodCo", "Frontend Engineer", "stage", "maybe")

    def test_rule_keeps_reply_verbatim(self):
        row = O.log_event(self.ws, "Mixed Co", "Senior Frontend Engineer", "rule", "approved", reply="block only that role")
        self.assertEqual(row["reply"], "block only that role")

    def _fake_history(self, n_high, n_low, high_iv, low_iv):
        rows = []
        for i in range(n_high + n_low):
            jid, high = f"co{i}/role", i < n_high
            rows.append({"date": "2026-06-01", "event": "filter", "job": jid, "value": "keep", "reason": [], "features": {"fit": 10 if high else 2}})
            rows.append({"date": "2026-06-02", "event": "stage", "job": jid, "value": "submitted"})
            got = (i < high_iv) if high else (i - n_high < low_iv)
            rows.append({"date": "2026-06-09", "event": "stage", "job": jid, "value": "interview" if got else "rejected"})
            if got:
                rows.append({"date": "2026-06-20", "event": "stage", "job": jid, "value": "rejected"})
        O.Log(self.ws).append(rows)

    def test_calibrate_insufficient_with_few_outcomes(self):
        self._fake_history(3, 3, 2, 1)
        self.assertIn("insufficient", O.calibrate(self.ws))

    def test_calibrate_separating(self):
        self._fake_history(6, 6, 4, 1)
        out = O.calibrate(self.ws)
        self.assertIn("separating", out)
        self.assertIn("4/6", out)

    def test_stats_funnel(self):
        self._fake_history(3, 3, 2, 1)
        self.assertIn("submitted 6 → screening 3 → interview 3", O.stats(self.ws))


class AtsTest(unittest.TestCase):
    def test_ashby_hybrid_not_remote_and_title_filter(self):
        fake = {"jobs": [
            {"id": "1", "title": "Senior Frontend Engineer", "isRemote": True, "workplaceType": "Hybrid", "location": "London",
             "jobUrl": "https://jobs.ashbyhq.com/x/1", "descriptionPlain": "React", "publishedAt": "2026-06-10T00:00:00Z"},
            {"id": "2", "title": "Frontend Engineer", "isRemote": True, "location": "Remote", "jobUrl": "u2", "descriptionPlain": "React"},
            {"id": "3", "title": "Account Executive", "isRemote": True, "location": "Remote", "jobUrl": "u3", "descriptionPlain": ""}]}
        old = S.getj
        S.getj = lambda url, **kw: fake
        try:
            jobs = S.ats_board("ashby", "x", S.re.compile("frontend", S.re.I))
        finally:
            S.getj = old
        self.assertEqual([j["title"] for j in jobs], ["Senior Frontend Engineer", "Frontend Engineer"])
        self.assertTrue(jobs[0]["loc"].startswith("Hybrid"))
        self.assertTrue(jobs[1]["loc"].startswith("Remote"))

    def test_lever_dates_and_salary(self):
        fake = [{"id": "a", "text": "Frontend Engineer", "workplaceType": "remote", "categories": {"location": "Brazil"},
                 "hostedUrl": "h", "descriptionPlain": "React", "createdAt": 1781000000000,
                 "salaryRange": {"min": 5000, "max": 7000, "currency": "USD", "interval": "per-month-salary"}}]
        old = S.getj
        S.getj = lambda url, **kw: fake
        try:
            j = S.ats_board("lever", "y", S.re.compile("frontend", S.re.I))[0]
        finally:
            S.getj = old
        self.assertEqual(j["sal"]["max"], 7000)
        self.assertTrue(j["posted"].startswith("2026-06"))
        self.assertIn("Brazil", j["loc"])


if __name__ == "__main__":
    unittest.main()

"""Regression tests for the v0.2.2 review: wrong results, unsafe fetches, privacy and first-run fixes.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, io, json, os, shutil, stat, subprocess, sys, tempfile, unittest, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
os.environ["JOB_HUNT_OFFLINE"] = "1"
import ats_check as A  # noqa: E402
import eligibility as E  # noqa: E402
import filter as F  # noqa: E402
import insights as I  # noqa: E402
import offers as OF  # noqa: E402
import outcomes as O  # noqa: E402
import scan as S  # noqa: E402

TODAY = dt.datetime(2026, 6, 15, tzinfo=dt.timezone.utc)
EXAMPLE = os.path.join(ROOT, "examples", "answers-frontend-portugal.json")
TXT = " Build the UI with React, TypeScript, Next.js and CSS for our product." * 6


def init(answers=EXAMPLE):
    ws = os.path.join(tempfile.mkdtemp(prefix="jh-hd-"), "ws")
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", ws, "--answers", answers],
                       capture_output=True, text=True)
    return ws, r


def J(company, loc, text=TXT, title="Senior Frontend Engineer"):
    return dict(source="Himalayas", sid=company, title=title, company=company, loc=loc, url=f"https://example.com/{company}",
                text=text, posted=(TODAY - dt.timedelta(days=3)).isoformat(), sal=None, extra={})


class Salary(unittest.TestCase):
    def test_amounts_and_period(self):
        cases = {"€50-60k per year": ([50000, 60000], "year"), "€4.000–5.000 per month": ([4000, 5000], "month"),
                 "€60.000–70.000 per year": ([60000, 70000], "year"), "$120,000 - $150,000": ([120000, 150000], ""),
                 "R$ 18.000,00 / mês": ([18000], "month"), "€4.5k/month": ([4500], "month"), "€500/day": ([500], "day")}
        for txt, (vals, per) in cases.items():
            with self.subTest(txt=txt):
                self.assertEqual(F.amounts(txt), vals)
                self.assertEqual(F.period(txt), per)


class Location(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ws, r = init()
        assert r.returncode == 0, r.stderr
        raw = os.path.join(cls.ws, "search", "scans", "raw-2026-06-15.json")
        jobs = [J("BareRemote", "Remote"), J("FullyRemote", "100% Remote"), J("UsOnly", "Remote - USA"),
                J("TzCo", "", TXT + " You must be located in a time zone with 4 hours overlap with CET."),
                J("UsText", "", TXT + " Candidates must be located in the United States.")]
        with open(raw, "w") as f:
            json.dump(jobs, f)
        r = F.run(cls.ws, raw, TODAY)
        cls.keep = {j["company"]: j for j in r["keep"]}
        cls.exc = {j["company"]: j for j in r["excluded"]}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(os.path.dirname(cls.ws))

    def test_bare_remote_is_unstated_not_restricted(self):
        for co in ("BareRemote", "FullyRemote"):
            self.assertIn(co, self.keep, self.exc.get(co, {}).get("reasons"))
            self.assertIn("location not stated: verify eligibility", self.keep[co]["flags"])

    def test_named_country_still_excluded(self):
        self.assertIn("UsOnly", self.exc)
        self.assertIn("UsText", self.exc)

    def test_condition_without_a_country_is_a_flag(self):
        self.assertIn("TzCo", self.keep)
        self.assertTrue(any(f.startswith("location condition") for f in self.keep["TzCo"]["flags"]))


class Eligibility(unittest.TestCase):
    def test_pronoun_us_is_not_the_usa(self):
        self.assertEqual(E.countries("a time zone that works for us"), [])
        self.assertEqual(E.countries("based in the US"), ["US"])
        self.assertEqual(E.countries("Remote, USA"), ["US"])

    def test_bad_timezone_does_not_crash(self):
        job = {"text": "Overlap with EST core hours required.", "loc": ""}
        err = io.StringIO()
        old, sys.stderr = sys.stderr, err
        try:
            self.assertEqual(E.tz_overlap(job, {"timezone": "BRT"}), (None, None))
        finally:
            sys.stderr = old
        self.assertIn("IANA", err.getvalue())


class AtsSections(unittest.TestCase):
    def test_bonus_in_a_sentence_is_not_a_heading(self):
        need, nice = A.split_posting("We offer a competitive salary and bonus. Requirements:\n- Python\n- Docker\n")
        self.assertEqual(nice, "")
        self.assertIn("Docker", need)

    def test_real_headings_split(self):
        need, nice = A.split_posting("Requirements:\n- Python\nNice to have:\n- Go\n")
        self.assertIn("Go", nice)
        self.assertNotIn("Go", need)
        self.assertIn("Go", A.split_posting("Requirements: Python. Preferred qualifications: Go")[1])


class Companies(unittest.TestCase):
    def test_same_company(self):
        self.assertTrue(F.same_company("Acme", "Acme Corp"))
        self.assertTrue(F.same_company("Able", "Able Inc."))
        self.assertFalse(F.same_company("The Foo Co", "The Bar Co"))
        self.assertFalse(F.same_company("Acme", "Acmeworks"))


class Offers(unittest.TestCase):
    CFG = {"pay": {"hoursPerMonth": 160}}

    def test_periods(self):
        self.assertEqual(OF.monthly_gross({"amount": 500, "per": "day"}, self.CFG)[0], 500 * 20)
        self.assertAlmostEqual(OF.monthly_gross({"amount": 1000, "per": "week"}, self.CFG)[0], 4330)
        with self.assertRaises(SystemExit):
            OF.monthly_gross({"name": "x", "amount": 1, "per": "fortnight"}, self.CFG)


class OutcomeLog(unittest.TestCase):
    def setUp(self):
        self.ws, r = init()
        assert r.returncode == 0, r.stderr

    def tearDown(self):
        shutil.rmtree(os.path.dirname(self.ws))

    def test_followed_up_silences_due_for_a_week(self):
        d = lambda n: str(TODAY.date() - dt.timedelta(days=n))  # noqa: E731
        O.log_event(self.ws, "Acme", "Dev", "stage", "submitted", date=d(8))
        self.assertEqual(I.due(self.ws, TODAY.date())["follow_up"], [("Acme", 8)])
        O.log_event(self.ws, "Acme", "Dev", "stage", "followed_up", date=d(2))
        self.assertEqual(I.due(self.ws, TODAY.date())["follow_up"], [])

    def test_bad_data_json_is_a_clean_error(self):
        with self.assertRaises(SystemExit) as c:
            O.log_event(self.ws, "Acme", "Dev", "stage", "submitted", data="{channel: x}")
        self.assertIn("JSON", str(c.exception))

    def test_redact_removes_old_backups(self):
        O.log_event(self.ws, "Acme", "Dev", "stage", "submitted", note="talked to Ana Souza")
        old = O.Log(self.ws).path + ".bak"
        shutil.copy(O.Log(self.ws).path, old)
        O.redact(self.ws, ["Ana Souza"])
        self.assertFalse(os.path.exists(old))


class Fetching(unittest.TestCase):
    def test_safe_url(self):
        self.assertEqual(S.safe_url("javascript:alert(1)"), "")
        self.assertEqual(S.safe_url("file:///etc/passwd"), "")
        self.assertEqual(S.safe_url("https://a.com/x‮"), "https://a.com/x")

    def test_private_hosts_refused(self):
        for u in ("http://localhost:8080/", "http://127.0.0.1/", "http://169.254.169.254/latest", "http://10.0.0.1/", "ftp://example.com/"):
            self.assertEqual(S.fetch_public(u)[0], 0, u)

    def test_redirect_to_private_host_refused(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "\n__META__302 http://127.0.0.1/admin", "")

        old_run, old_ip = S.subprocess.run, S.public_ip
        S.subprocess.run, S.public_ip = fake_run, lambda h: None if h in ("127.0.0.1", "localhost") else "93.184.215.14"
        try:
            self.assertEqual(S.fetch_public("https://example.com/job")[0], 0)
        finally:
            S.subprocess.run, S.public_ip = old_run, old_ip
        self.assertEqual(len(calls), 1)  # the private hop was never requested
        self.assertIn("example.com:443:93.184.215.14", calls[0])  # pinned to the checked address

    def test_api_key_never_follows_a_redirect(self):
        h = S.NoRedirect()
        with self.assertRaises(urllib.error.HTTPError) as c:
            h.redirect_request(urllib.request.Request("https://www.remoterocketship.com/x"), io.BytesIO(), 302, "Found", {}, "http://evil.example/")
        c.exception.close()

    def test_unknown_source_name_fails(self):
        ws, r = init()
        try:
            r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "scan.py"), "--workspace", ws, "--only", "remotiv"],
                               capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("unknown source", r.stderr)
        finally:
            shutil.rmtree(os.path.dirname(ws))


class FirstRun(unittest.TestCase):
    def test_private_workspace_with_real_skill_path(self):
        ws, r = init()
        try:
            self.assertEqual(stat.S_IMODE(os.stat(ws).st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(os.stat(os.path.join(ws, "applications.md")).st_mode) & 0o077, 0)
            with open(os.path.join(ws, "CLAUDE.md")) as f:
                md = f.read()
            self.assertIn(os.path.join(ROOT, "skill", "job-hunt"), md)
            self.assertNotIn("SKILL_DIR", md)
        finally:
            shutil.rmtree(os.path.dirname(ws))

    def test_bad_timezone_rejected(self):
        with open(EXAMPLE) as f:
            a = json.load(f)
        a["timezone"] = "Lisbon"
        p = os.path.join(tempfile.mkdtemp(prefix="jh-ans-"), "answers.json")
        with open(p, "w") as f:
            json.dump(a, f)
        ws, r = init(p)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("IANA", r.stderr)
        self.assertFalse(os.path.exists(ws))
        shutil.rmtree(os.path.dirname(p))


class RenderPdf(unittest.TestCase):
    def test_remote_resources_refused(self):
        d = tempfile.mkdtemp(prefix="jh-pdf-")
        try:
            for bad in ('<img src="https://evil.example/x.png">', "<style>@import url(//evil.example/a.css)</style>",
                        '<link rel="stylesheet" href="http://evil.example/a.css">'):
                with open(os.path.join(d, "cv.html"), "w") as f:
                    f.write(bad)
                r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "render_pdf.py"), "--html", os.path.join(d, "cv.html"),
                                    "--workspace", os.path.join(d, "ws"), "--company", "Acme"], capture_output=True, text=True)
                self.assertNotEqual(r.returncode, 0, bad)
                self.assertIn("remote resource", r.stderr)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()

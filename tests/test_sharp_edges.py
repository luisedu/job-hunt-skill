"""Regression tests for the sharp-edges review (Trail of Bits skill) and the source-terms changes.
Run: python3 -m unittest discover -s tests -v
"""
import io, json, os, shutil, subprocess, sys, tempfile, unittest
from contextlib import redirect_stderr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
import filter as F  # noqa: E402
import outcomes as O  # noqa: E402
import scan as S  # noqa: E402
import verify_company as V  # noqa: E402

EX = os.path.join(ROOT, "examples", "answers-frontend-portugal.json")


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="jh-se-")

    def tearDown(self):
        shutil.rmtree(self.d)


class CompanyCheck(unittest.TestCase):
    def test_unknown_ats_host_never_stands_in_for_the_employer(self):        # 1
        self.assertEqual(V.job_domain("Acme", {"urls": ["https://applytojob.com/acme/1", "https://jobs.gem.com/acme"]}), (None, None))
        self.assertEqual(V.job_domain("Acme", {"urls": ["https://careers.acme.com/1"]})[0], "careers.acme.com")

    def test_no_local_network_hosts(self):                                   # 12
        for u in ("https://x@127.0.0.1:8080/", "http://localhost/acme", "https://acme.local/", "http://[::1]/"):
            self.assertEqual(V.job_domain("Acme", {"urls": [u]}), (None, None), u)


class InitForce(Tmp):
    def test_force_backs_up_user_files(self):                                # 2
        ws = os.path.join(self.d, "ws")
        run = lambda *x: subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", ws, "--answers", EX, *x],
                                        check=True, capture_output=True, text=True)
        run()
        with open(os.path.join(ws, "applications.md"), "a") as f:
            f.write("| 2026-06-01 | Real Co | Engineer | link | submitted | 2026-06-01 | - | - |\n")
        out = run("--force").stdout
        self.assertIn("backed up", out)
        baks = [f for f in os.listdir(ws) if f.startswith("applications.md.bak-")]
        self.assertEqual(len(baks), 1)
        with open(os.path.join(ws, baks[0])) as f:
            self.assertIn("Real Co", f.read())

    def test_gitignore_enforced_in_existing_repo(self):                      # 9
        ws = os.path.join(self.d, "ws2")
        os.makedirs(ws)
        with open(os.path.join(ws, ".gitignore"), "w") as f:
            f.write("node_modules/\n")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", ws, "--answers", EX], check=True, capture_output=True)
        with open(os.path.join(ws, ".gitignore")) as f:
            lines = [x.strip() for x in f]
        self.assertIn("node_modules/", lines)
        self.assertIn("*", lines)


class Outcomes(Tmp):
    def test_redact_values_only_with_backup(self):                           # 4
        O.Log(self.d).append([{"date": "2026-06-01", "event": "stage", "job": "a/b", "value": "interview", "note": "call with Ana Souza"}])
        os.makedirs(os.path.join(self.d, "outcomes", "postings"), exist_ok=True)
        with open(os.path.join(self.d, "outcomes", "postings", "a__b.md"), "w") as f:
            f.write("Contact Ana Souza")
        with self.assertRaises(SystemExit):
            O.redact(self.d, ["ev"])                                          # too short: would hit keys/codes
        self.assertEqual(O.redact(self.d, ["Ana Souza"]), 1)
        row = O.Log(self.d).load()[0]
        self.assertEqual(set(row), {"v", "date", "event", "job", "value", "note"})   # keys intact
        self.assertIn("[redacted]", row["note"])
        self.assertFalse(os.path.exists(O.Log(self.d).path + ".bak"))  # a backup would keep the erased name
        with open(os.path.join(self.d, "outcomes", "postings", "a__b.md")) as f:
            self.assertNotIn("Ana", f.read())

    def test_export_drops_free_text(self):                                   # 5
        O.Log(self.d).append([{"date": "2026-06-01", "event": "decision", "job": "a/b", "value": "skipped",
                               "reason": ["low_fit", "referral from João Silva"], "data": {"channel": "panel with Jane (CTO)", "format": "video-call"}}])
        out = json.dumps(O.export_anonymised(self.d), ensure_ascii=False)
        self.assertNotIn("João", out)
        self.assertNotIn("Jane", out)
        self.assertIn("low_fit", out)
        self.assertIn("video-call", out)


class FilterEdges(Tmp):
    def test_fx_fallback_warns(self):                                        # 6
        old = os.environ.pop("JOB_HUNT_OFFLINE", None)
        old_run = F.subprocess.run
        F.subprocess.run = lambda *a, **k: type("R", (), {"stdout": "not json"})()
        err = io.StringIO()
        try:
            with redirect_stderr(err):
                F.fx_table({"profile": {"currency": "EUR"}, "fallbackFxPerCurrency": {}})
        finally:
            F.subprocess.run = old_run
            if old is not None:
                os.environ["JOB_HUNT_OFFLINE"] = old
        self.assertIn("live exchange rates unavailable", err.getvalue())

    def test_invalid_fit_regex_matches_literally(self):                      # 10
        self.assertTrue(F.safe_search("c++", "we use C++ daily"))
        self.assertTrue(F.safe_search(r"vis[ãa]o", "visão computacional"))

    def test_results_never_overwrite_input(self):                            # 7
        ws = os.path.join(self.d, "ws")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", ws, "--answers", EX], check=True, capture_output=True)
        raw = os.path.join(ws, "search", "scans", "mydata.json")
        with open(raw, "w") as f:
            json.dump([], f)
        r = F.run(ws, raw)
        self.assertNotEqual(os.path.abspath(r["path"]), os.path.abspath(raw))
        with open(raw) as f:
            self.assertEqual(json.load(f), [])


class ScanEdges(Tmp):
    def test_control_characters_stripped(self):                              # 11
        self.assertEqual(S.strip("Senior\x1b]8;;http://evil\x07 Engineer‮"), "Senior ]8;;http://evil Engineer")

    def test_gupy_warns_about_terms(self):                                   # terms L1
        err = io.StringIO()
        old = S.get
        S.get = lambda *a, **k: ""
        try:
            with redirect_stderr(err):
                S.src_gupy({"gupyTerms": ["x"], "queries": ["x"]})
        finally:
            S.get = old
        self.assertIn("terms of use", err.getvalue())


if __name__ == "__main__":
    unittest.main()

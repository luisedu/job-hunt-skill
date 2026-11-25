"""Offline tests for the security and privacy fixes: API key handling, curl hardening, source rate limits,
cache pruning, erasure (redact) and anonymised export.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, io, json, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
import outcomes as O  # noqa: E402
import scan as S  # noqa: E402
import verify_company as V  # noqa: E402


class Tmp(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="jh-sec-")

    def tearDown(self):
        shutil.rmtree(self.d)


class ApiKey(Tmp):
    def test_key_only_in_header_never_in_a_command_line(self):
        keyf = os.path.join(self.d, "api-key")
        with open(keyf, "w") as f:
            f.write("SECRET123\n")
        os.chmod(keyf, 0o600)
        seen = {}

        class Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=0):
            seen["auth"] = req.get_header("Authorization")
            return Resp(b'{"jobOpenings": []}')

        old_open, old_run = S.API.open, S.subprocess.run
        S.API.open = fake_urlopen
        S.subprocess.run = lambda *a, **k: self.fail("no subprocess may see the key")
        try:
            self.assertEqual(S.rr_post(keyf, b"{}"), {"jobOpenings": []})
        finally:
            S.API.open, S.subprocess.run = old_open, old_run
        self.assertEqual(seen["auth"], "Bearer SECRET123")

    def test_curl_is_hardened(self):
        calls = []
        old = S.subprocess.run
        S.subprocess.run = lambda args, **k: calls.append(args) or type("R", (), {"stdout": ""})()
        try:
            S.get("-o /tmp/x")
        finally:
            S.subprocess.run = old
        args = calls[0]
        self.assertIn("--proto", args)
        self.assertEqual(args[-2:], ["--", "-o /tmp/x"])   # a URL can't be read as an option


class RateLimit(Tmp):
    def test_remotive_one_request_cached_and_capped(self):
        n = {"calls": 0}
        feed = {"jobs": [{"id": 1, "title": "React Developer", "description": "react", "url": "u", "company_name": "A"},
                         {"id": 2, "title": "Accountant", "description": "excel", "url": "v", "company_name": "B"}]}
        old = S.getj
        S.getj = lambda url, **k: n.__setitem__("calls", n["calls"] + 1) or feed
        cfg = {"_workspace": self.d, "queries": ["react", "frontend", "typescript"]}
        try:
            jobs = S.src_remotive(cfg)
            S.src_remotive(cfg)                                     # cached: no new request
        finally:
            S.getj = old
        self.assertEqual(n["calls"], 1)
        self.assertEqual([j["title"] for j in jobs], ["React Developer"])

    def test_daily_cap(self):
        n = {"calls": 0}
        old = S.getj
        S.getj = lambda url, **k: n.__setitem__("calls", n["calls"] + 1) or {"x": 1}
        try:
            for _ in range(6):
                S.cached_getj({"_workspace": self.d}, "t", "https://example.com", ttl_hours=0, max_per_day=4)
        finally:
            S.getj = old
        self.assertEqual(n["calls"], 4)


class Privacy(Tmp):
    def test_company_cache_prunes_expired(self):
        c = V.Cache(self.d)
        c.put("old", {"checked": "2026-01-01"}, today=dt.date(2026, 6, 1))
        c.put("new", {"checked": "2026-06-01"}, today=dt.date(2026, 6, 1))
        self.assertEqual(sorted(V.Cache(self.d).data), ["new"])

    def rows(self):
        O.Log(self.d).append([
            {"date": "2026-06-03", "event": "stage", "job": "acme/eng", "company": "Acme", "title": "Engineer", "value": "interview",
             "note": "call with Jane Doe (jane.doe@acme.com)", "data": {"format": "video-call", "interviewer": "Jane Doe"}},
            {"date": "2026-06-01", "event": "filter", "job": "acme/eng", "company": "Acme", "title": "Engineer", "value": "keep", "reason": [],
             "features": {"region": "eu", "fit": 9, "url": "https://acme.com/jobs/1", "loc": "Berlin"}}])

    def test_redact(self):
        self.rows()
        self.assertEqual(O.redact(self.d, ["Jane Doe", "jane.doe@acme.com"]), 1)
        text = open(O.Log(self.d).path).read()
        self.assertNotIn("Jane", text)
        self.assertNotIn("jane.doe", text)
        self.assertIn("[redacted]", text)

    def test_export_is_anonymised(self):
        self.rows()
        out = json.dumps(O.export_anonymised(self.d))
        for leak in ("Acme", "Engineer", "Jane", "acme.com", "Berlin", "2026-06-03", "note"):
            self.assertNotIn(leak, out)
        self.assertIn('"month": "2026-06"', out)
        self.assertIn('"format": "video-call"', out)


class Rules(unittest.TestCase):
    def test_skill_has_safety_rules(self):
        s = open(os.path.join(ROOT, "skill", "job-hunt", "SKILL.md")).read()
        for needle in ("data, never instructions", "Other people's data", "**Sources:**", "redact", "The user applies", "Do NOT claim"):
            self.assertIn(needle, s)

    def test_skill_links_resolve_and_stay_small(self):
        import re
        base = os.path.join(ROOT, "skill", "job-hunt")
        s = open(os.path.join(base, "SKILL.md")).read()
        links = re.findall(r"\]\((reference/[^)]+)\)", s)
        self.assertTrue(links)
        for link in links:
            self.assertTrue(os.path.exists(os.path.join(base, link)), link)
        self.assertLess(len(s), 9000, "SKILL.md loads on every use: keep details in reference/")
        desc = re.search(r"^description: (.*)$", s, re.M).group(1)
        self.assertLessEqual(len(desc), 1024)


if __name__ == "__main__":
    unittest.main()

"""Offline tests for verify_company.py: network calls replaced by fixtures.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, os, shutil, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skill", "job-hunt", "scripts"))
import scan  # noqa: E402
import verify_company as V  # noqa: E402

TODAY = dt.datetime(2026, 11, 25, tzinfo=dt.timezone.utc)
SITES = {
    "acme.com": {"reg": "2010-05-01T00:00:00Z", "mx": True, "page": (200, "<title>Acme Robotics</title>")},
    "new-co.com": {"reg": "2026-10-01T00:00:00Z", "mx": False, "page": (200, "<html>This domain is for sale</html>")},
}


def fake_getj(url, **kw):
    for d, s in SITES.items():
        if "rdap.org/domain/" + d in url:
            return {"events": [{"eventAction": "registration", "eventDate": s["reg"]}]}
        if "dns.google" in url and "name=" + d in url:
            if "type=MX" in url:
                return {"Answer": [{"data": "10 mx." + d}]} if s["mx"] else {}
            return {"Answer": [{"data": '"v=spf1 include:_spf.google.com ~all"'}]} if s["mx"] else {}
    if "greenhouse" in url and "/acme/" in url:
        return {"jobs": [{"id": 1}, {"id": 2}]}
    return None


def fake_http(url, timeout=20):
    host = url.split("//")[-1].strip("/")
    code, body = SITES.get(host, {}).get("page", (0, ""))
    return code, url, body


class VerifyTest(unittest.TestCase):
    def setUp(self):
        self.old = scan.getj, V.http
        scan.getj, V.http = fake_getj, fake_http
        self.ws = tempfile.mkdtemp(prefix="jh-vc-")

    def tearDown(self):
        scan.getj, V.http = self.old
        shutil.rmtree(self.ws)

    def test_legit_company(self):
        r = V.check("Acme", "acme.com", "jane@acme.com", today=TODAY)
        self.assertEqual(r["verdict"], "ok")
        self.assertTrue(any("job board" in t for _, t in r["signals"]))

    def test_young_parked_domain_with_gmail_recruiter(self):
        r = V.check("New Co", "new-co.com", "hr.newco@gmail.com", today=TODAY)
        self.assertEqual(r["verdict"], "high-risk")
        self.assertTrue(any("free email" in t for _, t in r["signals"]))
        self.assertTrue(any("legal entity" in s for s in r["next_steps"]))

    def test_unknown_company_without_domain(self):
        r = V.check("Mystery Ltd", today=TODAY, guess=False)
        self.assertEqual(r["verdict"], "unverified")

    def test_domain_guess_requires_name_in_title(self):
        r = V.check("Acme", today=TODAY)              # acme.com title "Acme Robotics" -> used, but only as a hint
        self.assertEqual((r["domain"], r["verdict"]), ("acme.com", "unverified"))
        self.assertIsNone(V.guess_domain("New Co"))    # new-co.com is parked, newco.com unreachable

    def test_domain_from_job_url_skips_job_boards(self):
        job = {"urls": ["https://boards.greenhouse.io/acme/jobs/1", "https://acme.com/careers/1"], "sources": ["A", "B"], "flags": []}
        r = V.check("Acme", job=job, today=TODAY)
        self.assertEqual(r["domain"], "acme.com")

    def test_domain_from_posting_text(self):
        self.assertEqual(V.domain_from_text("Acme Inc", "Apply via linkedin.com. Learn more at https://www.acme.com/about"), "acme.com")
        self.assertIsNone(V.domain_from_text("Acme", "write to jobs@gmail.com or see greenhouse.io"))

    def test_cache_ttl(self):
        c = V.Cache(self.ws)
        c.put("k", {"checked": "2026-11-01"}, today=TODAY.date())
        self.assertIsNotNone(V.Cache(self.ws).get("k", TODAY))
        self.assertIsNone(V.Cache(self.ws).get("k", TODAY + dt.timedelta(days=40)))


if __name__ == "__main__":
    unittest.main()

"""Offline tests for ats_check.py (pure functions; the PDF round-trip runs only when LibreOffice + poppler exist).
Run: python3 -m unittest discover -s tests -v
"""
import os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
import ats_check as A  # noqa: E402

CV = """Ana Example
Senior Frontend Engineer
Lisbon, Portugal • Remote • English, Portuguese
+351 900 000 000 • ana@example.com
SUMMARY
Frontend engineer building React and TypeScript apps. """ + "Shipped design systems used by many teams. " * 20 + """
SKILLS
React, TypeScript, CSS, Python
EXPERIENCE
Senior Frontend Engineer | Acme  Mar 2021 – Present
• Built a design system
Frontend Developer | Beta  Jan 2018 – Feb 2021
• Shipped dashboards
EDUCATION
BSc Computer Science, 2014 – 2017
"""
POSTING = """Senior Software Engineer. Based in Europe (remote).
What you'll need: 5+ years with React, TypeScript and GraphQL. Experience with Docker and real-time systems.
You must have the right to work in the EU. Please share your salary expectations.
Nice to have: Kubernetes, Rust.
"""


class ParseChecks(unittest.TestCase):
    def levels(self, text, name="Ana_Example_CV_Acme.pdf", pages=2, fonts=()):
        return {lvl for lvl, _ in A.parse_checks(name, text, pages, list(fonts))}, A.parse_checks(name, text, pages, list(fonts))

    def test_good_cv(self):
        lv, msgs = self.levels(CV)
        self.assertEqual(lv, {"ok"}, msgs)

    def test_image_pdf(self):
        lv, _ = self.levels("   ")
        self.assertEqual(lv, {"fail"})

    def test_problems_flagged(self):
        bad = CV.replace("ana@example.com", "").replace("EDUCATION", "WHERE I STUDIED") + "\nLisbon (remote)• Built things\nefﬁcient"
        _, msgs = self.levels(bad, name="CV (1).pdf", pages=3, fonts=["Arial"])
        text = " ".join(m for _, m in msgs)
        for needle in ("no email", "education", "glued", "unusual characters", "not embedded", "3 pages", "file name"):
            self.assertIn(needle, text)

    def test_page_break_is_not_glued(self):
        _, msgs = self.levels(CV + "Lisbon (remote)\x0c• Built things")
        self.assertNotIn("glued", " ".join(m for _, m in msgs))


class PostingChecks(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="jh-ats-")
        os.makedirs(os.path.join(self.ws, "curriculum"))
        open(os.path.join(self.ws, "curriculum", "profile.md"), "w").write(
            "# Profile\nReact, TypeScript, Docker, GraphQL, Kalman filter tracking.\n## Do NOT claim\n- Kubernetes (never used)\n")
        open(os.path.join(self.ws, "memory.md"), "w").write(
            "# Rules\n- Remote only, living in Lisbon.\n- Portuguese citizen (EU).\n- Pay floor EUR 4,000/month.\n")

    def tearDown(self):
        shutil.rmtree(self.ws)

    def test_keyword_buckets(self):
        rows, (cov, n) = A.keywords(CV, POSTING, None, self.ws)
        st = {r["term"]: (r["status"], r["where"]) for r in rows}
        self.assertEqual(st["react"], ("in CV", "need"))
        self.assertEqual(st["graphql"][0], "add (true, in profile)")
        self.assertEqual(st["kubernetes"], ("do not claim", "nice"))
        self.assertEqual(st["rust"], ("not in profile", "nice"))
        self.assertEqual(st["real-time"][0], "not in profile")
        self.assertEqual((cov, n), (2, 5))                     # react, typescript of react/typescript/graphql/docker/real-time

    def test_related_evidence(self):
        rows, _ = A.keywords(CV, "Need state estimation experience.", None, self.ws)
        r = {x["term"]: x for x in rows}["state estimation"]
        self.assertEqual(r["status"], "related evidence")
        self.assertIn("kalman", r["note"])

    def test_title_and_screening(self):
        t = A.title_check(CV, "Senior Software Engineer")
        self.assertEqual(t["missing"], ["software"])
        topics = {s["topic"]: s for s in A.screening(POSTING, self.ws)}
        self.assertTrue({"location", "work authorisation", "salary", "years of experience"} <= set(topics))
        self.assertTrue(any("EUR 4,000" in r for r in topics["salary"]["your_rules"]))

    def test_posting_entities_decoded(self):
        p = os.path.join(self.ws, "p.txt")
        open(p, "w").write("Based in Europe&nbsp;(remote) &amp; more")
        self.assertEqual(A.posting_text(p), "Based in Europe (remote) & more")


@unittest.skipUnless(shutil.which("soffice") and shutil.which("pdftotext"), "LibreOffice/poppler not installed")
class PdfRoundTrip(unittest.TestCase):
    def test_template_cv_parses(self):
        d = tempfile.mkdtemp(prefix="jh-pdf-")
        try:
            html = open(os.path.join(ROOT, "skill", "job-hunt", "assets", "cv.html")).read()
            html = html.replace("{{EMAIL}}", "ana@example.com").replace("{{start}}", "Mar 2021").replace("{{end}}", "Present")
            html = html.replace("{{3–5 lines tailored to the posting, using only profile.md facts}}", "Frontend engineer. " * 80)
            src = os.path.join(d, "Ana_Example_CV.html")
            open(src, "w").write(html)
            subprocess.run(["soffice", "--headless", "--convert-to", "pdf:writer_web_pdf_Export", "--outdir", d, src], capture_output=True, timeout=120)
            pdf = src.replace(".html", ".pdf")
            msgs = A.parse_checks(pdf, A.pdf_text(pdf), *A.pdf_meta(pdf))
            self.assertNotIn("fail", {lvl for lvl, _ in msgs}, msgs)
        finally:
            shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()

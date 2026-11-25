"""Offline tests for insights.py (employers, companies, skills, weekly) and offers.py.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "job-hunt", "scripts")
sys.path.insert(0, SCRIPTS)
os.environ["JOB_HUNT_OFFLINE"] = "1"
import config  # noqa: E402
import insights as I  # noqa: E402
import netpay as N  # noqa: E402
import offers as OF  # noqa: E402
from outcomes import Log  # noqa: E402

TODAY = dt.date(2026, 6, 30)


def R(company, title, elig="eligible", status="keep", reasons=(), text="Remote role with Python and PyTorch.", pay=None):
    return {"company": company, "title": title, "eligibility": elig, "status": status, "reasons": list(reasons), "text": text,
            "sources": ["Himalayas"], "pay_monthly": pay, "loc": "LATAM"}


class Base(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp(prefix="jh-ins-")
        subprocess.run([sys.executable, os.path.join(SCRIPTS, "init_workspace.py"), "--workspace", self.ws,
                        "--answers", os.path.join(ROOT, "examples", "answers-frontend-portugal.json")], check=True, capture_output=True)
        self.cfg = config.load_config(self.ws)

    def tearDown(self):
        shutil.rmtree(self.ws)

    def results(self, date, jobs):
        with open(os.path.join(self.ws, "search", "scans", f"results-{date}.json"), "w") as f:
            json.dump({"keep": [j for j in jobs if j["status"] == "keep"], "excluded": [j for j in jobs if j["status"] != "keep"]}, f)


class Employers(Base):
    def test_ranking_and_exclusions(self):
        self.results("2026-06-20", [R("Acme", "Vision Engineer"), R("Beta", "ML Engineer"), R("Gamma", "CV Engineer", "no", "excluded", ["restricted to us"])])
        self.results("2026-06-27", [R("Acme", "Perception Engineer"), R("Delta", "CV Engineer", status="excluded", reasons=["onsite"]),
                                    R("Beta", "ML Engineer")])  # same job again: counted once
        rows = I.employers(self.ws, self.cfg, 90, TODAY)
        self.assertEqual([(r["company"], r["eligible"]) for r in rows], [("Acme", 2), ("Beta", 1)])
        self.assertEqual(rows[0]["first"], "2026-06-20")

    def test_add_ats_keeps_other_keys(self):
        boards = I.add_ats(self.ws, [{"kind": "ashby", "slug": "acme"}])
        self.assertEqual(boards["ashby"], ["acme"])
        cfg = config.load_config(self.ws)
        self.assertEqual(cfg["atsBoards"]["ashby"], ["acme"])
        self.assertEqual(cfg["pay"]["floorMonthly"], self.cfg["pay"]["floorMonthly"])


class Companies(Base):
    def test_track_record(self):
        Log(self.ws).append([
            {"date": "2026-06-01", "event": "stage", "job": "acme/vision-engineer", "company": "Acme", "value": "submitted", "data": {"channel": "ashby"}},
            {"date": "2026-06-07", "event": "stage", "job": "acme/vision-engineer", "company": "Acme", "value": "screening"},
            {"date": "2026-06-10", "event": "stage", "job": "acme/vision-engineer", "company": "Acme", "value": "interview", "data": {"format": "ai-audio", "vendor": "botco"}},
            {"date": "2026-06-02", "event": "stage", "job": "beta/ml-engineer", "company": "Beta", "value": "submitted"},
            {"date": "2026-06-28", "event": "stage", "job": "beta/ml-engineer", "company": "Beta", "value": "ghosted"},
            {"date": "2026-06-05", "event": "filter", "job": "gamma/cv", "company": "Gamma", "value": "excluded", "reason": ["repost"]},
        ])
        rows = {r["company"]: r for r in I.companies(self.ws)}
        self.assertEqual(rows["Acme"]["median_days_to_reply"], 6)
        self.assertEqual(rows["Acme"]["formats"], {"ai-audio (botco)": 1})
        self.assertIn("n too small", rows["Acme"]["reply_rate"])
        self.assertEqual(rows["Beta"]["ghosted"], 1)
        self.assertNotIn("Gamma", rows)                                           # never applied: hidden by default
        self.assertEqual({r["company"]: r for r in I.companies(self.ws, show_all=True)}["Gamma"]["reposts"], 1)


class Skills(Base):
    def test_have_gap_and_do_not_claim(self):
        open(os.path.join(self.ws, "curriculum", "profile.md"), "w").write(
            "# Profile\n## Skills\nPython, PyTorch, Docker\n## Do NOT claim\n- Kubernetes (never used)\n")
        jobs = [R(f"C{i}", "Engineer", text="Python, PyTorch, Kubernetes and Docker." if i % 2 else "Python and Kubernetes.",
                  pay=(10000 + 1000 * i, 12000 + 1000 * i)) for i in range(12)]
        self.results("2026-06-20", jobs)
        r = I.skills(self.ws, self.cfg)
        gaps = {x["skill"]: x for x in r["gaps"]}
        have = {x["skill"] for x in r["strengths"]}
        self.assertEqual(gaps["kubernetes"]["status"], "gap (listed in Do NOT claim)")
        self.assertEqual(gaps["kubernetes"]["jobs"], 12)
        self.assertTrue({"python", "pytorch", "docker"} <= have)
        self.assertIsNotNone({x["skill"]: x for x in r["pay_linked"]}.get("docker"))  # 6 vs 6 jobs with pay

    def test_short_language_names_need_context(self):
        go, r = I.term_re("go"), I.term_re("r")
        for txt in ("Python, Go and Rust", "Backend in Go (Golang)", "golang services", "Go/Rust/C++ experience"):
            self.assertTrue(go.search(txt), txt)
        for txt in ("We go live next month", "go-to-market team", "ready to go", "Go ahead with Python"):
            self.assertFalse(go.search(txt), txt)
        for txt in ("Python, R, SQL", "R or Python for statistics", "RStudio"):
            self.assertTrue(r.search(txt), txt)
        for txt in ("Salário R$ 20.000", "R&D team in Python", "R $ 15.000 com Python", "Team R & D Python"):
            self.assertFalse(r.search(txt), txt)

    def test_profile_salary_is_not_the_r_language(self):
        open(os.path.join(self.ws, "curriculum", "profile.md"), "w").write("# Profile\nPython, SQL. Pay floor R$ 20.000 per month.\n")
        self.results("2026-06-20", [R("C1", "Data Scientist", text="Python, R, SQL")])
        gaps = {x["skill"]: x["status"] for x in I.skills(self.ws, self.cfg)["gaps"]}
        self.assertEqual(gaps.get("r"), "gap")

    def test_pay_withheld_when_small(self):
        self.results("2026-06-20", [R("C1", "Engineer", text="Rust", pay=(1, 2)), R("C2", "Engineer", text="Go", pay=(1, 2))])
        self.assertEqual(I.skills(self.ws, self.cfg)["pay_linked"], [])


class Weekly(Base):
    def test_window_channels_and_tips(self):
        rows = []
        for i in range(5):
            rows.append({"date": "2026-06-25", "event": "stage", "job": f"c{i}/role", "company": f"C{i}", "value": "submitted", "data": {"channel": "boardx"}})
        rows += [{"date": "2026-06-01", "event": "stage", "job": "old/role", "company": "OldCo", "value": "submitted", "data": {"channel": "ashby"}},
                 {"date": "2026-06-29", "event": "filter", "job": "k/role", "company": "K", "value": "keep"}]
        Log(self.ws).append(rows)
        r = I.weekly(self.ws, 7, TODAY)
        self.assertEqual(r["this"]["applied"], 5)
        self.assertIn("boardx", r["suggestion"])                     # 5 applications, no reply
        self.assertEqual(r["ghost_risk"], [("OldCo", 29)])
        self.assertEqual(r["follow_up"], [(f"C{i}", 5) for i in range(5)])


class Offers(unittest.TestCase):
    cfg = {"profile": {"currency": "BRL"}, "pay": {"hoursPerMonth": 160},
           "person": {"netModel": "BR", "contractorBillableMonths": 12, "contracts": []}}
    fx = {"BRL": 1.0, "EUR": 6.0, "USD": 5.0}

    def test_compare_matches_netpay_and_fx(self):
        rows = OF.compare([{"name": "clt", "contract": "employee_local", "amount": 25000, "currency": "BRL", "benefitsMonthly": 1500},
                           {"name": "eu", "contract": "contractor", "amount": 8000, "currency": "EUR", "equity": "0.1%"}],
                          self.cfg, self.fx, history=False)
        clt, eu = rows
        self.assertEqual(clt["net"], N.net_monthly(25000, "employee_local", self.cfg["person"])["net"])
        self.assertEqual(clt["total"], clt["net"] + 1500)
        self.assertEqual(eu["gross_home"], 48000)
        self.assertEqual(eu["net"], N.net_monthly(48000, "contractor", self.cfg["person"], "rate")["net"])
        self.assertEqual(eu["total"], eu["net"])                       # equity never added
        self.assertLess(eu["fx"]["-10%"], eu["net"])
        self.assertGreater(eu["fx"]["+10%"], eu["net"])
        self.assertNotIn("fx", clt)

    def test_breakeven(self):
        target = N.net_monthly(48000, "contractor", self.cfg["person"], "rate")["net"]
        g = OF.breakeven_clt(target, self.cfg["person"])
        self.assertAlmostEqual(N.net_monthly(g, "employee_local", self.cfg["person"])["net"], target, delta=50)

    def test_history_range(self):
        old = OF.scan.getj
        OF.scan.getj = lambda url, **kw: {"rates": {"2026-01-02": {"BRL": 5.5}, "2026-03-02": {"BRL": 6.6}}}
        try:
            rows = OF.compare([{"name": "eu", "contract": "contractor", "amount": 8000, "currency": "EUR"}], self.cfg, self.fx, history=True)
        finally:
            OF.scan.getj = old
        x = rows[0]["fx_12m"]
        self.assertEqual((x["rate_min"], x["rate_max"]), (5.5, 6.6))
        self.assertLess(x["net_min"], x["net_max"])

    def test_example_offers_template_is_valid(self):
        ex = json.load(open(os.path.join(ROOT, "skill", "job-hunt", "templates", "interview", "offers.json")))
        self.assertTrue(all({"name", "contract", "amount", "currency"} <= set(o) for o in ex))


if __name__ == "__main__":
    unittest.main()

"""Offline tests: net pay (Brazil module + generic fallback), eligibility verdicts and contract detection.
Expected BR values are hand-computed from the 2026 tables in skill/job-hunt/scripts/netpay/BR.json.
Run: python3 -m unittest discover -s tests -v
"""
import datetime as dt, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skill", "job-hunt", "scripts"))
import eligibility as EL  # noqa: E402
import netpay as N  # noqa: E402

BR = {"netModel": "BR", "contractorBillableMonths": 12}
PERSON = {"residence": "BR", "citizenships": ["BR", "IT"], "timezone": "America/Sao_Paulo", "minOverlapHours": 4}
NOV = dt.datetime(2026, 11, 25, tzinfo=dt.timezone.utc)


def job(text="", loc="", source="Remotive", title="Engineer"):
    return {"title": title, "text": text, "loc": loc, "source": source, "extra": {}}


class NetPayBR(unittest.TestCase):
    m = N.load_model("BR")

    def test_tables_not_expired(self):
        until = dt.date.fromisoformat(self.m["validUntil"])
        if dt.date.today() > until:
            self.skipTest(f"BR.json expired on {until}: update the tables")  # visible in -v output, doesn't fail CI

    def test_inss_ceiling(self):
        self.assertAlmostEqual(N.br_inss_employee(self.m, 25000), 988.09, places=1)

    def test_irrf_reduction(self):
        self.assertEqual(N.br_irrf(self.m, 5000, N.br_inss_employee(self.m, 5000)), 0)          # exempt up to 5k
        self.assertAlmostEqual(N.br_irrf(self.m, 6000, N.br_inss_employee(self.m, 6000)), 385.10, places=1)  # phase-out

    def test_clt_25k(self):
        r = N.net_monthly(25000, "employee_local", BR)
        self.assertAlmostEqual(r["net"], 20352, delta=2)       # (25000 - 988.09 - 5694.55) x 13.33/12
        self.assertEqual(r["detail"]["fgts_deferred"], 2000)

    def test_contractor_export_picks_best_anexo(self):
        r = N.net_monthly(30000, "contractor", BR)
        self.assertEqual(r["detail"]["best"]["anexo"], "III")
        self.assertAlmostEqual(r["net"], 25766, delta=3)
        self.assertTrue(any("export" in a for a in r["assumptions"]))

    def test_local_pj_pays_more_tax_than_export(self):
        self.assertLess(N.net_monthly(30000, "pj_local", BR)["net"], N.net_monthly(30000, "contractor", BR)["net"])

    def test_high_income_dividend_rules(self):
        best = N.net_monthly(100000, "contractor", BR)["detail"]["best"]
        self.assertGreater(best["dividend_tax"], 0)

    def test_above_simples_ceiling_falls_back(self):
        self.assertIsNone(N.net_monthly(500000, "contractor", BR))  # no flat rates configured -> no estimate

    def test_foreign_payroll_no_estimate(self):
        self.assertIsNone(N.net_monthly(20000, "employee_foreign", BR)["net"])


class NetPayGeneric(unittest.TestCase):
    def test_flat_rates_and_billable_months(self):
        p = {"netRates": {"contractor": 0.8}, "contractorBillableMonths": 11}
        self.assertEqual(N.net_monthly(12000, "contractor", p, "rate")["net"], 8800)   # 12000 x 11/12 x 0.8
        self.assertEqual(N.net_monthly(12000, "contractor", p, "year")["net"], 9600)
        self.assertIsNone(N.net_monthly(12000, "employee_local", p))

    def test_unknown_contract_scenarios(self):
        self.assertEqual(sorted(N.scenarios(25000, "unknown", True, BR)), ["employee_local", "pj_local"])
        self.assertEqual(sorted(N.scenarios(25000, "unknown", False, BR)), ["contractor", "eor"])


class Eligibility(unittest.TestCase):
    def v(self, *a, **k):
        return EL.eligibility(job(*a, **k), PERSON, NOV)

    def test_residence_vs_citizenship(self):
        self.assertEqual(self.v("Fully remote. European residence required.")["verdict"], "relocation")
        self.assertEqual(self.v("Candidates must be located in the United States.")["verdict"], "no")
        self.assertEqual(self.v("You need the right to work in the EU.", "Worldwide")["verdict"], "eligible")
        self.assertEqual(self.v("You need the right to work in the EU.", "Remote, Europe")["verdict"], "relocation")

    def test_location_field(self):
        self.assertEqual(self.v("", "Remote - LATAM")["verdict"], "eligible")
        self.assertEqual(self.v("", "Remote Germany")["verdict"], "relocation")   # EU citizen, lives elsewhere
        self.assertEqual(self.v("", "Remote, India")["verdict"], "no")
        self.assertEqual(self.v("We are a remote team.", "")["verdict"], "likely")
        self.assertEqual(self.v("", "")["verdict"], "unclear")

    def test_us_payroll(self):
        r = self.v("Benefits: 401(k) match. W-2 employees only.", "Remote")
        self.assertEqual((r["verdict"], r["contract"]), ("no", "employee_foreign"))

    def test_contracts(self):
        self.assertEqual(EL.detect_contract(job("We hire globally through Deel.")), "eor")
        self.assertEqual(EL.detect_contract(job("Independent contractor, paid monthly.")), "contractor")
        self.assertEqual(EL.detect_contract(job("Regime CLT, home office.")), "employee_local")
        self.assertEqual(EL.detect_contract(job("", source="Gupy")), "employee_local")
        self.assertEqual(EL.detect_contract(job("Great team.")), "unknown")

    def test_timezone_overlap(self):
        r = self.v("Remote. You must overlap 4 hours with PST.", "Remote")
        self.assertEqual(r["tz_overlap"], 3)            # Sao Paulo UTC-3 vs PST UTC-8
        self.assertEqual(r["verdict"], "likely")
        self.assertEqual(self.v("Remote, core hours in CET.", "Worldwide")["tz_overlap"], 4)


if __name__ == "__main__":
    unittest.main()

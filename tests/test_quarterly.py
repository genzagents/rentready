"""Quarterly update figures guide: the committed page is what the generator writes, its periods are MTD's, and the
in-page readCsv(), categorise() and summarise() (run under node) read each bank layout and total the sample right."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_quarterly as g  # noqa: E402
import schema  # noqa: E402

REL = "docs/guides/making-tax-digital-quarterly-update-landlords.html"
PAGE = ROOT / REL

BANKS = {
    "monzo": "Transaction ID,Date,Time,Type,Name,Emoji,Category,Amount,Currency\n"
             "tx_1,07/10/2026,09:00,Faster payment,J Smith rent,,Income,1150.00,GBP\n"
             "tx_2,08/10/2026,10:00,Card payment,Screwfix,,Shopping,-12.50,GBP\n",
    "starling": "Date,Counter Party,Reference,Type,Amount (GBP),Balance (GBP),Spending Category,Notes\n"
                "07/10/2026,J Smith,RENT OCT,FASTER PAYMENT,1150.00,2000.00,INCOME,\n"
                "08/10/2026,Screwfix,,CARD,-12.50,1987.50,SHOPPING,\n",
    "lloyds": "Transaction Date,Transaction Type,Sort Code,Account Number,Transaction Description,Debit Amount,Credit Amount,Balance\n"
              "07/10/2026,FPI,'30-00-00,12345678,J SMITH RENT,,1150.00,2000.00\n"
              "08/10/2026,DEB,'30-00-00,12345678,SCREWFIX,12.50,,1987.50\n",
    "hsbc": "07 Oct 2026,J SMITH RENT,\"1,150.00\"\n08 Oct 2026,SCREWFIX,-12.50\n",
    "santander": "Date,Description,Money in,Money out,Balance\n"
                 "2026-10-07,J SMITH RENT,£1150.00,,£2000.00\n2026-10-08,SCREWFIX,,£12.50,£1987.50\n",
}


def run(js: str):
    return json.loads(subprocess.run(["node", "-e", js], capture_output=True, check=True, text=True).stdout)


class QuarterlyGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")
        self.logic = re.search(r'<script id="qu-logic">(.*?)</script>', self.t, re.S).group(1)

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply(REL, g.build()))

    def test_periods_are_mtd(self):
        self.assertEqual([d for _, d in g.PERIODS["standard"]], ["2026-08-07", "2026-11-07", "2027-02-07", "2027-05-07"])
        self.assertEqual([d for _, d in g.PERIODS["calendar"]], [d for _, d in g.PERIODS["standard"]])
        self.assertEqual(g.PERIODS["standard"][1][0], "2026-10-05")
        self.assertEqual(g.PERIODS["calendar"][1][0], "2026-09-30")
        self.assertIn("£90,000", self.t)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_bank_layouts(self):
        js = self.logic + "console.log(JSON.stringify(%s.map(function(t){return readCsv(t)})));" % json.dumps(list(BANKS.values()))
        for name, r in zip(BANKS, run(js)):
            with self.subTest(bank=name):
                self.assertEqual(r["error"], "")
                self.assertEqual([(l["date"], l["pence"]) for l in r["lines"]], [("2026-10-07", 115000), ("2026-10-08", -1250)])
                self.assertIn("SMITH", r["lines"][0]["desc"].upper() + "SMITH" * (name == "starling"))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_categorise(self):
        cases = [("J SMITH RENT FLAT 2", 115000), ("TENANT DEPOSIT DPS", 130000), ("PARAGON MORTGAGE", -61240),
                 ("HMRC SELF ASSESSMENT", -184000), ("FOXTONS MANAGEMENT FEE", -9000), ("BRITISH GAS", -4000),
                 ("GAS SAFETY CERTIFICATE", -7200), ("ACE PLUMBING", -18500), ("AMAZON", -2399), ("REFUND", 500)]
        js = self.logic + "console.log(JSON.stringify(%s.map(function(c){return categorise(c[0],c[1])})));" % json.dumps(cases)
        self.assertEqual(run(js), ["periodAmount", "exclude", "residentialFinancialCost", "exclude", "professionalFees",
                                   "premisesRunningCosts", "other", "repairsAndMaintenance", "unsorted", "periodAmount"])

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_sample_totals(self):
        js = self.logic + """var d=readCsv(%s),c=d.lines.map(function(l){return categorise(l.desc,l.pence)});
console.log(JSON.stringify([summarise(d.lines,c,"standard",1,100),summarise(d.lines,c,"calendar",1,100),
 summarise(d.lines,c,"standard",1,50),summarise(d.lines,c,"standard",0,100)]));""" % json.dumps(g.SAMPLE)
        std, cal, half, q1 = run(js)
        self.assertEqual(std["totals"]["periodAmount"], 690000)
        self.assertEqual(std["totals"]["residentialFinancialCost"], 367440)
        self.assertEqual(std["totals"]["repairsAndMaintenance"], 23185)
        self.assertEqual(std["totals"]["professionalFees"], 17900)
        self.assertEqual(std["totals"]["premisesRunningCosts"], 3820)
        self.assertEqual(std["totals"]["other"], 7200)
        self.assertEqual((std["income"], std["expenses"], std["finance"]), (690000, 52105, 367440))
        self.assertEqual(std["counts"]["unsorted"], 1)
        self.assertEqual(std["counts"]["after"], 1)
        self.assertTrue(std["simpler"])
        self.assertEqual(std["due"], "2026-11-07")
        self.assertEqual(cal["totals"]["professionalFees"], 2900)  # the 2 Oct accountant falls after 30 September
        self.assertEqual(half["income"], 345000)
        self.assertEqual(q1["totals"]["periodAmount"], 345000)

    def test_linked_and_in_sitemap(self):
        self.assertIn(g.URL, (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))
        for p in ("index.html", "landlord-deadlines-calendar.html", "hmrc-signed-me-up-making-tax-digital.html"):
            self.assertIn('href="making-tax-digital-quarterly-update-landlords.html"',
                          (ROOT / "docs/guides" / p).read_text(encoding="utf-8"))
        self.assertIn('RM.mtd($("rem-email").value,due,"quarterly figures")', self.t)


if __name__ == "__main__":
    unittest.main()

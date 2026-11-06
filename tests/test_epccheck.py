"""EPC check on the EPC guide (docs/epccheck.js): same windows as rentready.ROLLOUT, and the right answer for a valid,
lapsed-but-fine, lapsed-before-the-tenancy, missing or low-rated EPC."""
import json, shutil, subprocess, unittest
from pathlib import Path

import rentready as rr

ROOT = Path(__file__).resolve().parent.parent
JS = str(ROOT / "docs" / "epccheck.js")
NODE = shutil.which("node")
RUN = "const E=require(process.argv[1]);let i=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
      "console.log(JSON.stringify(i.map(([f,a])=>f==='rollout'?E.ROLLOUT:E[f](...a))))"


@unittest.skipUnless(NODE, "node not installed")
class EpcCheckTest(unittest.TestCase):
    def call(self, *calls):
        out = subprocess.run([NODE, "-e", RUN, JS], input=json.dumps(calls), capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def check(self, **o):
        o.setdefault("region", "West Midlands")
        o.setdefault("tenancy", "let")
        return self.call(["check", [o]])[0]

    def test_windows_match_rollout(self):
        rows, = self.call(["rollout", []])
        self.assertEqual({r[0]: (r[1], r[2]) for r in rows},
                         {n: (w["opens"], w["deadline"]) for n, w in rr.ROLLOUT.items()})

    def test_ten_years_and_leap_day(self):
        self.assertEqual(self.call(["plus10", ["2017-05-01"]], ["plus10", ["2016-02-29"]]), ["2027-05-01", "2026-03-01"])

    def test_valid_at_deadline(self):
        r = self.check(epc="2017-05-01", rating="C")
        self.assertEqual(r["verdict"], "yes")
        self.assertIn("1 May 2027", r["head"])

    def test_lapsed_but_valid_when_tenant_moved_in(self):
        r = self.check(epc="2016-01-10", tenancy_start="2020-06-01")
        self.assertEqual((r["verdict"], r["lapses"]), ("yes", "2026-01-10"))
        self.assertIn("tenancy start date", r["lines"][0])
        self.assertIn("lapsed on 10 January 2026", self.check(epc="2016-01-10", tenancy_start="2020-06-01", today="2026-11-06")["head"])

    def test_lapsed_before_tenancy_started(self):
        self.assertEqual(self.check(epc="2014-01-10", tenancy_start="2025-03-01")["verdict"], "no")

    def test_lapsed_without_tenancy_date_or_vacant(self):
        self.assertEqual(self.check(epc="2014-01-10")["verdict"], "later")
        self.assertEqual(self.check(epc="2014-01-10", tenancy="vacant")["verdict"], "no")

    def test_region_moves_the_deadline(self):
        # lapses 1 May 2027: after the West Midlands deadline, before London's
        self.assertEqual(self.check(epc="2017-05-01")["verdict"], "yes")
        self.assertEqual(self.check(epc="2017-05-01", region="London")["verdict"], "later")

    def test_no_epc(self):
        self.assertEqual(self.check(epc="", tenancy_start="2005-04-01")["verdict"], "yes")
        self.assertEqual(self.check(epc="", tenancy_start="2019-04-01")["verdict"], "no")
        self.assertEqual(self.check(epc="")["verdict"], "later")

    def test_low_rating_needs_exemption(self):
        r = self.check(epc="2020-01-01", rating="F")
        self.assertEqual(r["verdict"], "later")
        self.assertIn("MEES exemption", r["lines"][-1])


if __name__ == "__main__":
    unittest.main()

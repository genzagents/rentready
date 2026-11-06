"""EICR check on the EICR guide (docs/eicrcheck.js): same windows as rentready.ROLLOUT, the report's next-inspection
date capped at five years, and the right answer for no report, lapsed, valid at the deadline or lapsing before it."""
import json, shutil, subprocess, unittest
from pathlib import Path

import rentready as rr

ROOT = Path(__file__).resolve().parent.parent
JS = str(ROOT / "docs" / "eicrcheck.js")
NODE = shutil.which("node")
RUN = "const E=require(process.argv[1]);let i=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
      "console.log(JSON.stringify(i.map(([f,a])=>f==='rollout'?E.ROLLOUT:E[f](...a))))"


@unittest.skipUnless(NODE, "node not installed")
class EicrCheckTest(unittest.TestCase):
    def call(self, *calls):
        out = subprocess.run([NODE, "-e", RUN, JS], input=json.dumps(calls), capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def check(self, **o):
        o.setdefault("region", "West Midlands")
        o.setdefault("have", "eicr")
        o.setdefault("issued", "")
        o.setdefault("next", "")
        o.setdefault("today", "2026-11-06")
        return self.call(["check", [o]])[0]

    def test_windows_match_rollout(self):
        rows, = self.call(["rollout", []])
        self.assertEqual({r[0]: (r[1], r[2]) for r in rows},
                         {n: (w["opens"], w["deadline"]) for n, w in rr.ROLLOUT.items()})

    def test_no_report(self):
        for o in ({"have": "none", "issued": "2023-06-01"}, {}):
            r = self.check(**o)
            self.assertEqual(r["verdict"], "no")
            self.assertIn("28 days", r["lines"][0])

    def test_guide_example_in_date(self):
        # issued 1 Jun 2023, next inspection 1 Jun 2028, West Midlands deadline 14 Mar 2027
        r = self.check(issued="2023-06-01", next="2028-06-01")
        self.assertEqual((r["verdict"], r["expiry"], r["assumed"], r["update_by"]), ("yes", "2028-06-01", False, "2028-06-29"))

    def test_shorter_interval_moves_the_answer(self):
        # the guide's three-year example: fine in the West Midlands, too short for London
        o = {"issued": "2024-06-01", "next": "2027-06-01"}
        self.assertEqual(self.check(**o)["verdict"], "yes")
        self.assertEqual(self.check(region="London", **o)["verdict"], "later")

    def test_issue_date_only_assumes_five_years(self):
        r = self.check(issued="2022-01-10")
        self.assertEqual((r["verdict"], r["expiry"], r["assumed"]), ("later", "2027-01-10", True))
        self.assertTrue(any("five years" in s for s in r["lines"]))

    def test_cap_at_five_years(self):
        r = self.check(issued="2023-06-01", next="2029-01-01")
        self.assertEqual(r["expiry"], "2028-06-01")

    def test_lapsed(self):
        r = self.check(issued="2021-03-01", next="2026-03-01")
        self.assertEqual((r["verdict"], r["expiry"]), ("no", "2026-03-01"))

    def test_eic_named(self):
        r = self.check(have="eic", issued="2025-05-01")
        self.assertIn("EIC ", r["head"])


if __name__ == "__main__":
    unittest.main()

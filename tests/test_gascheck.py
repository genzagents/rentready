"""Gas check on the gas guide (docs/gascheck.js): same windows as rentready.ROLLOUT, 12-month due dates with the
2-month early window, and the right answer for no gas, no record, lapsed, valid at the deadline or lapsing before it."""
import json, shutil, subprocess, unittest
from pathlib import Path

import rentready as rr

ROOT = Path(__file__).resolve().parent.parent
JS = str(ROOT / "docs" / "gascheck.js")
NODE = shutil.which("node")
RUN = "const E=require(process.argv[1]);let i=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
      "console.log(JSON.stringify(i.map(([f,a])=>f==='rollout'?E.ROLLOUT:E[f](...a))))"


@unittest.skipUnless(NODE, "node not installed")
class GasCheckTest(unittest.TestCase):
    def call(self, *calls):
        out = subprocess.run([NODE, "-e", RUN, JS], input=json.dumps(calls), capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def check(self, **o):
        o.setdefault("region", "West Midlands")
        o.setdefault("gas", "yes")
        o.setdefault("today", "2026-11-06")
        return self.call(["check", [o]])[0]

    def test_windows_match_rollout(self):
        rows, = self.call(["rollout", []])
        self.assertEqual({r[0]: (r[1], r[2]) for r in rows},
                         {n: (w["opens"], w["deadline"]) for n, w in rr.ROLLOUT.items()})

    def test_month_arithmetic(self):
        self.assertEqual(self.call(["addMonths", ["2026-02-01", 12]], ["addMonths", ["2024-02-29", 12]],
                                   ["addMonths", ["2026-12-31", 2]]), ["2027-02-01", "2025-02-28", "2027-02-28"])

    def test_no_gas(self):
        r = self.check(gas="no", last="")
        self.assertEqual(r["verdict"], "yes")
        self.assertIn("no gas safety record", r["head"])

    def test_no_record(self):
        r = self.check(last="")
        self.assertEqual(r["verdict"], "no")
        self.assertIn("28 days", r["lines"][0])

    def test_lapsed(self):
        r = self.check(last="2025-09-01")
        self.assertEqual((r["verdict"], r["due"]), ("no", "2026-09-01"))

    def test_valid_at_deadline(self):
        r = self.check(last="2026-06-01")
        self.assertEqual((r["verdict"], r["due"], r["book_from"], r["update_by"]),
                         ("yes", "2027-06-01", "2027-04-01", "2027-06-29"))

    def test_lapses_before_deadline(self):
        # the guide's worked example: issued 1 Feb 2026, due 1 Feb 2027, West Midlands deadline 14 Mar 2027
        r = self.check(last="2026-02-01")
        self.assertEqual((r["verdict"], r["due"], r["book_from"]), ("later", "2027-02-01", "2026-12-01"))
        self.assertIn("anniversary", r["lines"][0])

    def test_region_moves_the_deadline(self):
        self.assertEqual(self.check(last="2026-05-01")["verdict"], "yes")
        self.assertEqual(self.check(last="2026-05-01", region="London")["verdict"], "later")


if __name__ == "__main__":
    unittest.main()

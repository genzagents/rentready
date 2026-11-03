import re
import shutil
import subprocess
import sys
import unittest
from datetime import date
from pathlib import Path

from rentready.fee import first_payment, renewal_date

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_fee  # noqa: E402


class FeeTest(unittest.TestCase):
    def test_official_worked_examples(self):
        # gov.uk guidance for landlords, "Worked examples"
        self.assertEqual(first_payment(date(2026, 12, 15)), 5.34)
        self.assertEqual(first_payment(date(2027, 6, 25)), 39.60)

    def test_renewal_is_one_year_from_first_property(self):
        self.assertEqual(renewal_date(date(2026, 12, 15)), date(2027, 12, 15))
        self.assertEqual(renewal_date(date(2028, 2, 29)), date(2029, 2, 28))

    def test_later_property_shares_renewal_date(self):
        # first property 15 Dec 2026 (renews 15 Dec 2027): one added 1 Mar 2027 pays the same 30 charged days
        self.assertEqual(first_payment(date(2027, 3, 1), first=date(2026, 12, 15)), 5.34)
        # added after charging starts: pays only the days left to the shared renewal date
        self.assertEqual(first_payment(date(2027, 11, 30), first=date(2026, 12, 15)), 2.67)

    def test_after_rollout_is_full_fee(self):
        self.assertEqual(first_payment(date(2028, 1, 10)), 65.0)
        # the last day of the South West window, the dearest day of the rollout: 365 of 366 days
        self.assertEqual(first_payment(date(2027, 11, 14)), 64.82)

    def test_later_property_before_first_is_an_error(self):
        with self.assertRaises(ValueError):
            first_payment(date(2026, 12, 1), first=date(2026, 12, 15))

    def test_fee_page_block_is_current(self):
        page = gen_fee.PAGE.read_text()
        i, j = page.index(gen_fee.START), page.index(gen_fee.END) + len(gen_fee.END)
        self.assertEqual(page[i:j], gen_fee.block(), "run python3 tools/gen_fee.py")
        self.assertIn("£5.34", page)
        self.assertIn("£64.82", page)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_page_calculator_matches_python(self):
        page = gen_fee.PAGE.read_text()
        js = re.search(r"<script>\n\(function \(\) \{(.*?)var f = document", page, re.S).group(1)
        cases = [((2026, 12, 15), (2026, 12, 15)), ((2027, 6, 25), (2027, 6, 25)), ((2027, 3, 1), (2026, 12, 15)),
                 ((2027, 11, 30), (2026, 12, 15)), ((2027, 11, 14), (2027, 11, 14)), ((2028, 1, 10), (2028, 1, 10))]
        calls = ",".join(f"pay(Date.UTC({r[0]},{r[1] - 1},{r[2]}),Date.UTC({f[0]},{f[1] - 1},{f[2]})).pence" for r, f in cases)
        out = subprocess.run(["node", "-e", js + f"console.log([{calls}].join(' '))"], capture_output=True, text=True, check=True)
        want = [round(first_payment(date(*r), first=date(*f)) * 100) for r, f in cases]
        self.assertEqual([int(x) for x in out.stdout.split()], want)


if __name__ == "__main__":
    unittest.main()

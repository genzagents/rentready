"""First-year cost guide: every figure on the page follows from the fee and the sourced certificate ranges, so a
price change in one place cannot leave the table, the lead, the FAQ and the calculator disagreeing."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs/guides/landlord-database-first-year-cost.html"
FEE, GAS, EICR, EPC = 65, (60, 90), (120, 280), (60, 120)


def money(x: int) -> str:
    return f"£{x:,}"


def rng(lo: int, hi: int) -> str:
    return f"{money(lo)} to {money(hi)}"


class CostGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_scenario_table(self):
        for n in (1, 3, 10):
            gas = rng(n * (FEE + GAS[0]), n * (FEE + GAS[1]))
            full = rng(n * (FEE + GAS[0] + EICR[0] + EPC[0]), n * (FEE + GAS[1] + EICR[1] + EPC[1]))
            self.assertIn(f"<tr><td>{n}</td><td>{money(n * FEE)}</td><td>{gas}</td><td>{full}</td></tr>", self.t)

    def test_average_and_lead(self):
        lo, hi = FEE + GAS[0] + EICR[0] // 5 + EPC[0] // 10, FEE + GAS[1] + EICR[1] // 5 + EPC[1] // 10
        self.assertIn(rng(lo, hi) + " a year", self.t)
        self.assertIn(rng(FEE + GAS[0], FEE + GAS[1]) + " a property", self.t)
        self.assertIn(rng(FEE + GAS[0] + EICR[0] + EPC[0], FEE + GAS[1] + EICR[1] + EPC[1]), self.t)

    def test_calculator_uses_the_same_ranges(self):
        self.assertIn(f"fee:[{FEE},{FEE}],g:[{GAS[0]},{GAS[1]}],e:[{EICR[0]},{EICR[1]}],p:[{EPC[0]},{EPC[1]}]", self.t)
        self.assertRegex(self.t, r'var fee=65\*n')

    def test_linked_and_in_sitemap(self):
        url = "https://genzagents.github.io/rentready/guides/landlord-database-first-year-cost.html"
        self.assertIn(url, (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))
        for g in ("index.html", "landlord-database-fee.html"):
            self.assertIn('href="landlord-database-first-year-cost.html"', (ROOT / "docs/guides" / g).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

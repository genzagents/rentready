"""Press page: committed files are current, the headline matches the region CSV, and the page is in the sitemap."""
import csv
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_press  # noqa: E402
import gen_epc_story as story  # noqa: E402
from schema import apply  # noqa: E402


class PressTest(unittest.TestCase):
    def test_committed_files_are_current(self):
        self.assertEqual(apply("docs/press.html", gen_press.build()), gen_press.OUT.read_text(encoding="utf-8"),
                         "docs/press.html is stale: run python3 tools/gen_press.py")
        _, years = story.compute()
        self.assertEqual(gen_press.chart(years, inline=False) + "\n", gen_press.SVG_OUT.read_text(encoding="utf-8"))

    def test_headline_matches_region_csv(self):
        rows = list(csv.DictReader((ROOT / "docs/data/epc-rental-expiry-by-region.csv").open(encoding="utf-8")))
        total = sum(int(r["rental_epcs_reaching_10_years_1_nov_2026_to_deadline"]) for r in rows)
        page = gen_press.OUT.read_text(encoding="utf-8")
        self.assertIn(f"About {round(total / 1000):,},000 rental EPCs", page)

    def test_linked_and_in_sitemap(self):
        self.assertIn("rentready/press.html", (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn("press.html", (ROOT / "docs/guides/epc-expiry-by-region.html").read_text(encoding="utf-8"))
        self.assertIn("press.html", (ROOT / "docs/about.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

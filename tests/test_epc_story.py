"""The EPC expiry data story: committed page and CSV match the generator, the arithmetic holds, and the headline
quoted on other pages matches the computed total."""
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_epc_story as g  # noqa: E402


class EpcStoryTest(unittest.TestCase):
    def test_committed_files_are_current(self):
        html, data, council_data = g.build()
        self.assertEqual(g.PAGE.read_text(encoding="utf-8"), html, "run python3 tools/gen_epc_story.py")
        self.assertEqual(g.DATA.read_text(encoding="utf-8"), data, "run python3 tools/gen_epc_story.py")
        self.assertEqual(g.COUNCIL_DATA.read_text(encoding="utf-8"), council_data, "run python3 tools/gen_epc_story.py")

    def test_councils_add_up_to_regions(self):
        regions, _ = g.compute()
        cs = g.councils()
        self.assertEqual(len({c["council"] for c in cs}), len(cs))
        for r in regions:
            mine = [c for c in cs if c["region"] == r["region"]]
            self.assertTrue(mine, r["region"])
            self.assertAlmostEqual(sum(c["before"] for c in mine), r["before"], delta=1)
            self.assertAlmostEqual(sum(c["wave"] for c in mine), r["wave"], delta=1)

    def test_unusual_quarter_flag(self):
        rows = [(f"{y}/{q}", 100) for y in range(2013, 2020) for q in range(1, 5)]
        self.assertFalse(g.unusual(rows, date(2016, 11, 1), date(2017, 9, 14)))
        rows[rows.index(("2017/2", 100))] = ("2017/2", 2000)
        self.assertTrue(g.unusual(rows, date(2016, 11, 1), date(2017, 9, 14)))
        self.assertFalse(g.unusual(rows, date(2018, 1, 1), date(2018, 6, 1)))
        self.assertTrue(next(c for c in g.councils() if c["council"] == "Sunderland")["unusual"])

    def test_pro_rata_and_whole_quarters(self):
        rows = [("2016/4", 920), ("2017/1", 900)]
        self.assertAlmostEqual(g.lodged(rows, date(2016, 10, 1), date(2017, 4, 1)), 1820)
        self.assertAlmostEqual(g.lodged(rows, date(2016, 11, 16), date(2017, 1, 1)), 920 * 46 / 92)
        self.assertEqual(g.lodged(rows, date(2018, 1, 1), date(2019, 1, 1)), 0)

    def test_regions_and_totals(self):
        regions, years = g.compute()
        self.assertEqual(len(regions), 9)
        for r in regions:
            self.assertLessEqual(r["window"], r["before"])
            self.assertGreater(r["window"], 0)
        # every quarter counted once: the year totals add up to the input file
        total = sum(int(l.rsplit(",", 1)[1]) for l in g.SRC.read_text(encoding="utf-8").splitlines()[1:])
        self.assertEqual(sum(years.values()), total)

    def test_headline_quoted_elsewhere_matches(self):
        regions, _ = g.compute()
        head = g.thousands(sum(r["before"] for r in regions))
        for page in ("docs/guides/index.html", "docs/guides/epc-rating-landlord-database.html"):
            self.assertIn(f"About {head} rental EPCs" if "rating" in page else f"about {head} rental EPCs",
                          (ROOT / page).read_text(encoding="utf-8"), page)


if __name__ == "__main__":
    unittest.main()

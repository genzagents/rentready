"""Selective licensing list: the committed page is what the generator writes, every live scheme in licensing.json is
listed once with its council's source link, the counts match the data, and the page is linked from the hub."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_licensing_guide as g  # noqa: E402
import schema  # noqa: E402

REL = "docs/guides/selective-licensing-councils-england.html"
PAGE = ROOT / REL


class LicensingGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")
        self.d = json.loads((ROOT / "docs/data/licensing.json").read_text(encoding="utf-8"))

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply(REL, g.build()))

    def test_every_live_scheme_listed(self):
        s = g.schemes(self.d)
        self.assertEqual(len(s), self.d["counts"]["selective"] + self.d["counts"]["additional"])
        self.assertEqual(self.t.count("<tr data-q="), len(s))
        for _, _, _, e in s:
            if e.get("source"):
                self.assertIn(e["source"].replace("&", "&amp;"), self.t)

    def test_counts_and_answer(self):
        n = self.d["counts"]
        self.assertIn(f"<strong>{n['either']} of England's {n['councils']} councils", self.t)
        self.assertIn("pay both", self.t)
        self.assertIn('"@type": "FAQPage"', self.t)

    def test_ending_soon_in_window(self):
        for _, _, _, e in g.schemes(self.d):
            if e.get("until") and g.TODAY <= e["until"] <= g.SOON:
                self.assertIn(g.nice(e["until"]), self.t)

    def test_linked(self):
        for p in ("index.html", "landlord-database-fee.html"):
            self.assertIn('href="selective-licensing-councils-england.html"',
                          (ROOT / "docs/guides" / p).read_text(encoding="utf-8"))
        self.assertIn("selective-licensing-councils-england.html", (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

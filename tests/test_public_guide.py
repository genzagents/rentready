"""Public search guide: the committed page is what the generator writes, it answers no in the first paragraph, every
timeline row cites the Act or guidance, and the page is linked from the hub and the sitemap."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_public_guide as g  # noqa: E402
import schema  # noqa: E402

REL = "docs/guides/can-you-search-landlord-database.html"
PAGE = ROOT / REL


class PublicGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply(REL, g.build()))

    def test_answer_first(self):
        first = self.t[self.t.index("</h1>"):self.t.index('<div class="kpis">')]
        self.assertIn("<strong>No.", first)
        self.assertIn("15 December 2026", first)
        self.assertIn('"@type": "FAQPage"', self.t)

    def test_timeline_sourced(self):
        self.assertEqual(len(g.TIMELINE), 4)
        for _, _, _, label, url in g.TIMELINE:
            self.assertIn(f'href="{url}"', self.t)
            self.assertTrue(url.startswith(("https://www.legislation.gov.uk/", "https://www.gov.uk/")))

    def test_no_placeholders_left(self):
        self.assertNotIn("__", self.t.replace("__proto__", ""))

    def test_linked(self):
        self.assertIn('href="can-you-search-landlord-database.html"',
                      (ROOT / "docs/guides/index.html").read_text(encoding="utf-8"))
        self.assertIn("can-you-search-landlord-database.html", (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

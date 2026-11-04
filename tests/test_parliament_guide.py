"""What ministers said guide: the committed page is what the generator writes, it answers in the first paragraph,
every answer cites a Hansard debate, and the page is linked from the hub and the sitemap."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_parliament_guide as g  # noqa: E402
import schema  # noqa: E402

REL = "docs/guides/landlord-database-what-ministers-said.html"
PAGE = ROOT / REL


class ParliamentGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply(REL, g.build()))

    def test_answer_first(self):
        first = self.t[self.t.index("</h1>"):self.t.index('<div class="kpis">')]
        self.assertIn("no bulk upload", first)
        self.assertIn('"@type": "FAQPage"', self.t)

    def test_every_answer_sourced(self):
        for q, _, _, src in g.ANSWERS:
            self.assertTrue(src and set(src) <= set(g.SRC), q)
        for k in g.SRC:
            self.assertTrue(g.SRC[k][1].startswith("https://hansard.parliament.uk/"))
            self.assertIn(f'href="{g.SRC[k][1]}"', self.t)

    def test_no_placeholders_left(self):
        self.assertNotIn("__", self.t.replace("__proto__", ""))

    def test_linked(self):
        self.assertIn('href="landlord-database-what-ministers-said.html"',
                      (ROOT / "docs/guides/index.html").read_text(encoding="utf-8"))
        self.assertIn("landlord-database-what-ministers-said.html", (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

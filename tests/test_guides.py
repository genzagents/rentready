import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_guides  # noqa: E402
import rentready as rr  # noqa: E402


class GuidesTest(unittest.TestCase):
    def test_committed_pages_are_current(self):
        for rel, text in gen_guides.build().items():
            self.assertEqual((ROOT / rel).read_text(encoding="utf-8"), text, f"{rel} is stale: run python3 tools/gen_guides.py")

    def test_every_region_page_has_its_deadline_and_is_linked(self):
        hub = (ROOT / "docs/guides/index.html").read_text(encoding="utf-8")
        table = (ROOT / "docs/guides/landlord-database-deadline-by-region.html").read_text(encoding="utf-8")
        for region, w in rr.ROLLOUT.items():
            name = gen_guides.slug(region) + ".html"
            text = (ROOT / "docs/guides" / name).read_text(encoding="utf-8")
            self.assertIn(gen_guides.long(w["deadline"]), text)
            self.assertIn(f'href="{name}"', hub)
            self.assertIn(f'href="{name}"', table)

    def test_internal_links_resolve(self):
        for page in (ROOT / "docs/guides").glob("*.html"):
            for href in re.findall(r'href="([^"]+)"', page.read_text(encoding="utf-8")):
                href = href.split("#")[0]
                if not href or ":" in href:
                    continue
                self.assertTrue((page.parent / href).exists(), f"{page.name} links to missing {href}")

    def test_sitemap_lists_every_guide_once(self):
        sm = (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8")
        for page in (ROOT / "docs/guides").glob("*.html"):
            loc = gen_guides.BASE + "guides/" + ("" if page.name == "index.html" else page.name) + "<"
            self.assertEqual(sm.count(loc), 1, loc)


if __name__ == "__main__":
    unittest.main()

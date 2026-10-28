import html
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
            href = gen_guides.region_href(region)
            if region in gen_guides.MERGED:
                self.assertIn(f'id="{gen_guides.slug(region)}"', table)
                self.assertIn(gen_guides.long(w["deadline"]), table)
                self.assertIn(f'href="#{gen_guides.slug(region)}"', table)
            else:
                text = (ROOT / "docs/guides" / href).read_text(encoding="utf-8")
                self.assertIn(gen_guides.long(w["deadline"]), text)
                self.assertIn(f'href="{href}"', table)
            self.assertIn(f'href="{href}"', hub)

    def test_merged_regions_redirect(self):
        for region in gen_guides.MERGED:
            text = (ROOT / "docs/guides" / (gen_guides.slug(region) + ".html")).read_text(encoding="utf-8")
            self.assertIn('http-equiv="refresh"', text)
            self.assertIn(f'#{gen_guides.slug(region)}"', text)
            self.assertIn(f'<link rel="canonical" href="{gen_guides.BASE}guides/{gen_guides.DEADLINE_PAGE}">', text)

    def test_region_pages_are_mostly_their_own(self):
        """Each standalone region page: at least 40% of its 5-word shingles appear on no other region page."""
        def shingles(p):
            t = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", p.read_text(encoding="utf-8"), flags=re.S)
            w = re.findall(r"[a-z0-9£']+", html.unescape(re.sub(r"<[^>]+>", " ", t)).lower())
            return {" ".join(w[i:i + 5]) for i in range(len(w) - 4)}
        pages = {f: shingles(ROOT / "docs/guides" / f) for f in gen_guides.REGION_FILES}
        for f, sh in pages.items():
            others = set().union(*(v for k, v in pages.items() if k != f))
            self.assertGreaterEqual(len(sh - others) / len(sh), 0.40, f"{f} is too much like the other region pages")

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
            stub = 'http-equiv="refresh"' in page.read_text(encoding="utf-8")
            self.assertEqual(sm.count(loc), 0 if stub else 1, loc)


if __name__ == "__main__":
    unittest.main()

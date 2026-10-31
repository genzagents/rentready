"""Structured data: every page's generated JSON-LD block is current, parses, and carries what the audit asked for."""
import json
import re
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import schema  # noqa: E402


def blocks(t: str) -> list:
    return [json.loads(b) for b in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', t, re.S)]


def types(t: str) -> set:
    out = set()
    for b in blocks(t):
        for node in b.get("@graph", [b]) if isinstance(b, dict) else b:
            out.add(node["@type"])
    return out


class SchemaTest(unittest.TestCase):
    def test_committed_pages_are_current(self):
        for rel, p in schema.pages():
            t = p.read_text(encoding="utf-8")
            self.assertEqual(schema.apply(rel, t), t, f"{rel} is stale: run python3 tools/schema.py")

    def test_every_page_has_the_right_types(self):
        for rel, p in schema.pages():
            t = p.read_text(encoding="utf-8")
            if 'http-equiv="refresh"' in t:
                self.assertNotIn("ld-site", t, rel)
                continue
            ty = types(t)
            self.assertIn("Organization", ty, rel)
            if rel != "docs/index.html":
                self.assertIn("BreadcrumbList", ty, rel)
            if rel.startswith("docs/guides/"):
                self.assertIn("Article", ty, rel)
        self.assertIn("WebApplication", types((ROOT / "docs/index.html").read_text(encoding="utf-8")))

    def test_article_fields_and_breadcrumb_ends_at_page(self):
        t = (ROOT / "docs/guides/landlord-database-fee.html").read_text(encoding="utf-8")
        g = next(b for b in blocks(t) if isinstance(b, dict) and "@graph" in b)["@graph"]
        art = next(n for n in g if n["@type"] == "Article")
        for k in ("headline", "datePublished", "dateModified", "author", "publisher", "image", "mainEntityOfPage"):
            self.assertTrue(art.get(k), k)
        reviewed = re.search(r"reviewed (\d+ \w+ 2026)", t).group(1)
        self.assertEqual(art["dateModified"], datetime.strptime(reviewed, "%d %B %Y").strftime("%Y-%m-%d"))  # from the byline
        crumbs = next(n for n in g if n["@type"] == "BreadcrumbList")["itemListElement"]
        self.assertEqual(crumbs[-1]["item"], art["mainEntityOfPage"])
        self.assertEqual([c["position"] for c in crumbs], list(range(1, len(crumbs) + 1)))

    def test_logo_exists(self):
        self.assertTrue((ROOT / "docs/assets/logo-512.png").stat().st_size > 1000)


if __name__ == "__main__":
    unittest.main()

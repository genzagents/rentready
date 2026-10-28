"""Search basics on every published page: canonical URL, one H1, title and meta description lengths, and internal
links that point at canonical URLs (never ../index.html or guides/index.html)."""
import html
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://genzagents.github.io/rentready/"


def pages():
    for p in sorted((ROOT / "docs").rglob("*.html")):
        t = p.read_text(encoding="utf-8")
        if 'http-equiv="refresh"' in t:  # redirect stubs are checked separately
            continue
        yield p, t


def canonical_for(p: Path) -> str:
    rel = p.relative_to(ROOT / "docs").as_posix()
    if rel.endswith("index.html"):
        rel = rel[: -len("index.html")]
    return BASE + rel


class SeoTest(unittest.TestCase):
    def test_canonical_matches_url(self):
        for p, t in pages():
            m = re.search(r'<link rel="canonical" href="([^"]+)">', t)
            self.assertIsNotNone(m, f"{p.name}: no canonical")
            self.assertEqual(m.group(1), canonical_for(p), p.name)

    def test_title_h1_and_description(self):
        for p, t in pages():
            title = html.unescape(re.search(r"<title>(.*?)</title>", t).group(1))
            self.assertLessEqual(len(title), 70, f"{p.name}: title {len(title)} chars")
            self.assertEqual(len(re.findall(r"<h1[ >]", t)), 1, f"{p.name}: one H1")
            m = re.search(r'<meta name="description" content="(.*?)">', t)
            self.assertIsNotNone(m, f"{p.name}: no meta description")
            self.assertLessEqual(len(html.unescape(m.group(1))), 160, f"{p.name}: description too long")

    def test_no_links_to_non_canonical_index(self):
        for p, t in pages():
            for href in re.findall(r'href="([^"]+)"', t):
                self.assertFalse(re.search(r"(^|/)index\.html(#|$)", href), f"{p.name} links to {href}")

    def test_search_terms_present(self):
        main = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn("PRS Database", re.search(r"<h1>(.*?)</h1>", main).group(1))
        hub = (ROOT / "docs/guides/index.html").read_text(encoding="utf-8")
        self.assertIn("PRS Database", hub)


if __name__ == "__main__":
    unittest.main()

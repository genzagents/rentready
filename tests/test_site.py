"""Trust and layout: about/privacy/terms/developers pages, footer and byline on every page, tool first on the main
page with developer content moved out, honest paid-watch wording, and one shared stylesheet with readable, non-blue colours."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def pages():
    for p in sorted(DOCS.rglob("*.html")):
        t = p.read_text(encoding="utf-8")
        if 'http-equiv="refresh"' not in t:
            yield p, t


class SiteTest(unittest.TestCase):
    def test_trust_pages_exist_and_say_what_they_must(self):
        about = (DOCS / "about.html").read_text(encoding="utf-8")
        for s in ("GenZAgents", "Manraj Singh Dhillon", "London", "not legal advice", "github.com/genzagents/rentready/issues"):
            self.assertIn(s.lower(), about.lower(), s)
        privacy = (DOCS / "privacy.html").read_text(encoding="utf-8")
        for s in ("in your browser", "postcodes.io", "GitHub Pages", "local storage"):
            self.assertIn(s, privacy)
        self.assertIn("Not legal advice", (DOCS / "terms.html").read_text(encoding="utf-8"))

    def test_footer_on_every_page(self):
        for p, t in pages():
            for href in ("about.html", "privacy.html", "terms.html", "developers.html", "github.com/genzagents/rentready/issues"):
                self.assertIn(href, t[t.find('<footer'):], f"{p.name} footer lacks {href}")

    def test_byline_and_sources_on_every_guide(self):
        for p, t in pages():
            if p.parent.name != "guides":
                continue
            self.assertRegex(t, r"Written by <a [^>]*>GenZAgents</a>, reviewed \d+ \w+ 2026", p.name)
            self.assertIn('id="sources"', t, p.name)

    def test_main_page_tool_first_developer_content_moved(self):
        t = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertLess(t.index('<section id="tool"'), t.index("What the landlord database is"))
        for dev in ("curl -sL", "pip install", "claude plugin", "uses: genzagents/rentready"):
            self.assertNotIn(dev, t)
            self.assertIn(dev, (DOCS / "developers.html").read_text(encoding="utf-8"))
        self.assertIn('data-label="EICR next inspection due"', t)
        self.assertIn("@media (max-width:520px){.fields{grid-template-columns:minmax(0,1fr)}", (DOCS / "assets" / "site.css").read_text(encoding="utf-8"))

    def test_paid_watch_is_worded_honestly(self):
        t = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn("Payments are not live yet", t)
        self.assertNotIn("checkout opens shortly", t)

    def test_every_page_uses_the_shared_stylesheet(self):
        for p, t in pages():
            rel = "../" if p.parent.name == "guides" else ""
            self.assertIn(f'<link rel="stylesheet" href="{rel}assets/site.css">', t, p.name)
            self.assertNotIn("<style>", t, p.name)
            self.assertIn('class="site-head"', t, p.name)

    def test_colours_readable_and_not_blue(self):
        css = (DOCS / "assets" / "site.css").read_text(encoding="utf-8")
        for old in ("#0645ad", "#8ab4f8", "#1f6feb", "#58a6ff"):
            self.assertNotIn(old, css)
        self.assertIn("--brand:#0e5a44", css)
        self.assertIn("prefers-color-scheme:dark", css)
        self.assertIn("a{color:var(--brand-text)", css)

if __name__ == "__main__":
    unittest.main()

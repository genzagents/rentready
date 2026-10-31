"""Which-properties guide: the in-page check (decide() in the page, run under node) must give the same answer as
the table for every kind of let, so the quick check and the written guide cannot drift apart."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "docs/guides/which-properties-to-register.html"
BASE = {"where": "england", "let": "let", "who": "home", "rent": "normal"}
# answer -> (table row text it must agree with, expected badge)
CASES = [
    ({}, "Ordinary let to people who live there as their home", "yes"),
    ({"let": "empty"}, "Empty, between tenancies or not yet marketed", "later"),
    ({"who": "company"}, "Company let (a company is the tenant)", "no"),
    ({"who": "holiday"}, "Holiday let", "no"),
    ({"who": "resident"}, "Lodger in your home", "no"),
    ({"who": "student"}, "Student let by a university", "no"),
    ({"who": "social"}, "Social housing (council or housing association landlord)", "no"),
    ({"who": "sea"}, "Supported exempt accommodation", "no"),
    ({"rent": "high"}, "Rent over £100,000 a year", "no"),
    ({"rent": "low"}, "No rent, or £250 a year or less", "no"),
    ({"where": "wales"}, "Property in Wales, Scotland or Northern Ireland", "no"),
    ({"where": "scotland"}, "Property in Wales, Scotland or Northern Ireland", "no"),
    ({"where": "ni"}, "Property in Wales, Scotland or Northern Ireland", "no"),
]
BADGE = {"yes": "who-y", "later": "who-n", "no": "who-n"}


class WhoGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_check_agrees_with_table(self):
        logic = re.search(r'<script id="who-logic">(.*?)</script>', self.t, re.S).group(1)
        answers = [dict(BASE, **c) for c, _, _ in CASES]
        out = subprocess.run(["node", "-e", logic + f"console.log(JSON.stringify({json.dumps(answers)}.map(decide)))"],
                             capture_output=True, text=True, check=True).stdout
        for (c, row, want), got in zip(CASES, json.loads(out)):
            self.assertEqual(got["v"], want, c)
            m = re.search(r"<tr><td>" + re.escape(row) + r".*?</td><td><span class=\"(who-[yn])\">", self.t)
            self.assertIsNotNone(m, row)
            self.assertEqual(m.group(1), BADGE[want], row)

    def test_linked_and_in_sitemap(self):
        url = "https://genzagents.github.io/rentready/guides/which-properties-to-register.html"
        self.assertIn(url, (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))
        for g in ("index.html", "landlord-database-registration.html"):
            self.assertIn('href="which-properties-to-register.html"', (ROOT / "docs/guides" / g).read_text(encoding="utf-8"))

    def test_sources_cover_every_citation(self):
        for src in ("ukpga/2025/26/section/63", "ukpga/2025/26/section/82", "ukdsi/2026/9780348286861",
                    "ukpga/1988/50/section/1", "ukpga/1988/50/schedule/1", "housinghub.campaign.gov.uk"):
            self.assertIn(src, self.t.split('id="sources"')[1])


if __name__ == "__main__":
    unittest.main()

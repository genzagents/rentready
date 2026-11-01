"""'HMRC signed me up' guide: the committed page is what the generator writes, the quarterly dates are MTD's, and the
in-page verdict (run under node) gives each case the right answer and the right overdue and next updates."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_signedup as g  # noqa: E402
import schema  # noqa: E402

REL = "docs/guides/hmrc-signed-me-up-making-tax-digital.html"
PAGE = ROOT / REL


class SignedUpGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply(REL, g.build()))

    def test_quarters_are_mtd_deadlines(self):
        self.assertEqual([d for d, _ in g.QUARTERS], ["2026-08-07", "2026-11-07", "2027-02-07", "2027-05-07"])
        self.assertIn("over £50,000", self.t)
        self.assertIn("31 January 2028", self.t)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_verdict(self):
        logic = re.search(r'<script id="su-logic">(.*?)</script>', self.t, re.S).group(1)
        cases = [
            ({"prop": "60,000", "se": "", "ceased": "no", "ex": "none"}, "2026-11-01"),
            ({"prop": "£30000", "se": "25000", "ceased": "no", "ex": "none"}, "2027-03-01"),
            ({"prop": "40000", "se": "", "ceased": "no", "ex": "none"}, "2026-11-01"),
            ({"prop": "25000", "se": "", "ceased": "no", "ex": "none"}, "2026-11-01"),
            ({"prop": "15000", "se": "", "ceased": "no", "ex": "none"}, "2026-11-01"),
            ({"prop": "90000", "se": "", "ceased": "before", "ex": "none"}, "2026-11-01"),
            ({"prop": "90000", "se": "", "ceased": "after", "ex": "none"}, "2026-11-01"),
            ({"prop": "90000", "se": "", "ceased": "no", "ex": "auto"}, "2026-11-01"),
            ({"prop": "90000", "se": "", "ceased": "no", "ex": "digital"}, "2026-11-01"),
            ({"prop": "", "se": "", "ceased": "no", "ex": "none"}, "2026-08-01"),
            ({"prop": "50000", "se": "", "ceased": "no", "ex": "none"}, "2026-11-01"),
        ]
        js = logic + "console.log(JSON.stringify(%s.map(function(c){return verdict(c[0],c[1])})));" % json.dumps(cases)
        r = json.loads(subprocess.run(["node", "-e", js], capture_output=True, check=True).stdout)
        self.assertEqual([x["code"] for x in r],
                         ["in", "in", "under-2027", "under-2028", "under-exempt", "ceased-before", "ceased-after",
                          "exempt-auto", "exempt-apply", "in", "under-2027"])
        self.assertEqual([e["d"] for e in r[0]["overdue"]], ["2026-08-07"])
        self.assertEqual(r[0]["next"]["d"], "2026-11-07")
        self.assertEqual(r[1]["q"], 55000)
        self.assertEqual(r[1]["next"]["d"], "2027-05-07")
        self.assertIsNone(r[9]["q"])
        self.assertEqual(r[9]["overdue"], [])
        self.assertEqual(r[9]["next"]["d"], "2026-08-07")
        self.assertIsNone(r[6]["next"])
        self.assertEqual(r[2]["overdue"], [])

    def test_linked_and_in_sitemap(self):
        self.assertIn(g.URL, (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))
        for p in ("index.html", "landlord-deadlines-calendar.html"):
            self.assertIn('href="hmrc-signed-me-up-making-tax-digital.html"',
                          (ROOT / "docs/guides" / p).read_text(encoding="utf-8"))
        self.assertIn("RM.mtd(", self.t)


if __name__ == "__main__":
    unittest.main()

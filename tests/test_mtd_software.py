"""MTD software finder: the committed page is what the generator writes from HMRC's data, the headline counts match the
data, and the in-page filter (run under node) agrees with the counts and honours each filter."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_mtd_software as g  # noqa: E402
import schema  # noqa: E402

REL = "docs/guides/making-tax-digital-software-for-landlords.html"
PAGE = ROOT / REL


class MtdSoftwareGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")
        self.ps = g.products()
        self.s = g.stats(self.ps)

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply(REL, g.build()))

    def test_data_is_whole_list(self):
        d = g.load()
        self.assertEqual(d["count"], len(d["products"]))
        self.assertGreater(len(self.ps), 100)
        self.assertEqual(len({p["n"] for p in self.ps}), len(self.ps))
        for p in self.ps:
            self.assertEqual(set(p["f"]), {c for c, _ in g.FEATURES})
            self.assertTrue(set(p["f"].values()) <= {"R", "D", "N"})

    def test_headline_counts_on_page(self):
        s = self.s
        self.assertEqual(s["uk"] - s["uk_no_return"], s["full"])
        self.assertIn(f"HMRC recognises {s['total']} products", self.t)
        self.assertIn(f"only {s['full']} of those", self.t)
        self.assertEqual(len(s["free_names"]), s["free_full"])
        for n in s["free_names"]:
            self.assertIn(n.replace("&", "&amp;"), self.t)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_filter(self):
        logic = re.search(r'<script id="sw-logic">(.*?)</script>', self.t, re.S).group(1)
        data = json.loads(re.search(r'<script id="sw-data" type="application/json">(.*?)</script>', self.t, re.S)
                          .group(1).replace("<\\/", "</"))
        cases = [{}, {"ret": True}, {"ret": True, "free": True}, {"ret": True, "how": "bridge"},
                 {"ret": True, "other": ["paye", "cgt"]}, {"ret": True, "other": ["paye", "cgt"], "soon": True},
                 {"ret": True, "free": True, "other": ["paye", "cgt"]}]
        js = logic + "var P=%s;console.log(JSON.stringify(%s.map(function(o){return P.filter(function(p){return match(p,o)}).length})));" % (
            json.dumps(data), json.dumps(cases))
        r = json.loads(subprocess.run(["node", "-e", js], capture_output=True, check=True).stdout)
        s, ps = self.s, self.ps
        full = [p for p in ps if p["f"]["uk"] == "R" and p["ret"]]
        self.assertEqual(r[0], s["uk"])
        self.assertEqual(r[1], s["full"])
        self.assertEqual(r[2], s["free_full"])
        self.assertEqual(r[3], s["bridge_full"])
        self.assertEqual(r[4], sum(p["f"]["paye"] == "R" and p["f"]["cgt"] == "R" for p in full))
        self.assertEqual(r[5], sum(p["f"]["paye"] in "RD" and p["f"]["cgt"] in "RD" for p in full))
        self.assertEqual(r[6], s["free_full_paye_cgt"])
        self.assertLessEqual(r[4], r[5])


if __name__ == "__main__":
    unittest.main()

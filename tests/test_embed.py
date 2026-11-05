"""Deadline card for other websites (docs/embed.js): same windows as rentready.ROLLOUT, right wording on each side of
a region's window, and an embed page whose snippet keeps a plain link."""
import json, shutil, subprocess, unittest
from pathlib import Path

import rentready as rr

ROOT = Path(__file__).resolve().parent.parent
JS = str(ROOT / "docs" / "embed.js")
NODE = shutil.which("node")
RUN = "const E=require(process.argv[1]);let i=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
      "console.log(JSON.stringify(i.map(([f,a])=>f==='status'?E.status(E.find(a[0]),E.day(a[1])):f==='rollout'?E.ROLLOUT:E[f](...a))))"


@unittest.skipUnless(NODE, "node not installed")
class EmbedTest(unittest.TestCase):
    def call(self, *calls):
        out = subprocess.run([NODE, "-e", RUN, JS], input=json.dumps(calls), capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_windows_match_rollout_and_guides_exist(self):
        rows, = self.call(["rollout", []])
        self.assertEqual({r[0]: (r[2], r[3]) for r in rows},
                         {n: (w["opens"], w["deadline"]) for n, w in rr.ROLLOUT.items()})
        for r in rows:
            self.assertTrue((ROOT / "docs/guides" / r[1]).exists(), r[1])

    def test_status_wording(self):
        before, early, open_, late = self.call(["status", ["West Midlands", "2026-11-05"]],
                                               ["status", ["London", "2026-11-05"]],
                                               ["status", ["West Midlands", "2027-03-13"]],
                                               ["status", ["West Midlands", "2027-03-15"]])
        self.assertEqual(before["head"], "West Midlands landlords: register by 14 March 2027")
        self.assertEqual((before["state"], before["big"]), ("soon", "129"))
        self.assertIn("Registration opens 15 December 2026", before["sub"])
        self.assertIn("register early from 15 December 2026", early["sub"])
        self.assertEqual((open_["state"], open_["big"], open_["unit"]), ("open", "1", "day left"))
        self.assertEqual(late["state"], "late")

    def test_find_aliases_and_unknown(self):
        a, b, c = self.call(["find", ["yorkshire & humber"]], ["find", ["  london "]], ["find", ["Wales"]])
        self.assertEqual(a[0], "Yorkshire and The Humber")
        self.assertEqual(b[0], "London")
        self.assertIsNone(c)


class EmbedPageTest(unittest.TestCase):
    def test_page_links_script_and_is_in_sitemap(self):
        t = (ROOT / "docs/embed.html").read_text(encoding="utf-8")
        self.assertIn('<script src="embed.js"></script>', t)
        self.assertIn('class="rentready-deadline"', t)
        self.assertIn("https://genzagents.github.io/rentready/embed.js", t)
        self.assertIn("https://genzagents.github.io/rentready/embed.html",
                      (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

"""Deadlines calendar guide: the region windows match rentready's rollout, the committed page is what the generator
writes, and the in-page picker (run under node) gives each income band and region the right dates."""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import gen_deadlines as g  # noqa: E402
import rentready as rr  # noqa: E402
import schema  # noqa: E402

PAGE = ROOT / "docs/guides/landlord-deadlines-calendar.html"


class DeadlinesGuideTest(unittest.TestCase):
    def setUp(self):
        self.t = PAGE.read_text(encoding="utf-8")

    def test_regions_match_rollout(self):
        self.assertEqual({n: (s, e) for n, _, s, e in g.REGIONS},
                         {n: (w["opens"], w["deadline"]) for n, w in rr.ROLLOUT.items()})

    def test_page_is_generated(self):
        self.assertEqual(self.t, schema.apply("docs/guides/landlord-deadlines-calendar.html", g.build()))

    def test_mtd_facts(self):
        for s in ("6 April 2026 over £50,000", "6 April 2027 over £30,000", "6 April 2028 over £20,000"):
            self.assertIn(s, self.t)
        quarters = [d for d, t, _, _ in g.EVENTS if t.startswith("MTD quarterly update")]
        self.assertTrue(all(d[5:] in ("02-07", "05-07", "08-07", "11-07") for d in quarters))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_picker(self):
        logic = re.search(r'<script id="dl-logic">(.*?)</script>', self.t, re.S).group(1)
        cases = [(["London"], "over50"), (["West Midlands", "South West"], "30to50"), ([], "under20"),
                 (["North East"], "20to30")]
        js = logic + "console.log(JSON.stringify(%s.map(function(c){return pick(c[0],c[1],'2026-11-01')})));" \
            % json.dumps(cases) + "console.log(ics(pick(['London'],'over50',''),'20261101T000000Z'))"
        out = subprocess.run(["node", "-e", js], capture_output=True, check=True).stdout.decode("utf-8")  # keep CRLF
        first, cal = out.split("\n", 1)
        london50, wm30, none20, ne20 = json.loads(first)
        d = lambda evs: {e["d"] for e in evs}
        self.assertIn("2026-11-07", d(london50))
        self.assertIn("2027-10-14", d(london50))
        self.assertNotIn("2027-03-14", d(london50))
        self.assertNotIn("2026-11-07", d(wm30))
        self.assertIn("2027-08-07", d(wm30))
        self.assertTrue({"2027-03-14", "2027-11-14"} <= d(wm30))
        self.assertEqual({e["w"] for e in none20}, {"all"})
        self.assertIn("2028-04-06", d(ne20))
        self.assertNotIn("2027-08-07", d(ne20))
        self.assertEqual(cal.count("BEGIN:VEVENT"), len(london50))
        self.assertIn("DTSTART;VALUE=DATE:20271014", cal)
        self.assertIn("TRIGGER:-P14D", cal)
        self.assertTrue(cal.startswith("BEGIN:VCALENDAR\r\n"))

    def test_table_lists_every_event(self):
        for d, title, _, _ in g.EVENTS:
            self.assertIn(f'<td class="tl-d">{g.nice(d)}</td><td><strong>{title}</strong>', self.t.replace("&#x27;", "'"))

    def test_linked_and_in_sitemap(self):
        self.assertIn(g.URL, (ROOT / "docs/sitemap.xml").read_text(encoding="utf-8"))
        for p in ("index.html", "landlord-database-deadline-by-region.html"):
            self.assertIn('href="landlord-deadlines-calendar.html"', (ROOT / "docs/guides" / p).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

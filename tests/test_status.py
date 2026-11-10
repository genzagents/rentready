"""Regulations status page: parsed from Parliament's record, steps marked in order, rebuilt page matches the committed one."""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_status as gs  # noqa: E402

RECORD = (ROOT / "tools/data/procedure.html").read_text(encoding="utf-8")


def item(d, *steps, link=None):
    return {"date": d, "steps": list(steps), "link": link}


class StatusTest(unittest.TestCase):
    def test_parse_saved_record(self):
        items = gs.parse(RECORD)
        self.assertGreaterEqual(len(items), 13)
        self.assertEqual(items[0]["date"], date(2026, 9, 9))
        self.assertEqual(items[0]["steps"], ["Instrument created"])
        self.assertTrue(all(it["steps"] for it in items))

    def test_saved_record_status(self):
        st = gs.status(gs.parse(RECORD), date(2026, 11, 1))
        self.assertEqual(set(st["done"]), {"laid", "jcsi", "slsc", "dlc", "gc"})
        self.assertEqual(st["lords_vote"][0], date(2026, 11, 4))
        self.assertEqual(st["trouble"], [])
        self.assertIn("neither House has voted", gs.headline(st))
        self.assertIn("4 November 2026", gs.headline(st))
        # after the listed day passes with no vote recorded, the page stops claiming a date
        self.assertIsNone(gs.status(gs.parse(RECORD), date(2026, 11, 5))["lords_vote"])

    def test_votes_and_made(self):
        base = gs.parse(RECORD)
        lords = base + [item(date(2026, 11, 4), "Motion to approve the instrument approved (House of Lords)")]
        st = gs.status(lords, date(2026, 11, 4))
        self.assertIsNone(st["lords_vote"])
        self.assertTrue(gs.headline(st).startswith("Not yet final. The House of Lords approved"))
        both = lords + [item(date(2026, 11, 10), "Motion to approve the instrument approved (House of Commons)")]
        self.assertTrue(gs.headline(gs.status(both, date(2026, 11, 10))).startswith("Almost."))
        made = both + [item(date(2026, 11, 12), "Instrument made")]
        st = gs.status(made, date(2026, 11, 12))
        self.assertTrue(gs.headline(st).startswith("Yes."))
        self.assertEqual(st["latest"], date(2026, 11, 12))
        page = gs.build(made, date(2026, 11, 12))
        self.assertIn("reviewed 12 November 2026", page)
        self.assertNotIn("Waits on the vote", page)

    def test_is_it_live(self):
        base = gs.parse(RECORD)
        st = gs.status(base, date(2026, 11, 2))
        self.assertEqual(gs.live(st, date(2026, 11, 2))[0], "Not yet.")
        self.assertIn("still need Parliament", gs.live(st, date(2026, 11, 2))[1])
        both = gs.status(base + [item(date(2026, 11, 4), "Motion to approve the instrument approved (House of Lords)"),
                                 item(date(2026, 11, 4), "Motion to approve the instrument approved (House of Commons)")], date(2026, 11, 10))
        self.assertIn("Both Houses of Parliament have approved", gs.live(both, date(2026, 11, 10))[1])
        self.assertNotIn("still need Parliament", gs.live(both, date(2026, 11, 10))[1])
        made = gs.status(base + [item(date(2026, 11, 12), "Instrument made")], date(2026, 11, 12))
        self.assertIn("regulations are law", gs.live(made, date(2026, 11, 12))[1])
        self.assertEqual(gs.live(made, date(2026, 12, 15))[0], "It should be open.")
        page = gs.build(base, date(2026, 11, 2))
        self.assertIn("<title>Is the PRS Database live yet?", page)
        self.assertIn("Is it live? Not yet.", page)

    def test_deferred_commons_vote(self):
        items = gs.parse(RECORD) + [
            item(date(2026, 11, 3), "Question on motion to approve the instrument put (House of Commons)",
                 "Decision on motion to approve the instrument deferred (House of Commons)"),
            item(date(2026, 11, 4), "Motion to approve the instrument approved (House of Lords)")]
        st = gs.status(items, date(2026, 11, 4))
        self.assertEqual(st["deferred"], date(2026, 11, 4))  # Tuesday's deferral is voted on Wednesday
        self.assertIn("deferred division on 4 November 2026", gs.headline(st))
        self.assertIn("deferred vote 4 November 2026", gs.build(items, date(2026, 11, 4)))
        done = items + [item(date(2026, 11, 4), "Division: 320 ayes, 100 noes",
                             "Motion to approve the instrument approved (House of Commons)")]
        st = gs.status(done, date(2026, 11, 5))
        self.assertIsNone(st["deferred"])
        self.assertTrue(gs.headline(st).startswith("Almost."))

    def test_votes_from_hansard_and_divisions(self):
        debates = [
            {"date": "2026-10-28", "house": "Lords", "id": "A", "items": [{"Value": "Motion to Consider"}, {"Value": "Motion agreed."}]},
            {"date": "2026-11-04", "house": "Lords", "id": "B", "items": [{"Value": "Motion to Approve"}, {"Value": "<p>Motion agreed.</p>"}]}]
        out = gs.votes_from(debates, [{"date": "2026-11-04", "id": 9, "ayes": 300, "noes": 120}])
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["steps"], ["Motion to approve the instrument approved (House of Lords)"])
        self.assertIn("/Lords/2026-11-04/debates/B/", out[0]["link"])
        self.assertIn("Motion to approve the instrument approved (House of Commons)", out[1]["steps"])
        lost = gs.votes_from([], [{"date": "2026-11-04", "id": 9, "ayes": 100, "noes": 120}])
        self.assertIn("not approved", lost[0]["steps"][1])

    def test_trouble_is_shown(self):
        bad = gs.parse(RECORD) + [item(date(2026, 11, 4), "Motion to approve the instrument not approved (House of Lords)")]
        page = gs.build(bad, date(2026, 11, 4))
        self.assertIn("Something unusual is in the record", page)

    def test_committed_page_is_current(self):
        committed = gs.OUT.read_text(encoding="utf-8")
        # the page depends on the build day only through a listed vote date, so some day since launch must reproduce it
        days = (gs.FIRST + timedelta(n) for n in range((date.today() - gs.FIRST).days + 2))
        builds = {gs.apply("docs/guides/landlord-database-regulations-status.html", gs.build(gs.load_items(), d)) for d in days}
        self.assertIn(committed, builds, "run python3 tools/gen_status.py")

    def test_linked_from_guides(self):
        for g in ("index.html", "landlord-database-registration.html", "landlord-database-deadline-by-region.html"):
            self.assertIn("landlord-database-regulations-status.html", (ROOT / "docs/guides" / g).read_text(encoding="utf-8"), g)


if __name__ == "__main__":
    unittest.main()

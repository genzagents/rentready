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

    def test_trouble_is_shown(self):
        bad = gs.parse(RECORD) + [item(date(2026, 11, 4), "Motion to approve the instrument not approved (House of Lords)")]
        page = gs.build(bad, date(2026, 11, 4))
        self.assertIn("Something unusual is in the record", page)

    def test_committed_page_is_current(self):
        committed = gs.OUT.read_text(encoding="utf-8")
        # the page depends on the build day only through a listed vote date, so some day since launch must reproduce it
        days = (gs.FIRST + timedelta(n) for n in range((date.today() - gs.FIRST).days + 2))
        builds = {gs.apply("docs/guides/landlord-database-regulations-status.html", gs.build(gs.parse(RECORD), d)) for d in days}
        self.assertIn(committed, builds, "run python3 tools/gen_status.py")

    def test_linked_from_guides(self):
        for g in ("index.html", "landlord-database-registration.html", "landlord-database-deadline-by-region.html"):
            self.assertIn("landlord-database-regulations-status.html", (ROOT / "docs/guides" / g).read_text(encoding="utf-8"), g)


if __name__ == "__main__":
    unittest.main()

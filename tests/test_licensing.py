"""Council licensing shown next to each property in the browser check (docs/data/licensing.json), and the fee guide's
'you pay both' counts, both from tools/councils.json."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_licensing  # noqa: E402


class LicensingTest(unittest.TestCase):
    def test_data_file_is_current(self):
        on_disk = json.loads((ROOT / "docs" / "data" / "licensing.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, gen_licensing.build(), "run python3 tools/gen_licensing.py")

    def test_keyed_by_ons_names_postcodes_io_returns(self):
        cs = gen_licensing.build()["councils"]
        for name in ("Birmingham", "Bristol, City of", "Kingston upon Hull, City of", "Herefordshire, County of"):
            self.assertIn(name, cs)
        for c in cs.values():
            for k in ("selective", "additional"):
                if c[k]["status"] in gen_licensing.LIVE:
                    self.assertTrue(c[k]["source"].startswith("http"))

    def test_check_uses_it(self):
        page = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("data/licensing.json", page)
        self.assertIn("admin_district", (ROOT / "docs" / "rentready.js").read_text(encoding="utf-8"))

    def test_fee_guide_counts_match(self):
        n = gen_licensing.build()["counts"]
        t = (ROOT / "docs" / "guides" / "landlord-database-fee.html").read_text(encoding="utf-8")
        self.assertIn(f"{n['either']} councils have a selective or additional licensing scheme", t)
        self.assertIn(f"{n['selective']} with selective licensing and {n['additional']} with additional HMO licensing", t)
        self.assertIn(f"of England's {n['councils']} local housing authorities", t)
        self.assertNotIn("not open yet", t)


if __name__ == "__main__":
    unittest.main()

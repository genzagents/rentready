"""The public numbers page is generated from docs/data/numbers.json and stays current."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import gen_numbers  # noqa: E402


class NumbersTest(unittest.TestCase):
    def test_committed_page_is_current(self):
        data = json.loads(gen_numbers.DATA.read_text(encoding="utf-8"))
        want = gen_numbers.apply("docs/numbers.html", gen_numbers.build(data))
        self.assertEqual(gen_numbers.OUT.read_text(encoding="utf-8"), want, "run python3 tools/gen_numbers.py")

    def test_newest_week_first_and_linked(self):
        data = json.loads(gen_numbers.DATA.read_text(encoding="utf-8"))
        newest = max(w["date"] for w in data["weeks"])
        self.assertIn(gen_numbers.nice(newest), gen_numbers.OUT.read_text(encoding="utf-8").split("<h2>")[0])
        self.assertIn("numbers.html", (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8"))
        self.assertIn("numbers.html", (ROOT / "docs" / "about.html").read_text(encoding="utf-8"))

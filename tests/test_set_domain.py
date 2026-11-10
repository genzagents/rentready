"""Domain move: the rewrite covers every form of the old address and the dry run changes nothing."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import set_domain  # noqa: E402


class SetDomainTest(unittest.TestCase):
    def test_rewrite_forms(self):
        t = ('<link rel="canonical" href="https://genzagents.github.io/rentready/press.html">'
             '<p>genzagents.github.io/rentready</p> UID:rr-dl-1@genzagents.github.io '
             '<a href="https://genzagents.github.io/citable/">')
        out = set_domain.rewrite(t, "landlords.genzagents.com")
        self.assertIn('href="https://landlords.genzagents.com/press.html"', out)
        self.assertIn("<p>landlords.genzagents.com</p>", out)
        self.assertIn("@landlords.genzagents.com", out)
        self.assertIn("https://genzagents.github.io/citable/", out)  # sibling sites stay put

    @unittest.skipIf((ROOT / "docs/CNAME").exists(), "already moved")
    def test_plan_covers_site_and_workflow(self):
        changes = {p.relative_to(ROOT).as_posix(): n for p, (n, _) in set_domain.plan("x.example.com").items()}
        for f in ("docs/index.html", "docs/sitemap.xml", "pyproject.toml", "server.json",
                  ".github/workflows/indexnow.yml", "rentready/hosted.py"):
            self.assertIn(f, changes)
        self.assertGreater(sum(changes.values()), 500)

    @unittest.skipIf((ROOT / "docs/CNAME").exists(), "already moved")
    def test_dry_run_writes_nothing(self):
        before = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
        subprocess.run([sys.executable, str(ROOT / "tools/set_domain.py"), "x.example.com"],
                       cwd=ROOT, capture_output=True, check=True)
        after = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout
        self.assertEqual(before, after)
        self.assertFalse((ROOT / "docs/CNAME").exists())


if __name__ == "__main__":
    unittest.main()

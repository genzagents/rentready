"""Set each hand-written page's <lastmod> in docs/sitemap.xml to the day its file last changed (git), so crawlers
re-read what changed. Region guides keep the date tools/gen_guides.py gives them. Needs full git history: run locally
before committing (a file with uncommitted changes counts as changed today), then python3 tools/gen_guides.py."""
from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://genzagents.github.io/rentready/"


def changed(rel: str) -> str:
    dirty = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if dirty:
        return date.today().isoformat()
    return subprocess.run(["git", "log", "-1", "--format=%cs", "--", rel], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def fix(line: str) -> str:
    m = re.search(r"<loc>" + re.escape(BASE) + r"([^<]*)</loc><lastmod>([^<]*)</lastmod>", line)
    if not m:
        return line
    rel = "docs/" + (m.group(1) + "index.html" if m.group(1).endswith("/") or not m.group(1) else m.group(1))
    if not (ROOT / rel).exists():
        return line
    when = max(m.group(2), changed(rel))  # never move a date backwards
    return line.replace(f"<lastmod>{m.group(2)}</lastmod>", f"<lastmod>{when}</lastmod>")


if __name__ == "__main__":
    p = ROOT / "docs" / "sitemap.xml"
    p.write_text("\n".join(fix(line) for line in p.read_text(encoding="utf-8").split("\n")), encoding="utf-8")

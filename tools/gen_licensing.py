"""Writes docs/data/licensing.json from tools/councils.json: one entry per council, keyed by its ONS name (the name
postcodes.io returns as admin_district), so the browser check can show the council's licensing schemes next to
each property. Run: python3 tools/gen_licensing.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data" / "licensing.json"
LIVE = ("in force", "designated")
KEEP = ("status", "area", "starts", "until", "note", "source")


def build() -> dict:
    data = json.loads((ROOT / "tools" / "councils.json").read_text(encoding="utf-8"))
    councils, checked = {}, set()
    for region, r in data.items():
        if region.startswith("_"):
            continue
        checked.add(r["checked"])
        for name, e in r["councils"].items():
            councils[name] = {"region": region, "checked": r["checked"],
                              **{k: {f: v[f] for f in KEEP if f in v} for k, v in e.items()}}
    live = lambda k: sum(1 for c in councils.values() if c[k]["status"] in LIVE)
    return {"about": "Selective (Housing Act 2004 Part 3) and additional HMO (Part 2) licensing per council, each read on the "
                     "council's own website (source). 'none found' is not a guarantee; 'not verified' means the website "
                     "could not be read. Generated from tools/councils.json.",
            "checked": max(checked), "councils": councils,
            "counts": {"councils": len(councils), "selective": live("selective"), "additional": live("additional"),
                       "either": sum(1 for c in councils.values() if any(c[k]["status"] in LIVE for k in ("selective", "additional")))}}


if __name__ == "__main__":
    d = build()
    OUT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(OUT, d["counts"])

"""Refresh the EPC data story's inputs from the government's live table D4(b) (an .ods file; stdlib only, no pandas).
Download "Table D4(b)" from the live tables page (gen_epc_story.TABLE_URL), then run
`python3 tools/extract_d4b.py D4B-_Domestic_Properties.ods` and `python3 tools/gen_epc_story.py`.

Writes the "Rental" column for England's nine regions (tools/data/epc-rental-lodgements-by-region.csv) and for every
English council (tools/data/epc-rental-lodgements-by-council.csv). The council sheet keeps the old district codes for
quarters before the 2019-2023 reorganisations, so those districts are added into today's council, and each council
is placed in its region by tools/councils.json."""
import csv
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools/data"
T = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
P = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p"

# Districts abolished since 2019, by the council that replaced them.
SUCCESSOR = {
    "Aylesbury Vale": "Buckinghamshire", "Chiltern": "Buckinghamshire", "South Bucks": "Buckinghamshire",
    "Wycombe": "Buckinghamshire",
    "Corby": "North Northamptonshire", "East Northamptonshire": "North Northamptonshire",
    "Kettering": "North Northamptonshire", "Wellingborough": "North Northamptonshire",
    "Daventry": "West Northamptonshire", "Northampton": "West Northamptonshire",
    "South Northamptonshire": "West Northamptonshire",
    "Allerdale": "Cumberland", "Carlisle": "Cumberland", "Copeland": "Cumberland",
    "Barrow-in-Furness": "Westmorland and Furness", "Eden": "Westmorland and Furness",
    "South Lakeland": "Westmorland and Furness",
    "Craven": "North Yorkshire", "Hambleton": "North Yorkshire", "Harrogate": "North Yorkshire",
    "Richmondshire": "North Yorkshire", "Ryedale": "North Yorkshire", "Scarborough": "North Yorkshire",
    "Selby": "North Yorkshire",
    "Mendip": "Somerset", "Sedgemoor": "Somerset", "Somerset West and Taunton": "Somerset",
    "South Somerset": "Somerset",
}


def sheets(path):
    """{sheet name: [row as a list of cell strings]}, repeated cells expanded (capped), empty rows dropped."""
    root = ET.fromstring(zipfile.ZipFile(path).read("content.xml"))
    out = {}
    for t in root.iter(T + "table"):
        rows = []
        for r in t.iter(T + "table-row"):
            cells = []
            for c in r:
                v = " ".join("".join(p.itertext()) for p in c.iter(P))
                cells += [v] * min(int(c.get(T + "number-columns-repeated", "1")), 50)
            while cells and cells[-1] == "":
                cells.pop()
            if cells:
                rows.append(cells)
        out[t.get(T + "name")] = rows
    return out


def table(rows):
    """The rows under the header row (the one starting with the given column name), as dicts."""
    i = next(i for i, r in enumerate(rows) if "Rental" in r)
    head = rows[i]
    return [dict(zip(head, r)) for r in rows[i + 1:]]


def num(s):
    return int(s.replace(",", "") or 0)


def extract(path):
    s = sheets(path)
    regions = json.loads((ROOT / "tools/councils.json").read_text(encoding="utf-8"))
    region_of = {c: r for r, v in regions.items() if r != "_about" for c in v["councils"]}
    by_region = [(r["Region"], r["Quarter"], num(r["Rental"])) for r in table(s["D4B_by_Region"])
                 if r["Region"] in regions and r.get("Quarter")]
    merged = {}
    for r in table(s["D4B_by_LA"]):
        if not r.get("Local Authority Code", "").startswith("E"):
            continue
        name = SUCCESSOR.get(r["Region"], r["Region"])  # this sheet's "Region" column holds the council name
        if name not in region_of:
            raise SystemExit(f"council {name!r} ({r['Local Authority Code']}) is not in tools/councils.json")
        key = (region_of[name], name, r["Quarter"])
        merged[key] = merged.get(key, 0) + num(r["Rental"])
    missing = set(region_of) - {k[1] for k in merged}
    if missing:
        raise SystemExit(f"no rows for {sorted(missing)}")
    return by_region, [(*k, v) for k, v in sorted(merged.items())]


def write(name, head, rows):
    with (DATA / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(head)
        w.writerows(rows)


if __name__ == "__main__":
    by_region, by_council = extract(sys.argv[1])
    write("epc-rental-lodgements-by-region.csv", ["region", "quarter", "rental_epcs_lodged"], by_region)
    write("epc-rental-lodgements-by-council.csv", ["region", "council", "quarter", "rental_epcs_lodged"], by_council)
    print(len(by_region), "region rows,", len(by_council), "council rows")

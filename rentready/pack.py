"""rentready pack: the registration pack, one page per property, for "Register your rental property".

Every question the service asks (gov.uk "Get ready to register", Oct 2026) with the answer pre-filled from the
portfolio CSV where we have it, a GATHER line where we do not, and the exact files to scan with a suggested
file name. Certificates that will have lapsed by the time you register are flagged, so you renew before you upload
rather than after. Nothing here registers for you: the landlord must start the entry with GOV.UK One Login.

Optional CSV columns read on top of the check columns (which include eicr_due, the report's next-inspection date): bedrooms, dwelling_type, ownership, let (yes/no),
occupants, households, licence (none/hmo/additional/selective), furnished (furnished/part/unfurnished),
rent, rent_frequency, bills (comma list or "none"), freeholder, manager.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from rentready import EICR_ASSUMED, FEE_PER_PROPERTY_GBP, __version__, _truthy, check_portfolio

SOURCE = "https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/"

LANDLORD_INDIVIDUAL = ["Name", "Date of birth", "Residential address", "Telephone number", "Email address"]
LANDLORD_ORGANISATION = [
    "Name of the organisation (or how it is known) and type of legal entity",
    "Address (not a PO Box), telephone number, email address",
    "Name, date of birth, email and phone of the person making the entry",
    "Nominated contact for the database, with email and phone",
    "Companies House or charity number; without one, names, dates of birth and addresses of all directors, trustees, partners or members",
    "If a trust: name, date of birth, address, email and phone of the lead trustee",
]
CAPACITY = ("If you register on someone else's behalf (power of attorney, executor, deputy, receiver, liquidator, "
            "mortgagee and similar): your name, address, phone, email, and a certified copy of the authority "
            "(power of attorney, grant of probate, court order, deed of appointment).")

# (CSV column, question as the service asks it)
DWELLING = [
    ("_address", "Address of dwelling"),
    ("ownership", "Ownership type"),
    ("dwelling_type", "Dwelling type"),
    ("bedrooms", "Number of bedrooms"),
    ("let", "Currently let?"),
    ("freeholder", "Freeholder / superior landlord (name and email), if any"),  # optional
    ("manager", "Property manager (name and email), if any"),  # optional
]
OPTIONAL = {"freeholder", "manager"}
TENANCY = [
    ("occupants", "Number of occupants"),
    ("households", "Number of households"),
    ("licence", "HMO, additional or selective licence required? (and how many)"),
    ("furnished", "Furnished, part furnished or unfurnished"),
    ("rent", "Rent charged"),
    ("rent_frequency", "Rent payment frequency"),
    ("bills", "Utilities included in the rent (which)"),
]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "property").lower()).strip("-")[:40] or "property"


def _status(report: Dict[str, Any], check: str) -> Optional[Dict[str, str]]:
    return next((f for f in report.get("findings", []) if f["check"] == check), None)


def _cert_line(report: Dict[str, Any], check: str, issued: str, label: str, fname: str) -> Dict[str, Any]:
    f = _status(report, check)
    expiry = (report.get("expiries") or {}).get(check)
    if not issued:
        return {"item": label, "file": fname, "state": "GATHER", "note": "no date in the CSV: find the certificate or book one"}
    if f and f["status"] == "FAIL":
        return {"item": label, "file": fname, "state": "RENEW", "note": f"{f['detail']}: renew before you register and upload the new one"}
    if f and f["status"] == "WARN":
        return {"item": label, "file": fname, "state": "RENEW SOON", "note": f"{f['detail']}: upload this one, then update the entry within 28 days of renewing"}
    return {"item": label, "file": fname, "state": "READY", "note": f"issued {issued}" + (f", valid to {expiry}" if expiry else "")}


def property_pack(row: Dict[str, str], report: Dict[str, Any]) -> Dict[str, Any]:
    name = report.get("name") or row.get("name") or "property"
    slug = _slug(name)
    answers: List[Dict[str, str]] = []
    vals = dict(row)
    vals["_address"] = ", ".join(x for x in (row.get("name"), report.get("postcode") or row.get("postcode")) if x)
    if "let" in vals and vals["let"]:
        vals["let"] = "yes" if _truthy(vals["let"]) else "no"
    for section, fields in (("Dwelling", DWELLING), ("Tenancy and rent", TENANCY)):
        for col, q in fields:
            v = (vals.get(col) or "").strip()
            state = "FILLED" if v else ("IF ANY" if col in OPTIONAL else "GATHER")
            answers.append({"section": section, "question": q, "answer": v, "state": state, "column": col.lstrip("_")})

    files: List[Dict[str, Any]] = []
    if _truthy(row.get("no_gas")):
        files.append({"item": "Gas safety record", "file": "", "state": "N/A", "note": "no gas supply: answer 'no gas supply' and upload nothing"})
    else:
        g = row.get("gas") or ""
        files.append(_cert_line(report, "gas safety record", g, "Gas safety record (CP12) and its issue date",
                                f"{slug}_gas-safety-record_{g or 'DATE'}.pdf"))
    e = row.get("eicr") or ""
    due = row.get("eicr_due") or ""
    eicr = _cert_line(report, "EICR", e or due, "EICR (or EIC) and its expiry date", f"{slug}_eicr_{e or due or 'DATE'}.pdf")
    if eicr["state"] == "READY":
        exp = (report.get("expiries") or {}).get("EICR")
        parts = [f"issued {e}"] if e else []
        if exp:
            parts.append(f"valid to {exp}" + ("" if due else f" ({EICR_ASSUMED})"))
        elif due:
            parts.append(f"next inspection due {due}")
        eicr["note"] = ", ".join(parts)
    files.append(eicr)
    p = row.get("epc") or ""
    epc = _cert_line(report, "EPC", p, "Most recent EPC (if one was required for the current tenant)", f"{slug}_epc_{p or 'DATE'}.pdf")
    if epc["state"] == "RENEW":
        # The service accepts a lapsed EPC with the current tenancy's start date; a new tenancy needs a new EPC.
        ts = row.get("tenancy_start") or ""
        epc["note"] = (epc["note"].split(": renew")[0] + ": upload it with the current tenancy start date ("
                       + (ts if ts else "GATHER it") + "); a new tenancy needs a new EPC first")
        epc["state"] = "READY" if ts else "GATHER"
    files.append(epc)
    rating = _status(report, "EPC rating")
    if rating and rating["status"] == "FAIL":
        files.append({"item": "MEES exemption", "file": f"{slug}_mees-exemption.pdf", "state": "GATHER",
                      "note": "rating below E: the service asks whether a registered MEES exemption applies and which type"})
    if (row.get("licence") or "").strip().lower() not in ("", "none", "no", "n/a"):
        files.append({"item": "Licence details", "file": "", "state": "GATHER",
                      "note": "licence number(s) from your council; the service asks how many licences apply"})

    todo = [a for a in answers if a["state"] == "GATHER"] + [f for f in files if f["state"] in ("GATHER", "RENEW")]
    return {"name": name, "slug": slug, "postcode": report.get("postcode") or row.get("postcode"),
            "region": report.get("region"), "window": report.get("window"), "in_scope": report.get("ready") is not None,
            "answers": answers, "files": files, "to_do": len(todo),
            "missing_columns": [a["column"] for a in answers if a["state"] == "GATHER"],
            "ready_to_register": report.get("ready") is True and not todo}


def build_pack(rows: List[Dict[str, str]], today: Optional[str] = None, organisation: bool = False) -> Dict[str, Any]:
    p = check_portfolio(rows, today=today)
    props = [property_pack(row, rep) for row, rep in zip(rows, p["properties"])]
    return {"version": __version__, "today": p["today"], "source": SOURCE, "organisation": organisation,
            "landlord": LANDLORD_ORGANISATION if organisation else LANDLORD_INDIVIDUAL, "capacity": CAPACITY,
            "properties": props, "fee_gbp_per_year": p["fee_gbp_per_year"], "earliest_deadline": p["earliest_deadline"],
            "ready_to_register": sum(1 for x in props if x["ready_to_register"]),
            "in_scope": sum(1 for x in props if x["in_scope"]),
            "missing_columns": sorted({c for x in props if x["in_scope"] for c in x["missing_columns"]})}


def format_pack(pk: Dict[str, Any]) -> str:
    L = [f"# Registration pack ({pk['today']})", "",
         f"For gov.uk *Register your rental property*. {pk['ready_to_register']} of {pk['in_scope']} properties in England "
         f"have every answer and file ready. Fee £{pk['fee_gbp_per_year']} a year (£{FEE_PER_PROPERTY_GBP} per property)"
         + (f"; earliest deadline {pk['earliest_deadline']}." if pk.get("earliest_deadline") else "."),
         "You start the entry yourself with GOV.UK One Login; an agent can upload some items but cannot register for you.", ""]
    if pk.get("missing_columns"):
        L += [f"Add these columns to your CSV and re-run to fill the GATHER lines: `{', '.join(pk['missing_columns'])}`.", ""]
    L += [
         "## You, once for every property", ""]
    L += [f"- [ ] {x}" for x in pk["landlord"]]
    L += ["", f"*{pk['capacity']}*", ""]
    for x in pk["properties"]:
        L.append(f"## {x['name']}")
        if not x["in_scope"]:
            L += ["", "Outside England: this database does not apply.", ""]
            continue
        w = x.get("window") or {}
        L += ["", f"{x.get('postcode') or ''} · {x.get('region') or 'region unknown'}"
              + (f" · register {w.get('opens')} to {w.get('deadline')}" if w else "")
              + (" · **ready to register**" if x["ready_to_register"] else f" · {x['to_do']} to do"), ""]
        section = None
        for a in x["answers"]:
            if a["section"] != section:
                section = a["section"]
                L += ([""] if section != x["answers"][0]["section"] else []) + [f"**{section}**", ""]
            if a["state"] == "FILLED":
                L.append(f"- [x] {a['question']}: {a['answer']}")
            elif a["state"] == "IF ANY":
                L.append(f"- [ ] {a['question']}: leave blank if none")
            else:
                L.append(f"- [ ] {a['question']}: GATHER")
        L += ["", "**Files to scan and upload** (within 28 days of the entry)", ""]
        for f in x["files"]:
            box = "x" if f["state"] in ("READY", "N/A") else " "
            fn = f" → `{f['file']}`" if f.get("file") else ""
            L.append(f"- [{box}] {f['item']}{fn}: {f['state']}, {f['note']}")
        L.append("")
    L.append(f"Questions as published at {pk['source']} (checked Oct 2026). rentready {pk['version']}.")
    return "\n".join(L)

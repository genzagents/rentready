#!/usr/bin/env python3
"""rentready: is this rental ready for England's landlord database ("Register your rental property")?

Usage:
  rentready check POSTCODE [--gas=YYYY-MM-DD] [--eicr=YYYY-MM-DD] [--epc=YYYY-MM-DD] [--epc-rating=C]
                           [--tenancy-start=YYYY-MM-DD] [--no-gas] [--properties=N] [--today=YYYY-MM-DD]
                           [--region="West Midlands"] [--json]
  rentready regions                 print the rollout timetable
  rentready mcp                     run as an MCP server over stdio (tool: check_property)

Zero dependencies. Region comes from postcodes.io (no key) unless --region is given.
Timetable, fee and required information: Private Rented Sector Database Regulations 2026 as summarised by
NRLA and HCR Law (Oct 2026). Dates are the regulations' as published; check gov.uk before relying on them.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

__version__ = "0.1.0"

FEE_PER_PROPERTY_GBP = 65

# region -> (requirement starts, registration deadline, midnight)
ROLLOUT: Dict[str, Dict[str, str]] = {
    "West Midlands":            {"opens": "2026-12-15", "deadline": "2027-03-14"},
    "East of England":          {"opens": "2027-01-15", "deadline": "2027-04-14"},
    "East Midlands":            {"opens": "2027-02-15", "deadline": "2027-05-14"},
    "South East":               {"opens": "2027-03-15", "deadline": "2027-06-14"},
    "Yorkshire and The Humber": {"opens": "2027-04-15", "deadline": "2027-07-14"},
    "North West":               {"opens": "2027-05-15", "deadline": "2027-08-14"},
    "North East":               {"opens": "2027-06-15", "deadline": "2027-09-14"},
    "London":                   {"opens": "2027-07-15", "deadline": "2027-10-14"},
    "South West":               {"opens": "2027-08-15", "deadline": "2027-11-14"},
}
REGION_ALIASES = {"yorkshire and humber": "Yorkshire and The Humber", "yorkshire": "Yorkshire and The Humber",
                  "east": "East of England", "greater london": "London"}

UPLOADS = [
    "Latest gas safety record (CP12) and its issue date, if the property has gas",
    "EICR (or EIC if no EICR yet) and its expiry date",
    "Latest EPC, and any MEES exemption; if the EPC has lapsed, the start date of the current tenancy",
]
DETAILS = [
    "Landlord: name, date of birth, residential address, phone, email (companies: entity type, registered address, Companies House number or all directors)",
    "Property: address, ownership type, freeholder or superior landlord, dwelling type, bedrooms, currently let?",
    "Tenancy: rent, bills included?, payment frequency, occupiers, households, HMO licence status, furnishing",
    "Each joint landlord needs their own landlord entry linked to the one property entry; an agent cannot register for you",
]
PENALTIES = [
    "Up to £7,000 civil penalty for letting or marketing without an active entry, omitting the reference from adverts, or not updating within 28 days",
    "Up to £40,000 for a repeat breach; rent repayment orders for false information",
    "No possession order from the court while the landlord or dwelling entry is inactive (anti-social behaviour cases excepted)",
]


def _d(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def lookup_region(postcode: str, timeout: float = 8.0) -> Dict[str, Any]:
    """Region and country for a postcode via postcodes.io. Returns {region, country, postcode} or {error}."""
    pc = urllib.parse.quote(postcode.strip())
    try:
        with urllib.request.urlopen(f"https://api.postcodes.io/postcodes/{pc}", timeout=timeout) as r:
            data = json.loads(r.read().decode())
    except Exception as e:  # network or 404
        return {"error": f"postcode lookup failed: {type(e).__name__}: {e}"}
    res = data.get("result") or {}
    return {"postcode": res.get("postcode", postcode), "region": res.get("region"), "country": res.get("country")}


def normalise_region(region: Optional[str]) -> Optional[str]:
    if not region:
        return None
    r = region.strip()
    if r in ROLLOUT:
        return r
    low = r.lower()
    if low in REGION_ALIASES:
        return REGION_ALIASES[low]
    for k in ROLLOUT:
        if k.lower() == low:
            return k
    return None


def check_property(postcode: str = "", *, region: Optional[str] = None, gas: Optional[str] = None, no_gas: bool = False,
                   eicr: Optional[str] = None, epc: Optional[str] = None, epc_rating: Optional[str] = None,
                   tenancy_start: Optional[str] = None, properties: int = 1, today: Optional[str] = None) -> Dict[str, Any]:
    t = _d(today) or date.today()
    out: Dict[str, Any] = {"version": __version__, "today": t.isoformat(), "postcode": postcode or None,
                           "findings": [], "actions": [], "fee_gbp_per_year": FEE_PER_PROPERTY_GBP * max(1, int(properties))}
    reg = normalise_region(region)
    country = None
    if not reg and postcode:
        lk = lookup_region(postcode)
        if "error" in lk:
            out["findings"].append({"status": "WARN", "check": "region", "detail": lk["error"] + "; pass --region to continue"})
        else:
            country = lk.get("country")
            reg = normalise_region(lk.get("region"))
            out["postcode"] = lk.get("postcode")
    out["region"] = reg
    if country and country != "England":
        out["findings"].append({"status": "INFO", "check": "scope", "detail": f"{country}: the England database does not apply; Wales and Scotland have their own landlord registration schemes"})
        out["ready"] = None
        return out
    if not reg:
        out["findings"].append({"status": "FAIL", "check": "region", "detail": "region unknown; registration window cannot be computed"})
        out["ready"] = False
        return out

    opens, deadline = _d(ROLLOUT[reg]["opens"]), _d(ROLLOUT[reg]["deadline"])
    out["window"] = {"opens": opens.isoformat(), "deadline": deadline.isoformat(),
                     "days_to_deadline": (deadline - t).days, "service_opens_everywhere": "2026-12-15"}
    if t > deadline:
        out["findings"].append({"status": "FAIL", "check": "registration deadline", "detail": f"{reg} deadline {deadline} has passed; register now, penalties up to £7,000 and no possession orders apply"})
    elif t >= opens:
        out["findings"].append({"status": "WARN", "check": "registration deadline", "detail": f"{reg} window is open: register by {deadline} ({(deadline - t).days} days)"})
    else:
        out["findings"].append({"status": "PASS", "check": "registration deadline", "detail": f"{reg} requirement starts {opens}, deadline {deadline}; you can register from 2026-12-15"})

    # Certificates: each must be in date at the deadline and ideally at registration.
    def cert(name: str, issued: Optional[str], years: int, missing_msg: str, what: str) -> None:
        if issued is None:
            out["findings"].append({"status": "FAIL", "check": name, "detail": missing_msg})
            out["actions"].append(what)
            return
        d0 = _d(issued)
        try:
            expiry = d0.replace(year=d0.year + years)
        except ValueError:  # 29 Feb
            expiry = d0.replace(year=d0.year + years, day=28)
        days = (expiry - t).days
        if expiry <= t:
            out["findings"].append({"status": "FAIL", "check": name, "detail": f"expired {expiry}"})
            out["actions"].append(f"Renew now: {what}")
        elif expiry <= deadline:
            out["findings"].append({"status": "WARN", "check": name, "detail": f"expires {expiry}, before the {deadline} deadline ({days} days)"})
            out["actions"].append(f"Book before {expiry}: {what}")
        else:
            out["findings"].append({"status": "PASS", "check": name, "detail": f"valid to {expiry}"})

    if no_gas:
        out["findings"].append({"status": "PASS", "check": "gas safety record", "detail": "no gas supply declared; not required"})
    else:
        cert("gas safety record", gas, 1, "no gas safety record date given (annual CP12 is required and uploaded)", "annual gas safety check by a Gas Safe engineer; upload the record and issue date")
    cert("EICR", eicr, 5, "no EICR date given (five-yearly report is required and uploaded with its expiry)", "EICR by a qualified electrician; upload the report and expiry date")
    cert("EPC", epc, 10, "no EPC date given (upload the latest EPC; if lapsed, give the current tenancy start date)", "EPC assessment; upload the certificate")
    if epc and epc_rating:
        r = epc_rating.strip().upper()[:1]
        if r in ("F", "G"):
            out["findings"].append({"status": "FAIL", "check": "EPC rating", "detail": f"rating {r} is below the current E minimum (MEES); register an exemption or improve"})
        elif r in ("D", "E"):
            out["findings"].append({"status": "INFO", "check": "EPC rating", "detail": f"rating {r} meets today's E minimum; the proposed C minimum for new tenancies from 2028 and all tenancies from 2030 would not be met"})
        else:
            out["findings"].append({"status": "PASS", "check": "EPC rating", "detail": f"rating {r}"})
    if tenancy_start:
        out["tenancy_start"] = tenancy_start

    out["uploads"] = UPLOADS
    out["details_required"] = DETAILS
    out["penalties"] = PENALTIES
    out["renewal"] = "annual, on the anniversary of the first property registered (one date for the whole portfolio); later properties pay pro rata"
    fails = [f for f in out["findings"] if f["status"] == "FAIL"]
    out["ready"] = not fails
    return out


def format_report(r: Dict[str, Any]) -> str:
    lines = [f"rentready {r['version']}  {r.get('postcode') or ''}  region: {r.get('region') or 'unknown'}"]
    w = r.get("window")
    if w:
        lines.append(f"Window: requirement starts {w['opens']}, deadline {w['deadline']} ({w['days_to_deadline']} days from {r['today']}); the service opens for everyone on {w['service_opens_everywhere']}")
    for f in r["findings"]:
        lines.append(f"  {f['status']:<4} {f['check']}: {f['detail']}")
    if r.get("actions"):
        lines.append("Do next:")
        lines += [f"  - {a}" for a in r["actions"]]
    if "fee_gbp_per_year" in r and r.get("region"):
        lines.append(f"Fee: £{r['fee_gbp_per_year']} a year ({FEE_PER_PROPERTY_GBP} per property); renewal {r.get('renewal','')}")
    if r.get("uploads"):
        lines.append("Upload at registration (within 28 days of the entry):")
        lines += [f"  - {u}" for u in r["uploads"]]
    if r.get("ready") is True:
        lines.append("READY: nothing expires before your deadline. Gather the details above and register when your window opens.")
    elif r.get("ready") is False:
        lines.append("NOT READY: fix the FAIL lines first.")
    return "\n".join(lines)


def format_regions() -> str:
    rows = ["Region                     Requirement starts  Deadline (midnight)"]
    for k, v in ROLLOUT.items():
        rows.append(f"{k:<26} {v['opens']:<19} {v['deadline']}")
    rows.append(f"Registration opens for all of England on 2026-12-15. Fee £{FEE_PER_PROPERTY_GBP} per property per year.")
    return "\n".join(rows)


MCP_TOOLS: List[Dict[str, Any]] = [{
    "name": "check_property",
    "description": "Is an English rental property ready for the landlord database (Register your rental property, Renters' Rights Act)? "
                   "Returns the region's registration window and deadline, whether the gas safety record, EICR and EPC will still be valid, "
                   "the £65/property fee, the upload checklist and the penalties.",
    "inputSchema": {"type": "object", "properties": {
        "postcode": {"type": "string", "description": "Property postcode (England)"},
        "region": {"type": "string", "description": "Override region, e.g. 'London', if no postcode"},
        "gas": {"type": "string", "description": "Gas safety record issue date YYYY-MM-DD"},
        "no_gas": {"type": "boolean", "description": "True if the property has no gas supply"},
        "eicr": {"type": "string", "description": "EICR issue date YYYY-MM-DD"},
        "epc": {"type": "string", "description": "EPC issue date YYYY-MM-DD"},
        "epc_rating": {"type": "string", "description": "EPC rating letter A-G"},
        "tenancy_start": {"type": "string", "description": "Current tenancy start date YYYY-MM-DD"},
        "properties": {"type": "integer", "description": "Number of properties, for the fee"},
    }},
}]


def _mcp_send(obj: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def mcp_serve() -> None:
    """Minimal MCP server over stdio (newline-delimited JSON-RPC 2.0). No dependencies."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception:
            _mcp_send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if mid is None:
            continue
        try:
            if method == "initialize":
                result = {"protocolVersion": params.get("protocolVersion", "2025-06-18"), "capabilities": {"tools": {}},
                          "serverInfo": {"name": "rentready", "version": __version__}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": MCP_TOOLS}
            elif method == "tools/call":
                name, a = params.get("name"), params.get("arguments") or {}
                if name != "check_property":
                    raise KeyError(f"unknown tool {name}")
                r = check_property(a.get("postcode", ""), region=a.get("region"), gas=a.get("gas"), no_gas=bool(a.get("no_gas")),
                                   eicr=a.get("eicr"), epc=a.get("epc"), epc_rating=a.get("epc_rating"),
                                   tenancy_start=a.get("tenancy_start"), properties=int(a.get("properties") or 1))
                result = {"content": [{"type": "text", "text": format_report(r)}], "structuredContent": r, "isError": False}
            else:
                _mcp_send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}})
                continue
            _mcp_send({"jsonrpc": "2.0", "id": mid, "result": result})
        except Exception as e:
            _mcp_send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32603, "message": f"{type(e).__name__}: {e}"}})


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip()); return 0
    if argv[0] in ("-V", "--version"):
        print(__version__); return 0
    if argv[0] == "mcp":
        mcp_serve(); return 0
    if argv[0] == "regions":
        print(format_regions()); return 0
    if argv[0] != "check":
        print(__doc__.strip(), file=sys.stderr); return 2
    rest = argv[1:]
    pos = [a for a in rest if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in rest if a.startswith("--"))
    postcode = " ".join(pos)
    r = check_property(postcode, region=opts.get("region"), gas=opts.get("gas"), no_gas="no-gas" in opts, eicr=opts.get("eicr"),
                       epc=opts.get("epc"), epc_rating=opts.get("epc-rating"), tenancy_start=opts.get("tenancy-start"),
                       properties=int(opts.get("properties", 1)), today=opts.get("today"))
    print(json.dumps(r, indent=2) if "json" in opts else format_report(r))
    return 0 if r.get("ready") else 1


if __name__ == "__main__":
    sys.exit(main())

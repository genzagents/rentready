#!/usr/bin/env python3
"""rentready: is this rental ready for England's landlord database ("Register your rental property")?

Usage:
  rentready check POSTCODE [--gas=YYYY-MM-DD] [--eicr=YYYY-MM-DD] [--eicr-due=YYYY-MM-DD] [--epc=YYYY-MM-DD] [--epc-rating=C]
                           [--tenancy-start=YYYY-MM-DD] [--no-gas] [--properties=N] [--today=YYYY-MM-DD]
                           [--region="West Midlands"] [--json]
  rentready portfolio FILE.csv      check every property in a CSV (columns: name, postcode, gas, no_gas, eicr, eicr_due,
                                    epc, epc_rating, tenancy_start, region); one table, total fee, earliest deadline
  rentready calendar FILE.csv|POSTCODE [check flags] [--reminders=60,14] [--out=rentready.ics]
                                    write an iCalendar file: window opens, deadline, each certificate expiry,
                                    with reminders; import into Google/Apple/Outlook calendar
  rentready watch FILE.csv          re-check monthly and raise the alarm only when something changes: a certificate
                                    comes within 60 days of expiring, a window opens, a deadline nears, a property
                                    stops being ready; remembers the last run in a GitHub issue (Actions) or --state=FILE
  rentready hosted run|replay|launchd   the paid monthly watch with no repo: polls Polar for subscribers, emails
                                    the first report within the hour, alerts on change, a monthly digest otherwise;
                                    `replay` re-runs a stored report from its stored inputs (see rentready/hosted.py)
  rentready pack FILE.csv [--organisation] [--out=pack.md] [--json]
                                    the registration pack: every question the service asks, pre-filled from the CSV,
                                    GATHER where it is missing, and each file to scan with a name; flags certificates
                                    to renew before you upload (optional columns: see rentready/pack.py)
  rentready regions                 print the rollout timetable
  rentready mcp                     run as an MCP server over stdio (tools: check_property, check_portfolio, make_calendar,
                                    registration_pack)

Zero dependencies. Region comes from postcodes.io (no key) unless --region is given.
EICR: --eicr is the report's issue date, --eicr-due the date the report gives for the next inspection. The law
requires inspection at least every 5 years, or sooner if the report says so (SI 2020/312 reg 3(2)), and the service
asks for the expiry date, so the report's date is used when given; issue date + 5 years is only a fallback, and the
result says so.
Timetable and required information: the draft Private Rented Sector Database Regulations 2026 (laid before
Parliament on 9 Sep 2026; not yet approved as of 28 Oct 2026) and the official guidance at housinghub.campaign.gov.uk.
The £65 fee is from the official guidance; the draft leaves the amount to the database operator (reg 14). Upload
within 28 days or the entry becomes inactive (draft regs 6(2), 11(2)(a)); update within 28 days of a change (reg 9(4)).
Check gov.uk before relying on a date.
EPC C minimum: all private tenancies by 1 October 2030, no earlier date for new tenancies (government response,
21 Jan 2026, not yet law): https://www.gov.uk/government/consultations/improving-the-energy-performance-of-privately-rented-homes-2025-update/outcome/improving-the-energy-performance-of-privately-rented-homes-government-response-html
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

__version__ = "0.8.1"

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
    "Up to £40,000 for the section 92 offences: knowingly or recklessly giving false or misleading information, continuing a breach 28 days after a penalty, or a different breach within five years of one; rent repayment orders can also apply",
    "No possession order from the court while the landlord or dwelling entry is inactive, except on Ground 7A or Ground 14 (section 90)",
]
EICR_ASSUMED = "assumed 5 years from issue; give the next-inspection date on the report if it sets one"
RENEWAL = "every 12 months: the renewal date is the last day of the 12 months from your first entry, one date for the whole portfolio (draft regulation 10); later properties pay pro rata"


def _d(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _add_years(d0: date, years: int) -> date:
    try:
        return d0.replace(year=d0.year + years)
    except ValueError:  # 29 Feb
        return d0.replace(year=d0.year + years, day=28)


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
                   eicr: Optional[str] = None, eicr_due: Optional[str] = None, epc: Optional[str] = None, epc_rating: Optional[str] = None,
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
        out["findings"].append({"status": "FAIL", "check": "registration deadline", "detail": f"{reg} deadline {deadline} has passed; register now: penalties up to £7,000, and no possession order except on Ground 7A or Ground 14"})
    elif t >= opens:
        out["findings"].append({"status": "WARN", "check": "registration deadline", "detail": f"{reg} window is open: register by {deadline} ({(deadline - t).days} days)"})
    else:
        out["findings"].append({"status": "PASS", "check": "registration deadline", "detail": f"{reg} requirement starts {opens}, deadline {deadline}; you can register from 2026-12-15"})

    # Certificates: each must be in date at the deadline and ideally at registration.
    def cert(name: str, issued: Optional[str], years: int, missing_msg: str, what: str,
             due: Optional[str] = None, assumed: str = "") -> None:
        if issued is None and due is None:
            out["findings"].append({"status": "FAIL", "check": name, "detail": missing_msg})
            out["actions"].append(what)
            return
        expiry = _add_years(_d(issued), years) if issued else None
        note = ""
        if due:  # the date the certificate itself gives wins, but never later than the legal maximum
            expiry = min(_d(due), expiry) if expiry else _d(due)
        elif assumed:
            note = f" ({assumed})"
            out.setdefault("assumptions", []).append(f"{name}: {assumed}")
        days = (expiry - t).days
        out.setdefault("expiries", {})[name] = expiry.isoformat()
        if expiry <= t:
            out["findings"].append({"status": "FAIL", "check": name, "detail": f"expired {expiry}{note}"})
            out["actions"].append(f"Renew now: {what}")
        elif expiry <= deadline:
            out["findings"].append({"status": "WARN", "check": name, "detail": f"expires {expiry}, before the {deadline} deadline ({days} days){note}"})
            out["actions"].append(f"Book before {expiry}: {what}")
        else:
            out["findings"].append({"status": "PASS", "check": name, "detail": f"valid to {expiry}{note}"})

    if no_gas:
        out["findings"].append({"status": "PASS", "check": "gas safety record", "detail": "no gas supply declared; not required"})
    else:
        cert("gas safety record", gas, 1, "no gas safety record date given (annual CP12 is required and uploaded)", "annual gas safety check by a Gas Safe engineer; upload the record and issue date")
    cert("EICR", eicr, 5, "no EICR date given (an EICR is required at least every 5 years, sooner if the report says so, and uploaded with its expiry date)",
         "EICR by a qualified electrician; upload the report and expiry date", due=eicr_due, assumed=EICR_ASSUMED)
    cert("EPC", epc, 10, "no EPC date given (upload the latest EPC; if lapsed, give the current tenancy start date)", "EPC assessment; upload the certificate")
    if epc and epc_rating:
        r = epc_rating.strip().upper()[:1]
        if r in ("F", "G"):
            out["findings"].append({"status": "FAIL", "check": "EPC rating", "detail": f"rating {r} is below the current E minimum (MEES); register an exemption or improve"})
        elif r in ("D", "E"):
            out["findings"].append({"status": "INFO", "check": "EPC rating", "detail": f"rating {r} meets today's E minimum; it would not meet the C minimum set for all tenancies from 1 October 2030 (government response, 21 Jan 2026; not yet law)"})
        else:
            out["findings"].append({"status": "PASS", "check": "EPC rating", "detail": f"rating {r}"})
    if tenancy_start:
        out["tenancy_start"] = tenancy_start
    if eicr_due:
        out["eicr_due"] = eicr_due

    out["uploads"] = UPLOADS
    out["details_required"] = DETAILS
    out["penalties"] = PENALTIES
    out["renewal"] = RENEWAL
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
        lines.append("Upload at registration (within 28 days of the entry, or it becomes inactive):")
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


# ---------------------------------------------------------------------------
# Portfolio (many properties from a CSV) and calendar (.ics with reminders)
# ---------------------------------------------------------------------------
PORTFOLIO_COLUMNS = ["name", "postcode", "region", "gas", "no_gas", "eicr", "eicr_due", "epc", "epc_rating", "tenancy_start"]
_COLUMN_ALIASES = {"address": "name", "property": "name", "label": "name", "post_code": "postcode", "post code": "postcode",
                   "gas_date": "gas", "gas safety": "gas", "gas_safety": "gas", "cp12": "gas", "eicr_date": "eicr",
                   "eicr_next": "eicr_due", "eicr_expiry": "eicr_due", "eicr next inspection": "eicr_due",
                   "eicr_next_inspection": "eicr_due", "next_inspection": "eicr_due", "next inspection": "eicr_due",
                   "epc_date": "epc", "epc rating": "epc_rating", "rating": "epc_rating", "tenancy": "tenancy_start",
                   "tenancy start": "tenancy_start", "no gas": "no_gas", "nogas": "no_gas"}


def _norm_col(c: str) -> str:
    c = (c or "").strip().lower().replace("-", "_")
    return _COLUMN_ALIASES.get(c, c.replace(" ", "_"))


def read_portfolio(text: str) -> List[Dict[str, str]]:
    """Parse a portfolio from CSV text (header row required) or a JSON list of objects."""
    import csv
    import io
    text = text.lstrip("\ufeff")
    if text.lstrip().startswith("["):
        rows = json.loads(text)
        return [{_norm_col(k): ("" if v is None else str(v)) for k, v in r.items()} for r in rows]
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for r in reader:
        row = {_norm_col(k): (v or "").strip() for k, v in r.items() if k is not None}
        if any(row.values()):
            out.append(row)
    return out


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "x")


def check_portfolio(rows: List[Dict[str, str]], today: Optional[str] = None) -> Dict[str, Any]:
    """Run check_property for every row. Fee is £65 per property; the earliest deadline is the one to plan around."""
    t = _d(today) or date.today()
    props: List[Dict[str, Any]] = []
    region_cache: Dict[str, Dict[str, Any]] = {}
    for i, row in enumerate(rows, 1):
        pc = (row.get("postcode") or "").strip()
        region = row.get("region") or None
        if pc and not region:
            key = pc.upper().replace(" ", "")
            if key not in region_cache:
                region_cache[key] = lookup_region(pc)
            lk = region_cache[key]
            if "error" not in lk:
                region = lk.get("region")
                if lk.get("country") and lk["country"] != "England":
                    region = None
        r = check_property(pc, region=region, gas=row.get("gas") or None, no_gas=_truthy(row.get("no_gas")),
                           eicr=row.get("eicr") or None, eicr_due=row.get("eicr_due") or None, epc=row.get("epc") or None,
                           epc_rating=row.get("epc_rating") or None,
                           tenancy_start=row.get("tenancy_start") or None, properties=1, today=t.isoformat())
        if pc and not region and not row.get("region"):
            lk = region_cache.get(pc.upper().replace(" ", ""), {})
            if lk.get("country") and lk["country"] != "England":
                r["findings"] = [{"status": "INFO", "check": "scope", "detail": f"{lk['country']}: the England database does not apply"}]
                r["ready"] = None
        r["name"] = row.get("name") or pc or f"property {i}"
        nxt = _next_date(r)
        r["next"] = nxt
        props.append(r)
    in_scope = [p for p in props if p.get("ready") is not None]
    deadlines = sorted(p["window"]["deadline"] for p in in_scope if p.get("window"))
    out = {"version": __version__, "today": t.isoformat(), "properties": props,
           "count": len(props), "in_scope": len(in_scope),
           "fee_gbp_per_year": FEE_PER_PROPERTY_GBP * len(in_scope),
           "earliest_deadline": deadlines[0] if deadlines else None,
           "ready": sum(1 for p in in_scope if p.get("ready") is True),
           "not_ready": sum(1 for p in in_scope if p.get("ready") is False),
           "renewal": RENEWAL}
    return out


def _next_date(r: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """The soonest dated thing for one property: a certificate expiry, the window opening or the deadline."""
    t = _d(r.get("today")) or date.today()
    cands: List[tuple] = []
    for name, iso in (r.get("expiries") or {}).items():
        cands.append((iso, f"{name} expires"))
    w = r.get("window")
    if w:
        if _d(w["opens"]) >= t:
            cands.append((w["opens"], "registration window opens"))
        cands.append((w["deadline"], "registration deadline"))
    cands = [c for c in cands if _d(c[0]) >= t] or cands
    if not cands:
        return None
    iso, what = sorted(cands)[0]
    return {"date": iso, "what": what, "days": (_d(iso) - t).days}


def format_portfolio(p: Dict[str, Any]) -> str:
    lines = [f"rentready {p['version']}  portfolio of {p['count']} ({p['in_scope']} in England)  today {p['today']}"]
    lines.append(f"{'Property':<28} {'Postcode':<9} {'Region':<24} {'Deadline':<11} {'Status':<9} Next")
    for r in p["properties"]:
        w = r.get("window") or {}
        st = "READY" if r.get("ready") is True else "NOT READY" if r.get("ready") is False else "n/a"
        nxt = r.get("next")
        nxt_s = f"{nxt['date']} {nxt['what']} ({nxt['days']}d)" if nxt else ""
        lines.append(f"{str(r['name'])[:28]:<28} {(r.get('postcode') or '')[:9]:<9} {(r.get('region') or 'unknown')[:24]:<24} {w.get('deadline', ''):<11} {st:<9} {nxt_s}")
    for r in p["properties"]:
        bad = [f for f in r["findings"] if f["status"] in ("FAIL", "WARN")]
        if bad:
            lines.append(f"{r['name']}:")
            lines += [f"  {f['status']:<4} {f['check']}: {f['detail']}" for f in bad]
    lines.append(f"Fee: £{p['fee_gbp_per_year']} a year for {p['in_scope']} properties (£{FEE_PER_PROPERTY_GBP} each); renewal {p['renewal']}")
    if p.get("earliest_deadline"):
        lines.append(f"Earliest deadline: {p['earliest_deadline']}. {p['ready']} ready, {p['not_ready']} not ready.")
    return "\n".join(lines)


def calendar_events(reports: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Dated events for one or more check_property results: window opens, deadline, each certificate expiry."""
    events: List[Dict[str, str]] = []
    for r in reports:
        name = r.get("name") or r.get("postcode") or "property"
        w = r.get("window")
        if w:
            events.append({"date": w["opens"], "summary": f"Landlord database: register {name} (window opens)",
                           "description": f"{r.get('region')}: the registration requirement starts today; register at gov.uk Register your rental property. Deadline {w['deadline']}. Fee £{FEE_PER_PROPERTY_GBP} per property per year. Upload: " + "; ".join(UPLOADS), "property": name, "kind": "opens"})
            events.append({"date": w["deadline"], "summary": f"Landlord database DEADLINE: {name}",
                           "description": f"{r.get('region')}: last day to register. After this: up to £7,000 penalty, and no possession order except on Ground 7A or Ground 14.", "property": name, "kind": "deadline"})
        for cert, iso in (r.get("expiries") or {}).items():
            what = {"gas safety record": "book the annual Gas Safe check before this date and upload the new CP12",
                    "EICR": "book an electrician for the next EICR before this date (the report's next-inspection date, at most 5 years) and upload the new report",
                    "EPC": "book an EPC assessment before this date and upload the new certificate"}.get(cert, "renew before this date")
            events.append({"date": iso, "summary": f"{cert} expires: {name}", "description": f"{what}. Update the property entry on the database within 28 days.", "property": name, "kind": cert})
    events.sort(key=lambda e: (e["date"], e["property"], e["summary"]))
    return events


def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _ics_fold(line: str) -> str:
    out, b = [], line.encode("utf-8")
    while len(b) > 73:
        cut = 73
        while cut > 0 and (b[cut] & 0xC0) == 0x80:  # do not split a UTF-8 sequence
            cut -= 1
        out.append(b[:cut].decode("utf-8")); b = b" " + b[cut:]
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def format_ics(events: List[Dict[str, str]], reminders: Optional[List[int]] = None, stamp: Optional[str] = None) -> str:
    """RFC 5545 calendar of all-day events with VALARMs N days before. Deterministic UIDs, so re-importing updates rather than duplicates."""
    import hashlib
    reminders = [60, 14] if reminders is None else reminders
    ds = (stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//genzagents//rentready {__version__}//EN", "CALSCALE:GREGORIAN",
           "METHOD:PUBLISH", "X-WR-CALNAME:rentready: landlord database and certificate dates"]
    for e in events:
        d = _d(e["date"])
        uid = hashlib.sha1(f"{e['property']}|{e['kind']}|{e['date']}".encode()).hexdigest()[:20] + "@rentready"
        out += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{ds}", f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(d + timedelta(days=1)).strftime('%Y%m%d')}",
                f"SUMMARY:{_ics_escape(e['summary'])}", f"DESCRIPTION:{_ics_escape(e['description'])}",
                "URL:https://genzagents.github.io/rentready/", "TRANSP:TRANSPARENT"]
        for n in reminders:
            out += ["BEGIN:VALARM", "ACTION:DISPLAY", f"TRIGGER;VALUE=DURATION:-P{int(n)}D",
                    f"DESCRIPTION:{_ics_escape(e['summary'])} in {int(n)} days", "END:VALARM"]
        out.append("END:VEVENT")
    out.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(l) for l in out) + "\r\n"


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
        "eicr_due": {"type": "string", "description": "Date the EICR gives for the next inspection YYYY-MM-DD (used instead of issue + 5 years; give it whenever the report has one)"},
        "epc": {"type": "string", "description": "EPC issue date YYYY-MM-DD"},
        "epc_rating": {"type": "string", "description": "EPC rating letter A-G"},
        "tenancy_start": {"type": "string", "description": "Current tenancy start date YYYY-MM-DD"},
        "properties": {"type": "integer", "description": "Number of properties, for the fee"},
    }},
}, {
    "name": "check_portfolio",
    "description": "Check many English rental properties at once for the landlord database. Input is CSV text (header row: name, postcode, gas, no_gas, eicr, eicr_due, epc, epc_rating, tenancy_start, region) "
                   "or a JSON list of objects with those keys. Returns one line per property, the total £65/property fee, the earliest deadline and every FAIL/WARN.",
    "inputSchema": {"type": "object", "required": ["portfolio"], "properties": {
        "portfolio": {"type": "string", "description": "CSV text or JSON list of properties"},
        "today": {"type": "string", "description": "Override today's date YYYY-MM-DD"},
    }},
}, {
    "name": "make_calendar",
    "description": "Build an iCalendar (.ics) file for one property or a portfolio: registration window opens, registration deadline, and each gas/EICR/EPC expiry as all-day events with reminders. "
                   "Save the returned text as rentready.ics and import it into Google, Apple or Outlook calendar.",
    "inputSchema": {"type": "object", "properties": {
        "portfolio": {"type": "string", "description": "CSV text or JSON list of properties (omit for a single property)"},
        "postcode": {"type": "string"}, "region": {"type": "string"}, "name": {"type": "string", "description": "Label for the property"},
        "gas": {"type": "string"}, "no_gas": {"type": "boolean"}, "eicr": {"type": "string"}, "eicr_due": {"type": "string"}, "epc": {"type": "string"},
        "reminder_days": {"type": "array", "items": {"type": "integer"}, "description": "Days before each event to alarm, default [60, 14]"},
    }},
}, {
    "name": "registration_pack",
    "description": "Prepare the registration pack for England's 'Register your rental property' service: every question the service asks "
                   "(landlord, dwelling, tenancy, rent, health and safety), pre-filled from the portfolio where known and marked GATHER where not, "
                   "and each certificate to scan with a suggested file name, flagging any that must be renewed before upload. Returns a markdown checklist. "
                   "Extra optional columns: bedrooms, dwelling_type, ownership, let, occupants, households, licence, furnished, rent, rent_frequency, bills, freeholder, manager.",
    "inputSchema": {"type": "object", "required": ["portfolio"], "properties": {
        "portfolio": {"type": "string", "description": "CSV text or JSON list of properties"},
        "organisation": {"type": "boolean", "description": "True if the landlord is a company, trust or other organisation"},
        "today": {"type": "string", "description": "Override today's date YYYY-MM-DD"},
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
                if name == "check_property":
                    r = check_property(a.get("postcode", ""), region=a.get("region"), gas=a.get("gas"), no_gas=bool(a.get("no_gas")),
                                       eicr=a.get("eicr"), eicr_due=a.get("eicr_due"), epc=a.get("epc"), epc_rating=a.get("epc_rating"),
                                       tenancy_start=a.get("tenancy_start"), properties=int(a.get("properties") or 1))
                    result = {"content": [{"type": "text", "text": format_report(r)}], "structuredContent": r, "isError": False}
                elif name == "check_portfolio":
                    p = check_portfolio(read_portfolio(a["portfolio"]), today=a.get("today"))
                    result = {"content": [{"type": "text", "text": format_portfolio(p)}], "structuredContent": p, "isError": False}
                elif name == "make_calendar":
                    if a.get("portfolio"):
                        reports = check_portfolio(read_portfolio(a["portfolio"]))["properties"]
                    else:
                        r = check_property(a.get("postcode", ""), region=a.get("region"), gas=a.get("gas"), no_gas=bool(a.get("no_gas")),
                                           eicr=a.get("eicr"), eicr_due=a.get("eicr_due"), epc=a.get("epc"))
                        r["name"] = a.get("name") or r.get("postcode") or "property"
                        reports = [r]
                    ev = calendar_events(reports)
                    ics = format_ics(ev, a.get("reminder_days"))
                    result = {"content": [{"type": "text", "text": ics}], "structuredContent": {"events": ev, "ics": ics}, "isError": False}
                elif name == "registration_pack":
                    from rentready.pack import build_pack, format_pack
                    pk = build_pack(read_portfolio(a["portfolio"]), today=a.get("today"), organisation=bool(a.get("organisation")))
                    result = {"content": [{"type": "text", "text": format_pack(pk)}], "structuredContent": pk, "isError": False}
                else:
                    raise KeyError(f"unknown tool {name}")
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
    if argv[0] == "watch":
        from rentready.watch import main as watch_main
        return watch_main(argv[1:])
    if argv[0] == "hosted":
        from rentready.hosted import main as hosted_main
        return hosted_main(argv[1:])
    if argv[0] == "pack":
        from rentready.pack import build_pack, format_pack
        files = [a for a in argv[1:] if not a.startswith("--")]
        o = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in argv[1:] if a.startswith("--"))
        if not files:
            print("pack: give a portfolio CSV", file=sys.stderr); return 2
        with open(files[0], encoding="utf-8") as fh:
            pk = build_pack(read_portfolio(fh.read()), today=o.get("today"), organisation="organisation" in o)
        text = json.dumps(pk, indent=2) if "json" in o else format_pack(pk)
        if o.get("out"):
            with open(o["out"], "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
            print(f"wrote {o['out']}: {pk['ready_to_register']} of {pk['in_scope']} ready to register", file=sys.stderr)
        else:
            print(text)
        return 0
    if argv[0] not in ("check", "portfolio", "calendar"):
        print(__doc__.strip(), file=sys.stderr); return 2
    rest = argv[1:]
    pos = [a for a in rest if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) if "=" in a else (a[2:], "1") for a in rest if a.startswith("--"))
    import os
    if argv[0] == "portfolio" or (argv[0] == "calendar" and pos and os.path.isfile(pos[0])):
        if not pos or not os.path.isfile(pos[0]):
            print("portfolio: give a CSV file (columns: name, postcode, gas, no_gas, eicr, eicr_due, epc, epc_rating, tenancy_start, region)", file=sys.stderr); return 2
        with open(pos[0], encoding="utf-8") as fh:
            p = check_portfolio(read_portfolio(fh.read()), today=opts.get("today"))
        if argv[0] == "portfolio":
            print(json.dumps(p, indent=2) if "json" in opts else format_portfolio(p))
            return 0 if p["not_ready"] == 0 else 1
        reports = p["properties"]
    else:
        postcode = " ".join(pos)
        r = check_property(postcode, region=opts.get("region"), gas=opts.get("gas"), no_gas="no-gas" in opts, eicr=opts.get("eicr"),
                           eicr_due=opts.get("eicr-due"), epc=opts.get("epc"), epc_rating=opts.get("epc-rating"), tenancy_start=opts.get("tenancy-start"),
                           properties=int(opts.get("properties", 1)), today=opts.get("today"))
        if argv[0] == "check":
            print(json.dumps(r, indent=2) if "json" in opts else format_report(r))
            return 0 if r.get("ready") else 1
        r["name"] = opts.get("name") or r.get("postcode") or "property"
        reports = [r]
    reminders = [int(x) for x in opts["reminders"].split(",") if x.strip()] if "reminders" in opts else None
    ics = format_ics(calendar_events(reports), reminders)
    if opts.get("out"):
        with open(opts["out"], "w", encoding="utf-8", newline="") as fh:
            fh.write(ics)
        print(f"wrote {opts['out']}: {ics.count('BEGIN:VEVENT')} events", file=sys.stderr)
    else:
        sys.stdout.write(ics)
    return 0


if __name__ == "__main__":
    sys.exit(main())

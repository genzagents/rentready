#!/usr/bin/env python3
"""rentready hosted: the paid monthly watch for landlords who do not want a GitHub repo. No server to run.

A subscriber pays on Polar and pastes their portfolio into the checkout's custom field (one property per line,
or the same CSV `rentready portfolio` reads). This runner (a cron or launchd job on any always-on machine) polls
Polar for active subscriptions, re-checks every property, keeps one state file per subscriber, and emails:

  * a first report within one run of paying (the product lands minutes after the card does),
  * an alert the moment something needs action (a gas safety record, EICR or EPC within 60 days of expiring,
    the region's window opening, a deadline nearing or passing, a property no longer ready),
  * a monthly digest otherwise, so they know it is still watching.

Every email is reproducible: the state file keeps the exact inputs, the date and the version, and
`rentready hosted replay FILE` re-runs the check offline and confirms the stored report comes out byte for byte.

    rentready hosted run                        # one pass against Polar + the email provider
    rentready hosted run --subscribers=f.json   # one pass against a local list (no Polar)
    rentready hosted run --dry-run              # never sends: prints every email it would send
    rentready hosted replay ~/.rentready-hosted/<id>.json
    rentready hosted launchd                    # prints a launchd plist that runs `run` hourly

Environment:
  POLAR_ACCESS_TOKEN        organisation access token (subscriptions:read). Required unless --subscribers.
  POLAR_PRODUCT_ID          optional: only subscriptions of this product.
  POLAR_SANDBOX=1           use sandbox-api.polar.sh.
  RESEND_API_KEY            email provider key. Required unless --dry-run.
  RENTREADY_FROM            sender, e.g. "rentready <watch@example.com>" (a verified Resend domain).
  RENTREADY_STATE_DIR       where state lives (default ~/.rentready-hosted).
  RENTREADY_LIMIT           properties per subscriber (default 10, what the page promises).
  RENTREADY_PRODUCT_LIMITS  per-product limits, "product_id=50,product_id2=10" (a bigger tier).
  RENTREADY_WARN_DAYS       days before an expiry or deadline to alert (default 60).

Polar custom field slugs read from each subscription's custom_field_data: `portfolio` (or properties / csv).
Zero dependencies.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rentready import __version__, _norm_col, check_portfolio, format_portfolio, read_portfolio  # noqa: E402
from rentready import watch as W  # noqa: E402

ACTIVE = {"active", "trialing", "past_due"}
MONTH = 30 * 24 * 3600
PORTFOLIO_KEYS = ("portfolio", "properties", "csv", "property", "rentals")
POSITIONAL = ["name", "postcode", "gas", "eicr", "epc", "epc_rating", "tenancy_start"]
NONE_WORDS = {"", "-", "none", "n/a", "na", "?", "unknown"}


# ----------------------------------------------------------------------------- pure logic (tested)

def _pick(data: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    low = {str(k).lower().strip(): v for k, v in (data or {}).items()}
    for k in keys:
        if k in low and low[k] not in (None, ""):
            return low[k]
    return None


def parse_portfolio_text(text: Any) -> List[Dict[str, str]]:
    """What a landlord types into a checkout box -> portfolio rows.

    Accepts the CSV `rentready portfolio` reads (header row), a JSON list, or one property per line with no header:
        name, postcode, gas date, EICR date, EPC date, EPC rating[, tenancy start]
    Use "-" for a date you do not have and "no gas" (or "none") in the gas column for an all-electric property."""
    if not isinstance(text, str) or not text.strip():
        return []
    text = text.strip().lstrip("﻿")
    if text.startswith("["):
        return read_portfolio(text)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    first = [_norm_col(c) for c in re.split(r"[,\t|;]", lines[0])]
    if "postcode" in first:
        return read_portfolio("\n".join(lines))
    rows: List[Dict[str, str]] = []
    for ln in lines:
        cells = [c.strip() for c in re.split(r"[,\t|;]", ln)]
        row: Dict[str, str] = {}
        for col, val in zip(POSITIONAL, cells):
            if col == "gas" and val.lower().replace("-", " ").replace("_", " ") in ("no gas", "nogas", "electric", "all electric"):
                row["no_gas"] = "yes"
                continue
            if val.lower() in NONE_WORDS:
                continue
            row[col] = val
        if row.get("postcode") or row.get("name"):
            rows.append(row)
    return rows


def limit_for(sub: Dict[str, Any]) -> int:
    """Properties allowed for this subscription: per-product override, else RENTREADY_LIMIT, else 10."""
    raw = os.environ.get("RENTREADY_PRODUCT_LIMITS", "")
    pid = str(sub.get("product_id") or (sub.get("product") or {}).get("id") or "")
    for part in raw.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            if k.strip() == pid and v.strip().isdigit():
                return max(1, int(v))
    try:
        return max(1, int(os.environ.get("RENTREADY_LIMIT", "10")))
    except ValueError:
        return 10


def normalise(sub: Dict[str, Any], limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Polar subscription -> {id, email, name, rows, limit}. None when not active or no email/portfolio."""
    if sub.get("status") not in ACTIVE:
        return None
    customer = sub.get("customer") or {}
    email = (customer.get("email") or sub.get("email") or "").strip()
    data = sub.get("custom_field_data") or {}
    rows = parse_portfolio_text(_pick(data, PORTFOLIO_KEYS))
    if not email or not rows:
        return None
    lim = limit if limit is not None else limit_for(sub)
    return {
        "id": str(sub.get("id") or email),
        "email": email,
        "name": (customer.get("name") or "").strip(),
        "rows": rows[:lim],
        "dropped": max(0, len(rows) - lim),
        "limit": lim,
        "period_end": sub.get("current_period_end") or "",
    }


def decide(state: Optional[Dict[str, Any]], alerts: List[str], better: List[str], now: float) -> str:
    """What to email this run: 'first', 'alert', 'digest' or ''."""
    if not state or not state.get("last_report_at"):
        return "first"
    if alerts or better:
        return "alert"
    if now - float(state.get("last_report_at", 0)) >= MONTH:
        return "digest"
    return ""


def subject(kind: str, p: Dict[str, Any], alerts: List[str]) -> str:
    counts = f"{p['ready']} ready, {p['not_ready']} not ready"
    if kind == "first":
        return f"Your first rentready report: {counts}"
    if kind == "alert":
        return f"rentready: {alerts[0] if alerts else 'something improved'}"
    nxt = f", earliest deadline {p['earliest_deadline']}" if p.get("earliest_deadline") else ""
    return f"rentready monthly: {counts}{nxt}"


def render_email(kind: str, sub: Dict[str, Any], p: Dict[str, Any], alerts: List[str], better: List[str],
                 warn_days: int = W.DEFAULT_WARN_DAYS) -> Tuple[str, str]:
    """(text, html) bodies. Plain text first; HTML is the same text in a readable wrapper (no dependencies)."""
    name = sub.get("name") or "there"
    lines: List[str] = [f"Hi {name},", ""]
    if kind == "first":
        lines += ["This is your first rentready report. From now on you get an email the moment something needs action",
                  f"(a gas safety record, EICR or EPC within {warn_days} days of expiring, your region's window opening,",
                  "a deadline nearing or passing, a property no longer ready) and a short digest once a month otherwise.", ""]
    if alerts:
        lines += ["ACTION NEEDED"] + [f"  - {a}" for a in alerts] + [""]
    if better:
        lines += ["IMPROVED"] + [f"  - {b}" for b in better] + [""]
    if kind == "digest" and not alerts and not better:
        lines += ["Monthly check: nothing changed since the last report. The table below is today's picture.", ""]
    lines += [format_portfolio(p).rstrip(), ""]
    if sub.get("dropped"):
        lines += [f"Note: your plan covers {sub['limit']} properties; {sub['dropped']} more in your list were not checked.", ""]
    lines += ["--", f"rentready {__version__} hosted watch. Reply to this email to change your portfolio;",
              "manage or cancel the subscription from the Polar receipt. Dates are the regulations' as published; check gov.uk.",
              "https://genzagents.github.io/rentready/"]
    text = "\n".join(lines)
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = ("<div style=\"font-family:ui-monospace,Menlo,monospace;font-size:13px;line-height:1.45;white-space:pre-wrap;"
            "max-width:860px\">" + esc + "</div>")
    return text, html


def with_regions(rows: List[Dict[str, str]], state: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Fill `region` from the last run's inputs (same postcode) so later runs need no lookup and replay is offline."""
    known: Dict[str, str] = {}
    for r in (state or {}).get("inputs") or []:
        if r.get("postcode") and r.get("region"):
            known[r["postcode"].upper().replace(" ", "")] = r["region"]
    out = []
    for r in rows:
        r = dict(r)
        key = (r.get("postcode") or "").upper().replace(" ", "")
        if key and not r.get("region") and key in known:
            r["region"] = known[key]
        out.append(r)
    return out


def record_inputs(rows: List[Dict[str, str]], p: Dict[str, Any]) -> List[Dict[str, str]]:
    """The rows as checked, with the region the lookup found written in, so the check can be replayed offline."""
    out = []
    for row, r in zip(rows, p["properties"]):
        row = dict(row)
        if r.get("region") and not row.get("region"):
            row["region"] = r["region"]
        elif r.get("ready") is None and not row.get("region"):
            row["region"] = row.get("region") or ""
        out.append(row)
    return out


def replay(state: Dict[str, Any]) -> Dict[str, Any]:
    """Re-run the stored inputs on the stored date and compare with the stored snapshot. Offline when regions are stored."""
    rows = state.get("inputs") or []
    today = state.get("today")
    p = check_portfolio(rows, today=today)
    snap = W.snapshot(p, int(state.get("warn_days") or W.DEFAULT_WARN_DAYS))
    stored = state.get("snapshot") or {}
    same_snapshot = _canon(snap) == _canon(stored)
    report = format_portfolio(p)
    same_report = report == state.get("report")
    return {"today": today, "version_then": state.get("version"), "version_now": __version__,
            "properties": len(rows), "same_snapshot": same_snapshot, "same_report": same_report,
            "report": report, "last_email": state.get("last_email") or {}}


def _canon(d: Dict[str, Any]) -> str:
    d = dict(d)
    d.pop("version", None)
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


# ----------------------------------------------------------------------------- I/O

def _http(method: str, url: str, headers: Dict[str, str], body: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Dict[str, Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", **headers})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {url} -> {e.code}: {e.read().decode('utf-8', 'replace')[:300]}") from None
    return json.loads(raw) if raw.strip() else {}


def polar_subscriptions() -> List[Dict[str, Any]]:
    token = os.environ.get("POLAR_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("POLAR_ACCESS_TOKEN is not set (or pass --subscribers=file.json)")
    base = "https://sandbox-api.polar.sh" if os.environ.get("POLAR_SANDBOX") else "https://api.polar.sh"
    product = os.environ.get("POLAR_PRODUCT_ID", "")
    out: List[Dict[str, Any]] = []
    page = 1
    while True:
        url = f"{base}/v1/subscriptions/?limit=100&page={page}" + (f"&product_id={product}" if product else "")
        res = _http("GET", url, {"Authorization": f"Bearer {token}"})
        items = res.get("items") or []
        out += items
        if page >= int((res.get("pagination") or {}).get("max_page") or 1) or not items:
            return out
        page += 1


def send_email(to: str, subj: str, text: str, html: str) -> str:
    key = os.environ.get("RESEND_API_KEY")
    sender = os.environ.get("RENTREADY_FROM", "rentready <onboarding@resend.dev>")
    if not key:
        raise RuntimeError("RESEND_API_KEY is not set (use --dry-run to print emails instead)")
    res = _http("POST", "https://api.resend.com/emails", {"Authorization": f"Bearer {key}"},
                {"from": sender, "to": [to], "subject": subj, "text": text, "html": html})
    return str(res.get("id", ""))


def state_dir() -> str:
    d = os.environ.get("RENTREADY_STATE_DIR") or os.path.join(os.path.expanduser("~"), ".rentready-hosted")
    os.makedirs(d, exist_ok=True)
    return d


def _state_path(sub_id: str) -> str:
    return os.path.join(state_dir(), re.sub(r"[^A-Za-z0-9_.-]", "_", sub_id) + ".json")


def load_state(sub_id: str) -> Optional[Dict[str, Any]]:
    p = _state_path(sub_id)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_state(sub_id: str, state: Dict[str, Any]) -> None:
    with open(_state_path(sub_id), "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)


def process(sub: Dict[str, Any], now: float, today: Optional[str] = None,
            warn_days: int = W.DEFAULT_WARN_DAYS) -> Dict[str, Any]:
    """Run one subscriber: check the portfolio, diff against state, return what to send (not sent)."""
    state = load_state(sub["id"]) or {}
    rows = with_regions(sub["rows"], state)
    today = today or dt.datetime.fromtimestamp(now, dt.timezone.utc).date().isoformat()
    p = check_portfolio(rows, today=today)
    snap = W.snapshot(p, warn_days)
    alerts, better = W.diff(state.get("snapshot"), snap)
    kind = decide(state, alerts, better, now)
    new_state = {**state, "email": sub["email"], "inputs": record_inputs(rows, p), "today": today,
                 "warn_days": warn_days, "snapshot": snap, "report": format_portfolio(p),
                 "last_run_at": now, "version": __version__}
    return {"kind": kind, "portfolio": p, "alerts": alerts, "better": better, "state": new_state}


def run(subscribers: List[Dict[str, Any]], dry_run: bool, now: Optional[float] = None, today: Optional[str] = None,
        warn_days: int = W.DEFAULT_WARN_DAYS, out=sys.stdout) -> int:
    now = now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    sent = 0
    for sub in subscribers:
        try:
            res = process(sub, now, today=today, warn_days=warn_days)
        except Exception as e:  # noqa: BLE001 - one subscriber's failure must not stop the others
            print(f"hosted: {sub['email']}: {e}", file=sys.stderr)
            continue
        kind = res["kind"]
        if kind:
            subj = subject(kind, res["portfolio"], res["alerts"])
            text, html = render_email(kind, sub, res["portfolio"], res["alerts"], res["better"], warn_days)
            if dry_run:
                print(f"=== would send [{kind}] to {sub['email']}: {subj}\n{text}\n", file=out)
            else:
                msg_id = send_email(sub["email"], subj, text, html)
                print(f"hosted: sent [{kind}] to {sub['email']} ({msg_id}): {subj}", file=out)
            res["state"]["last_report_at"] = now
            res["state"]["last_kind"] = kind
            res["state"]["last_email"] = {"kind": kind, "subject": subj, "text": text, "at": now}
            sent += 1
        else:
            hours = max(0, int((MONTH - (now - float(res["state"].get("last_report_at", now)))) / 3600))
            print(f"hosted: {sub['email']}: no change, next digest in {hours}h", file=out)
        save_state(sub["id"], res["state"])
    print(f"hosted: {len(subscribers)} subscriber(s), {sent} email(s){' (dry run)' if dry_run else ''}", file=out)
    return 0


LAUNCHD = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.genzagents.rentready.hosted</string>
  <key>ProgramArguments</key><array>
    <string>{python}</string><string>-m</string><string>rentready.hosted</string><string>run</string>
  </array>
  <key>WorkingDirectory</key><string>{cwd}</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{home}/.rentready-hosted/run.log</string>
  <key>StandardErrorPath</key><string>{home}/.rentready-hosted/run.err</string>
</dict></plist>
<!-- Secrets: put POLAR_ACCESS_TOKEN, RESEND_API_KEY and RENTREADY_FROM in the EnvironmentVariables dict
     (or source them from the keychain in a wrapper script). Install:
       cp this ~/Library/LaunchAgents/io.genzagents.rentready.hosted.plist && launchctl load -w ~/Library/LaunchAgents/io.genzagents.rentready.hosted.plist -->
"""


def _flag(flags: List[str], name: str, default: str = "") -> str:
    for f in flags:
        if f.startswith(name + "="):
            return f.split("=", 1)[1]
    return default


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0
    cmd, flags = argv[0], [a for a in argv[1:] if a.startswith("--")]
    paths = [a for a in argv[1:] if not a.startswith("--")]
    if cmd == "launchd":
        print(LAUNCHD.format(python=sys.executable, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                             home=os.path.expanduser("~")))
        return 0
    if cmd == "replay":
        if not paths or not os.path.isfile(paths[0]):
            print("replay: give a state file (~/.rentready-hosted/<id>.json)", file=sys.stderr)
            return 2
        with open(paths[0], encoding="utf-8") as f:
            res = replay(json.load(f))
        ok = res["same_snapshot"] and res["same_report"]
        print(f"replay of {paths[0]}: {res['properties']} properties on {res['today']}, "
              f"stored with {res['version_then']}, replayed with {res['version_now']}: "
              f"{'IDENTICAL' if ok else 'DIFFERENT'} (snapshot {'same' if res['same_snapshot'] else 'differs'}, "
              f"report {'same' if res['same_report'] else 'differs'})")
        if res["last_email"]:
            print(f"last email [{res['last_email'].get('kind')}]: {res['last_email'].get('subject')}")
        if "--show" in flags or not ok:
            print()
            print(res["report"])
        return 0 if ok else 1
    if cmd != "run":
        print(f"unknown command {cmd!r}; see --help", file=sys.stderr)
        return 2
    src = _flag(flags, "--subscribers")
    if src:
        with open(src, encoding="utf-8") as f:
            raw = json.load(f)
        raw = raw.get("items", raw) if isinstance(raw, dict) else raw
    else:
        raw = polar_subscriptions()
    subs = [s for s in (normalise(x) for x in raw) if s]
    skipped = len(raw) - len(subs)
    if skipped:
        print(f"hosted: {skipped} subscription(s) skipped (not active, or no email/portfolio in custom fields)", file=sys.stderr)
    warn_days = int(_flag(flags, "--warn-days", os.environ.get("RENTREADY_WARN_DAYS", str(W.DEFAULT_WARN_DAYS))))
    now = float(_flag(flags, "--now", "0")) or None
    return run(subs, dry_run="--dry-run" in flags, now=now, today=_flag(flags, "--today", "") or None, warn_days=warn_days)


if __name__ == "__main__":
    sys.exit(main())

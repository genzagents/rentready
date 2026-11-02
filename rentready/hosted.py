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
    rentready hosted run --source=github        # GitHub Sponsors + private repo per landlord, no Polar/Resend
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

GitHub Sponsors instead of Polar and Resend (`run --source=github`): a landlord sponsors the org once
(RENTREADY_GH_ONE_TIME dollars, default 16, about £12, buys a year) or monthly (RENTREADY_GH_MONTHLY, default 2).
Within the hour the runner makes a private repo `<org>/rentready-<login>`, invites them, and opens one issue asking
for their properties. Addresses never go anywhere public. Their latest comment that parses as a portfolio is what
gets watched; reports are comments on that issue that @mention them, so GitHub emails each one. The runner keeps
a ledger (sponsors.json in the state dir) because GitHub lists a one-time sponsor as active for 30 days only.
  GITHUB_TOKEN         token with repo + read:org (default: `gh auth token`).
  RENTREADY_GH_ORG     sponsored org and owner of the private repos (default genzagents).
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
YEAR = 365 * 24 * 3600
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
              "manage or cancel the subscription from the Polar receipt. Dates are the draft regulations' as published; check gov.uk.",
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

# ----------------------------------------------------------------------------- GitHub Sponsors (pure, tested)

def update_ledger(ledger: Dict[str, Any], sponsors: List[Dict[str, Any]], now: float,
                  one_time_min: int = 16, monthly_min: int = 2) -> List[str]:
    """Fold GitHub's active sponsors into the ledger in place; return the logins that just paid for the first time.

    A one-time payment of one_time_min dollars or more buys a year from the first run that sees it (GitHub keeps it
    listed for 30 days, so it is only counted once). A monthly sponsorship of monthly_min or more stays paid while
    GitHub lists it, plus five days of grace. A one-time payment seen again after its year has ended renews it."""
    new: List[str] = []
    for s in sponsors:
        login = str(s.get("login") or "").lower()
        amount = int(s.get("monthly") or 0)
        if not login:
            continue
        rec = ledger.get(login)
        if s.get("one_time"):
            if amount < one_time_min:
                continue
            if rec and float(rec.get("paid_until", 0)) > now:
                continue
            until = now + YEAR
        else:
            if amount < monthly_min:
                continue
            until = now + MONTH + 5 * 24 * 3600
        if not rec:
            new.append(login)
            rec = ledger[login] = {"login": s.get("login"), "first_paid_at": now}
        rec["paid_until"] = max(float(rec.get("paid_until", 0)), until)
        rec["plan"] = "monthly" if not s.get("one_time") else "year"
        rec.pop("expired_notice_at", None)
    return new


def repo_name(org: str, login: str) -> str:
    return f"{org}/rentready-{re.sub(r'[^A-Za-z0-9_.-]', '-', login.lower())}"


def welcome_body(login: str) -> str:
    return (f"@{login} thank you for paying for the rentready watch. This repository is private: only you and "
            "genzagents can see it.\n\n"
            "**Reply to this issue with your properties**, one per line, and the watch starts within the hour. "
            "The order is: name, postcode, gas safety date, EICR date, EPC date, EPC rating, tenancy start.\n\n"
            "```\n"
            "Flat 1, B15 2TT, 2026-03-01, 2023-06-10, 2019-01-20, D, 2024-09-01\n"
            "Cottage, CV37 6BB, no gas, 2022-11-02, 2017-05-14, E, -\n```\n\n"
            "Use `-` for a date you do not have and `no gas` for an all-electric property. You can also paste the "
            "CSV the free check at https://genzagents.github.io/rentready/ downloads. Your plan covers up to 10 "
            "properties. To change the list later, post a new comment with the whole list; the newest one is used.\n\n"
            "From then on this issue gets a comment, and GitHub emails you, the moment something needs action "
            "(a gas safety record, EICR or EPC within 60 days of expiring, your region's registration window "
            "opening, a deadline nearing or passing, a property no longer ready), and a short digest once a month "
            "otherwise.\n\n"
            "Dates follow the draft regulations as published; check gov.uk before you act on one. "
            "Terms: https://genzagents.github.io/rentready/terms.html")


def latest_portfolio(comments: List[Dict[str, Any]], login: str) -> Tuple[List[Dict[str, str]], str]:
    """The sponsor's newest comment that parses as a portfolio -> (rows, comment id). ([], '') when none yet."""
    for c in sorted(comments, key=lambda c: int(c.get("id") or 0), reverse=True):
        if str(c.get("author") or "").lower() != login.lower():
            continue
        body = re.sub(r"```[a-z]*", "", str(c.get("body") or ""))
        body = re.sub(r"(?im)^\s*name,\s*postcode,\s*gas safety date.*$", "", body)  # our instruction line, copied
        rows = [r for r in parse_portfolio_text(body) if r.get("postcode")]
        if rows:
            return rows, str(c.get("id"))
    return [], ""


def comment_text(login: str, subj: str, text: str) -> str:
    return f"@{login} **{subj}**\n\n```\n{text}\n```"


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


def gh_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    import subprocess
    return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()


def _gh(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Any:
    return _http(method, "https://api.github.com" + path, {"Authorization": f"Bearer {gh_token()}",
                                                         "X-GitHub-Api-Version": "2022-11-28"}, body)


def fetch_sponsors(org: str) -> List[Dict[str, Any]]:
    q = ("query($org:String!){organization(login:$org){sponsorshipsAsMaintainer(first:100,activeOnly:true){nodes{"
         "tier{monthlyPriceInDollars isOneTime} "
         "sponsorEntity{... on User{login} ... on Organization{login}}}}}}")
    res = _gh("POST", "/graphql", {"query": q, "variables": {"org": org}})
    if res.get("errors"):
        raise RuntimeError(f"GitHub sponsors query: {res['errors'][0].get('message')}")
    nodes = (((res.get("data") or {}).get("organization") or {}).get("sponsorshipsAsMaintainer") or {}).get("nodes") or []
    return [{"login": (n.get("sponsorEntity") or {}).get("login", ""),
             "monthly": (n.get("tier") or {}).get("monthlyPriceInDollars") or 0,
             "one_time": bool((n.get("tier") or {}).get("isOneTime"))} for n in nodes]


def provision(org: str, rec: Dict[str, Any]) -> None:
    """Private repo + invitation + the welcome issue for one new sponsor (idempotent on rec)."""
    login = rec["login"]
    repo = rec.get("repo") or repo_name(org, login)
    if not rec.get("repo"):
        try:
            _gh("POST", f"/orgs/{org}/repos", {"name": repo.split("/", 1)[1], "private": True, "auto_init": True,
                                                "has_wiki": False, "has_projects": False,
                                                "description": f"rentready watch for {login} (private)"})
        except RuntimeError as e:
            if "422" not in str(e):  # already exists from an interrupted run
                raise
        rec["repo"] = repo
    if not rec.get("invited"):
        _gh("PUT", f"/repos/{repo}/collaborators/{login}", {"permission": "triage"})
        rec["invited"] = True
    if not rec.get("issue"):
        res = _gh("POST", f"/repos/{repo}/issues", {"title": "Your rentready watch: reply with your properties",
                                                     "body": welcome_body(login)})
        rec["issue"] = int(res["number"])


def fetch_comments(repo: str, issue: int) -> List[Dict[str, Any]]:
    raw = _gh("GET", f"/repos/{repo}/issues/{issue}/comments?per_page=100") or []
    return [{"id": c.get("id"), "author": (c.get("user") or {}).get("login", ""), "body": c.get("body") or ""} for c in raw]


def post_comment(repo: str, issue: int, body: str) -> str:
    return str(_gh("POST", f"/repos/{repo}/issues/{issue}/comments", {"body": body}).get("html_url", ""))


def load_ledger() -> Dict[str, Any]:
    return load_state("sponsors") or {}


def github_pass(org: str, now: float, dry_run: bool, out=sys.stdout) -> List[Dict[str, Any]]:
    """Update the ledger, provision new sponsors, expire lapsed ones; return subscribers ready to be checked."""
    ledger = load_ledger()
    sponsors = fetch_sponsors(org)
    new = update_ledger(ledger, sponsors, now, int(os.environ.get("RENTREADY_GH_ONE_TIME", "16")),
                        int(os.environ.get("RENTREADY_GH_MONTHLY", "2")))
    print(f"hosted: {len(sponsors)} active sponsor(s), {len(ledger)} in ledger, {len(new)} new", file=sys.stderr)
    subs: List[Dict[str, Any]] = []
    for login, rec in sorted(ledger.items()):
        if float(rec.get("paid_until", 0)) <= now:
            if rec.get("issue") and not rec.get("expired_notice_at") and not dry_run:
                post_comment(rec["repo"], rec["issue"], f"@{rec['login']} your rentready year has ended, so the watch "
                             "has stopped. Renew at https://genzagents.github.io/rentready/#watch and it carries on "
                             "here with the same list.")
                rec["expired_notice_at"] = now
            continue
        if dry_run and not rec.get("issue"):
            print(f"=== would create {repo_name(org, rec['login'])}, invite @{rec['login']}, open the welcome issue", file=out)
            continue
        provision(org, rec)
        rows, cid = latest_portfolio(fetch_comments(rec["repo"], rec["issue"]), rec["login"])
        if not rows:
            print(f"hosted: @{rec['login']}: waiting for their properties on {rec['repo']}#{rec['issue']}", file=out)
            continue
        lim = int(os.environ.get("RENTREADY_LIMIT", "10"))
        subs.append({"id": f"gh-{login}", "email": f"@{rec['login']}", "name": rec["login"], "rows": rows[:lim],
                     "dropped": max(0, len(rows) - lim), "limit": lim, "repo": rec["repo"], "issue": rec["issue"],
                     "comment_id": cid, "period_end": dt.datetime.fromtimestamp(float(rec["paid_until"]),
                                                                                  dt.timezone.utc).date().isoformat()})
    if not dry_run:
        save_state("sponsors", ledger)
    return subs


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
            if sub.get("repo"):
                text = text.replace("Reply to this email to change your portfolio;\nmanage or cancel the subscription from the Polar receipt.",
                                    "Post your whole list again here to change it;\nrenew from https://genzagents.github.io/rentready/#watch .")
            if dry_run:
                print(f"=== would send [{kind}] to {sub['email']}: {subj}\n{text}\n", file=out)
            elif sub.get("repo"):
                url = post_comment(sub["repo"], sub["issue"], comment_text(sub["name"], subj, text))
                print(f"hosted: posted [{kind}] for {sub['email']} ({url}): {subj}", file=out)
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
    warn_days = int(_flag(flags, "--warn-days", os.environ.get("RENTREADY_WARN_DAYS", str(W.DEFAULT_WARN_DAYS))))
    now = float(_flag(flags, "--now", "0")) or None
    if _flag(flags, "--source") == "github":
        t = now or dt.datetime.now(dt.timezone.utc).timestamp()
        subs = github_pass(os.environ.get("RENTREADY_GH_ORG", "genzagents"), t, "--dry-run" in flags)
        return run(subs, dry_run="--dry-run" in flags, now=t, today=_flag(flags, "--today", "") or None, warn_days=warn_days)
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
    return run(subs, dry_run="--dry-run" in flags, now=now, today=_flag(flags, "--today", "") or None, warn_days=warn_days)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""rentready watch: re-check a portfolio CSV, remember the result, and raise the alarm the moment something
changes: a certificate expires or comes within N days of expiring, a property stops being ready, a region's
registration window opens, or a deadline approaches or passes.

    rentready watch properties.csv [--warn-days=60] [--state=FILE | --repo=OWNER/NAME] [--no-issue]
                                   [--notify=@login] [--label=rentready] [--always-comment]
                                   [--no-fail-on-regression] [--fail-if-not-ready] [--today=YYYY-MM-DD]

Two ways to remember the previous run:
  * a GitHub issue titled "rentready watch: <file>" in --repo (or $GITHUB_REPOSITORY): the body is the current
    portfolio table, the state is kept in an HTML comment, and a comment (GitHub emails it to subscribers) is
    posted only when something changed. Needs the `gh` CLI (present on every GitHub Actions runner).
  * --state=FILE: a local JSON file, for cron on your own machine. Nothing leaves the machine except the
    postcode lookup.

Designed for GitHub Actions (see action.yml and docs/watch.yml). Environment used when present: GH_TOKEN,
GITHUB_REPOSITORY, GITHUB_STEP_SUMMARY, GITHUB_OUTPUT, GITHUB_SERVER_URL, GITHUB_RUN_ID. Zero dependencies.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rentready import __version__, _d, check_portfolio, format_portfolio, read_portfolio  # noqa: E402

STATE_RE = re.compile(r"<!-- rentready-state (\{.*?\}) -->", re.S)
TITLE_PREFIX = "rentready watch: "
RANK = {"PASS": 0, "INFO": 0, "WARN": 1, "FAIL": 2}
DEFAULT_WARN_DAYS = 60


# ----------------------------------------------------------------------------- pure logic (tested)

def snapshot(p: Dict[str, Any], warn_days: int = DEFAULT_WARN_DAYS) -> Dict[str, Any]:
    """The facts worth comparing between runs, per property, keyed by name (made unique)."""
    t = _d(p["today"]) or date.today()
    props: Dict[str, Any] = {}
    for r in p["properties"]:
        name = str(r.get("name") or r.get("postcode") or "property")
        key, n = name, 2
        while key in props:
            key, n = f"{name} ({n})", n + 1
        w = r.get("window") or {}
        window = None
        if w:
            opens, deadline = _d(w["opens"]), _d(w["deadline"])
            window = "passed" if t > deadline else "open" if t >= opens else "upcoming"
        due: Dict[str, str] = {}
        for cert, iso in (r.get("expiries") or {}).items():
            days = (_d(iso) - t).days
            if 0 <= days <= warn_days:
                due[cert] = iso
        deadline_due = bool(w) and 0 <= (_d(w["deadline"]) - t).days <= warn_days
        props[key] = {
            "postcode": r.get("postcode"), "region": r.get("region"), "ready": r.get("ready"),
            "window": window, "deadline": w.get("deadline"), "deadline_due": deadline_due,
            "checks": {f["check"]: f["status"] for f in r.get("findings", [])},
            "details": {f["check"]: f["detail"] for f in r.get("findings", []) if f["status"] in ("WARN", "FAIL")},
            "expiries": r.get("expiries") or {}, "due": due,
            "actions": list(r.get("actions") or []),
        }
    return {"version": __version__, "today": p["today"], "warn_days": warn_days,
            "fee": p.get("fee_gbp_per_year"), "earliest_deadline": p.get("earliest_deadline"),
            "ready": p.get("ready"), "not_ready": p.get("not_ready"), "properties": props}


def _status_word(ready: Optional[bool]) -> str:
    return "READY" if ready is True else "NOT READY" if ready is False else "out of scope"


def diff(prev: Optional[Dict[str, Any]], cur: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Returns (alerts, better): sentences describing what needs attention now and what improved.

    Alerts are regressions (a check got worse, a property is no longer ready, a deadline passed) and
    things that just came due (a certificate or deadline entered the warn window, a window opened).
    The first run (prev is None) produces no sentences: creating the issue is the first email."""
    alerts: List[str] = []
    better: List[str] = []
    if not prev:
        return alerts, better
    pp, cp = prev.get("properties", {}), cur.get("properties", {})
    for name, c in cp.items():
        p = pp.get(name)
        if p is None:
            alerts.append(f"{name}: added to the portfolio ({_status_word(c['ready'])}).") if c["ready"] is False \
                else better.append(f"{name}: added to the portfolio ({_status_word(c['ready'])}).")
            continue
        if p.get("ready") is True and c["ready"] is False:
            alerts.append(f"{name}: no longer READY.")
        elif p.get("ready") is False and c["ready"] is True:
            better.append(f"{name}: READY again.")
        for check, status in c["checks"].items():
            if check == "registration deadline":
                continue  # window and deadline transitions are reported in plainer words below
            before = p.get("checks", {}).get(check, "PASS")
            if RANK.get(status, 0) > RANK.get(before, 0):
                alerts.append(f"{name}: {check} is now {status} ({c['details'].get(check, '')}).".replace(" ().", "."))
            elif RANK.get(status, 0) < RANK.get(before, 0):
                better.append(f"{name}: {check} is now {status}.")
        for cert, iso in c["due"].items():
            if cert not in p.get("due", {}) and c["checks"].get(cert) != "FAIL":
                days = (_d(iso) - _d(cur["today"])).days
                alerts.append(f"{name}: {cert} expires {iso} ({days} days); book the renewal now.")
        if c.get("window") == "open" and p.get("window") == "upcoming":
            alerts.append(f"{name}: the {c.get('region')} registration window is open; register by {c.get('deadline')}.")
        if c.get("window") == "passed" and p.get("window") != "passed":
            alerts.append(f"{name}: the {c.get('region')} registration deadline {c.get('deadline')} has passed.")
        elif c.get("deadline_due") and not p.get("deadline_due") and c.get("window") == "open":
            days = (_d(c["deadline"]) - _d(cur["today"])).days
            alerts.append(f"{name}: registration deadline {c['deadline']} is {days} days away.")
    for name in pp:
        if name not in cp:
            better.append(f"{name}: removed from the portfolio.")
    return alerts, better


def parse_state(body: str) -> Optional[Dict[str, Any]]:
    m = STATE_RE.search(body or "")
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def issue_title(path: str) -> str:
    return TITLE_PREFIX + os.path.basename(path)


def render_body(path: str, p: Dict[str, Any], snap: Dict[str, Any], run_url: str = "") -> str:
    out = [f"## {issue_title(path)}", ""]
    line = (f"**{p['ready']} ready, {p['not_ready']} not ready** of {p['in_scope']} in England "
            f"· fee £{p['fee_gbp_per_year']} a year · earliest deadline {p.get('earliest_deadline') or 'n/a'} "
            f"· checked {p['today']}")
    if run_url:
        line += f" · [run]({run_url})"
    out += [line, "", "| Property | Region | Deadline | Status | Next |", "|---|---|---|---|---|"]
    for r in p["properties"]:
        w = r.get("window") or {}
        nxt = r.get("next")
        nxt_s = f"{nxt['date']} {nxt['what']} ({nxt['days']}d)" if nxt else ""
        out.append(f"| {r['name']} | {r.get('region') or 'unknown'} | {w.get('deadline', '')} | {_status_word(r.get('ready'))} | {nxt_s} |")
    bad = [(r["name"], f) for r in p["properties"] for f in r["findings"] if f["status"] in ("FAIL", "WARN")]
    if bad:
        out += ["", "**Needs attention**", ""]
        for name, f in bad:
            out.append(f"- [{f['status']}] {name}: {f['check']}: {f['detail']}")
    actions = [(r["name"], a) for r in p["properties"] for a in r.get("actions", [])]
    if actions:
        out += ["", "**Do next**", ""]
        out += [f"- {name}: {a}" for name, a in actions]
    out += ["", f"<sub>Kept up to date by [rentready watch](https://github.com/genzagents/rentready#watch) "
                f"{__version__}. It comments here only when something changes (a certificate comes within "
                f"{snap['warn_days']} days of expiring, a window opens, a deadline nears, a property stops being ready), "
                f"so subscribe to this issue to get the email. Dates are the regulations' as published; check gov.uk.</sub>",
            "", f"<!-- rentready-state {json.dumps(snap, separators=(',', ':'))} -->"]
    return "\n".join(out)


def render_comment(alerts: List[str], better: List[str], p: Dict[str, Any], notify: str, run_url: str,
                   heading: str = "Action needed") -> str:
    out: List[str] = []
    if alerts:
        mention = f"{notify} " if notify else ""
        out.append(f"{mention}**{heading}**")
        out += [f"- {a}" for a in alerts]
    if better:
        out.append("" if alerts else "**Improved**")
        out += [f"- {b}" for b in better]
    if not alerts and not better:
        out.append(f"**Monthly check: nothing changed.** {p['ready']} ready, {p['not_ready']} not ready; "
                   f"earliest deadline {p.get('earliest_deadline') or 'n/a'}.")
    else:
        out.append(f"\nNow {p['ready']} ready, {p['not_ready']} not ready; earliest deadline {p.get('earliest_deadline') or 'n/a'}.")
    if run_url:
        out.append(f"Full report: {run_url}")
    return "\n".join(out)


# ----------------------------------------------------------------------------- GitHub glue (gh CLI)

def gh(*args: str, input_: Optional[str] = None) -> str:
    pr = subprocess.run(["gh", *args], capture_output=True, text=True, input=input_)
    if pr.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} failed: {pr.stderr.strip()[:400]}")
    return pr.stdout


def find_issue(repo: str, title: str) -> Optional[Dict[str, Any]]:
    raw = gh("issue", "list", "--repo", repo, "--state", "all", "--limit", "100",
             "--search", f'"{title}" in:title', "--json", "number,title,body,state")
    for it in json.loads(raw or "[]"):
        if it["title"].strip().lower() == title.lower():
            return it
    return None


def upsert_issue(repo: str, path: str, p: Dict[str, Any], snap: Dict[str, Any], notify: str, run_url: str,
                 label: str = "rentready", always_comment: bool = False) -> Dict[str, Any]:
    title = issue_title(path)
    body = render_body(path, p, snap, run_url)
    existing = find_issue(repo, title)
    prev = parse_state(existing["body"]) if existing else None
    alerts, better = diff(prev, snap)
    if existing is None:
        try:
            gh("label", "create", label, "--repo", repo, "--color", "0e8a16",
               "--description", "rentready watch results", "--force")
        except RuntimeError:
            pass
        out = gh("issue", "create", "--repo", repo, "--title", title, "--body", body, "--label", label)
        number = int(out.strip().rsplit("/", 1)[-1])
        return {"number": number, "created": True, "alerts": alerts, "better": better}
    number = int(existing["number"])
    gh("issue", "edit", str(number), "--repo", repo, "--body", body)
    if alerts or better or always_comment:
        if alerts and existing.get("state", "").upper() == "CLOSED":
            gh("issue", "reopen", str(number), "--repo", repo)
        gh("issue", "comment", str(number), "--repo", repo, "--body", render_comment(alerts, better, p, notify, run_url))
    return {"number": number, "created": False, "alerts": alerts, "better": better}


# ----------------------------------------------------------------------------- entry point

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
    flags = [a for a in argv if a.startswith("--")]
    paths = [a for a in argv if not a.startswith("--")]
    if len(paths) != 1 or not os.path.isfile(paths[0]):
        print("watch: give one portfolio CSV (or JSON) file", file=sys.stderr)
        return 2
    path = paths[0]
    warn_days = int(_flag(flags, "--warn-days", str(DEFAULT_WARN_DAYS)))
    state_file = _flag(flags, "--state", "")
    use_issue = "--no-issue" not in flags and not state_file
    repo = _flag(flags, "--repo", os.environ.get("GITHUB_REPOSITORY", ""))
    notify = _flag(flags, "--notify", "")
    if notify and not notify.startswith("@"):
        notify = "@" + notify
    label = _flag(flags, "--label", "rentready")
    always_comment = "--always-comment" in flags
    fail_on_regression = "--no-fail-on-regression" not in flags
    fail_if_not_ready = "--fail-if-not-ready" in flags
    today = _flag(flags, "--today", "") or None
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID") and repo:
        run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"

    with open(path, encoding="utf-8") as fh:
        p = check_portfolio(read_portfolio(fh.read()), today=today)
    snap = snapshot(p, warn_days)
    print(format_portfolio(p))
    print()

    alerts: List[str] = []
    better: List[str] = []
    issue_cell = "off"
    if state_file:
        prev = None
        if os.path.isfile(state_file):
            with open(state_file, encoding="utf-8") as fh:
                try:
                    prev = json.load(fh)
                except ValueError:
                    prev = None
        alerts, better = diff(prev, snap)
        with open(state_file, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=1)
        issue_cell = f"state file {state_file}"
    elif use_issue:
        if not repo:
            print("watch: no --repo, no GITHUB_REPOSITORY and no --state; nothing remembered (use --no-issue to silence)", file=sys.stderr)
        else:
            try:
                res = upsert_issue(repo, path, p, snap, notify, run_url, label, always_comment)
                alerts, better = res["alerts"], res["better"]
                issue_cell = f"[#{res['number']}](https://github.com/{repo}/issues/{res['number']})" + (" (new)" if res["created"] else "")
            except RuntimeError as e:
                issue_cell = f"error: {e}"
                print(f"watch: {e}", file=sys.stderr)
    for a in alerts:
        print(f"  ALERT: {a}")
    for b in better:
        print(f"  improved: {b}")
    regressed = bool(alerts)
    changed = bool(alerts or better)

    summary = [f"## rentready watch {__version__}", "",
               "| Portfolio | Ready | Not ready | Earliest deadline | Changed | Issue |", "|---|---|---|---|---|---|",
               f"| {os.path.basename(path)} | {p['ready']} | {p['not_ready']} | {p.get('earliest_deadline') or 'n/a'} | "
               f"{'; '.join(alerts) if alerts else ('; '.join(better) if better else 'no')} | {issue_cell} |"]
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("\n".join(summary) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        nxt = min((r["next"]["days"] for r in p["properties"] if r.get("next")), default="")
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"ready={p['ready']}\nnot-ready={p['not_ready']}\nearliest-deadline={p.get('earliest_deadline') or ''}\n"
                    f"days-to-next={nxt}\nregressed={'true' if regressed else 'false'}\nchanged={'true' if changed else 'false'}\n")
    rc = 0
    if regressed and fail_on_regression:
        rc = 1
    if fail_if_not_ready and p["not_ready"]:
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())

"""Build docs/numbers.html, rentready's public weekly numbers, from docs/data/numbers.json.

Add one entry to "weeks" per weekly report and re-run; the newest entry is shown at the top.
"""
import html
import json
from datetime import date
from pathlib import Path

from schema import apply

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data" / "numbers.json"
OUT = ROOT / "docs" / "numbers.html"
BASE = "https://genzagents.github.io/rentready/"
ICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' "
        "fill='%230e5a44'/%3E%3Cpath d='M8 15.5 16 9l8 6.5V24H8z' fill='none' stroke='%23fff' stroke-width='2.2' "
        "stroke-linejoin='round'/%3E%3Cpath d='m12.5 18.5 2.6 2.6 4.6-5' fill='none' stroke='%23fff' stroke-width='2.2' "
        "stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")
BRAND = ('<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#0e5a44"/><path d="M8 15.5 16 9l8 6.5V24H8z" '
         'fill="none" stroke="#fff" stroke-width="2.2" stroke-linejoin="round"/><path d="m12.5 18.5 2.6 2.6 4.6-5" fill="none" stroke="#fff" '
         'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
FOOT = ('<footer class="foot mut"><a href="{b}about.html">About</a> · <a href="{b}guides/">Guides</a> · <a href="{b}developers.html">Developers</a> · '
        '<a href="{b}privacy.html">Privacy</a> · <a href="{b}terms.html">Terms</a> · <a href="https://github.com/genzagents/rentready/issues">'
        'Contact (GitHub issues)</a><br>rentready is made by GenZAgents in London. Not legal advice.</footer>').format(b=BASE)


def nice(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.day} {x.strftime('%B %Y')}"


def short(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.day} {x.strftime('%b %Y')}"


def stat(value, label) -> str:
    return f'<div class="stat"><b>{html.escape(str(value))}</b><span>{html.escape(label)}</span></div>'


def build(data: dict) -> str:
    weeks = sorted(data["weeks"], key=lambda w: w["date"], reverse=True)
    w = weeks[0]
    e = html.escape
    cards = "".join([
        stat(f"£{w['revenue_gbp']:,}", "revenue to date"),
        stat(w["paying"], "paying landlords"),
        stat(w["reminder_signups"], "reminder sign-ups"),
        stat(w["pages_in_google"], "pages in Google's index"),
        stat(f"{w['panel_cited']} of {w['panel_questions']}", "AI answers that cite us"),
        stat(w["github_uniques_14d"], "people who opened the code on GitHub (14 days)"),
    ])
    done = "".join(f"<li>{e(x)}</li>" for x in w["done"])
    rows = "".join(
        f"<tr><td>{short(x['date'])}</td><td>£{x['revenue_gbp']:,}</td><td>{x['paying']}</td><td>{x['reminder_signups']}</td>"
        f"<td>{x['pages_in_google']}</td><td>{x['panel_cited']}/{x['panel_questions']}</td><td>{x['github_uniques_14d']}</td></tr>"
        for x in weeks)
    top = ", ".join(f"{e(h)} ({n})" for h, n in data["panel_top_sources"])
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>rentready in numbers: revenue, sign-ups and AI citations each week</title>
<meta name="description" content="rentready's real numbers, published every week, zeros included: revenue, paying landlords, reminder sign-ups, pages indexed and AI-answer citations.">
<link rel="canonical" href="{BASE}numbers.html">
<meta name="theme-color" content="#0e5a44">
<link rel="icon" href="{ICON}">
<link rel="stylesheet" href="assets/site.css">
</head><body>
<header class="site-head"><div class="container">
<a class="brand" href="{BASE}">{BRAND}rentready</a>
<nav class="site-nav"><a href="{BASE}guides/">Guides</a><a href="{BASE}guides/landlord-database-deadline-by-region.html">Deadlines</a><a href="{BASE}about.html">About</a></nav>
<a class="btn sm" href="{BASE}#tool">Check a property</a>
</div></header>
<main>
<p class="crumbs"><a href="{BASE}">rentready</a> / Numbers</p>
<h1>rentready in numbers</h1>
<p class="lead">We publish rentready's real numbers every week, including the zeros. Latest update: {nice(w['date'])}.</p>
<div class="summary wide">{cards}</div>
<h2>This week</h2>
<ul>{done}</ul>
<p><strong>Next:</strong> {e(w['next'])}</p>
<h2>Every week</h2>
<div class="weekly"><table>
<thead><tr><th>Week</th><th>Revenue</th><th>Paying</th><th>Sign-ups</th><th>Indexed</th><th>AI cites</th><th>GitHub</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>How we count</h2>
<ul>
<li><strong>Revenue and paying landlords:</strong> money actually received for the reminder service (£12 a year for up to 10 properties). No projections and no annualised figures.</li>
<li><strong>Reminder sign-ups:</strong> landlords who asked for the monthly certificate and deadline email.</li>
<li><strong>Pages in Google's index:</strong> rentready pages that a <code>site:</code> search on Google returns.</li>
<li><strong>AI answers that cite us:</strong> each week we ask the same {w['panel_questions']} landlord database questions and count the answers that link to a rentready page. This week Google showed an AI Overview for {w['panel_ai_overviews']} of them. The sources it cited most were {top}.</li>
<li><strong>GitHub visitors:</strong> unique people who opened the rentready or citable code on GitHub in the last 14 days, from GitHub's own traffic figures. The checker itself has no analytics and no cookies, so we do not count its visitors yet.</li>
</ul>
<p class="mut">Made by GenZAgents in London. Questions about these figures: <a href="https://github.com/genzagents/rentready/issues">open a GitHub issue</a>.</p>
{FOOT}
</main></body></html>
"""


if __name__ == "__main__":
    OUT.write_text(apply("docs/numbers.html", build(json.loads(DATA.read_text(encoding="utf-8")))), encoding="utf-8")
    print(OUT.relative_to(ROOT))

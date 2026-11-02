"""Build docs/guides/landlord-database-regulations-status.html: where the draft Private Rented Sector Database
Regulations 2026 stand in Parliament, from the Parliament procedure browser's record of the instrument.

    python3 tools/gen_status.py           rebuild from the saved record (tools/data/procedure.html)
    python3 tools/gen_status.py --fetch   download the record first (a launchd job on the Mac mini runs this twice a day: ops/runners/regs-status.sh in the co-founder folder)

The page only changes when Parliament's record changes: the "reviewed" date is the date of the latest business item,
never today's date, so the scheduled run commits nothing on quiet days."""
import html
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path

from gen_numbers import BASE, BRAND, FOOT, ICON
from schema import apply

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "guides" / "landlord-database-regulations-status.html"
RECORD = ROOT / "tools" / "data" / "procedure.html"
SOURCE = "https://api.parliament.uk/procedure-browser/work-packages/mNlSJVmc"
DRAFT = "https://www.legislation.gov.uk/ukdsi/2026/9780348286861"
ACT = "https://www.legislation.gov.uk/ukpga/2025/26"
GUIDANCE = "https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/"
FIRST = date(2026, 11, 1)  # page first published

# The draft affirmative procedure, in order: (key, what it means, text that marks it done in Parliament's record)
STEPS = [
    ("laid", "Laid before both Houses", "Laid before the House of Lords"),
    ("jcsi", "Checked by the Joint Committee on Statutory Instruments", "Considered by the Joint Committee on Statutory Instruments"),
    ("slsc", "Checked by the Lords Secondary Legislation Scrutiny Committee", "Considered by the Secondary Legislation Scrutiny Committee"),
    ("dlc", "Debated by a Commons committee", "Delegated Legislation Committee (DLC) debate"),
    ("gc", "Debated by the Lords in Grand Committee", "Grand Committee debate"),
    ("lords", "Approved by the House of Lords", "Motion to approve the instrument approved (House of Lords)"),
    ("commons", "Approved by the House of Commons", "Motion to approve the instrument approved (House of Commons)"),
    ("made", "Signed into law (made) by the minister", "Instrument made"),
]
TROUBLE = ("not approved", "rejected", "withdrawn", "revoked", "negatived")


def long_date(d: date) -> str:
    return f"{d.day} {d:%B %Y}"


def parse(t: str) -> list:
    """Parliament's record as [{date, steps: [text], link}] in date order."""
    items = []
    for m in re.finditer(r'<li id="date-(\d{4}-\d{2}-\d{2})">(.*?)</ol>\s*</li>', t, re.S):
        day = datetime.strptime(m.group(1), "%Y-%m-%d").date()
        for b in re.finditer(r'<li id="business-item-[^"]+">(.*?)</li>', m.group(2), re.S):
            steps = [html.unescape(s).strip() for s in re.findall(r'<p id="business-item-[^"]+-actualising-[^"]+">(.*?)</p>', b.group(1), re.S)]
            link = re.search(r'Read at <a href="([^"]+)"', b.group(1))
            items.append({"date": day, "steps": steps, "link": html.unescape(link.group(1)) if link else None})
    return items


def status(items: list, today: date) -> dict:
    done = {}
    for it in items:
        for s in it["steps"]:
            for key, _, mark in STEPS:
                if mark in s and key not in done:
                    done[key] = it["date"]
    trouble = [(it["date"], s) for it in items for s in it["steps"] if any(w in s.lower() for w in TROUBLE)
               and "motion to consider" not in s.lower()]
    lords_vote = None
    for it in items:
        if any("Motion to approve the instrument tabled by the Government (House of Lords)" in s for s in it["steps"]):
            m = re.search(r"businessPaperDate=(\d{4}-\d{2}-\d{2})", it["link"] or "")
            if m:
                d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
                lords_vote = (d, it["link"]) if d >= today and "lords" not in done else None
    return {"done": done, "trouble": trouble, "lords_vote": lords_vote,
            "latest": max([it["date"] for it in items] + [FIRST])}


def headline(st: dict) -> str:
    done = st["done"]
    if "made" in done:
        return f"Yes. The regulations were signed into law on {long_date(done['made'])}, after both Houses of Parliament approved them."
    if "lords" in done and "commons" in done:
        return ("Almost. Both Houses of Parliament have approved the regulations "
                f"(the last vote on {long_date(max(done['lords'], done['commons']))}); the minister still has to sign them into law.")
    if "lords" in done or "commons" in done:
        house, other = ("House of Lords", "House of Commons") if "lords" in done else ("House of Commons", "House of Lords")
        return (f"Not yet final. The {house} approved the regulations on {long_date(done.get('lords') or done.get('commons'))}; "
                f"the {other} still has to vote, and then the minister signs them into law.")
    s = "Not yet final. Both Houses of Parliament have debated the landlord database regulations in committee"
    if "dlc" in done:
        s += f" ({long_date(max(done['dlc'], done.get('gc', done['dlc'])))})"
    s += ", but neither House has voted to approve them yet."
    if st["lords_vote"]:
        s += f" The House of Lords business paper lists the approval vote for {long_date(st['lords_vote'][0])}."
    return s


OPENS = date(2026, 12, 15)  # registration opening day in the official guidance


def live(st: dict, today: date) -> tuple:
    """Answer to 'is the PRS Database live?': dates only, so the page changes on a vote or on opening day, not daily."""
    if today >= OPENS:
        return ("It should be open.", "The official guidance gave 15 December 2026 as the day registration opens, starting with the West Midlands; "
                "check gov.uk for the registration service itself.")
    if "made" in st["done"]:
        return ("Not yet.", "The regulations are law, and the official guidance gives 15 December 2026 as the day registration opens. "
                "No landlord has to register before then.")
    return ("Not yet.", "Registration is due to open on 15 December 2026, and the regulations behind it still need Parliament's approval. "
            "No landlord can register or has to register before then.")


def build(items: list, today: date) -> str:
    e = html.escape
    st = status(items, today)
    done = st["done"]
    nxt = next((k for k, _, _ in STEPS if k not in done), None)
    track = []
    for key, label, _ in STEPS:
        if key in done:
            track.append(f'<li class="t-done"><b>{e(label)}</b><span>{long_date(done[key])}</span></li>')
        else:
            note = ""
            if key == "lords" and st["lords_vote"]:
                note = f'listed for {long_date(st["lords_vote"][0])}'
            track.append(f'<li class="{"t-next" if key == nxt else "t-todo"}"><b>{e(label)}</b><span>{note or "not yet"}</span></li>')
    def row(it):
        link = f'<a href="{e(it["link"])}">record</a>' if it["link"] else ""
        return f"<tr><td>{long_date(it['date'])}</td><td>{'<br>'.join(e(s) for s in it['steps'])}</td><td>{link}</td></tr>"
    rows = "".join(row(it) for it in reversed(items))
    trouble = ""
    if st["trouble"]:
        trouble = ('<p class="who-out who-no"><b>Something unusual is in the record:</b> '
                   + "; ".join(f"{e(s)} ({long_date(d)})" for d, s in st["trouble"]) + ". Check gov.uk before acting.</p>")
    reviewed = long_date(st["latest"])
    REG = "Made: in force as the regulations say" if "made" in done else "Waits on the vote"
    head = headline(st)
    is_live = live(st, today)
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Is the PRS Database live yet? Where the landlord database stands</title>
<meta name="description" content="Is the PRS Database (landlord database) live yet? When registration opens, and where its regulations stand in Parliament, from Parliament&apos;s own record.">
<link rel="canonical" href="{BASE}guides/landlord-database-regulations-status.html">
<meta name="theme-color" content="#0e5a44">
<link rel="icon" href="{ICON}">
<link rel="stylesheet" href="../assets/site.css">
</head><body>
<header class="site-head"><div class="container">
<a class="brand" href="{BASE}">{BRAND}rentready</a>
<nav class="site-nav"><a href="{BASE}guides/">Guides</a><a href="{BASE}guides/landlord-database-deadline-by-region.html">Deadlines</a><a href="{BASE}about.html">About</a></nav>
<a class="btn sm" href="{BASE}#tool">Check a property</a>
</div></header>
<main>
<p class="crumbs"><a href="{BASE}">rentready</a> / <a href="{BASE}guides/">Landlord database guides</a></p>
<h1>Is the PRS Database live yet? Where the landlord database stands</h1>
<p class="mut byline">Written by <a href="{BASE}about.html">GenZAgents</a>, reviewed {reviewed}. Rebuilt twice a day from <a href="{SOURCE}">Parliament's record</a>. <a href="#sources">Sources</a> below.</p>
<div class="who-out"><b>Is it live? {e(is_live[0])}</b><p>{e(is_live[1])}</p></div>
<p><strong>{e(head)}</strong> The database itself is set up by the Renters' Rights Act 2025, which is already law. The regulations set the detail: the £65 fee, the regional deadlines and what you upload. The <a href="{GUIDANCE}">official guidance</a> still gives 15 December 2026 as the day registration opens.</p>
{trouble}
<h2>The steps</h2>
<p>The regulations follow the draft affirmative procedure: they cannot become law until both the House of Commons and the House of Lords vote to approve them. These are the steps, from Parliament's record.</p>
<ol class="track">{"".join(track)}</ol>
<h2>What is in the Act, and what waits on the vote</h2>
<div class="wrap"><table>
<thead><tr><th>Rule</th><th>Where it is</th><th>Status</th></tr></thead>
<tbody>
<tr><td>A private rented sector database, with landlord and dwelling entries</td><td><a href="{ACT}/part/2/chapter/3">Act, Part 2, Chapter 3</a></td><td>In the Act</td></tr>
<tr><td>Penalties up to £7,000, and up to £40,000 for the offences</td><td><a href="{ACT}/section/91">Act, s.91</a> and <a href="{ACT}/section/92">s.92</a></td><td>In the Act</td></tr>
<tr><td>No possession order without an active entry (except Grounds 7A and 14)</td><td><a href="{ACT}/section/90">Act, s.90</a></td><td>In the Act</td></tr>
<tr><td>Adverts must carry the landlord and dwelling identifiers</td><td><a href="{ACT}/section/82">Act, s.82</a></td><td>In the Act; MHCLG says not before 15 November 2027</td></tr>
<tr><td>The £65 fee per property a year</td><td><a href="{DRAFT}">Draft regulations</a></td><td>{REG}</td></tr>
<tr><td>Regional start dates and deadlines, 14 March to 14 November 2027</td><td><a href="{DRAFT}/schedule/3/part/2">Draft regulations, Schedule 3</a></td><td>{REG}</td></tr>
<tr><td>Certificates uploaded within 28 days of the entry</td><td><a href="{DRAFT}/regulation/6">Draft regulations, reg. 6(2)</a></td><td>{REG}</td></tr>
<tr><td>One renewal date a year for all your properties</td><td><a href="{DRAFT}/regulation/10">Draft regulations, reg. 10</a></td><td>{REG}</td></tr>
</tbody></table></div>
<p class="mut">"In the Act" means Parliament has passed it; each section applies from a date the government sets. The MHCLG date for adverts is from its <a href="https://www.propertytribes.com/mhclg-answer-questions-about-prs-database-t-127669645.html">28 October answers to The Lettings Industry Council</a>.</p>
<h2>What to do now</h2>
<p>A draft like this cannot be amended in Parliament, only approved or not, and its dates match the official guidance. The work a landlord can do today does not depend on the vote: find each property's gas safety record, EICR and EPC, and renew any that lapse before your region's deadline. Registration needs them all.</p>
<p><a class="btn" href="{BASE}#tool">Check your properties free</a> <span class="mut">Shows each property's deadline and which certificate lapses first. Runs in your browser; only the postcode leaves it.</span></p>
<h2>Parliament's record</h2>
<p class="mut">Every business item so far, newest first, as the Parliament procedure browser lists it.</p>
<div class="wrap"><table class="record">
<thead><tr><th>Date</th><th>What happened</th><th>Link</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<h2>Questions</h2>
<h3>Is the PRS Database live yet?</h3>
<p>{e(" ".join(is_live))} Until it opens, you can check each property's deadline and certificates with the <a href="{BASE}#tool">free checker</a>.</p>
<h3>Is the landlord database definitely happening?</h3>
<p>The database is in the Renters' Rights Act 2025, which is law. The regulations that set the fee, the dates and the uploads are the part still going through Parliament. Status today: {e(head[0].lower() + head[1:])}</p>
<h3>What happens if Parliament does not approve the regulations?</h3>
<p>Under the draft affirmative procedure the regulations cannot be made without approval from both Houses. The government would have to lay a new draft, and the fee and dates could change. This page is rebuilt from Parliament's record twice a day, so it will show any vote within hours.</p>
<h3>Does the vote change my deadline?</h3>
<p>Not so far. The deadlines in the draft regulations match the <a href="{GUIDANCE}">official guidance</a>: the West Midlands first, by 14 March 2027, and the South West last, by 14 November 2027. See <a href="landlord-database-deadline-by-region.html">deadlines by region</a>.</p>
<h2>Related guides</h2>
<ul><li><a href="landlord-database-registration.html">Landlord database registration explained</a></li><li><a href="landlord-database-deadline-by-region.html">Deadlines by region</a></li><li><a href="landlord-database-fee.html">The £65 fee</a></li><li><a href="landlord-database-penalties.html">Penalties</a></li></ul>
<h2 id="sources">Sources</h2>
<ul class="mut"><li><a href="{SOURCE}">UK Parliament procedure browser: Private Rented Sector Database Regulations 2026</a></li><li><a href="{DRAFT}">Draft Private Rented Sector Database Regulations 2026 (legislation.gov.uk)</a></li><li><a href="{ACT}/contents">Renters' Rights Act 2025 (legislation.gov.uk)</a></li><li><a href="{GUIDANCE}">Get ready to register: Register your rental property (official guidance)</a></li><li><a href="https://publications.parliament.uk/pa/ld5902/ldselect/ldsecleg/68/6803.htm">Secondary Legislation Scrutiny Committee, 13th report</a></li></ul>
<p class="mut">Not legal advice. Check gov.uk before relying on this.</p>
{FOOT}
</main></body></html>
"""


def fetch() -> None:
    req = urllib.request.Request(SOURCE, headers={"User-Agent": "rentready-status (+https://github.com/genzagents/rentready)"})
    t = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    if not parse(t):
        sys.exit("procedure browser page has no business items; layout changed?")
    RECORD.write_text(t, encoding="utf-8")


if __name__ == "__main__":
    if "--fetch" in sys.argv:
        fetch()
    page = apply("docs/guides/landlord-database-regulations-status.html", build(parse(RECORD.read_text(encoding="utf-8")), date.today()))
    OUT.write_text(page, encoding="utf-8")
    print(OUT.relative_to(ROOT))

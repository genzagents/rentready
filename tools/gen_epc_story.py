"""Generate the EPC expiry data story: how many rental EPCs reach ten years before each region's landlord database
deadline, and the 2028-2030 expiry wave. Input: tools/data/epc-rental-lodgements-by-region.csv, the "Rental" column of
the government's live table D4(b) by region and quarter. Output: docs/guides/epc-expiry-by-region.html and
docs/data/epc-rental-expiry-by-region.csv. Run `python3 tools/gen_epc_story.py`; tests/test_epc_story.py fails if the
committed files are stale."""
import csv
import io
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from rentready import ROLLOUT  # noqa: E402
import schema  # noqa: E402  (tools/schema.py, same folder)

SRC = ROOT / "tools/data/epc-rental-lodgements-by-region.csv"
PAGE = ROOT / "docs/guides/epc-expiry-by-region.html"
DATA = ROOT / "docs/data/epc-rental-expiry-by-region.csv"
BASE = "https://genzagents.github.io/rentready/"
FROM = date(2026, 11, 1)  # count certificates reaching ten years from this date
REVIEWED = "29 October 2026"
TABLE_URL = "https://www.gov.uk/government/statistical-data-sets/live-tables-on-energy-performance-of-buildings-certificates"
REGION_PAGE = {"North East": "landlord-database-deadline-by-region.html#north-east",
               "South West": "landlord-database-deadline-by-region.html#south-west"}


def slug(region):
    return REGION_PAGE.get(region, region.lower().replace(" ", "-") + ".html")


def load():
    rows = {}
    with SRC.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.setdefault(r["region"], []).append((r["quarter"], int(r["rental_epcs_lodged"])))
    return rows


def quarter(q):
    y, n = map(int, q.split("/"))
    return date(y, 3 * n - 2, 1), date(y + (n == 4), (3 * n) % 12 + 1, 1)


def lodged(rows, start, end):
    """Certificates lodged in [start, end), spreading each quarter's count evenly over its days."""
    tot = 0.0
    for q, v in rows:
        a, b = quarter(q)
        lo, hi = max(a, start), min(b, end)
        if hi > lo:
            tot += v * (hi - lo).days / (b - a).days
    return tot


def back10(d):
    return date(d.year - 10, d.month, d.day)


def compute():
    data = load()
    regions = []
    for name, w in ROLLOUT.items():
        rows = data[name]
        opens, deadline = date.fromisoformat(w["opens"]), date.fromisoformat(w["deadline"])
        regions.append({"region": name, "opens": opens, "deadline": deadline,
                        "before": lodged(rows, back10(FROM), back10(deadline)),
                        "window": lodged(rows, back10(opens), back10(deadline)),
                        "wave": lodged(rows, date(2018, 1, 1), date(2021, 1, 1))})
    years = {}
    for rows in data.values():
        for q, v in rows:
            y = int(q.split("/")[0]) + 10
            years[y] = years.get(y, 0) + v
    return regions, years


def r100(x):
    return int(round(x / 100.0)) * 100


def n(x):
    return f"{r100(x):,}"


def thousands(x):
    return f"{round(x / 1000):,},000"


def long_date(d):
    return f"{d.day} {d.strftime('%B %Y')}"


def csv_text(regions):
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["region", "registration_opens", "registration_deadline",
                "rental_epcs_reaching_10_years_1_nov_2026_to_deadline", "of_which_inside_the_region_window",
                "rental_epcs_reaching_10_years_2028_to_2030"])
    for r in regions:
        w.writerow([r["region"], r["opens"], r["deadline"], r100(r["before"]), r100(r["window"]), r100(r["wave"])])
    return out.getvalue()


def chart(years):
    shown = {y: v for y, v in years.items() if 2023 <= y <= 2035}
    top = max(shown.values())
    out = ['<div class="ybars" role="img" aria-label="Rental EPCs in England reaching ten years, by year: '
           + "; ".join(f"{y} {thousands(v)}" for y, v in shown.items()) + '">']
    for y, v in shown.items():
        cls = ' class="hi"' if 2028 <= y <= 2030 else ""
        out.append(f'<div{cls}><span class="y">{y}</span><span class="track"><span class="fill" style="width:{100 * v / top:.1f}%">'
                   f'</span></span><span class="v">{round(v / 1000):,}k</span></div>')
    out.append("</div>")
    return "\n".join(out)


def page(regions, years):
    before = sum(r["before"] for r in regions)
    window = sum(r["window"] for r in regions)
    wave = sum(r["wave"] for r in regions)
    y2026, y2029 = years[2026], years[2029]
    wm = regions[0]
    rows = "\n".join(
        f'<tr><td><a href="{slug(r["region"])}">{r["region"]}</a>{" *" if r["region"] == "North East" else ""}</td>'
        f'<td>{r["deadline"].strftime("%-d %b %Y")}</td><td>{n(r["before"])}</td><td>{n(r["window"])}</td><td>{n(r["wave"])}</td></tr>'
        for r in regions)
    title = "EPCs expiring before the landlord database deadline, by region"
    desc = (f"About {thousands(before)} rental EPCs in England reach ten years before their region's landlord database "
            "deadline. The figures by region, from government data.")
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{BASE}guides/epc-expiry-by-region.html">
<meta name="theme-color" content="#0e5a44">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230e5a44'/%3E%3Cpath d='M8 15.5 16 9l8 6.5V24H8z' fill='none' stroke='%23fff' stroke-width='2.2' stroke-linejoin='round'/%3E%3Cpath d='m12.5 18.5 2.6 2.6 4.6-5' fill='none' stroke='%23fff' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="stylesheet" href="../assets/site.css">
</head><body>
<header class="site-head"><div class="container">
<a class="brand" href="{BASE}"><svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#0e5a44"/><path d="M8 15.5 16 9l8 6.5V24H8z" fill="none" stroke="#fff" stroke-width="2.2" stroke-linejoin="round"/><path d="m12.5 18.5 2.6 2.6 4.6-5" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>rentready</a>
<nav class="site-nav"><a href="{BASE}guides/">Guides</a><a href="{BASE}guides/landlord-database-deadline-by-region.html">Deadlines</a><a href="{BASE}about.html">About</a></nav>
<a class="btn sm" href="{BASE}#tool">Check a property</a>
</div></header>
<main>
<p class="crumbs"><a href="{BASE}">rentready</a> / <a href="{BASE}guides/">Landlord database guides</a></p>
<h1>How many rental EPCs expire before your landlord database deadline</h1>
<p class="mut byline">Written by <a href="{BASE}about.html">GenZAgents</a>, reviewed {REVIEWED}. Our own analysis of government data. <a href="#method">Method</a> and <a href="#sources">sources</a> below.</p>
<p><strong>About {thousands(before)} energy performance certificates (EPCs) lodged in England for a rental reach their ten-year expiry between 1 November 2026 and their region's landlord database deadline.</strong> About {thousands(window)} of them lapse inside the region's own three-month registration window. A lapsed EPC does not stop you registering: you upload it and give the start date of the current tenancy. But any new tenancy needs a valid EPC, so a landlord re-letting in the next year should check the date first.</p>
<div class="summary wide">
<div class="stat"><b>{thousands(before)}</b><span>rental EPCs reach ten years before their region's deadline</span></div>
<div class="stat"><b>{thousands(window)}</b><span>of them lapse inside the region's own registration window</span></div>
<div class="stat"><b>{round(wave / 1e6, 2)} million</b><span>reach ten years in 2028 to 2030, the run-up to the planned C minimum</span></div>
</div>
<h2>By region</h2>
<p>Each region has three months to register, from the dates in the <a href="landlord-database-deadline-by-region.html">deadline guide</a>. The West Midlands goes first: about {n(wm["before"])} rental EPCs there reach ten years before its {long_date(wm["deadline"])} deadline. Later regions have longer to wait, so more of their certificates lapse first. London has the most.</p>
<div class="wrap"><table>
<tr><th>Region</th><th>Deadline</th><th>Reach ten years, 1 Nov 2026 to deadline</th><th>Of which in the window</th><th>Reach ten years, 2028 to 2030</th></tr>
{rows}
</table></div>
<p class="mut">Rounded to the nearest 100. * The North East figure includes a one-off quarter: 27,114 rental EPCs were lodged there from April to June 2017, about four times its usual quarter, which looks like a bulk lodgement by a large landlord. <a href="{BASE}data/epc-rental-expiry-by-region.csv">Download the table (CSV)</a>.</p>
<h2>The bigger wave: 2028 to 2030</h2>
<p>Rental EPC lodgements rose sharply from 2018, the year the E minimum started to apply to new lettings (1 April 2018). Ten years on, those certificates come due together: about {thousands(years[2028])} in 2028, {thousands(y2029)} in 2029 and {thousands(years[2030])} in 2030, against {thousands(y2026)} in 2026. That lands just before 1 October 2030, when the government plans to require a C rating for all private tenancies. The C minimum still needs legislation and will be measured on new EPC metrics (see the <a href="epc-rating-landlord-database.html">EPC guide</a>).</p>
<p class="mut">Rental EPCs in England reaching ten years, by year (thousands)</p>
{chart(years)}
<div class="cta"><p><strong>Is your EPC one of them?</strong> rentready checks each property's EPC, gas safety record and EICR against its region's deadline, free.</p><p><a class="btn" href="{BASE}#tool">Check your properties free</a> <span class="mut">Runs in your browser. Only the postcode leaves it, to find the region.</span></p></div>
<h2 id="method">Method and limits</h2>
<ul>
<li><strong>Source.</strong> Table D4(b) of the government's <a href="{TABLE_URL}">live tables on Energy Performance of Buildings Certificates</a> (published 30 July 2026, data to 30 June 2026): domestic EPCs by region, quarter and type of transaction. We use the "Rental" transaction type, England's nine regions.</li>
<li><strong>Expiry.</strong> An EPC is valid for ten years, so a certificate lodged in a quarter reaches ten years in the same quarter a decade later. Where a date range cuts a quarter, we count that quarter's certificates in proportion to its days.</li>
<li><strong>These are certificates, not homes.</strong> A home may have had a newer EPC since, so the number of let homes with a lapsed EPC is lower. Certificates lodged for a sale and later used for a let are not counted, which pulls the other way.</li>
<li><strong>Private and social lettings.</strong> The table does not split rental EPCs by landlord type, so housing association lettings are included.</li>
<li><strong>Revisions.</strong> The government aligns these tables to its address-level data, and opt-outs are removed, so figures can fall slightly between publications.</li>
<li><strong>Reproduce it.</strong> The input and the script are in the <a href="https://github.com/genzagents/rentready/tree/main/tools">rentready repository</a> (tools/gen_epc_story.py).</li>
</ul>
<p>Journalists and landlord bodies may use these figures with credit to rentready by GenZAgents. Questions: <a href="https://github.com/genzagents/rentready/issues">GitHub issues</a>.</p>
<h2>Related guides</h2>
<ul><li><a href="epc-rating-landlord-database.html">EPC ratings and the landlord database</a></li><li><a href="landlord-database-deadline-by-region.html">Deadlines by region</a></li><li><a href="what-you-need-to-register.html">What you need to register</a></li></ul>
<h2 id="sources">Sources</h2>
<ul class="mut"><li><a href="{TABLE_URL}">Live tables on Energy Performance of Buildings Certificates, table D4(b) (gov.uk)</a></li><li><a href="https://www.gov.uk/guidance/domestic-private-rented-property-minimum-energy-efficiency-standard-landlord-guidance">Domestic private rented property: minimum energy efficiency standard, landlord guidance (gov.uk)</a></li><li><a href="https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/">Get ready to register: Register your rental property (official guidance, housinghub.campaign.gov.uk)</a></li><li><a href="https://www.legislation.gov.uk/ukdsi/2026/9780348286861">Draft Private Rented Sector Database Regulations 2026 (legislation.gov.uk; not yet made)</a></li></ul>
<p class="mut">Not legal advice. Check gov.uk before relying on this. Last checked 29 Oct 2026.</p>
<footer class="foot mut"><a href="{BASE}about.html">About</a> · <a href="{BASE}guides/">Guides</a> · <a href="{BASE}developers.html">Developers</a> · <a href="{BASE}privacy.html">Privacy</a> · <a href="{BASE}terms.html">Terms</a> · <a href="https://github.com/genzagents/rentready/issues">Contact (GitHub issues)</a><br>rentready is made by GenZAgents in London. Not legal advice.</footer>
</main></body></html>
"""


def build():
    regions, years = compute()
    rel = PAGE.relative_to(ROOT).as_posix()
    return schema.apply(rel, page(regions, years)), csv_text(regions)


if __name__ == "__main__":
    html, data = build()
    PAGE.write_text(html, encoding="utf-8")
    DATA.parent.mkdir(exist_ok=True)
    DATA.write_text(data, encoding="utf-8")
    print(PAGE.relative_to(ROOT), DATA.relative_to(ROOT))

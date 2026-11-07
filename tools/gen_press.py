"""Build docs/press.html, the press page for the EPC expiry data story, and docs/data/epc-expiry-by-year.svg, a
standalone chart journalists can download. Figures come from gen_epc_story.compute(), so they always match the story."""
import html
import json
from datetime import date
from pathlib import Path

import gen_epc_story as story
from gen_numbers import BASE, BRAND, FOOT, ICON
from schema import apply

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "press.html"
SVG_OUT = ROOT / "docs" / "data" / "epc-expiry-by-year.svg"
YEARS = range(2026, 2036)  # full calendar years only: the table ends at Q3 2026, so 2036 is part-year
STORY = BASE + "guides/epc-expiry-by-region.html"
REVIEWED = "31 October 2026"
NOTICES = json.loads((ROOT / "tools" / "data" / "council-notices.json").read_text(encoding="utf-8"))


def councils() -> str:
    """The second story: how many councils in the first regions to register have told landlords about the database.
    Same data as the council-notices section of each region guide, so the two always agree."""
    regions = {r: v for r, v in NOTICES.items() if not r.startswith("_")}
    if not regions:
        return ""
    e = html.escape
    rows, told_all, dated_all, n_all = "", 0, 0, 0
    for r, v in regions.items():
        cs = [c for c in v["councils"].values() if c["status"] != "unreachable"]
        told = sum(c["status"] in ("deadline", "mentions") for c in cs)
        dated = sum(c["status"] == "deadline" for c in cs)
        told_all, dated_all, n_all = told_all + told, dated_all + dated, n_all + len(cs)
        href = f"{BASE}guides/{r.lower().replace(' ', '-')}.html#council-notices"
        rows += f'<tr><td><a href="{href}">{e(r)}</a></td><td>{len(cs)}</td><td>{told}</td><td>{dated}</td></tr>'
    checked = max(date.fromisoformat(v["checked"]) for v in regions.values())
    return f"""<h2 id="councils">Second story: most councils have not told landlords when to register</h2>
<p>On {checked.day} {checked:%B %Y} we read the landlord pages of every council in the first {['one', 'two', 'three', 'four', 'five'][len(regions) - 1]} regions to register. <strong>{told_all} of {n_all}</strong> mention the landlord database at all, and only <strong>{dated_all}</strong> give the right dates. Some give wrong ones: Castle Point tells landlords the database is unlikely before 2028. In the East Midlands only the three Lincolnshire councils that share one partnership page (Boston, East Lindsey, South Holland) give the dates; Nottingham, Mansfield and Chesterfield say nothing about the database. Every quote links to the council's own page.</p>
<div class="wrap"><table>
<thead><tr><th>Region</th><th>Councils read</th><th>Mention the database</th><th>Give the right dates</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="mut">The full council-by-council table with quotes is on each region's guide (linked). Data: <a href="https://github.com/genzagents/rentready/blob/main/tools/data/council-notices.json">council-notices.json</a>.</p>
"""


def chart(years: dict, inline: bool) -> str:
    """Bar chart of rental EPCs reaching ten years per year. Inline it follows the page theme through CSS variables;
    the standalone file uses fixed light colours so it pastes into any article."""
    w, h, left, top, bottom = 640, 300, 56, 34, 40
    peak = max(years[y] for y in YEARS)
    scale = 700_000
    step = (w - left - 12) / len(YEARS)
    bar, hi, ink, mut, line = (("var(--brand)", "var(--warn)", "var(--ink)", "var(--muted)", "var(--line)") if inline
                               else ("#0e5a44", "#8a4b00", "#1c1a16", "#6b665c", "#e4dfd3"))
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-labelledby="chart-t" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif">',
           '<title id="chart-t">Rental EPCs in England reaching ten years, by year, 2026 to 2035</title>']
    if not inline:
        out.append(f'<rect width="{w}" height="{h}" fill="#ffffff"/>')
    for tick in range(0, scale + 1, 200_000):
        y = top + (h - top - bottom) * (1 - tick / scale)
        out.append(f'<line x1="{left}" x2="{w - 8}" y1="{y:.1f}" y2="{y:.1f}" stroke="{line}"/>')
        out.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="{mut}">{tick // 1000:,}k</text>')
    for i, yr in enumerate(YEARS):
        v = years[yr]
        bh = (h - top - bottom) * v / scale
        x = left + i * step + step * 0.18
        colour = hi if yr in (2028, 2029, 2030) else bar
        out.append(f'<rect x="{x:.1f}" y="{h - bottom - bh:.1f}" width="{step * 0.64:.1f}" height="{bh:.1f}" rx="3" fill="{colour}">'
                   f'<title>{yr}: about {story.thousands(v)}</title></rect>')
        out.append(f'<text x="{x + step * 0.32:.1f}" y="{h - bottom + 18}" text-anchor="middle" font-size="12" fill="{ink}">{yr}</text>')
        if yr in (2026, 2029) or v == peak:
            out.append(f'<text x="{x + step * 0.32:.1f}" y="{h - bottom - bh - 6:.1f}" text-anchor="middle" font-size="12" '
                       f'font-weight="700" fill="{ink}">{round(v / 1000):,}k</text>')
    out.append(f'<text x="{left}" y="18" font-size="13" font-weight="700" fill="{ink}">Rental EPCs reaching ten years, England</text>')
    if not inline:
        out.append(f'<text x="{w - 8}" y="{h - 6}" text-anchor="end" font-size="11" fill="{mut}">'
                   'Source: gov.uk EPC live table D4(b), to 30 Sep 2026. Analysis: rentready (GenZAgents)</text>')
    out.append("</svg>")
    return "".join(out)


def build() -> str:
    regions, years = story.compute()
    e = html.escape
    before = sum(r["before"] for r in regions)
    window = sum(r["window"] for r in regions)
    wave = years[2028] + years[2029] + years[2030]
    first = min(regions, key=lambda r: r["deadline"])
    most = max(regions, key=lambda r: r["before"])
    rows = "".join(
        f"<tr><td>{e(r['region'])}{' *' if r['region'] == 'North East' else ''}</td><td>{story.long_date(r['deadline'])}</td><td>{story.n(story.r100(r['before']))}</td>"
        f"<td>{story.n(story.r100(r['window']))}</td><td>{story.n(story.r100(r['wave']))}</td></tr>"
        for r in sorted(regions, key=lambda r: r["deadline"]))
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Press: rental EPC expiry and the landlord database, free data</title>
<meta name="description" content="Free to use with credit: how many rental EPCs in England expire before each region's landlord database deadline, with chart, CSVs and method.">
<link rel="canonical" href="{BASE}press.html">
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
<p class="crumbs"><a href="{BASE}">rentready</a> / Press</p>
<h1>Press: rental EPCs and the landlord database</h1>
<p class="lead">About {story.thousands(before)} rental EPCs in England reach their ten-year expiry between 1 November 2026 and their region's deadline to register on the new landlord database (the PRS Database). Everything on this page is free to use with credit to <strong>rentready (GenZAgents)</strong>.</p>
<p class="mut">Figures from the government's EPC lodgement table, data to 30 September 2026. Reviewed {REVIEWED}.</p>
<div class="summary wide">
<div class="stat"><b>{story.thousands(before)}</b><span>rental EPCs reach ten years before their region's deadline</span></div>
<div class="stat"><b>{story.thousands(window)}</b><span>of them inside the region's own three-month window</span></div>
<div class="stat"><b>{story.n(first['before'])}</b><span>in the {e(first['region'])}, first to register (by {story.long_date(first['deadline'])})</span></div>
<div class="stat"><b>{story.n(most['before'])}</b><span>in {e(most['region'])}, the most of any region</span></div>
<div class="stat"><b>{story.thousands(wave)}</b><span>reach ten years in 2028 to 2030, before the planned C minimum</span></div>
<div class="stat"><b>{story.thousands(years[2029])}</b><span>in 2029 alone, against {story.thousands(years[2026])} in 2026</span></div>
</div>
<h2>The chart</h2>
<figure class="chart">{chart(years, inline=True)}
<figcaption class="mut">Rental EPCs reaching ten years each year (certificates, not homes; includes social lets). Highlighted: 2028 to 2030, the years before the planned C minimum on 1 October 2030. <a href="{BASE}data/epc-expiry-by-year.svg" download>Download the chart (SVG)</a>.</figcaption></figure>
<h2>By region</h2>
<div class="wrap"><table>
<thead><tr><th>Region</th><th>Deadline to register</th><th>Reach ten years, 1 Nov 2026 to deadline</th><th>Inside the region's window</th><th>2028 to 2030</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="mut">Rounded to the nearest hundred. * The North East figure includes a one-off quarter (27,114 rental EPCs lodged from April to June 2017, about four times its usual quarter), likely a bulk lodgement by a large landlord. Region deadlines are from the official guidance and the draft regulations, which Parliament has not yet approved.</p>
{councils()}<h2>Data you can use</h2>
<ul>
<li><a href="{BASE}data/epc-rental-expiry-by-region.csv">Region figures (CSV)</a></li>
<li><a href="{BASE}data/epc-rental-expiry-by-council.csv">Every English council, 296 rows (CSV)</a>: a local figure for any area, for example Birmingham about 2,040 before 14 March 2027.</li>
<li><a href="{BASE}data/epc-expiry-by-year.svg" download>The chart (SVG, with source line)</a></li>
<li><a href="{STORY}">The full data story</a>, with method and the searchable council table.</li>
</ul>
<h2>What it means for a landlord</h2>
<p>A lapsed EPC does not stop a landlord registering an existing tenancy, but every new let needs a valid one, and the database asks for the certificate. Landlords who will re-let next year should check their dates now. The free <a href="{BASE}">rentready check</a> shows, per property, the region's deadline and which certificate lapses first.</p>
<h2>Method in brief</h2>
<p>An EPC is valid for ten years. We take the government's quarterly count of EPCs lodged for private and social rented homes (<a href="{story.TABLE_URL}">live table D4(b)</a>) and move each quarter forward ten years. A quarter that straddles a cut-off date is split by days. The counts are certificates, not homes: a home re-assessed within ten years is counted twice, and some landlords renew early. Full method and caveats are in <a href="{STORY}#method">the data story</a>.</p>
<h2>Credit and contact</h2>
<p>Please credit <strong>rentready (GenZAgents)</strong> and link to <a href="{STORY}">the data story</a>. rentready is a free landlord database checker made by GenZAgents in London; the founder is Manraj Singh Dhillon. For other cuts of the figures, a correction or an interview, <a href="https://github.com/genzagents/rentready/issues/new?title=Press%20request">open a request on GitHub</a> (public, so leave out phone numbers) and we reply the same day.</p>
<p class="mut">Not legal advice. Last checked {REVIEWED}.</p>
{FOOT}
</main></body></html>
"""


if __name__ == "__main__":
    _, years = story.compute()
    SVG_OUT.write_text(chart(years, inline=False) + "\n", encoding="utf-8")
    OUT.write_text(apply("docs/press.html", build()), encoding="utf-8")
    print(OUT.relative_to(ROOT), SVG_OUT.relative_to(ROOT))

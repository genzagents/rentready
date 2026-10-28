#!/usr/bin/env python3
"""Generate one search guide per region in docs/guides/ and add them to docs/sitemap.xml, from rentready's own data.

The topic guides (fee, certificates, penalties...) are hand-written. The dates, fee, upload list and penalties here
come from rentready/__init__.py, so a region page can never say something the checker disagrees with.
tests/test_guides.py fails if the committed pages are stale. Run: python3 tools/gen_guides.py
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import rentready as rr  # noqa: E402

BASE = "https://genzagents.github.io/rentready/"
UPDATED = "2026-10-28"  # bump when the wording or the data changes
FIRST = "2026-12-15"  # the service opens to every landlord in England

PLACES = {
    "West Midlands": "Birmingham, Coventry, Wolverhampton, Stoke-on-Trent, Walsall, Dudley, Worcester, Hereford, Telford and Shrewsbury",
    "East of England": "Norwich, Cambridge, Peterborough, Ipswich, Luton, Chelmsford, Colchester, Southend-on-Sea and Watford",
    "East Midlands": "Nottingham, Leicester, Derby, Northampton, Lincoln, Chesterfield and Loughborough",
    "South East": "Brighton and Hove, Southampton, Portsmouth, Reading, Oxford, Milton Keynes, Canterbury, Guildford, Slough and Maidstone",
    "Yorkshire and The Humber": "Leeds, Sheffield, Bradford, Hull, York, Huddersfield, Doncaster and Wakefield",
    "North West": "Manchester, Liverpool, Salford, Preston, Bolton, Stockport, Warrington, Blackpool, Lancaster and Chester",
    "North East": "Newcastle upon Tyne, Sunderland, Middlesbrough, Durham, Gateshead and Darlington",
    "London": "all 32 London boroughs and the City of London",
    "South West": "Bristol, Plymouth, Exeter, Bath, Bournemouth, Swindon, Gloucester, Cheltenham and Truro",
}

CSS = """:root{--bg:#fff;--fg:#111;--mut:#555;--acc:#087a3a;--link:#0645ad;--box:#f4f4f4;--bd:#ddd}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#111;--fg:#eee;--mut:#aaa;--box:#1c1c1c;--bd:#333;--link:#8ab4f8}} a{color:var(--link)}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:32px 16px}
h1{font-size:2rem;margin:.2em 0}h2{margin-top:2em}
table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid var(--bd);padding:6px 8px;text-align:left}
.wrap{overflow-x:auto}.mut{color:var(--mut)}.now{font-weight:700}
.cta{background:var(--box);border:1px solid var(--bd);border-radius:8px;padding:16px;margin:1.5em 0}
.btn{display:inline-block;background:var(--acc);color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:600}"""

SOURCES = [
    ("https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/", "Get ready to register: Register your rental property (official guidance)"),
    ("https://www.legislation.gov.uk/ukdsi/2026/9780348286861", "Draft Private Rented Sector Database Regulations 2026 (legislation.gov.uk; not yet made)"),
    ("https://www.nrla.org.uk/resources/renters-rights/landlord-database-register-your-rental-property-service", "NRLA: Register your rental property service"),
]


def long(s: str) -> str:
    x = date.fromisoformat(s)
    return f"{x.day} {x.strftime('%B %Y')}"


def slug(region: str) -> str:
    return region.lower().replace(" ", "-")


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def ul(items: list) -> str:
    return "<ul>\n" + "".join(f"<li>{esc(i)}</li>\n" for i in items) + "</ul>\n"


def timetable(highlight: str) -> str:
    now = ' class="now"'
    rows = "".join(
        f"<tr{now if r == highlight else ''}><td><a href=\"{slug(r)}.html\">{esc(r)}</a></td><td>{long(w['opens'])}</td><td>{long(w['deadline'])}</td></tr>\n"
        for r, w in rr.ROLLOUT.items())
    return f'<div class="wrap"><table><thead><tr><th>Region</th><th>Requirement starts</th><th>Register by</th></tr></thead><tbody>\n{rows}</tbody></table></div>\n'


def region_page(region: str, w: dict) -> tuple:
    fee = rr.FEE_PER_PROPERTY_GBP
    o, dl = long(w["opens"]), long(w["deadline"])
    name = f"{slug(region)}.html"
    h1 = f"Landlord database registration in {region}: deadline {dl}"
    faq = [(f"When do landlords in {region} have to register?",
            f"The requirement starts on {o} and the deadline is {dl}. The service opens to every landlord in England on {long(FIRST)}, so you can register earlier."),
           (f"How much is the landlord database fee in {region}?", f"£{fee} per property per year, the same in every region."),
           ("Does the deadline go by where I live or where the property is?",
            "Where the property is. A landlord living elsewhere with a property in this region meets this region's deadline.")]
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": h1, "dateModified": UPDATED,
           "author": {"@type": "Organization", "name": "genzagents"}, "mainEntityOfPage": BASE + "guides/" + name},
          {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
              {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}]
    body = (f"<p><strong>If your rental is in {esc(region)}, you must register it on the government's "
            f"<em>Register your rental property</em> service by {dl}.</strong> The requirement for {esc(region)} starts on {o}; "
            f"the service opens to every landlord in England on {long(FIRST)}, so you can register earlier.</p>\n"
            f"<p>The region goes by the property's address, not yours. {esc(region)} covers {esc(PLACES[region])}.</p>\n"
            f"<h2>What it costs</h2><p>£{fee} per property per year; five properties cost £{fee * 5}. Renewal is "
            f"{esc(rr.RENEWAL)}. <a href=\"landlord-database-fee.html\">The fee explained</a>.</p>\n"
            f"<h2>What you upload for each property</h2>{ul(rr.UPLOADS)}"
            f"<p>Check the dates now: a certificate that lapses before {dl} has to be renewed first. A gas safety record lasts "
            f"12 months, an EICR five years, an EPC ten years. Guides: <a href=\"gas-safety-certificate-landlord-database.html\">gas safety</a>, "
            f"<a href=\"eicr-landlord-database.html\">EICR</a>, <a href=\"epc-rating-landlord-database.html\">EPC and rating</a>.</p>\n"
            f"<h2>What you will be asked</h2>{ul(rr.DETAILS)}<p><a href=\"what-you-need-to-register.html\">Everything the service asks</a>.</p>\n"
            f"<h2>If you miss {dl}</h2>{ul(rr.PENALTIES)}<p><a href=\"landlord-database-penalties.html\">Penalties explained</a>.</p>\n"
            f"<h2>Every region's dates</h2>{timetable(region)}"
            "<h2>Questions</h2>\n" + "".join(f"<h3>{esc(q)}</h3>\n<p>{esc(a)}</p>\n" for q, a in faq))
    doc = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Landlord database {esc(region)}: register by {dl}</title>
<meta name="description" content="{html.escape(f'Landlords in {region} must register each rental on England’s landlord database by {dl} (requirement starts {o}). £{fee} a property a year. What to upload, what you are asked, penalties.')}">
<link rel="canonical" href="{BASE}guides/{name}">
<style>
{CSS}
</style>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head><body><main>
<p class="mut"><a href="../index.html">rentready</a> / <a href="index.html">Landlord database guides</a></p>
<h1>{esc(h1)}</h1>
{body}<div class="cta"><p><strong>Check your own properties in two minutes.</strong> Enter each postcode and the dates on your gas safety record, EICR and EPC: rentready shows your deadline, which certificates lapse before it, the fee, and a pre-filled registration pack to print. Free, in your browser; only the postcode leaves it, to find the region.</p>
<a class="btn" href="../index.html#tool">Check my properties</a></div>
<h2>Sources</h2>
<ul class="mut">{''.join(f'<li><a href="{u}">{esc(t)}</a></li>' for u, t in SOURCES)}</ul>
<p class="mut">Dates and fee are the draft Private Rented Sector Database Regulations 2026 (laid 9 September 2026, awaiting approval by both Houses) as summarised by the NRLA and HCR Law. Not legal advice; check gov.uk before relying on this. Last checked {long(UPDATED)}.</p>
</main></body></html>
"""
    return name, doc


REGION_FILES = [f"{slug(r)}.html" for r in rr.ROLLOUT]


def sitemap(existing: str) -> str:
    """Add the region pages to the hand-written sitemap, keeping its other entries."""
    keep = [line for line in existing.splitlines() if "<url>" in line and not any("guides/" + f + "<" in line for f in REGION_FILES)]
    add = [f"  <url><loc>{BASE}guides/{f}</loc><lastmod>{UPDATED}</lastmod></url>" for f in REGION_FILES]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(keep + add) + "\n</urlset>\n")


def build() -> dict:
    files = {f"docs/guides/{n}": doc for n, doc in (region_page(r, w) for r, w in rr.ROLLOUT.items())}
    files["docs/sitemap.xml"] = sitemap((ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8"))
    return files


if __name__ == "__main__":
    for rel, text in build().items():
        (ROOT / rel).write_text(text, encoding="utf-8")
        print(rel)

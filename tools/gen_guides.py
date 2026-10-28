#!/usr/bin/env python3
"""Generate one search guide per region in docs/guides/ and add them to docs/sitemap.xml, from rentready's own data.

The topic guides (fee, certificates, penalties...) are hand-written. The dates, fee, upload list and penalties here
come from rentready/__init__.py, so a region page can never say something the checker disagrees with.
tests/test_guides.py fails if the committed pages are stale. Run: python3 tools/gen_guides.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import rentready as rr  # noqa: E402
import schema  # noqa: E402  (tools/schema.py, same folder)

BASE = "https://genzagents.github.io/rentready/"
REGS = "https://www.legislation.gov.uk/ukdsi/2026/9780348286861"
WP = "https://api.parliament.uk/procedure-browser/work-packages/mNlSJVmc"
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

HEAD_TAGS = '<meta name="theme-color" content="#0e5a44">\n<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 32 32\'%3E%3Crect width=\'32\' height=\'32\' rx=\'8\' fill=\'%230e5a44\'/%3E%3Cpath d=\'M8 15.5 16 9l8 6.5V24H8z\' fill=\'none\' stroke=\'%23fff\' stroke-width=\'2.2\' stroke-linejoin=\'round\'/%3E%3Cpath d=\'m12.5 18.5 2.6 2.6 4.6-5\' fill=\'none\' stroke=\'%23fff\' stroke-width=\'2.2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'/%3E%3C/svg%3E">\n<link rel="stylesheet" href="../assets/site.css">'
SITE_HEADER = '<header class="site-head"><div class="container">\n<a class="brand" href="https://genzagents.github.io/rentready/"><svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="8" fill="#0e5a44"/><path d="M8 15.5 16 9l8 6.5V24H8z" fill="none" stroke="#fff" stroke-width="2.2" stroke-linejoin="round"/><path d="m12.5 18.5 2.6 2.6 4.6-5" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>rentready</a>\n<nav class="site-nav"><a href="https://genzagents.github.io/rentready/guides/">Guides</a><a href="https://genzagents.github.io/rentready/guides/landlord-database-deadline-by-region.html">Deadlines</a><a href="https://genzagents.github.io/rentready/about.html">About</a></nav>\n<a class="btn sm" href="https://genzagents.github.io/rentready/#tool">Check a property</a>\n</div></header>'

SOURCES = [
    ("https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/", "Get ready to register: Register your rental property (official guidance)"),
    ("https://www.legislation.gov.uk/ukdsi/2026/9780348286861", "Draft Private Rented Sector Database Regulations 2026 (legislation.gov.uk; not yet made)"),
]


# How each region reads in a sentence ("landlords in the East Midlands"), and its short name for titles.
# ONS calls it "Yorkshire and The Humber"; the official guidance says "Yorkshire and Humber".
NAMED = {"London": "London", "Yorkshire and The Humber": "Yorkshire and the Humber"}
TITLE_NAME = {"Yorkshire and The Humber": "Yorkshire and Humber"}


def the(region: str) -> str:
    return NAMED.get(region, "the " + region)


def The(region: str) -> str:
    t = the(region)
    return t[0].upper() + t[1:]


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
        f"<tr{now if r == highlight else ''}><td><a href=\"{slug(r)}.html\">{esc(NAMED.get(r, r))}</a></td><td>{long(w['opens'])}</td><td>{long(w['deadline'])}</td></tr>\n"
        for r, w in rr.ROLLOUT.items())
    return f'<div class="wrap"><table><thead><tr><th>Region</th><th>Requirement starts</th><th>Register by</th></tr></thead><tbody>\n{rows}</tbody></table></div>\n'


COUNCILS = json.loads((ROOT / "tools" / "councils.json").read_text(encoding="utf-8"))
# ONS names that read oddly in a sentence.
DISPLAY = {"Bristol, City of": "Bristol", "Kingston upon Hull, City of": "Hull (Kingston upon Hull)",
           "Herefordshire, County of": "Herefordshire", "St. Helens": "St Helens"}
ONS_LOOKUP = ("https://geoportal.statistics.gov.uk/", "ONS Open Geography Portal: ward to local authority to region lookup (May 2026)")
SCHEDULE_3 = REGS + "/schedule/3/part/2"
LIVE = ("in force", "designated")


def council_name(c: str) -> str:
    return DISPLAY.get(c, c)


def names(cs: list) -> str:
    cs = [council_name(c) for c in cs]
    return cs[0] if len(cs) == 1 else ", ".join(cs[:-1]) + " and " + cs[-1]


def scheme_line(kind: str, x: dict) -> str:
    label = {"selective": "Selective licensing", "additional": "Additional HMO licensing"}[kind]
    area = x.get("area", "")
    area = re.sub(r"^parts:\s*", "Parts: ", area) if area else ""
    area = area[0].upper() + area[1:] if area else ""
    when = f"starts {long(x['starts'])}" if x["status"] == "designated" and x.get("starts") else "in force"
    text = f"<strong>{label}</strong> ({when})" + (f": {esc(area)}" if area else "")
    if x.get("until"):
        text += f", until {long(x['until'])}"
    text += "."
    if x.get("note"):
        text += " " + esc(x["note"])
    return f'<li>{text} <a href="{html.escape(x["source"])}">Council page</a></li>'


def councils_section(region: str) -> tuple:
    """The region's councils and their selective/additional licensing, from tools/councils.json (each scheme read
    on the council's own website, which the page links). Returns (html, faq pairs, counts)."""
    data = COUNCILS[region]
    cs = data["councils"]
    live = {c: {k: v for k, v in e.items() if v["status"] in LIVE} for c, e in cs.items()}
    sel = [c for c in cs if "selective" in live[c]]
    add = [c for c in cs if "additional" in live[c]]
    unverified = [c for c, e in cs.items() if any(v["status"] == "not verified" for v in e.values())]
    none_found = [c for c in cs if not live[c] and c not in unverified]
    out = [f"<h2>Councils in {esc(the(region))} and their licensing schemes</h2>\n",
           f"<p>{esc(The(region))} has {len(cs)} local councils that act as the local housing authority "
           f"(<a href=\"{ONS_LOOKUP[0]}\">ONS</a>, May 2026). The registration service asks whether each property needs an HMO, "
           f"additional or selective licence, and for the licence numbers (<a href=\"{SCHEDULE_3}\">draft Schedule 3, paragraph 10</a>), "
           f"so check your council first. Mandatory HMO licensing applies everywhere; these schemes are on top.</p>\n",
           f"<p>On {long(data['checked'])} we found {len(sel)} council{'s' if len(sel) != 1 else ''} in {esc(the(region))} with selective "
           f"licensing and {len(add)} with additional HMO licensing, in force or designated to start.</p>\n"]
    for c in cs:
        if live[c]:
            out.append(f"<h3>{esc(council_name(c))}</h3>\n<ul>"
                       + "".join(scheme_line(k, live[c][k]) for k in ("selective", "additional") if k in live[c]) + "</ul>\n")
    if none_found:
        out.append(f"<p><strong>No selective or additional scheme found</strong> on the council's own website: {esc(names(none_found))}. "
                   "That is not a guarantee: a council can start a scheme at any time, so check before you let.</p>\n")
    if unverified:
        out.append(f"<p><strong>Not verified:</strong> we could not confirm the schemes for {esc(names(unverified))} from the council's own "
                   "website, so we list nothing for them here. Check with the council.</p>\n")
    checked = long(data["checked"])
    if sel:
        faq = [(f"Which councils in {the(region)} have selective licensing?",
                f"As of {checked}: {names(sel)}. Most schemes cover only some wards, so check the council's map for your street.")]
    else:
        faq = [(f"Which councils in {the(region)} have selective licensing?",
                f"We found none on the councils' own websites on {checked}" + (", though we could not verify every council." if unverified else "."))]
    if add:
        faq.append((f"Which councils in {the(region)} have additional HMO licensing?", f"As of {checked}: {names(add)}."))
    return "".join(out), faq, (len(cs), len(sel), len(add))


RELATED = [("landlord-database-deadline-by-region.html", "Other regions"), ("what-you-need-to-register.html", "What you need"),
           ("gas-safety-certificate-landlord-database.html", "Gas"), ("eicr-landlord-database.html", "EICR"), ("epc-rating-landlord-database.html", "EPC")]


def region_page(region: str, w: dict) -> tuple:
    fee = rr.FEE_PER_PROPERTY_GBP
    o, dl = long(w["opens"]), long(w["deadline"])
    name = f"{slug(region)}.html"
    h1 = f"Landlord database registration in {the(region)}: deadline {dl}"
    title = f"{TITLE_NAME.get(region, region)} landlord database deadline: {dl}"
    councils_html, council_faq, (n, n_sel, n_add) = councils_section(region)
    desc = (f"Landlords in {the(region)} must register on England's landlord database (PRS Database) by {dl}. "
            f"Its {n} councils and their licensing schemes.")
    faq = [(f"When do landlords in {the(region)} have to register?",
            f"The requirement starts on {o} and the deadline is {dl}. The service opens to every landlord in England on {long(FIRST)}, so you can register earlier.")] + council_faq
    ld = [{"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
              {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}]
    body = (f"<p><strong>If your rental is in {esc(the(region))}, you must register it on the government's "
            f"<em>Register your rental property</em> service (the landlord database, or PRS Database) by {dl}.</strong> The requirement for {esc(the(region))} starts on {o}; "
            f"the service opens to every landlord in England on {long(FIRST)}, so you can register earlier. "
            f"The region goes by the property's address, not yours. {esc(The(region))} covers {esc(PLACES[region])}.</p>\n"
            + councils_html
            + f"<h2>Before {dl}</h2>\n"
            f"<p>£{fee} a property a year (<a href=\"landlord-database-fee.html\">fee</a>). Upload the gas safety record, EICR and EPC "
            f"(<a href=\"what-you-need-to-register.html\">full list</a>) within 28 days or the entry becomes inactive "
            f"(<a href=\"{REGS}/regulation/11\">draft reg 11(2)(a)</a>); renew anything that lapses before {dl} first. "
            f"Up to £7,000 if you miss it (<a href=\"landlord-database-penalties.html\">penalties</a>).</p>\n"
            "<h2>Questions</h2>\n" + "".join(f"<h3>{esc(q)}</h3>\n<p>{esc(a)}</p>\n" for q, a in faq)
            + "<h2>Related guides</h2>\n<p>" + " · ".join(f'<a href="{u}">{esc(t)}</a>' for u, t in RELATED) + "</p>\n")
    sources = SOURCES + [ONS_LOOKUP, (SCHEDULE_3, "Draft Schedule 3, Part 2: what the service asks, including licences")]
    doc = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{BASE}guides/{name}">
{HEAD_TAGS}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head><body>
{SITE_HEADER}
<main>
<p class="crumbs"><a href="{BASE}">rentready</a> / <a href="{BASE}guides/">Landlord database guides</a></p>
<h1>{esc(h1)}</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed {long(UPDATED)}. <a href="#sources">Sources</a> below.</p>
{body}<div class="cta"><p><strong>Check your properties against {dl}.</strong> Postcode and certificate dates in; deadline, what lapses first and a registration pack out. Free, in your browser.</p>
<a class="btn" href="{BASE}#tool">Check my properties</a></div>
<h2 id="sources">Sources</h2>
<ul class="mut">{''.join(f'<li><a href="{u}">{esc(t)}</a></li>' for u, t in sources)}</ul>
<p class="mut">Dates: official guidance and the draft regulations, which Parliament has not yet approved (<a href="landlord-database-registration.html">status</a>). Fee: official guidance. Councils and schemes: read on each council's own website on {long(COUNCILS[region]['checked'])}. Not legal advice. Last checked {long(UPDATED)}.</p>
<footer class="foot mut"><a href="https://genzagents.github.io/rentready/about.html">About</a> · <a href="https://genzagents.github.io/rentready/guides/">Guides</a> · <a href="https://genzagents.github.io/rentready/developers.html">Developers</a> · <a href="https://genzagents.github.io/rentready/privacy.html">Privacy</a> · <a href="https://genzagents.github.io/rentready/terms.html">Terms</a> · <a href="https://github.com/genzagents/rentready/issues">Contact (GitHub issues)</a><br>rentready is made by GenZAgents in London. Not legal advice.</footer>
</main></body></html>
"""
    return name, doc




# Regions without enough region-only content for a page of their own (tests/test_guides.py holds every standalone
# region page to at least 40% unique text). Their councils and schemes are a section of the deadline-by-region page,
# and the old URL is a redirect stub (meta refresh plus canonical), left out of the sitemap.
MERGED = ("North East", "South West")
DEADLINE_PAGE = "landlord-database-deadline-by-region.html"
MARK_START, MARK_END = "<!-- generated:merged-regions -->", "<!-- /generated:merged-regions -->"
REGION_FILES = [f"{slug(r)}.html" for r in rr.ROLLOUT if r not in MERGED]


def region_href(region: str) -> str:
    """Where a region's guide lives, relative to docs/guides/."""
    return f"{DEADLINE_PAGE}#{slug(region)}" if region in MERGED else f"{slug(region)}.html"


def merged_section(region: str) -> str:
    w = rr.ROLLOUT[region]
    body, _, _ = councils_section(region)
    body = body.replace("<h3>", "<h4>").replace("</h3>", "</h4>").replace("<h2>", "<h3>").replace("</h2>", "</h3>")
    return (f'<h2 id="{slug(region)}">{esc(NAMED.get(region, region))}: register by {long(w["deadline"])}</h2>\n'
            f"<p>The requirement for {esc(the(region))} starts on {long(w['opens'])} and the deadline is {long(w['deadline'])}. "
            f"{esc(The(region))} covers {esc(PLACES[region])}.</p>\n" + body)


def deadline_page(existing: str) -> str:
    """Write the merged regions' sections between the markers in the hand-written deadline page."""
    a, b = existing.index(MARK_START) + len(MARK_START), existing.index(MARK_END)
    return existing[:a] + "\n" + "".join(merged_section(r) for r in MERGED) + existing[b:]


def redirect_stub(region: str) -> str:
    target = BASE + "guides/" + region_href(region)
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(NAMED.get(region, region))} landlord database deadline</title>
<link rel="canonical" href="{BASE}guides/{DEADLINE_PAGE}">
<meta http-equiv="refresh" content="0; url={html.escape(target)}">
</head><body><p>This guide has moved to <a href="{html.escape(target)}">{esc(the(region))} on the deadline-by-region page</a>.</p></body></html>
"""


def sitemap(existing: str) -> str:
    """Add the region pages to the hand-written sitemap, keeping its other entries and dropping merged regions."""
    every = [f"{slug(r)}.html" for r in rr.ROLLOUT]
    keep = [line for line in existing.splitlines() if "<url>" in line and not any("guides/" + f + "<" in line for f in every)]
    add = [f"  <url><loc>{BASE}guides/{f}</loc><lastmod>{UPDATED}</lastmod></url>" for f in REGION_FILES]
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(keep + add) + "\n</urlset>\n")


def build() -> dict:
    files = {f"docs/guides/{n}": doc for n, doc in (region_page(r, w) for r, w in rr.ROLLOUT.items() if r not in MERGED)}
    files.update({f"docs/guides/{slug(r)}.html": redirect_stub(r) for r in MERGED})
    files[f"docs/guides/{DEADLINE_PAGE}"] = deadline_page((ROOT / "docs" / "guides" / DEADLINE_PAGE).read_text(encoding="utf-8"))
    files = {rel: schema.apply(rel, t) if rel.endswith(".html") else t for rel, t in files.items()}  # Article, breadcrumbs
    files["docs/sitemap.xml"] = sitemap((ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8"))
    return files


if __name__ == "__main__":
    for rel, text in build().items():
        (ROOT / rel).write_text(text, encoding="utf-8")
        print(rel)

"""Structured data for every published page (site audit fix 14).

Adds one generated JSON-LD block per page, kept apart from any hand-written FAQPage block:
- every page with breadcrumbs: BreadcrumbList built from the visible crumbs
- every guide: Article with headline, datePublished, dateModified (the byline's "reviewed" date), author, publisher, image
- the main page: WebApplication (free) and the Organization
- the about page: AboutPage and the Organization with its founder

Run `python3 tools/schema.py` after editing a page; tools/gen_guides.py applies it to the pages it generates, and
tests/test_schema.py fails if any committed page is out of date.
"""
import html
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://genzagents.github.io/rentready/"
LOGO = BASE + "assets/logo-512.png"
PUBLISHED = "2026-10-28"  # first publication of the guides; add an entry to PUBLISHED_AT for later pages
PUBLISHED_AT: dict = {"docs/guides/epc-expiry-by-region.html": "2026-10-29"}
MARK = '<script type="application/ld+json" id="ld-site">'
BLOCK = re.compile(re.escape(MARK) + r".*?</script>\n", re.S)

ORG = {"@type": "Organization", "@id": BASE + "about.html#org", "name": "GenZAgents", "url": BASE + "about.html",
       "logo": {"@type": "ImageObject", "url": LOGO, "width": 512, "height": 512},
       "founder": {"@type": "Person", "name": "Manraj Singh Dhillon"},
       "sameAs": ["https://github.com/genzagents"]}
ORG_REF = {"@id": ORG["@id"]}


def text_of(fragment: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def canonical(t: str) -> str:
    return re.search(r'<link rel="canonical" href="([^"]+)">', t).group(1)


def crumbs(t: str, url: str) -> list:
    m = re.search(r'<p class="crumbs">(.*?)</p>', t, re.S)
    if not m:
        return []
    items = [(text_of(name), href) for href, name in re.findall(r'<a href="([^"]+)">(.*?)</a>', m.group(1))]
    tail = text_of(re.sub(r".*</a>", "", m.group(1), flags=re.S)).lstrip("/ ").strip()
    if not items or items[-1][1] != url:  # the hub's crumbs already end with a link to itself
        items.append((tail or text_of(re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S).group(1)), url))
    return items


def reviewed(t: str):
    m = re.search(r"reviewed (\d{1,2} \w+ \d{4})", t)
    return datetime.strptime(m.group(1), "%d %B %Y").date().isoformat() if m else None


def graph(rel: str, t: str) -> list:
    url = canonical(t)
    h1 = text_of(re.search(r"<h1[^>]*>(.*?)</h1>", t, re.S).group(1))
    out = []
    trail = crumbs(t, url)
    if trail:
        out.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": n, "item": u} for i, (n, u) in enumerate(trail)]})
    if rel.startswith("docs/guides/"):
        out.append({"@type": "Article", "headline": h1[:110], "datePublished": PUBLISHED_AT.get(rel, PUBLISHED),
                    "dateModified": reviewed(t) or PUBLISHED, "author": ORG_REF, "publisher": ORG_REF,
                    "image": LOGO, "inLanguage": "en-GB", "mainEntityOfPage": url})
    if rel == "docs/index.html":
        out.append({"@type": "WebApplication", "name": "rentready", "url": url, "applicationCategory": "BusinessApplication",
                    "operatingSystem": "Any (runs in the browser)", "inLanguage": "en-GB", "isAccessibleForFree": True,
                    "description": "Checks each rental's gas safety record, EICR and EPC against its landlord database deadline and builds the registration pack.",
                    "offers": {"@type": "Offer", "price": "0", "priceCurrency": "GBP"}, "publisher": ORG_REF})
    if rel == "docs/about.html":
        out.append({"@type": "AboutPage", "url": url, "about": ORG_REF})
    if out:  # the Organization node goes on every page that refers to it
        out.append(ORG)
    return out


def apply(rel: str, t: str) -> str:
    t = BLOCK.sub("", t)
    if 'http-equiv="refresh"' in t:
        return t
    g = graph(rel, t)
    if not g:
        return t
    block = MARK + json.dumps({"@context": "https://schema.org", "@graph": g}, ensure_ascii=False) + "</script>\n"
    return t.replace("</head>", block + "</head>", 1)


def pages():
    for p in sorted((ROOT / "docs").rglob("*.html")):
        yield p.relative_to(ROOT).as_posix(), p


if __name__ == "__main__":
    for rel, p in pages():
        old = p.read_text(encoding="utf-8")
        new = apply(rel, old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            print(rel)

"""Fetch HMRC's list of software recognised for Making Tax Digital for Income Tax.

Source: https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software/
(Open Government Licence v3.0). Walks the public "show all software" route as a
sole trader or landlord, then reads each product's feature page. Writes
tools/data/mtd_software.json. Polite: one request a second.
"""
import html
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

BASE = "https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software"
OUT = Path(__file__).parent / "data" / "mtd_software.json"

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [("User-Agent", "genzagents-rentready/1.0 (+https://genzagents.github.io/rentready/)")]


def get(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    with opener.open(url, body, timeout=30) as r:
        return r.read().decode("utf-8")


def csrf(page):
    return re.search(r'name="csrfToken" value="([^"]+)"', page).group(1)


def text_lines(fragment):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", fragment, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", "\n", t))
    return [line.strip() for line in t.split("\n") if line.strip()]


def results_page():
    start = get(BASE + "/")
    p = get(BASE + "/how-to-find-software", {"csrfToken": csrf(start), "how-you-find-software": "view-all"})
    return get(BASE + "/about-you", {"csrfToken": csrf(p), "type-of-user": "sole-trader-or-landlord"})


STATUSES = ("Ready now", "In development", "Not included")


def product(pid):
    page = get(f"{BASE}/product-details?productId={pid}")
    sites = [u for u in re.findall(r'href="(https?://[^"]+)"', page)
             if "gov.uk" not in u and "nationalarchives" not in u]
    lines = text_lines(page[page.find("Back"):])
    features = {}
    for a, b in zip(lines, lines[1:]):
        if b in STATUSES and a not in STATUSES and a not in ("Status", "Meaning") and not a.endswith("."):
            features[a] = b
    spec = {}
    for key in ("Software type", "Language"):
        if key in lines:
            spec[key] = lines[lines.index(key) + 1]
    if "Compatible with" in lines:
        i = lines.index("Compatible with") + 1
        comp = []
        while i < len(lines) and lines[i] not in ("Language", "Getting started with this software"):
            comp.append(lines[i])
            i += 1
        spec["Compatible with"] = comp
    return {"website": sites[0] if sites else None, "features": features, **spec}


LIST_FIELDS = ("Price", "Type of software", "Submission type", "Income sources")


def list_summary(block, names):
    """The results list: name -> {"submission": [...]} (quarterly updates and/or tax return)."""
    out, cur, key = {}, None, None
    for line in text_lines(block):
        if line.endswith("features and their availability"):
            continue
        if line in LIST_FIELDS:
            key = line
            continue
        if line in names:
            cur = {}
            out[line] = cur
            key = None
            continue
        if key:
            cur[key] = line
            key = None
            continue
    return {name: [s.strip() for s in v.get("Submission type", "").split(",") if s.strip()]
            for name, v in out.items() if "Price" in v}


def main():
    page = results_page()
    block = page[page.find("Software results based on"):]
    ids = re.findall(r'product-details\?productId=(\d+)"[^>]*>\s*(?:<[^>]+>\s*)*([^<]*?)\s*features and their availability', block)
    total = int(re.search(r"You have (\d+) software results", page).group(1))
    assert len(ids) == total, (len(ids), total)
    submission = list_summary(block, {html.unescape(n) for _, n in ids})
    products = []
    for n, (pid, name) in enumerate(ids, 1):
        time.sleep(1)
        info = product(pid)
        name = html.unescape(name)
        products.append({"id": int(pid), "name": name, "submission": submission.get(name, []), **info})
        print(f"{n}/{total} {name}", file=sys.stderr)
    products.sort(key=lambda p: p["name"].lower())
    OUT.write_text(json.dumps({"fetched": date.today().isoformat(), "source": BASE + "/",
                               "count": total, "products": products}, indent=1, ensure_ascii=False))
    print(f"wrote {OUT} ({total} products)")


if __name__ == "__main__":
    main()

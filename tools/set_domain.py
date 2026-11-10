"""Move the site from genzagents.github.io/rentready to its own host in one step.

    python3 tools/set_domain.py landlords.genzagents.com          # dry run: counts only
    python3 tools/set_domain.py landlords.genzagents.com --write  # rewrite the repo

Run it only after the DNS record exists (CNAME <host> -> genzagents.github.io),
otherwise GitHub redirects every github.io visitor to a host that does not resolve.
Once docs/CNAME is pushed, GitHub Pages answers 301 from every old
genzagents.github.io/rentready/... address to the same path on the new host,
so Google and Bing carry what they have indexed across.

What it changes:
- every https://genzagents.github.io/rentready URL in text files (pages, sitemap,
  generators, package metadata, MCP server.json, emails the paid runner sends, tests)
- docs/CNAME, docs/robots.txt (the host root now belongs to us, not the org site)
- the IndexNow key file and the Google verification file copied into docs/, so
  IndexNow keeps working and Search Console verifies the new host with the same token
- INDEXNOW_HOST in the indexnow workflow and the calendar UID domain
- the bare genzagents.github.io/rentready text printed on the agents' card
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OLD = "https://genzagents.github.io/rentready"
OLD_HOST = "genzagents.github.io"
BARE = OLD_HOST + "/rentready"
INDEXNOW_KEY = "7bf25f454fd71c2a00b4be9bcf94b12d"
GOOGLE_FILE = "google8d8707e774021389.html"
TEXT = {".html", ".xml", ".txt", ".md", ".json", ".toml", ".py", ".js", ".yml", ".csv", ".svg", ".ics"}
SKIP_DIRS = {".git", "__pycache__", "dist", "build", ".pytest_cache"}


def files():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in TEXT and not SKIP_DIRS & set(p.relative_to(ROOT).parts):
            if p.name == "set_domain.py":
                continue
            yield p


def rewrite(text, host):
    # https and bare forms (printed on cards), then calendar UIDs
    return (text.replace(OLD, "https://" + host).replace(BARE, host)
            .replace("@" + OLD_HOST, "@" + host))


def count(text):
    return text.count(BARE) + text.count("@" + OLD_HOST)


def robots(host):
    return ("User-agent: *\nAllow: /\n\n"
            f"Sitemap: https://{host}/sitemap.xml\n")


def plan(host):
    changes = {}
    for p in files():
        t = p.read_text(encoding="utf-8")
        n = count(t)
        if n:
            changes[p] = (n, rewrite(t, host))
    wf = ROOT / ".github/workflows/indexnow.yml"
    t = changes.get(wf, (0, wf.read_text(encoding="utf-8")))[1]
    t2 = re.sub(r"INDEXNOW_HOST: \S+", "INDEXNOW_HOST: " + host, t)
    t2 = t2.replace(f"https://{OLD_HOST}/<key>.txt", f"https://{host}/<key>.txt")
    if t2 != wf.read_text(encoding="utf-8"):
        changes[wf] = (changes.get(wf, (0,))[0] + 1, t2)
    return changes


def main(argv):
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    host, write = argv[0].lower().strip("/"), "--write" in argv
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", host):
        sys.exit("not a host name: " + host)
    changes = plan(host)
    total = sum(n for n, _ in changes.values())
    print(f"{total} replacements in {len(changes)} files -> https://{host}/")
    if not write:
        for p, (n, _) in sorted(changes.items()):
            print(f"  {n:4d}  {p.relative_to(ROOT)}")
        print("dry run; add --write to apply")
        return
    for p, (_, t) in changes.items():
        p.write_text(t, encoding="utf-8")
    docs = ROOT / "docs"
    (docs / "CNAME").write_text(host + "\n", encoding="utf-8")
    (docs / "robots.txt").write_text(robots(host), encoding="utf-8")
    (docs / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY + "\n", encoding="utf-8")
    (docs / GOOGLE_FILE).write_text("google-site-verification: " + GOOGLE_FILE, encoding="utf-8")
    print("wrote docs/CNAME, docs/robots.txt, IndexNow key file, Google verification file")


if __name__ == "__main__":
    main(sys.argv[1:])

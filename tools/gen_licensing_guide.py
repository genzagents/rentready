"""Selective licensing in England: every council's scheme (docs/guides/selective-licensing-councils-england.html).

One page built from docs/data/licensing.json (tools/gen_licensing.py), which holds what we read on each of England's
296 local housing authorities' own websites on 28 October 2026. It answers "does my council license private lets?"
for a postcode, lists every scheme in force or starting, shows the schemes that end in the next twelve months (when
councils consult on renewals), and says what the landlord database adds on top: a licence is not registration, and
you pay both fees.

Run `python3 tools/gen_licensing.py`, then this, then `python3 tools/schema.py`; tests/test_licensing_guide.py checks
the page.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rentready import ROLLOUT  # noqa: E402

OUT = ROOT / "docs/guides/selective-licensing-councils-england.html"
URL = "https://genzagents.github.io/rentready/guides/selective-licensing-councils-england.html"
REVIEWED = "3 November 2026"
TODAY = "2026-11-03"
SOON = "2027-11-30"  # schemes whose current designation ends by this date are listed as "ending soon"
LIVE = ("in force", "designated")
KIND = {"selective": "Selective", "additional": "Additional HMO"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def nice(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {MONTHS[int(m) - 1]} {y}"


def short(name: str) -> str:
    return name.replace(", City of", "").replace(", County of", "")


def data() -> dict:
    return json.loads((ROOT / "docs/data/licensing.json").read_text(encoding="utf-8"))


def schemes(d: dict) -> list:
    """Every live scheme as (region, council, kind, entry), sorted by region then council."""
    out = []
    for name, c in d["councils"].items():
        for k in KIND:
            if c[k]["status"] in LIVE:
                out.append((c["region"], name, k, c[k]))
    return sorted(out, key=lambda s: (s[0], short(s[1]), s[2]))


def area(e: dict) -> str:
    a = (e.get("area") or "").strip()
    return a[0].upper() + a[1:] if a else "See the council's map"


def faq(d: dict) -> list:
    n = d["counts"]
    return [
        ("Which councils in England have selective licensing?",
         f"On 28 October 2026 we found {n['selective']} of England's {n['councils']} councils with a selective "
         f"licensing scheme in force or about to start, and {n['additional']} with additional licensing for shared "
         f"houses; {n['either']} councils have one or both. Most selective schemes cover only some wards or streets, "
         "so check the council's map for your address. The full list, with each council's own page, is on this page."),
        ("Do I need a selective licence and to register on the landlord database?",
         "Yes, if your property is in a licensing area. A council licence does not count as registration on the "
         "private rented sector database, and the draft regulations give no exemption or discount for licensed homes. "
         "You need both and pay both fees, and the registration service asks for the licence number."),
        ("How much does a selective licence cost?",
         "Each council sets its own fee for the five-year licence, often several hundred pounds a property, usually "
         "paid in two parts. The landlord database is about £65 a property a year on top. Check the fee on the "
         "council's page linked from the table."),
        ("What happens when a selective licensing scheme ends?",
         "A designation lasts up to five years. Before it ends the council usually consults on a renewal, and since "
         "December 2024 councils in England no longer need the government's approval for schemes of any size. If a "
         "scheme ends without renewal, licences under it end too, but the property still needs its database entry."),
    ]


def scheme_row(s: tuple) -> str:
    region, name, k, e = s
    when = ("starts " + nice(e["starts"]) if e["status"] == "designated" and e.get("starts")
            else "until " + nice(e["until"]) if e.get("until") else "in force")
    src = f'<a href="{html.escape(e["source"])}" rel="noopener">Council page</a>' if e.get("source") else ""
    return (f'<tr data-q="{html.escape((short(name) + " " + region).lower())}"><td>{html.escape(short(name))}</td>'
            f"<td>{KIND[k]}</td><td>{html.escape(area(e))}</td><td>{when}</td><td>{src}</td></tr>")


def build() -> str:
    d = data()
    n = d["counts"]
    all_s = schemes(d)
    regions = sorted({s[0] for s in all_s})
    by_region = []
    for r in regions:
        rs = [s for s in all_s if s[0] == r]
        dl = ROLLOUT[r]["deadline"]
        by_region.append(f'<h3 class="lr" data-r="{html.escape(r)}">{html.escape(r)} '
                         f'<small class="mut">{len({s[1] for s in rs})} councils · database deadline {nice(dl)}</small></h3>\n'
                         '<div class="wrap"><table class="lt"><thead><tr><th>Council</th><th>Scheme</th><th>Where</th>'
                         '<th>Dates</th><th>Source</th></tr></thead><tbody>\n'
                         + "\n".join(scheme_row(s) for s in rs) + "\n</tbody></table></div>")
    ending = sorted((s for s in all_s if s[3].get("until") and TODAY <= s[3]["until"] <= SOON),
                    key=lambda s: s[3]["until"])
    starting = sorted((s for s in all_s if s[3]["status"] == "designated"), key=lambda s: s[3].get("starts", ""))
    end_rows = "\n".join(f"<tr><td>{nice(s[3]['until'])}</td><td>{html.escape(short(s[1]))}</td><td>{KIND[s[2]]}</td>"
                         f"<td>{html.escape(area(s[3]))}</td></tr>" for s in ending)
    start_rows = "\n".join(f"<tr><td>{nice(s[3]['starts'])}</td><td>{html.escape(short(s[1]))}</td><td>{KIND[s[2]]}</td>"
                           f"<td>{html.escape(area(s[3]))}</td></tr>" for s in starting if s[3].get("starts"))
    whole = sum(1 for s in all_s if s[2] == "selective" and (s[3].get("area") or "").lower().startswith("whole"))
    unv = sum(1 for c in d["councils"].values() if c["selective"]["status"] == "not verified")
    london = sum(1 for c in d["councils"].values() if c["region"] == "London"
                 and any(c[k]["status"] in LIVE for k in KIND))
    london_all = sum(1 for c in d["councils"].values() if c["region"] == "London")
    q = faq(d)
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": a, "acceptedAnswer": {"@type": "Answer", "text": b}} for a, b in q]},
        ensure_ascii=False, indent=1)
    src = (ROOT / "docs/guides/landlord-database-first-year-cost.html").read_text(encoding="utf-8")
    header = src[src.index("<header"):src.index("</header>") + 9]
    footer = src[src.index("<footer"):]
    windows = json.dumps({r: w["deadline"] for r, w in ROLLOUT.items()}, separators=(",", ":"))
    t = PAGE
    for k, v in {"__URL__": URL, "__FAQ__": faq_ld, "__HEADER__": header, "__FOOTER__": footer,
                 "__REVIEWED__": REVIEWED, "__CHECKED__": nice(d["checked"]), "__N__": str(n["councils"]),
                 "__SEL__": str(n["selective"]), "__ADD__": str(n["additional"]), "__EITHER__": str(n["either"]),
                 "__WHOLE__": str(whole), "__UNV__": str(unv), "__LONDON__": f"{london} of {london_all}",
                 "__NEND__": str(len(ending)), "__ENDROWS__": end_rows, "__STARTROWS__": start_rows,
                 "__REGIONS__": "\n".join(by_region), "__WINDOWS__": windows,
                 "__FAQ_HTML__": "\n".join(f"<h3>{html.escape(a)}</h3>\n<p>{html.escape(b)}</p>" for a, b in q)}.items():
        t = t.replace(k, v)
    return t


PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Selective licensing councils in England: the full list (2026)</title>
<meta name="description" content="Every English council with selective or additional licensing, read on each council's site: where it applies, when it ends, and the database fee on top.">
<link rel="canonical" href="__URL__">
<meta name="theme-color" content="#0e5a44">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%230e5a44'/%3E%3Cpath d='M8 15.5 16 9l8 6.5V24H8z' fill='none' stroke='%23fff' stroke-width='2.2' stroke-linejoin='round'/%3E%3Cpath d='m12.5 18.5 2.6 2.6 4.6-5' fill='none' stroke='%23fff' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="stylesheet" href="../assets/site.css">
<script type="application/ld+json">
__FAQ__
</script>
</head><body>
__HEADER__
<main>
<p class="crumbs"><a href="https://genzagents.github.io/rentready/">rentready</a> / <a href="https://genzagents.github.io/rentready/guides/">Landlord guides</a></p>
<h1>Selective licensing councils in England: the full list</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed __REVIEWED__. Each scheme read on the council's own website on __CHECKED__. <a href="#sources">Sources</a> below.</p>
<p><strong>__EITHER__ of England's __N__ councils license private lets beyond the national HMO rules: __SEL__ run selective licensing and __ADD__ run additional licensing for shared houses.</strong> Most selective schemes cover only some wards or streets. A council licence does not count as registration on the new landlord database, which opens on 15 December 2026, so licensed landlords pay both fees.</p>

<div class="kpis">
<div><b>__SEL__</b><span>councils with selective licensing</span></div>
<div><b>__ADD__</b><span>with additional HMO licensing</span></div>
<div><b>__LONDON__</b><span>London boroughs with a scheme</span></div>
<div><b>__NEND__</b><span>schemes due to end by November 2027</span></div>
</div>

<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="lk-h">
<h2 id="lk-h" style="margin-top:0">Does your council license your let?</h2>
<form class="lookup" id="lk" onsubmit="return false">
<label>Property postcode <input class="dl-sel" id="pc" autocomplete="postal-code" placeholder="e.g. B29 6BD"></label>
<button type="submit" class="go">Check</button>
</form>
<div class="who-out" id="lic-out" aria-live="polite" style="display:none"></div>
<form class="remind wait dl-rem" id="rem" novalidate style="display:none"><p><strong>Email me before my landlord database deadline.</strong> Two reminders, nothing else. No account.</p>
<div class="remind-row"><label class="sr" for="rem-email">Email address</label><input type="email" id="rem-email" autocomplete="email" placeholder="you@example.com" required>
<button type="submit" class="go">Remind me</button></div>
<p class="mut remind-f">We keep only your email, your region and its deadline, never the postcode. <a href="../privacy.html#reminders">How to be removed</a>.</p><p class="remind-msg" id="rem-msg" role="status"></p></form>
<p class="mut" style="margin-bottom:0">Only the postcode goes to postcodes.io to find the council. To check gas, EICR and EPC dates as well, <a href="https://genzagents.github.io/rentready/">run the full check</a>.</p>
</section>

<h2>Licensed? You still register, and pay both</h2>
<p>From 15 December 2026 every private landlord in England must register each let on the private rented sector database, region by region, at about £65 a property a year. The draft regulations give no exemption or discount for homes that already hold a selective or additional licence, and the registration form asks for the licence number. A licence costs several hundred pounds for five years, set by each council. See <a href="landlord-database-fee.html">what the database fee covers</a> and <a href="landlord-database-first-year-cost.html">the first-year cost per property</a>.</p>
<p>Mandatory HMO licensing (five or more people from two or more households) applies in every council and is not listed here.</p>

<h2>Schemes due to end by November 2027</h2>
<p>A designation lasts up to five years. Councils usually consult on renewing it in the year before it ends, and since December 2024 they no longer need the government's approval, whatever the size. These are the schemes whose current end date falls in the next twelve months or so.</p>
<div class="wrap"><table class="lt"><thead><tr><th>Ends</th><th>Council</th><th>Scheme</th><th>Where</th></tr></thead><tbody>
__ENDROWS__
</tbody></table></div>

<h2>New schemes starting</h2>
<div class="wrap"><table class="lt"><thead><tr><th>Starts</th><th>Council</th><th>Scheme</th><th>Where</th></tr></thead><tbody>
__STARTROWS__
</tbody></table></div>

<h2 id="all">Every council with a scheme, by region</h2>
<p>__WHOLE__ selective schemes cover a whole borough or city; the rest cover named wards or streets, so check the council's map. "Dates" is the end of the current designation where the council publishes it. We could not read __UNV__ councils' websites; they are left out rather than guessed.</p>
<label class="mut" for="flt" style="display:block;margin:10px 0 4px">Filter by council or region</label>
<input class="dl-sel" id="flt" placeholder="e.g. Leeds" autocomplete="off" style="width:100%">
__REGIONS__

<h2>Questions</h2>
__FAQ_HTML__
<h2 id="sources">Sources</h2>
<ul class="mut">
<li>Each council's own licensing page, linked in its row above, read on __CHECKED__. The data is free to reuse: <a href="../data/licensing.json">licensing.json</a>.</li>
<li><a href="https://www.legislation.gov.uk/ukpga/2004/34/part/3">Housing Act 2004, Part 3 (selective licensing)</a> and <a href="https://www.legislation.gov.uk/ukpga/2004/34/part/2">Part 2 (additional HMO licensing)</a></li>
<li><a href="https://www.gov.uk/government/publications/selective-licensing-in-the-private-rented-sector-a-guide-for-local-authorities">gov.uk: selective licensing, a guide for local authorities</a></li>
<li><a href="landlord-database-regulations-status.html">The draft landlord database regulations and their status</a></li>
</ul>
<p class="mut">Not legal advice. Councils change schemes; check the council's page before you apply or register. Last checked __REVIEWED__.</p>
<script src="../remind.js"></script>
<script>
(function(){
var W=__WINDOWS__,RM=window.rentreadyRemind,L=null,cur=null;
var MON=["January","February","March","April","May","June","July","August","September","October","November","December"];
function $(i){return document.getElementById(i);}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function dd(s){var p=String(s||"").split("-");return p.length===3?(+p[2])+" "+MON[+p[1]-1]+" "+p[0]:"";}
function data(){return L||(L=fetch("../data/licensing.json").then(function(r){return r.ok?r.json():null;}).catch(function(){return null;}));}
function line(k,x){var a=(x.area||"").replace(/^parts:\\s*/i,"in parts: ");
 return '<li><strong>'+(k==="selective"?"Selective licensing":"Additional HMO licensing")+'</strong> '+(x.status==="designated"?"starts "+dd(x.starts):"in force")+(a?", "+esc(a):"")+(x.until?", until "+dd(x.until):"")+'. <a rel="noopener" href'+'="'+esc(x.source)+'">Council page</a></li>';}
async function go(){
 var pc=$("pc").value.trim(),o=$("lic-out");if(!pc)return;
 o.style.display="";o.className="who-out";o.innerHTML="<p>Looking up "+esc(pc)+"...</p>";
 var r=null;try{var x=await fetch("https://api.postcodes.io/postcodes/"+encodeURIComponent(pc));r=x.ok?(await x.json()).result:null;}catch(e){}
 if(!r){o.innerHTML="<b>Postcode not found</b><p>Check it and try again.</p>";$("rem").style.display="none";return;}
 if(r.country!=="England"){o.innerHTML="<b>"+esc(r.country)+" is not covered</b><p>This list and the landlord database are for England only.</p>";$("rem").style.display="none";return;}
 var D=await data(),c=D&&D.councils[r.admin_district],name=String(r.admin_district).replace(/, (City|County) of$/,"");
 var reg=r.region==="East of England"||W[r.region]?r.region:null,dl=reg&&W[reg];
 var live=c?["selective","additional"].filter(function(k){return c[k].status==="in force"||c[k].status==="designated";}):[];
 var tail=dl?"<p>Database: register by <strong>"+dd(dl)+"</strong> ("+esc(reg)+"), about £65 a property a year"+(live.length?", on top of any licence fee":"")+".</p>":"";
 if(c&&live.length){o.className="who-out who-later";o.innerHTML="<b>"+esc(name)+" licenses private lets</b><ul>"+live.map(function(k){return line(k,c[k]);}).join("")+"</ul><p>Check the council's map for your street.</p>"+tail;}
 else if(c&&c.selective.status==="not verified"){o.innerHTML="<b>We could not confirm "+esc(name)+"'s schemes</b><p>Its website could not be read. Ask the council before you register.</p>"+tail;}
 else{o.className="who-out who-yes";o.innerHTML="<b>No selective or additional licensing found in "+esc(name)+"</b><p>Checked on the council's website on "+dd(D?D.checked:"")+". Mandatory HMO licensing still applies everywhere.</p>"+tail;}
 cur=dl?{region:reg,deadline:dl}:null;$("rem").style.display=cur?"":"none";}
$("lk").addEventListener("submit",go);
var f=$("flt");f.addEventListener("input",function(){var q=f.value.trim().toLowerCase();
 document.querySelectorAll(".lt tbody tr[data-q]").forEach(function(tr){tr.style.display=!q||tr.getAttribute("data-q").indexOf(q)>=0?"":"none";});
 document.querySelectorAll(".lr").forEach(function(h){var t=h.nextElementSibling,any=[].some.call(t.querySelectorAll("tr[data-q]"),function(tr){return tr.style.display!=="none";});h.style.display=t.style.display=any?"":"none";});});
var rm=$("rem"),m=$("rem-msg");
rm.addEventListener("submit",async function(ev){ev.preventDefault();
 var d=RM&&cur&&RM.calendar($("rem-email").value,[cur.region],cur.deadline);
 if(!d){m.textContent="Please enter a valid email address.";return;}
 d[RM.FIELDS.source]="licensing list";
 m.textContent="Sending...";try{await RM.send(d);m.textContent="Done. We will email you before "+dd(cur.deadline)+".";rm.querySelector("button").disabled=true;}
 catch(x){m.textContent="That did not send. Please try again in a moment.";}});
})();
</script>
__FOOTER__"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT.relative_to(ROOT))

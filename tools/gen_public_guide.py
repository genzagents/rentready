"""Can you search the landlord database? (docs/guides/can-you-search-landlord-database.html).

Search Console shows people typing "search prs database", "what is the landlord register" and "uk landlord database".
The answer nobody else spells out: on 15 December 2026 nothing on the database is public (gov.uk landlord guidance),
the Renters' Rights Act 2025 leaves what becomes public to later regulations (section 86), the draft 2026 regulations
make none, and the first thing a tenant will see is the pair of identifiers on adverts once section 82 starts (not
before 15 November 2027, MHCLG to TLIC). Until then the public registers that exist are each council's licence register
(Housing Act 2004 section 232), which the postcode check finds from docs/data/licensing.json.

Run this, then `python3 tools/schema.py`; tests/test_public_guide.py checks the page.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rentready import ROLLOUT  # noqa: E402

OUT = ROOT / "docs/guides/can-you-search-landlord-database.html"
URL = "https://genzagents.github.io/rentready/guides/can-you-search-landlord-database.html"
REVIEWED = "4 November 2026"
ACT = "https://www.legislation.gov.uk/ukpga/2025/26/section/"
GUIDE = "https://www.gov.uk/guidance/register-your-rental-property-service-guidance-for-landlords"
MHCLG = "https://www.propertytribes.com/mhclg-answer-questions-about-prs-database-t-127669645.html"
LONDON = "https://www.london.gov.uk/rogue-landlord-checker"

# (when, what is visible, who sees it, source label, source url)
TIMELINE = [
    ("Now, and from 15 December 2026", "Nothing on the database is public. Your landlord and property entries are seen "
     "by you, the database operator, councils and other enforcement bodies.", "Councils, trading standards, the "
     "Greater London Authority, mayoral combined authorities, the government", "gov.uk guidance; Act s.86(2)", GUIDE),
    ("Not before 15 November 2027", "Every written advert for a let must show the landlord's and the property's "
     "unique identifiers, and a home cannot be marketed without active entries. This is the first thing tenants will "
     "see.", "Anyone reading the advert", "Act s.82 and s.84; MHCLG to TLIC", ACT + "82"),
    ("Later, by new regulations", "Some details from landlord and property entries become public. Which fields, and "
     "how they are shown, is left to regulations not yet drafted.", "The public", "Act s.86(1)(a) and (d)", ACT + "86"),
    ("Later, by new regulations", "Banning orders, convictions and council fines for landlord offences, entered by "
     "councils and linked to your landlord entry, published no sooner than 21 days after you are told, so you can "
     "point out errors.", "The public", "Act s.83 and s.86(1)(b), (c)", ACT + "83"),
]


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def nice(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {MONTHS[int(m) - 1]} {y}"


def faq() -> list:
    return [
        ("Can you search the PRS database?",
         "Not yet. When the Register your rental property service opens on 15 December 2026, government guidance says "
         "landlord and property information will not be shared publicly. The Renters' Rights Act 2025 lets ministers "
         "choose later, by regulations, which details become public (section 86), and the draft 2026 regulations do "
         "not do that. Councils and enforcement bodies can see the database from the start."),
        ("How can a tenant check if a landlord is registered?",
         "There is no public look-up at launch. The first visible sign will be the landlord and property identifiers "
         "that every written advert must show once section 82 of the Act starts, which MHCLG says will not be before "
         "15 November 2027. Today a tenant can check the council's public register of licences if the home is in a "
         "licensing area or is a licensed HMO, and in London the Mayor's Rogue Landlord Checker."),
        ("Will tenants see my address on the landlord database?",
         "Nothing is public at launch, and no regulation yet says which fields will be. The Act allows ministers to "
         "publish some details later. Government guidance says the privacy notice will be updated before any change "
         "to how data is shared, and registered landlords will be told."),
        ("Will fines and banning orders be shown on the landlord database?",
         "Councils must add an entry for a landlord under a banning order, or convicted or fined by them for a banning "
         "order offence, once appeals are over (section 83). Ministers can make those entries public and link them to "
         "the landlord's own entry, but only from at least 21 days after the council tells the landlord, so errors can "
         "be corrected (section 86)."),
    ]


def build() -> str:
    d = json.loads((ROOT / "docs/data/licensing.json").read_text(encoding="utf-8"))
    n = d["counts"]
    q = faq()
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": a, "acceptedAnswer": {"@type": "Answer", "text": b}} for a, b in q]},
        ensure_ascii=False, indent=1)
    rows = "\n".join(f'<li class="card vis"><b>{html.escape(w)}</b><p>{html.escape(v)}</p>'
                     f'<p class="mut">Who sees it: {html.escape(who)}. Source: '
                     f'<a href="{html.escape(u)}" rel="noopener">{html.escape(s)}</a></p></li>' for w, v, who, s, u in TIMELINE)
    src = (ROOT / "docs/guides/landlord-database-first-year-cost.html").read_text(encoding="utf-8")
    header = src[src.index("<header"):src.index("</header>") + 9]
    footer = src[src.index("<footer"):]
    windows = json.dumps({r: w["deadline"] for r, w in ROLLOUT.items()}, separators=(",", ":"))
    t = PAGE
    for k, v in {"__URL__": URL, "__FAQ__": faq_ld, "__HEADER__": header, "__FOOTER__": footer,
                 "__REVIEWED__": REVIEWED, "__ROWS__": rows, "__WINDOWS__": windows, "__ACT__": ACT,
                 "__GUIDE__": GUIDE, "__MHCLG__": MHCLG, "__LONDON__": LONDON, "__EITHER__": str(n["either"]),
                 "__N__": str(n["councils"]), "__CHECKED__": nice(d["checked"]),
                 "__FAQ_HTML__": "\n".join(f"<h3>{html.escape(a)}</h3>\n<p>{html.escape(b)}</p>" for a, b in q)}.items():
        t = t.replace(k, v)
    return t


PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Can you search the landlord database? What tenants will see (2026)</title>
<meta name="description" content="No public search when the PRS database opens on 15 December 2026. What the Renters' Rights Act lets ministers publish later, and what tenants can check today.">
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
<h1>Can you search the landlord database?</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed __REVIEWED__, from the Renters' Rights Act 2025, the draft regulations and the official landlord guidance. <a href="#sources">Sources</a> below.</p>
<p><strong>No. When England's private rented sector database (the "Register your rental property" service) opens on 15 December 2026, nothing on it is public: landlord and property details are seen only by the landlord, councils and enforcement bodies.</strong> The Renters' Rights Act 2025 lets ministers decide later, by new regulations, which details the public can see. The draft 2026 regulations make none, so there is no public search, and no date for one.</p>

<div class="kpis">
<div><b>0</b><span>fields public when the service opens</span></div>
<div><b>15 Nov 2027</b><span>earliest date adverts must show the identifiers</span></div>
<div><b>21 days</b><span>minimum notice before a fine or ban is published</span></div>
<div><b>__EITHER__</b><span>councils with a public licence register for private lets</span></div>
</div>

<h2>What becomes visible, and when</h2>
<ol class="vis-list">
__ROWS__
</ol>
<p>The Act names who must have access from the start (<a href="__ACT__86">section 86(2)</a>): councils, local trading standards, the lead enforcement authority, mayoral combined authorities and the Greater London Authority. Councils can also verify and correct entries (draft regulation 13). The public is not on that list; public access exists only once ministers make regulations under <a href="__ACT__86">section 86(1)</a>.</p>

<h2>Landlords: what this means for you</h2>
<ul>
<li><strong>Register on time anyway.</strong> Not being public does not mean not checked: councils see every entry and every gap from the first day, and can fine you for a missing entry. See <a href="landlord-database-penalties.html">the penalties</a> and <a href="landlord-database-deadline-by-region.html">your region's deadline</a>.</li>
<li><strong>Write each entry as if it may be read.</strong> Which fields become public is not decided. The official guidance says the privacy notice will be updated before any change to how data is shared, and registered landlords will be told. The service asks for a correspondence address in England or Wales for each property; choose one you are content to use for tenant and council letters.</li>
<li><strong>Adverts will carry your numbers.</strong> Once section 82 starts (MHCLG says not before the rollout ends on 15 November 2027), every written advert must show your landlord identifier and the property's identifier, and you cannot market a home without active entries. Keep both numbers with your letting paperwork.</li>
<li><strong>Fines and bans may become public.</strong> Councils must enter banning orders and the offences and fines that lead to them (<a href="__ACT__83">section 83</a>). If those are published, you get at least 21 days' notice first to point out mistakes.</li>
</ul>

<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="lk-h">
<h2 id="lk-h" style="margin-top:0">Tenants: what you can check today</h2>
<p>There is no public look-up on the database yet. Two public registers exist now: every council must keep a register of the licences it grants that anyone can inspect (<a href="https://www.legislation.gov.uk/ukpga/2004/34/section/232">Housing Act 2004, section 232</a>), and London has the Mayor's <a href="__LONDON__" rel="noopener">Rogue Landlord Checker</a>. Enter the property's postcode to see which apply.</p>
<form class="lookup" id="lk" onsubmit="return false">
<label>Property postcode <input class="dl-sel" id="pc" autocomplete="postal-code" placeholder="e.g. SE5 8QZ"></label>
<button type="submit" class="go">Check</button>
</form>
<div class="who-out" id="pub-out" aria-live="polite" style="display:none"></div>
<form class="remind wait dl-rem" id="rem" novalidate style="display:none"><p><strong>Landlord? Email me before my database deadline.</strong> Two reminders, nothing else. No account.</p>
<div class="remind-row"><label class="sr" for="rem-email">Email address</label><input type="email" id="rem-email" autocomplete="email" placeholder="you@example.com" required>
<button type="submit" class="go">Remind me</button></div>
<p class="mut remind-f">We keep only your email, your region and its deadline, never the postcode. <a href="../privacy.html#reminders">How to be removed</a>.</p><p class="remind-msg" id="rem-msg" role="status"></p></form>
<p class="mut" style="margin-bottom:0">Only the postcode goes to postcodes.io to find the council. Licensing schemes were read on each council's website on __CHECKED__ (<a href="selective-licensing-councils-england.html">the full list</a>). Every council licenses large HMOs, so a shared house of five or more people should be on its register wherever it is.</p>
</section>

<h2>Questions</h2>
__FAQ_HTML__
<h2 id="sources">Sources</h2>
<ul class="mut">
<li><a href="__GUIDE__">gov.uk: Register your rental property service, guidance for landlords</a> (29 October 2026): information "will not be shared publicly" now; some may be viewable later; privacy notice updated before changes</li>
<li>Renters' Rights Act 2025: <a href="__ACT__82">section 82</a> (marketing and adverts), <a href="__ACT__83">section 83</a> (banning orders, offences and fines), <a href="__ACT__84">section 84</a> (unique identifiers), <a href="__ACT__86">section 86</a> (access to the database), <a href="__ACT__87">section 87</a> (disclosure by the operator)</li>
<li><a href="https://www.legislation.gov.uk/ukdsi/2026/9780348286861">Draft Private Rented Sector Database Regulations 2026</a> (no provision on public access; regulation 13 on verification)</li>
<li><a href="__MHCLG__" rel="noopener">MHCLG's answers to The Lettings Industry Council, on Property Tribes, 28 October 2026</a>: the advertising rules start no earlier than the end of the rollout</li>
<li><a href="https://www.legislation.gov.uk/ukpga/2004/34/section/232">Housing Act 2004, section 232</a> (public register of licences); <a href="__LONDON__" rel="noopener">Mayor of London: Rogue Landlord Checker</a></li>
<li><a href="landlord-database-regulations-status.html">Where the regulations are in Parliament</a></li>
</ul>
<p class="mut">Not legal advice. What becomes public depends on regulations not yet made; we will update this page when they are laid. Last checked __REVIEWED__.</p>
<script src="../remind.js"></script>
<script>
(function(){
var W=__WINDOWS__,RM=window.rentreadyRemind,L=null,cur=null;
var MON=["January","February","March","April","May","June","July","August","September","October","November","December"];
function $(i){return document.getElementById(i);}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function dd(s){var p=String(s||"").split("-");return p.length===3?(+p[2])+" "+MON[+p[1]-1]+" "+p[0]:"";}
function data(){return L||(L=fetch("../data/licensing.json").then(function(r){return r.ok?r.json():null;}).catch(function(){return null;}));}
async function go(){
 var pc=$("pc").value.trim(),o=$("pub-out");if(!pc)return;
 o.style.display="";o.className="who-out";o.innerHTML="<p>Looking up "+esc(pc)+"...</p>";
 var r=null;try{var x=await fetch("https://api.postcodes.io/postcodes/"+encodeURIComponent(pc));r=x.ok?(await x.json()).result:null;}catch(e){}
 if(!r){o.innerHTML="<b>Postcode not found</b><p>Check it and try again.</p>";$("rem").style.display="none";return;}
 if(r.country!=="England"){o.innerHTML="<b>"+esc(r.country)+" is not covered</b><p>The landlord database is for England only.</p>";$("rem").style.display="none";return;}
 var D=await data(),c=D&&D.councils[r.admin_district],name=String(r.admin_district).replace(/, (City|County) of$/,"");
 var dl=W[r.region],live=c?["selective","additional"].filter(function(k){return c[k].status==="in force"||c[k].status==="designated";}):[];
 var li=[];
 live.forEach(function(k){var s=c[k];li.push("<li><strong>"+esc(name)+"'s licence register</strong>: "+(k==="selective"?"selective licensing":"additional licensing for shared houses")+(s.area?", "+esc(String(s.area).replace(/^parts:\\s*/i,"in parts: ")):"")+(s.status==="designated"?", starts "+dd(s.starts):"")+". Ask the council to inspect the register, or see <a rel=\\"noopener\\" href"+"=\\""+esc(s.source)+"\\">its licensing page</a>.</li>");});
 if(!live.length)li.push("<li><strong>"+esc(name)+"</strong> has no selective or additional licensing that we found, so only large shared houses (HMOs) appear on its licence register.</li>");
 if(r.region==="London")li.push("<li><strong>The Mayor's <a rel=\\"noopener\\" href"+"=\\"__LONDON__\\">Rogue Landlord Checker</a></strong>: landlords and agents prosecuted or fined by participating London boroughs.</li>");
 li.push("<li><strong>The landlord database</strong>: no public look-up."+(dl?" Landlords in "+esc(r.region)+" must be registered by <strong>"+dd(dl)+"</strong>.":"")+"</li>");
 o.className="who-out "+(live.length?"who-later":"who-yes");
 o.innerHTML="<b>What you can check for "+esc(r.postcode)+"</b><ul>"+li.join("")+"</ul>";
 cur=dl?{region:r.region,deadline:dl}:null;$("rem").style.display=cur?"":"none";}
$("lk").addEventListener("submit",go);
var rm=$("rem"),m=$("rem-msg");
rm.addEventListener("submit",async function(ev){ev.preventDefault();
 var d=RM&&cur&&RM.calendar($("rem-email").value,[cur.region],cur.deadline);
 if(!d){m.textContent="Please enter a valid email address.";return;}
 d[RM.FIELDS.source]="public search guide";
 m.textContent="Sending...";try{await RM.send(d);m.textContent="Done. We will email you before "+dd(cur.deadline)+".";rm.querySelector("button").disabled=true;}
 catch(x){m.textContent="That did not send. Please try again in a moment.";}});
})();
</script>
__FOOTER__"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT.relative_to(ROOT))

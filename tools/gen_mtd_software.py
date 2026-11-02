"""Making Tax Digital software for landlords (docs/guides/making-tax-digital-software-for-landlords.html).

HMRC recognises 165 products for Making Tax Digital for Income Tax, but its finder shows them in random order and
does not say which ones can do the whole job for a landlord: quarterly updates for UK property AND the 2026-27 tax
return with the landlord's other income (wages, pensions, dividends, a property sale). This page takes HMRC's own
feature data (tools/data/mtd_software.json, from tools/fetch_mtd_software.py) and filters it in the browser.
The headline counts are computed here and the page's filter, match(), is tested under node against them.

Run `python3 tools/fetch_mtd_software.py` (about 3 minutes), then this, then `python3 tools/schema.py`;
tests/test_mtd_software.py checks the page.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tools/data/mtd_software.json"
OUT = ROOT / "docs/guides/making-tax-digital-software-for-landlords.html"
URL = "https://genzagents.github.io/rentready/guides/making-tax-digital-software-for-landlords.html"

# HMRC feature names kept on the page, with a short code each. Status: R ready now, D in development, N not included.
FEATURES = [
    ("free", "Free version"), ("records", "Software that creates digital records"),
    ("bridge", "Bridging software that connects to records"), ("std", "Standard update period (6 April to 5 April)"),
    ("cal", "Calendar update period (1 April to 31 March)"), ("vat", "Making Tax Digital for VAT"),
    ("uk", "UK property"), ("foreign", "Foreign property"), ("se", "Sole trader"),
    ("paye", "Employment (PAYE)"), ("statepen", "State Pension income"), ("pen", "Private pension incomes"),
    ("int", "UK interest"), ("div", "UK dividends"), ("cgt", "Capital Gains"), ("partner", "Partner income from a partnership"),
    ("hicbc", "High Income Child Benefit Charge"), ("loan", "Student Loan"), ("assist", "HMRC Assist (Submission Feedback)"),
]
ACCESS = ["Blindness or impaired vision", "Deafness or impaired hearing", "Motor or physical difficulties", "Cognitive impairments"]
CODE = {"Ready now": "R", "In development": "D", "Not included": "N"}
RETURN_ITEMS = [("paye", "wages (PAYE)"), ("statepen", "State Pension"), ("pen", "a private pension"),
                ("int", "UK interest"), ("div", "UK dividends"), ("cgt", "a property sale (Capital Gains)")]

QUARTERS = ["2026-11-07", "2027-02-07", "2027-05-07", "2027-08-07", "2027-11-07", "2028-02-07", "2028-05-07"]

LOGIC = r"""
// p: {f:{code:"R"|"D"|"N"}, ret:bool}. o: filters. Returns true when the product fits.
function ok(s,soon){return s==="R"||(soon&&s==="D");}
function match(p,o){
  var f=p.f,soon=!!o.soon;
  if(!ok(f.uk,false))return false;
  if(o.foreign&&!ok(f.foreign,soon))return false;
  if(o.se&&!ok(f.se,soon))return false;
  if(o.ret&&!p.ret)return false;
  if(o.free&&f.free!=="R")return false;
  if(o.how==="records"&&f.records!=="R")return false;
  if(o.how==="bridge"&&f.bridge!=="R")return false;
  if(o.cal&&f.cal!=="R")return false;
  for(var i=0;i<(o.other||[]).length;i++)if(!ok(f[o.other[i]],soon))return false;
  if(o.mac&&p.mac===false)return false;
  if(o.welsh&&!p.welsh)return false;
  if(o.access&&!p.access)return false;
  return true;
}
"""


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def compact(p: dict) -> dict:
    feats = p["features"]
    f = {code: CODE.get(feats.get(name, ""), "N") for code, name in FEATURES}
    out = {"n": p["name"], "u": p["website"] or "", "f": f, "ret": "Tax return" in p.get("submission", [])}
    comp = p.get("Compatible with") or []
    out["web"] = p.get("Software type") == "Web browser"
    out["mac"] = (out["web"] or any("mac" in c.lower() for c in comp)) if comp or out["web"] else None
    out["welsh"] = "Welsh" in (p.get("Language") or "")
    out["access"] = any(feats.get(a) == "Ready now" for a in ACCESS)
    return out


def stats(products: list) -> dict:
    uk = [p for p in products if p["f"]["uk"] == "R"]
    full = [p for p in uk if p["ret"]]
    free_full = [p for p in full if p["f"]["free"] == "R"]
    return {
        "total": len(products), "uk": len(uk), "uk_no_return": len(uk) - len(full), "full": len(full),
        "free_full": len(free_full),
        "full_paye_now": sum(p["f"]["paye"] == "R" for p in full),
        "full_cgt_now": sum(p["f"]["cgt"] == "R" for p in full),
        "full_cgt_never": sum(p["f"]["cgt"] == "N" for p in full),
        "free_full_paye_cgt": sum(p["f"]["paye"] == "R" and p["f"]["cgt"] == "R" for p in free_full),
        "bridge_full": sum(p["f"]["bridge"] == "R" for p in full),
        "free_names": sorted((p["n"] for p in free_full), key=str.lower),
    }


def nice(d: str) -> str:
    y, m, day = d.split("-")
    return f"{int(day)} {['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'][int(m) - 1]} {y}"


def faq(s: dict) -> list:
    return [
        ("Is there free Making Tax Digital software for landlords?",
         f"Yes. Of the {s['total']} products HMRC recognises, {s['free_full']} have a free version and can send UK "
         "property quarterly updates and the tax return. Check what the free version includes on the company's site: "
         "some limit the number of properties or transactions, and HMRC does not vet prices."),
        ("Can I keep using my spreadsheet for Making Tax Digital?",
         f"Yes, with bridging software, which reads your spreadsheet and sends the figures to HMRC. {s['bridge_full']} "
         "products that handle UK property and the tax return offer bridging. The spreadsheet itself must be your "
         "digital record, with each rent and expense line, and figures must move to the software digitally, not retyped."),
        ("Does my MTD software have to file my tax return?",
         "Yes. From the 2026-27 tax year, due 31 January 2028, anyone in Making Tax Digital files the tax return "
         f"through compatible software, not HMRC's online form. {s['uk_no_return']} of the {s['uk']} products that "
         "send UK property updates do not list the tax return, so with one of them you would need a second product next January."),
        ("What if I have wages, a pension or sold a property as well as rent?",
         "Your MTD software files your whole tax return, so it must handle every other income on it. Tick those "
         "items in the finder. Products marked in development have promised HMRC they will be ready for the 2026-27 return."),
    ]


PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MTD software for landlords: which of HMRC's __TOTAL__ do the whole job</title>
<meta name="description" content="Filter all __TOTAL__ HMRC-recognised MTD products to the ones that do UK property and the tax return: free versions, spreadsheets, wages, pensions, sales.">
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
<h1>Making Tax Digital software for landlords: which of HMRC's __TOTAL__ products do the whole job</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed __FETCHED__ from HMRC's own software data. <a href="#sources">Sources</a> below.</p>
<p><strong>HMRC recognises __TOTAL__ products for Making Tax Digital for Income Tax and lists them in random order. __UK__ can send quarterly updates for UK property, but only __FULL__ of those can also file the tax return, which every landlord in MTD must send from software from January 2028. __FREE_FULL__ of them have a free version.</strong> Use the finder below to narrow HMRC's own feature data to products that fit your lets and the rest of your tax return.</p>

<div class="sw-stats">
<div><b>__UK__</b><span>of __TOTAL__ products send UK property quarterly updates</span></div>
<div><b>__UK_NO_RETURN__</b><span>of those cannot file the tax return, so you would need a second product</span></div>
<div><b>__FREE_FULL__</b><span>do updates and the return and have a free version</span></div>
<div><b>__CGT_NEVER__</b><span>of the __FULL__ full products will not report Capital Gains, for example a property sale</span></div>
</div>

<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="sw-h">
<h2 id="sw-h" style="margin-top:0">Find software that fits your lets</h2>
<form class="sw-f" id="sw" onsubmit="return false">
<fieldset><legend>Your income from MTD</legend>
<label><input type="checkbox" checked disabled> UK property (always on)</label>
<label><input type="checkbox" id="o-foreign"> Overseas property too</label>
<label><input type="checkbox" id="o-se"> Self-employment too</label>
</fieldset>
<fieldset><legend>What you need</legend>
<label><input type="checkbox" id="o-ret" checked> Files the tax return as well</label>
<label><input type="checkbox" id="o-free"> Has a free version</label>
<label><input type="checkbox" id="o-cal"> Calendar quarters (1 April to 31 March)</label>
</fieldset>
<fieldset><legend>Your records</legend>
<label><input type="radio" name="how" value="any" checked> Either</label>
<label><input type="radio" name="how" value="records"> Keep records in the software</label>
<label><input type="radio" name="how" value="bridge"> Keep my spreadsheet (bridging)</label>
</fieldset>
<fieldset><legend>Also on your tax return</legend>
__OTHER__
</fieldset>
<fieldset><legend>Other</legend>
<label><input type="checkbox" id="o-soon"> Count features HMRC lists as in development</label>
<label><input type="checkbox" id="o-mac"> Works on a Mac</label>
<label><input type="checkbox" id="o-welsh"> In Welsh</label>
<label><input type="checkbox" id="o-access"> Accessibility features</label>
</fieldset>
</form>
<div class="sw-count" aria-live="polite"><b id="sw-n"></b><span class="mut" id="sw-s"></span></div>
<ul class="sw-list" id="sw-list"></ul>
<p class="sw-more"><button type="button" class="ghost" id="sw-more" hidden>Show all</button></p>
<form class="remind wait dl-rem" id="rem" novalidate><p><strong>Email me two weeks before the next quarterly update.</strong> One email, nothing else. No account.</p>
<div class="remind-row"><label class="sr" for="rem-email">Email address</label><input type="email" id="rem-email" autocomplete="email" placeholder="you@example.com" required>
<button type="submit" class="go">Remind me</button></div>
<p class="mut remind-f">We keep only your email and the deadline date. <a href="../privacy.html#reminders">How to be removed</a>.</p><p class="remind-msg" id="rem-msg" role="status"></p></form>
</section>

<h2>How to choose, in four checks</h2>
<ol>
<li><strong>UK property and the tax return.</strong> Quarterly updates are only half the job. For 2026-27 your software also sends the final declaration (the tax return) by 31 January 2028. A product without it means switching or paying twice next winter.</li>
<li><strong>Everything else on your return.</strong> MTD software files your whole return, so it must handle your wages, pensions, dividends and any property you sold. "In development" means the company has promised HMRC it will be ready for the 2026-27 return; it is not there yet.</li>
<li><strong>Records or spreadsheet.</strong> If you already keep a good spreadsheet, bridging software sends its figures to HMRC. Otherwise pick software that keeps the records, ideally with a bank feed.</li>
<li><strong>The real price.</strong> HMRC only says whether a free version exists. Free versions often cap properties or transactions, so read the company's pricing page before you start, and check the product is still listed on HMRC's finder.</li>
</ol>
<p>Then <a href="https://www.gov.uk/guidance/sign-up-your-business-for-making-tax-digital-for-income-tax">sign up for MTD</a> if HMRC has not done it for you, authorise the software in your HMRC account, and send the update due by 7 November 2026 (it covers 6 April to 5 October). Need the figures? <a href="making-tax-digital-quarterly-update-landlords.html">Work out your quarterly update from a bank statement</a>.</p>

<h2>The free products that do updates and the tax return</h2>
<p>__FREE_LIST__. Of these, __FREE_PAYE_CGT__ already handle both wages and Capital Gains on the return. Free versions vary, so check each company's limits.</p>

<h2>The other compulsory deadline for landlords</h2>
<p>England's landlord database opens on 15 December 2026, with a separate deadline for each region, from 14 March 2027 in the West Midlands. Every property needs a valid gas safety record, EICR and EPC uploaded. <a href="https://genzagents.github.io/rentready/">Check your properties in two minutes</a>, or see <a href="landlord-deadlines-calendar.html">every landlord deadline to 2028</a>.</p>

<h2>Questions</h2>
__FAQ_HTML__
<h2 id="sources">Sources</h2>
<ul class="mut">
<li><a href="https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software/">HMRC: find software that works with Making Tax Digital for Income Tax</a> (all __TOTAL__ products and their feature pages, fetched __FETCHED__; Open Government Licence v3.0)</li>
<li><a href="https://www.gov.uk/guidance/choose-the-right-software-for-making-tax-digital-for-income-tax">gov.uk: choose the right software for Making Tax Digital for Income Tax (updated 13 July 2026)</a></li>
<li><a href="https://www.gov.uk/guidance/use-making-tax-digital-for-income-tax/send-quarterly-updates">gov.uk: send quarterly updates</a></li>
</ul>
<p class="mut">HMRC does not recommend any product and neither do we; nobody paid to be listed and the order is alphabetical. rentready is not MTD software. Not tax advice. Data refreshed from HMRC's finder; last fetched __FETCHED__.</p>
<script src="../remind.js"></script>
<script id="sw-data" type="application/json">__DATA__</script>
<script id="sw-logic">__LOGIC__</script>
<script>
(function(){
var P=JSON.parse(document.getElementById("sw-data").textContent),Q=__QUARTERS__,RM=window.rentreadyRemind,all=false;
var OTHER=__OTHER_CODES__,LABEL={paye:"Wages",statepen:"State Pension",pen:"Pension",int:"Interest",div:"Dividends",cgt:"Capital Gains"};
function $(i){return document.getElementById(i);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function dd(d){return new Date(d+"T12:00:00Z").toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"});}
function opts(){return {foreign:$("o-foreign").checked,se:$("o-se").checked,ret:$("o-ret").checked,free:$("o-free").checked,cal:$("o-cal").checked,
 how:document.querySelector("input[name=how]:checked").value,other:OTHER.filter(function(c){return $("o-"+c).checked;}),
 soon:$("o-soon").checked,mac:$("o-mac").checked,welsh:$("o-welsh").checked,access:$("o-access").checked};}
function tag(t,c){return '<span class="'+(c||"")+'">'+esc(t)+"</span>";}
function card(p,o){var f=p.f,t=[];
 t.push(f.free==="R"?tag("Free version","y"):tag("Paid"));
 t.push(p.ret?tag("Tax return","y"):tag("Updates only"));
 if(f.bridge==="R")t.push(tag("Spreadsheet bridging","y"));
 if(f.foreign==="R")t.push(tag("Overseas property"));
 OTHER.forEach(function(c){if(o.other.indexOf(c)>=0||f[c]!=="R"){if(f[c]==="R")t.push(tag(LABEL[c],"y"));else if(f[c]==="D")t.push(tag(LABEL[c]+" soon","d"));}});
 var href=p.u?esc(p.u):"https://www.tax.service.gov.uk/find-making-tax-digital-income-tax-software/";
 return '<li><a class="sw-n" href='+JSON.stringify(href)+' rel="nofollow noopener" target="_blank">'+esc(p.n)+'</a><div class="sw-t">'+t.join("")+"</div></li>";}
function go(){var o=opts(),hit=P.filter(function(p){return match(p,o);});
 $("sw-n").textContent=hit.length+(hit.length===1?" product fits":" products fit");
 $("sw-s").textContent="of "+P.length+" recognised by HMRC, alphabetical";
 var show=all?hit:hit.slice(0,24);
 $("sw-list").innerHTML=show.map(function(p){return card(p,o);}).join("")||'<li>None fit all of these. Try counting features in development, or untick one.</li>';
 $("sw-more").hidden=hit.length<=24||all;$("sw-more").textContent="Show all "+hit.length;}
$("sw").addEventListener("change",go);$("sw-more").addEventListener("click",function(){all=true;go();});go();
function nextDue(){var today=new Date().toISOString().slice(0,10);for(var i=0;i<Q.length;i++)if(Q[i]>=today)return Q[i];return null;}
var r=$("rem"),m=$("rem-msg");
r.addEventListener("submit",async function(ev){ev.preventDefault();var due=nextDue();
var d=RM&&due&&RM.mtd($("rem-email").value,due,"software finder");
if(!d){m.textContent="Please enter a valid email address.";return;}
m.textContent="Sending...";try{await RM.send(d);m.textContent="Done. We will email you two weeks before "+dd(due)+".";r.querySelector("button").disabled=true;}
catch(x){m.textContent="That did not send. Please try again in a moment.";}});
})();
</script>
__FOOTER__"""


def products() -> list:
    return sorted((compact(p) for p in load()["products"]), key=lambda p: re.sub(r"^\W+", "", p["n"]).lower())


def build() -> str:
    d = load()
    ps = products()
    s = stats(ps)
    fetched = nice(d["fetched"])
    src = (ROOT / "docs/guides/landlord-database-first-year-cost.html").read_text(encoding="utf-8")
    header = src[src.index("<header"):src.index("</header>") + 9]
    footer = src[src.index("<footer"):]
    items = faq(s)
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in items]},
        ensure_ascii=False, indent=1)
    faq_html = "\n".join(f"<h3>{html.escape(q)}</h3>\n<p>{html.escape(a)}</p>" for q, a in items)
    other = "\n".join(f'<label><input type="checkbox" id="o-{c}"> {html.escape(label[0].upper() + label[1:])}</label>'
                      for c, label in RETURN_ITEMS)
    names = s["free_names"]
    free_list = ", ".join(html.escape(n) for n in names[:-1]) + " and " + html.escape(names[-1]) if len(names) > 1 else "".join(names)
    data = json.dumps(ps, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    t = PAGE
    for k, v in {"__URL__": URL, "__FAQ__": faq_ld, "__HEADER__": header, "__FOOTER__": footer, "__FETCHED__": fetched,
                 "__TOTAL__": str(s["total"]), "__UK__": str(s["uk"]), "__UK_NO_RETURN__": str(s["uk_no_return"]),
                 "__FULL__": str(s["full"]), "__FREE_FULL__": str(s["free_full"]), "__CGT_NEVER__": str(s["full_cgt_never"]),
                 "__FREE_PAYE_CGT__": str(s["free_full_paye_cgt"]), "__FREE_LIST__": free_list, "__OTHER__": other,
                 "__FAQ_HTML__": faq_html, "__DATA__": data, "__LOGIC__": LOGIC,
                 "__QUARTERS__": json.dumps(QUARTERS), "__OTHER_CODES__": json.dumps([c for c, _ in RETURN_ITEMS])}.items():
        t = t.replace(k, v)
    return t


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT.relative_to(ROOT))

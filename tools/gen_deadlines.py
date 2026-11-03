"""Every landlord deadline, November 2026 to May 2028: the landlord database by region and Making Tax Digital for
Income Tax by income, on one page (docs/guides/landlord-deadlines-calendar.html).

The timeline table, the in-page picker and the calendar file are all built from EVENTS below, so they cannot disagree.
Sources (checked 1 Nov 2026): gov.uk "Find out if and when you need to use Making Tax Digital for Income Tax"
(thresholds), "Send quarterly updates" (deadlines, no penalty points for late updates in 2026-27), "Work out your
qualifying income" (gross, your share of joint lets); region windows from rentready's deadline data (official
guidance, housinghub.campaign.gov.uk).

Run `python3 tools/gen_deadlines.py`, then `python3 tools/schema.py`; tests/test_deadlines.py checks the page.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/guides/landlord-deadlines-calendar.html"
URL = "https://genzagents.github.io/rentready/guides/landlord-deadlines-calendar.html"
REVIEWED = "1 November 2026"

# (region, page, requirement starts, deadline): the same windows as landlord-database-deadline-by-region.html
REGIONS = [
    ("West Midlands", "west-midlands.html", "2026-12-15", "2027-03-14"),
    ("East of England", "east-of-england.html", "2027-01-15", "2027-04-14"),
    ("East Midlands", "east-midlands.html", "2027-02-15", "2027-05-14"),
    ("South East", "south-east.html", "2027-03-15", "2027-06-14"),
    ("Yorkshire and The Humber", "yorkshire-and-the-humber.html", "2027-04-15", "2027-07-14"),
    ("North West", "north-west.html", "2027-05-15", "2027-08-14"),
    ("North East", "north-east.html", "2027-06-15", "2027-09-14"),
    ("London", "london.html", "2027-07-15", "2027-10-14"),
    ("South West", "south-west.html", "2027-08-15", "2027-11-14"),
]

# who: "all"; "r:<region>"; "m50" (MTD since April 2026); "m30" (MTD from April 2027, and the m50 group too);
# "m20" (from April 2028)
EVENTS = [
    ("2026-11-04", "Lords vote on the landlord database regulations (listed)", "all",
     'The approval motion is on the Lords business paper. <a href="landlord-database-regulations-status.html">Live status</a>.'),
    ("2026-11-07", "MTD quarterly update: 6 April to 5 October 2026", "m50",
     "Second update of the first MTD year. It covers the year so far, so it also makes up a missed August update."),
    ("2026-12-15", "Landlord database opens for every landlord in England", "all",
     "You can register any property from this day, whatever your region's dates."),
    ("2027-01-31", "Self Assessment for 2025-26: return and tax due", "all",
     "The property and self-employment income on this return decides whether MTD starts for you in April 2027 (over £30,000)."),
    ("2027-02-07", "MTD quarterly update: 6 April 2026 to 5 January 2027", "m50", ""),
    ("2027-04-06", "MTD starts if your 2025-26 qualifying income was over £30,000", "m30",
     "From this day you keep digital records and send quarterly updates from software."),
    ("2027-05-07", "MTD quarterly update: the whole 2026-27 year", "m50", ""),
    ("2027-08-07", "MTD quarterly update: 6 April to 5 July 2027", "m30",
     "From 2027-28 a late update earns a penalty point; 4 points means a £200 penalty."),
    ("2027-11-07", "MTD quarterly update: 6 April to 5 October 2027", "m30", ""),
    ("2028-01-31", "Tax return for 2026-27 due", "all",
     "If you used MTD in 2026-27 you file it from your MTD software. Its income decides the April 2028 group (over £20,000)."),
    ("2028-02-07", "MTD quarterly update: 6 April 2027 to 5 January 2028", "m30", ""),
    ("2028-04-06", "MTD starts if your 2026-27 qualifying income was over £20,000", "m20",
     "Your first update, for 6 April to 5 July 2028, is due on 7 August 2028."),
    ("2028-05-07", "MTD quarterly update: the whole 2027-28 year", "m30", ""),
]
for name, page, start, end in REGIONS:
    EVENTS.append((start, f"{name}: landlord database requirement starts", "r:" + name,
                   f'Properties in {name} must be registered within three months. <a href="{page}">{name} guide</a>.'))
    EVENTS.append((end, f"{name}: deadline to register every property", "r:" + name,
                   "Each property needs a valid gas safety record, EICR and EPC uploaded when you register."))
EVENTS.sort(key=lambda e: (e[0], e[1]))

BANDS = [("over50", "Over £50,000"), ("30to50", "£30,000 to £50,000"), ("20to30", "£20,000 to £30,000"),
         ("under20", "Under £20,000"), ("unsure", "Not sure")]

WHO_LABEL = {"all": "Every landlord", "m50": "MTD since April 2026 (over £50,000)",
             "m30": "MTD from April 2027 or earlier (over £30,000)", "m20": "MTD from April 2028 (over £20,000)"}


def nice(d: str) -> str:
    x = date.fromisoformat(d)
    return f"{x.day} {x.strftime('%B %Y')}"


def who_label(w: str) -> str:
    return "Properties in " + w[2:] if w.startswith("r:") else WHO_LABEL[w]


def table() -> str:
    rows = []
    for d, title, who, note in EVENTS:
        cls = ' class="tl-db"' if who.startswith("r:") or "database" in title else ""
        rows.append(f'<tr{cls}><td class="tl-d">{nice(d)}</td><td><strong>{html.escape(title)}</strong>'
                    + (f'<br><span class="mut">{note}</span>' if note else "")
                    + f'</td><td class="tl-w">{html.escape(who_label(who))}</td></tr>')
    return "\n".join(rows)


def js_events() -> str:
    return json.dumps([{"d": d, "t": t, "w": w, "n": re.sub(r"<[^>]+>", "", n)} for d, t, w, n in EVENTS],
                      ensure_ascii=False, separators=(",", ":"))


FAQ = [
    ("What are the landlord deadlines for 2026 and 2027?",
     "Two systems. The landlord database opens on 15 December 2026 and each region has its own deadline, from 14 March "
     "2027 in the West Midlands to 14 November 2027 in the South West. Making Tax Digital for Income Tax already applies "
     "to landlords whose property and self-employment income was over £50,000 (quarterly updates due 7 August, "
     "7 November, 7 February and 7 May), and starts on 6 April 2027 for those over £30,000."),
    ("Does Making Tax Digital apply to landlords?",
     "Yes. Qualifying income is your gross property income plus any self-employment income, before expenses. For a "
     "jointly owned property only your share counts. Over £50,000 on your 2024-25 return: from 6 April 2026. Over "
     "£30,000 on your 2025-26 return: from 6 April 2027. Over £20,000 on your 2026-27 return: from 6 April 2028."),
    ("Is there a penalty for a late MTD quarterly update?",
     "Not in 2026-27: HMRC will not give penalty points for late quarterly updates in that year, though you must send "
     "them before you can file the tax return. From 2027-28 each late update earns a point and 4 points means a £200 "
     "penalty."),
]


def faq_ld() -> str:
    return json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
        ensure_ascii=False, indent=1)


def region_boxes() -> str:
    return "".join(f'<label class="dl-box"><input type="checkbox" name="r" value="{html.escape(n)}"> {html.escape(n)}</label>'
                   for n, _, _, _ in REGIONS)


def band_opts() -> str:
    return "".join(f'<option value="{v}"{" selected" if v == "unsure" else ""}>{html.escape(l)}</option>'
                   for v, l in BANDS)


LOGIC = r"""
var EVENTS=__EVENTS__;
// Which events apply: every-landlord dates, the chosen regions' windows, and the MTD dates for the income band.
// over50 is in MTD now, so it gets the 2026-27 updates and every later one; 30to50 joins in April 2027.
var BAND_TAGS={over50:["m50","m30"],"30to50":["m30"],"20to30":["m20"],under20:[],unsure:["m50","m30","m20"]};
function pick(regions,band,today){
  var tags=BAND_TAGS[band]||BAND_TAGS.unsure;
  return EVENTS.filter(function(e){
    if(today&&e.d<today)return false;
    if(e.w==="all")return true;
    if(e.w.slice(0,2)==="r:")return regions.indexOf(e.w.slice(2))>=0;
    return tags.indexOf(e.w)>=0;
  });
}
function ics(evs,stamp){
  function esc(s){return String(s).replace(/\\/g,"\\\\").replace(/;/g,"\\;").replace(/,/g,"\\,").replace(/\n/g,"\\n");}
  function next(d){var x=new Date(d+"T12:00:00Z");x.setUTCDate(x.getUTCDate()+1);return x.toISOString().slice(0,10).replace(/-/g,"");}
  var L=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//GenZAgents//rentready deadlines//EN","CALSCALE:GREGORIAN","X-WR-CALNAME:Landlord deadlines"];
  evs.forEach(function(e,i){var d=e.d.replace(/-/g,"");
    L.push("BEGIN:VEVENT","UID:rr-dl-"+d+"-"+i+"@genzagents.github.io","DTSTAMP:"+stamp,"DTSTART;VALUE=DATE:"+d,"DTEND;VALUE=DATE:"+next(e.d),
      "SUMMARY:"+esc(e.t),"DESCRIPTION:"+esc((e.n?e.n+" ":"")+"https://genzagents.github.io/rentready/guides/landlord-deadlines-calendar.html"),
      "BEGIN:VALARM","ACTION:DISPLAY","DESCRIPTION:"+esc(e.t),"TRIGGER:-P14D","END:VALARM","END:VEVENT");});
  L.push("END:VCALENDAR");return L.join("\r\n")+"\r\n";
}
"""

PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Landlord deadlines 2026 to 2028: database and Making Tax Digital</title>
<meta name="description" content="Every landlord deadline to May 2028: your region&#x27;s landlord database dates and your Making Tax Digital quarterly updates, in one calendar file.">
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
<p class="crumbs"><a href="https://genzagents.github.io/rentready/">rentready</a> / <a href="https://genzagents.github.io/rentready/guides/">Landlord database guides</a></p>
<h1>Every landlord deadline, November 2026 to May 2028</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed __REVIEWED__. <a href="#sources">Sources</a> below.</p>
<p><strong>Two compulsory systems now run on separate clocks for the same landlords: the landlord database, where the deadline depends on the region each property is in (14 March 2027 in the West Midlands to 14 November 2027 in the South West), and Making Tax Digital for Income Tax, where the start date depends on your income (6 April 2026 over £50,000, 6 April 2027 over £30,000, 6 April 2028 over £20,000).</strong> Nobody else puts both on one calendar. Pick your regions and income below to get only your dates, as a calendar file with a reminder 14 days before each.</p>

<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="pick-h">
<h2 id="pick-h" style="margin-top:0">Your dates</h2>
<form class="firm-form" id="pick" onsubmit="return false" style="grid-template-columns:1fr">
<fieldset><legend>Where are your rental properties? <small class="mut">Tick every region you let in</small></legend>
<div class="dl-boxes">__BOXES__</div></fieldset>
<label>Property plus self-employment income on your last tax return, before expenses <small class="mut" style="font-weight:400">your share for joint lets; wages, pensions and dividends do not count</small>
<select class="dl-sel" id="band">__BANDS__</select></label>
</form>
<div class="summary" id="sum" aria-live="polite">
<div class="stat"><b id="s-n">0</b><span>Dates from today</span></div>
<div class="stat"><b id="s-next">-</b><span>Next one</span></div>
<div class="stat"><b id="s-db">-</b><span>Your last database deadline</span></div>
</div>
<p style="margin:0"><button type="button" class="go" id="dl">Download calendar (.ics)</button></p>
<p class="calc-note mut" style="margin:8px 0 0">Works with Google, Apple and Outlook calendars. Nothing leaves your browser.</p>
<ol class="dl-list" id="list"></ol>
<form class="remind wait dl-rem" id="rem" novalidate><p><strong>Email me before my database deadline.</strong> One email when your region opens and one 30 days before your deadline. No account.</p>
<div class="remind-row"><label class="sr" for="rem-email">Email address</label><input type="email" id="rem-email" autocomplete="email" placeholder="you@example.com" required>
<button type="submit" class="go">Remind me</button></div>
<p class="mut remind-f">We keep only your email, the regions you ticked and your deadline. <a href="../privacy.html#reminders">How to be removed</a>.</p><p class="remind-msg" id="rem-msg" role="status"></p></form>
</section>

<h2>All the dates</h2>
<p>Database dates are marked with a green edge. MTD quarterly updates use the standard periods; if you chose calendar periods (1 April to 31 March) the deadlines are the same days.</p>
<div class="wrap"><table class="tl"><thead><tr><th>Date</th><th>What</th><th>Who</th></tr></thead><tbody>
__TABLE__
</tbody></table></div>

<h2>How the two systems differ</h2>
<table><tr><th></th><th>Landlord database</th><th>Making Tax Digital</th></tr>
<tr><td>Decided by</td><td>The region each property is in</td><td>Your income from property and self-employment</td></tr>
<tr><td>Counted per</td><td>Property: one entry and one £65 fee each</td><td>Person: joint owners each count their share</td></tr>
<tr><td>What you do</td><td>Register once, upload gas, EICR and EPC, renew yearly</td><td>Digital records, four updates a year, a tax return from software</td></tr>
<tr><td>First year leniency</td><td>Not announced</td><td>No penalty points for late updates in 2026-27</td></tr></table>
<p>A landlord with £35,000 of rent from two flats in the East Midlands, for example, registers both by 14 May 2027 and starts MTD on 6 April 2027, with the first quarterly update due 7 August 2027. Joint owners are counted differently by the two systems: the database has one entry per property, with each joint landlord getting an identifier (<a href="which-properties-to-register.html">which properties to register</a>); MTD counts only your share of the rent.</p>
<p>The database rules still need Parliament's approval. The Lords vote is listed for 4 November 2026 and the Commons vote is not yet scheduled (<a href="landlord-database-regulations-status.html">live status</a>). The dates here follow the official guidance and will be updated if they move.</p>

<h2>Questions</h2>
__FAQ_HTML__
<h2>Related guides</h2>
<ul><li><a href="making-tax-digital-quarterly-update-landlords.html">Your MTD quarterly update from a bank statement</a></li><li><a href="hmrc-signed-me-up-making-tax-digital.html">HMRC signed me up for Making Tax Digital</a></li><li><a href="landlord-database-deadline-by-region.html">Deadlines by region</a></li><li><a href="landlord-database-first-year-cost.html">The true first-year cost</a></li><li><a href="what-you-need-to-register.html">What you need to register</a></li><li><a href="landlord-database-penalties.html">Penalties</a></li></ul>
<h2 id="sources">Sources</h2>
<ul class="mut">
<li><a href="https://www.gov.uk/guidance/find-out-if-and-when-you-need-to-use-making-tax-digital-for-income-tax">gov.uk: find out if and when you need to use Making Tax Digital for Income Tax (thresholds and start dates)</a></li>
<li><a href="https://www.gov.uk/guidance/work-out-your-qualifying-income-for-making-tax-digital-for-income-tax">gov.uk: work out your qualifying income (gross income; your share of a jointly owned property)</a></li>
<li><a href="https://www.gov.uk/guidance/use-making-tax-digital-for-income-tax/send-quarterly-updates">gov.uk: send quarterly updates (deadlines; no penalty points for late updates in 2026-27; 4 points means £200)</a></li>
<li><a href="https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/">Get ready to register: Register your rental property (official guidance, regional dates)</a></li>
<li><a href="https://www.legislation.gov.uk/ukdsi/2026/9780348286861">Draft Private Rented Sector Database Regulations 2026 (legislation.gov.uk; not yet made)</a></li>
</ul>
<p class="mut">Not legal or tax advice. Check gov.uk before relying on this. Last checked __REVIEWED__.</p>
<script src="../remind.js"></script>
<script id="dl-logic">__LOGIC__</script>
<script>
(function(){
var f=document.getElementById("pick"),RM=window.rentreadyRemind,last=[];
function dd(d){return new Date(d+"T12:00:00Z").toLocaleDateString("en-GB",{day:"numeric",month:"short",year:"numeric",timeZone:"UTC"});}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function regions(){return Array.prototype.map.call(f.querySelectorAll("input[name=r]:checked"),function(x){return x.value;});}
function dbLast(evs){var d=evs.filter(function(e){return e.w.slice(0,2)==="r:"&&/deadline/.test(e.t);});return d.length?d[d.length-1].d:"";}
function go(){var today=new Date().toISOString().slice(0,10);last=pick(regions(),document.getElementById("band").value,today);
document.getElementById("s-n").textContent=last.length;
document.getElementById("s-next").textContent=last.length?dd(last[0].d):"-";
var db=dbLast(last);document.getElementById("s-db").textContent=db?dd(db):"Tick a region";
document.getElementById("list").innerHTML=last.map(function(e){var isdb=e.w.slice(0,2)==="r:"||/database/.test(e.t);
return '<li class="'+(isdb?"db":"")+'"><b>'+dd(e.d)+'</b><span>'+esc(e.t)+'</span></li>';}).join("");}
f.addEventListener("change",go);go();
document.getElementById("dl").onclick=function(){var s=new Date().toISOString().replace(/[-:]/g,"").slice(0,15)+"Z";
var b=new Blob([ics(last,s)],{type:"text/calendar"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="landlord-deadlines.ics";document.body.appendChild(a);a.click();a.remove();};
var r=document.getElementById("rem"),m=document.getElementById("rem-msg");
r.addEventListener("submit",async function(ev){ev.preventDefault();
var d=RM&&RM.calendar(document.getElementById("rem-email").value,regions(),dbLast(last));
if(!d){m.textContent="Please enter a valid email address.";return;}
if(!regions().length){m.textContent="Tick at least one region first, so we know your deadline.";return;}
m.textContent="Sending...";try{await RM.send(d);m.textContent="Done. We will email you when your region opens and 30 days before your deadline.";r.querySelector("button").disabled=true;}
catch(x){m.textContent="That did not send. Please try again in a moment.";}});
})();
</script>
__FOOTER__"""


def build() -> str:
    src = (ROOT / "docs/guides/landlord-database-first-year-cost.html").read_text(encoding="utf-8")
    header = src[src.index("<header"):src.index("</header>") + 9]
    footer = src[src.index("<footer"):]
    faq_html = "\n".join(f"<h3>{html.escape(q)}</h3>\n<p>{html.escape(a)}</p>" for q, a in FAQ)
    t = PAGE
    for k, v in {"__URL__": URL, "__FAQ__": faq_ld(), "__HEADER__": header, "__REVIEWED__": REVIEWED,
                 "__BOXES__": region_boxes(), "__BANDS__": band_opts(), "__TABLE__": table(),
                 "__FAQ_HTML__": faq_html, "__LOGIC__": LOGIC.replace("__EVENTS__", js_events()),
                 "__FOOTER__": footer}.items():
        t = t.replace(k, v)
    return t


# The home page's "Coming up" strip: the next few dated events from EVENTS, each with the tool that helps with it.
# Written between markers in docs/index.html; a small script hides events once their day has passed.
HOME = ROOT / "docs/index.html"
HOME_WHO = {"all": "Every landlord in England", "m50": "Landlords in Making Tax Digital (income over £50,000)",
            "m30": "Landlords with income over £30,000", "r:West Midlands": "West Midlands landlords"}


def home_cta(title: str, who: str) -> tuple:
    if title.startswith("MTD quarterly update"):
        return "Work out your figures", "guides/making-tax-digital-quarterly-update-landlords.html"
    if title.startswith("Lords vote"):
        return "Live status", "guides/landlord-database-regulations-status.html"
    if title.startswith("Landlord database opens"):
        return "Check your properties", "#tool"
    if title.startswith("Self Assessment"):
        return "Does MTD start for you?", "guides/hmrc-signed-me-up-making-tax-digital.html"
    if title.startswith("MTD starts"):
        return "Find MTD software", "guides/making-tax-digital-software-for-landlords.html"
    if who.startswith("r:"):
        return "West Midlands guide", "guides/west-midlands.html"
    return "All deadlines", "guides/landlord-deadlines-calendar.html"


def home_strip(today: date, n: int = 6) -> str:
    rows = []
    for d, title, who, _ in EVENTS:
        if d < today.isoformat() or who not in HOME_WHO:
            continue
        x = date.fromisoformat(d)
        cta, href = home_cta(title, who)
        rows.append(f'<li data-date="{d}"><time datetime="{d}"><b>{x.day}</b>{x.strftime("%b")}</time>'
                    f'<div><strong>{html.escape(title.replace(" (listed)", ""))}</strong><span>{html.escape(HOME_WHO[who])}'
                    f' · <em class="when"></em></span></div><a class="btn sm ghost" href="{href}">{html.escape(cta)}</a></li>')
        if len(rows) == n:
            break
    return ("<!-- upcoming:start -->\n"
            '<section class="band upcoming" aria-labelledby="upcoming-h"><div class="container">\n'
            '<div class="upcoming-head"><h2 id="upcoming-h">Coming up for landlords</h2>'
            '<a href="guides/landlord-deadlines-calendar.html">Every deadline to 2028</a></div>\n'
            '<ol class="upcoming-list">\n' + "\n".join(rows) + "\n</ol>\n"
            "<script>(function(){var t=new Date();t.setHours(0,0,0,0);var shown=0;"
            "document.querySelectorAll('.upcoming-list li').forEach(function(li){"
            "var d=new Date(li.dataset.date+'T00:00:00');var n=Math.round((d-t)/864e5);"
            "if(n<0||shown>=3){li.hidden=true;return;}shown++;"
            "li.querySelector('.when').textContent=n===0?'today':n===1?'tomorrow':'in '+n+' days';});})();</script>\n"
            "</div></section>\n<!-- upcoming:end -->")


def write_home(today: date) -> None:
    s = HOME.read_text(encoding="utf-8")
    a, b = s.index("<!-- upcoming:start -->"), s.index("<!-- upcoming:end -->") + len("<!-- upcoming:end -->")
    HOME.write_text(s[:a] + home_strip(today) + s[b:], encoding="utf-8")


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT.relative_to(ROOT))
    write_home(date.today())
    print(HOME.relative_to(ROOT))

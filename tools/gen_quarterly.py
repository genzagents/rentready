"""Landlord quarterly update figures from a bank statement (docs/guides/making-tax-digital-quarterly-update-landlords.html).

A landlord in Making Tax Digital for Income Tax sends HMRC a running total of rent and expenses each quarter. The page
reads a bank statement CSV in the browser, sorts each line into HMRC's UK property categories (the same field names as
the Property Business API v6.0 cumulative summary, ported from build/taxfiler/taxfiler/categories.py), lets the
landlord change any line, and shows the year-to-date figures to type into their MTD software. Nothing is uploaded.
Its readCsv(), categorise() and summarise() are tested under node.

Sources (read 2 Nov 2026): gov.uk "Send quarterly updates" (updated 16 Oct 2026: cumulative from 6 April, standard and
calendar periods, deadlines, no penalty points for late updates in 2026-27) and "Create digital records" (updated
16 Oct 2026: under £90,000 UK property turnover a landlord may use simpler categorisation, but must still record
which expenses are restricted (residential) finance costs).

Run `python3 tools/gen_quarterly.py`, then `python3 tools/schema.py`; tests/test_quarterly.py checks the page.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/guides/making-tax-digital-quarterly-update-landlords.html"
URL = "https://genzagents.github.io/rentready/guides/making-tax-digital-quarterly-update-landlords.html"
REVIEWED = "2 November 2026"

# HMRC UK property field -> label as MTD software shows it. Order follows HMRC's schema.
CATS = [
    ("periodAmount", "in", "Rents from property"),
    ("otherIncome", "in", "Other property income"),
    ("premisesRunningCosts", "out", "Rent, rates, insurance, ground rents"),
    ("repairsAndMaintenance", "out", "Property repairs and maintenance"),
    ("financialCosts", "out", "Loan interest and other financial costs"),
    ("professionalFees", "out", "Legal, management and other professional fees"),
    ("costOfServices", "out", "Cost of services provided, including wages"),
    ("travelCosts", "out", "Car, van and travel costs"),
    ("other", "out", "Other allowable property expenses"),
    ("residentialFinancialCost", "out", "Residential finance costs (mortgage interest)"),
    ("exclude", "none", "Not property money (transfer, deposit, tax)"),
    ("unsorted", "none", "Needs a category"),
]

# 2026-27 periods. Each update runs from 6 April 2026: the first MTD year starts on 6 April under calendar periods too.
PERIODS = {
    "standard": [("2026-07-05", "2026-08-07"), ("2026-10-05", "2026-11-07"), ("2027-01-05", "2027-02-07"), ("2027-04-05", "2027-05-07")],
    "calendar": [("2026-06-30", "2026-08-07"), ("2026-09-30", "2026-11-07"), ("2026-12-31", "2027-02-07"), ("2027-03-31", "2027-05-07")],
}

# Keyword rules, first match wins. Applied to the upper-cased description; dir is "in", "out" or "" (either).
RULES = [
    ("exclude", "", r"\bDEPOSIT\b|\bDPS\b|MYDEPOSITS|\bTDS\b|DEPOSIT PROTECTION"),
    ("exclude", "", r"\bHMRC\b|SELF ASSESSMENT|TRANSFER|\bTFR\b|OWN ACCOUNT|SAVINGS|\bPOT\b|ISA\b|CREDIT CARD|AMEX|BARCLAYCARD"),
    ("residentialFinancialCost", "out", r"MORTGAGE|\bMTG\b|\bBTL\b|BUY TO LET|PARAGON|KENT RELIANCE|PRECISE|FOUNDATION HOME|BM SOLUTIONS|THE MORTGAGE WORKS|LOAN INTEREST"),
    ("professionalFees", "out", r"LETTING|LETTINGS|ESTATE AGENT|MANAGEMENT FEE|OPENRENT|FOXTONS|HAMPTONS|COUNTRYWIDE|ACCOUNTANT|ACCOUNTANCY|SOLICITOR|LEGAL|\bNRLA\b|REFERENCING|GOODLORD|INVENTORY"),
    ("premisesRunningCosts", "out", r"COUNCIL TAX|COUNCIL|INSURANCE|DIRECT LINE|ALAN BOSWELL|SIMPLY BUSINESS|GROUND RENT|SERVICE CHARGE|BRITISH GAS|OCTOPUS|\bEDF\b|E\.ON|\bEON\b|\bOVO\b|SCOTTISH POWER|THAMES WATER|SEVERN TRENT|ANGLIAN WATER|UNITED UTILITIES|YORKSHIRE WATER|SOUTHERN WATER|WATER|TV LICEN|LANDLORD DATABASE|LICENCE FEE"),
    ("other", "out", r"GAS SAFETY|GAS SAFE|\bEICR\b|\bEPC\b|ENERGY PERFORMANCE|PAT TEST|SMOKE ALARM|ADVERT|RIGHTMOVE|ZOOPLA|SPAREROOM|BANK CHARGE|ACCOUNT FEE"),
    ("repairsAndMaintenance", "out", r"REPAIR|PLUMB|ELECTRICIAN|BOILER|HEATING|LOCKSMITH|GLAZING|ROOF|DAMP|PEST|SCREWFIX|TOOLSTATION|B&Q|B & Q|WICKES|HOMEBASE|TRAVIS PERKINS|HANDYMAN|DECORAT|PAINT|CLEAN|GARDEN|CHECKATRADE|MYBUILDER"),
    ("costOfServices", "out", r"CONCIERGE|CARETAKER|PAYROLL"),
    ("travelCosts", "out", r"\bTFL\b|TRAINLINE|PARKING|\bFUEL\b|PETROL|SHELL|\bESSO\b|\bBP\b"),
    ("periodAmount", "in", r"RENT|STANDING ORDER|\bSO\b|TENANT|FLAT|\bAPT\b|ROOM"),
]

FAQ = [
    ("What figures go in a landlord's Making Tax Digital quarterly update?",
     "Totals for each income and expense category since 6 April, not just the last three months. For UK property that "
     "is rent received and the expense categories your software shows: rent, rates and insurance, repairs and "
     "maintenance, professional fees, finance costs, services, travel and other costs, with residential mortgage "
     "interest kept separate. HMRC does not calculate tax from a quarterly update; it is a running total."),
    ("Can I send one total for all my property expenses?",
     "Yes, if your UK property income for the year is under £90,000, gov.uk allows simpler categorisation: you can "
     "record each line as income or expense without splitting expenses into categories. You must still record which "
     "expenses are residential finance costs, such as buy-to-let mortgage interest, because they get a 20% tax "
     "reduction instead of being deducted."),
    ("Do I include my whole mortgage payment as an expense?",
     "No. Only the interest counts, and for a residential let it goes in residential finance costs, not in expenses. "
     "The capital part of a repayment mortgage is never an expense. If your bank statement shows the whole monthly "
     "payment, use the interest figure from your lender's annual statement instead."),
    ("When is the 7 November 2026 quarterly update due and what does it cover?",
     "It is due by 7 November 2026 and covers 6 April to 5 October 2026 (or 6 April to 30 September if your software "
     "uses calendar periods). Because each update is cumulative, it also makes up a missed August update. HMRC will "
     "not give penalty points for late quarterly updates in the 2026-27 tax year."),
    ("Is this tool Making Tax Digital software?",
     "No. It works out the figures from your bank statement in your browser; you still send the update from software "
     "HMRC recognises. Nothing you load here is uploaded, and it is not tax advice."),
]

LOGIC = r"""
var CATS=__CATS__,PERIODS=__PERIODS__,RULES=__RULES__;
var START="2026-04-06";
function splitCsv(text){var rows=[],row=[],f="",q=false,i,c;text=String(text||"").replace(/^﻿/,"");
 for(i=0;i<text.length;i++){c=text[i];
  if(q){if(c==='"'){if(text[i+1]==='"'){f+='"';i++;}else q=false;}else f+=c;}
  else if(c==='"')q=true;else if(c===","){row.push(f);f="";}
  else if(c==="\n"||c==="\r"){if(c==="\r"&&text[i+1]==="\n")i++;row.push(f);f="";if(row.join("").trim())rows.push(row);row=[];}
  else f+=c;}
 row.push(f);if(row.join("").trim())rows.push(row);return rows;}
var MON={jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
function pad(n){return (n<10?"0":"")+n;}
// UK bank dates, always day first. Returns "YYYY-MM-DD" or null.
function parseDate(s){s=String(s||"").trim().replace(/^['"]|['"]$/g,"");var m;
 if((m=s.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/)))return m[1]+"-"+pad(+m[2])+"-"+pad(+m[3]);
 if((m=s.match(/^(\d{1,2})[\/.\-](\d{1,2})[\/.\-](\d{2,4})(?:[ T].*)?$/))){var y=+m[3];if(y<100)y+=2000;return y+"-"+pad(+m[2])+"-"+pad(+m[1]);}
 if((m=s.match(/^(\d{1,2})[ \-]([A-Za-z]{3,9})[ \-,]*(\d{2,4})$/))&&MON[m[2].slice(0,3).toLowerCase()]){var y2=+m[3];if(y2<100)y2+=2000;return y2+"-"+pad(MON[m[2].slice(0,3).toLowerCase()])+"-"+pad(+m[1]);}
 return null;}
// "£1,234.56" -> 123456 pence; "(12.50)" or "12.50 DR" -> -1250; blank -> null.
function parseAmount(s){var t=String(s==null?"":s).replace(/[£,\s]|GBP/g,"");if(t===""||t==="-")return null;var sg=1;
 if(/^\(.*\)$/.test(t)){sg=-1;t=t.slice(1,-1);}
 if(/DR$/i.test(t)){sg=-sg;t=t.slice(0,-2);}else if(/CR$/i.test(t))t=t.slice(0,-2);
 if(!/^[+\-]?\d*\.?\d+$/.test(t))return null;return sg*Math.round(parseFloat(t)*100);}
function findCol(h,res){for(var r=0;r<res.length;r++)for(var i=0;i<h.length;i++)if(res[r].test(h[i]))return i;return -1;}
// Any UK bank export: a date column, a description column and one signed amount or separate money in / out columns.
function readCsv(text){var rows=splitCsv(text),out={lines:[],skipped:0,error:""};if(!rows.length){out.error="empty";return out;}
 var h=rows[0].map(function(x){return String(x).trim().toLowerCase();}),body=rows.slice(1);
 var di=findCol(h,[/^(transaction |completed |started )?date$/,/date/]);
 var ti=findCol(h,[/^(transaction )?description$/,/^counter ?party$/,/^name$/,/^payee$/,/^details$/,/^memo$/,/narrative/,/description/,/reference/]);
 var ai=findCol(h,[/^amount( \(gbp\))?$/,/^value$/,/^amount/]);
 var ii=findCol(h,[/^(paid in|money in|credit( amount)?|in)$/,/credit|paid in|money in/]);
 var oi=findCol(h,[/^(paid out|money out|debit( amount)?|out)$/,/debit|paid out|money out|withdrawn/]);
 if(di<0&&parseDate(rows[0][0])){body=rows;di=0;ti=1;ai=rows[0].length-1>2?2:rows[0].length-1;ii=oi=-1;}
 if(di<0||(ai<0&&(ii<0||oi<0))){out.error="columns";return out;}
 if(ai>=0)ii=oi=-1;
 body.forEach(function(r){var d=parseDate(r[di]),a=null;
  if(ai>=0)a=parseAmount(r[ai]);else{var pi=parseAmount(r[ii]),po=parseAmount(r[oi]);if(pi||po)a=(pi?Math.abs(pi):0)-(po?Math.abs(po):0);}
  if(!d||a===null||a===0){out.skipped++;return;}
  var desc=ti>=0?String(r[ti]||"").trim():"";
  if(ti>=0&&!desc){var j=findCol(h,[/reference/,/type/]);if(j>=0)desc=String(r[j]||"").trim();}
  out.lines.push({date:d,desc:desc,pence:a});});
 return out;}
function categorise(desc,pence){var u=String(desc||"").toUpperCase(),dir=pence>0?"in":"out";
 for(var i=0;i<RULES.length;i++){var r=RULES[i];if(r[1]&&r[1]!==dir)continue;if(new RegExp(r[2]).test(u))return r[0];}
 return dir==="in"?"periodAmount":"unsorted";}
function kind(c){for(var i=0;i<CATS.length;i++)if(CATS[i][0]===c)return CATS[i][1];return "none";}
// Year-to-date totals for update q (0..3) of the chosen period type, in pence, scaled by the owner's share (0-100].
function summarise(lines,cats,type,q,share){var end=PERIODS[type][q][0],s=(share>0&&share<=100?share:100)/100;
 var t={},n={inRange:0,before:0,after:0,unsorted:0,wrongWay:0};CATS.forEach(function(c){t[c[0]]=0;});
 lines.forEach(function(l,i){if(l.date<START){n.before++;return;}if(l.date>end){n.after++;return;}n.inRange++;
  var c=cats[i],k=kind(c);if(c==="unsorted")n.unsorted++;
  if(k==="in")t[c]+=l.pence;else if(k==="out")t[c]-=l.pence;
  if((k==="in"&&l.pence<0)||(k==="out"&&l.pence>0))n.wrongWay++;});
 var r={end:end,due:PERIODS[type][q][1],totals:{},counts:n,income:0,expenses:0,finance:0};
 CATS.forEach(function(c){var v=Math.round(t[c[0]]*s);r.totals[c[0]]=v;
  if(c[1]==="in")r.income+=v;else if(c[1]==="out"){if(c[0]==="residentialFinancialCost")r.finance+=v;else r.expenses+=v;}});
 r.simpler=r.income*(365/Math.max(1,(Date.parse(end)-Date.parse(START))/864e5+1))<9000000;
 return r;}
"""

SAMPLE = """Date,Description,Amount
06/04/2026,Opening balance transfer,2500.00
07/04/2026,J SMITH RENT FLAT 2,1150.00
12/04/2026,PARAGON MORTGAGE,-612.40
15/04/2026,DIRECT LINE LANDLORD INSURANCE,-38.20
20/04/2026,TENANT DEPOSIT DPS,-1300.00
07/05/2026,J SMITH RENT FLAT 2,1150.00
09/05/2026,ACE PLUMBING BOILER REPAIR,-185.00
12/05/2026,PARAGON MORTGAGE,-612.40
02/06/2026,GAS SAFETY CERTIFICATE,-72.00
07/06/2026,J SMITH RENT FLAT 2,1150.00
12/06/2026,PARAGON MORTGAGE,-612.40
18/06/2026,OPENRENT REFERENCING,-29.00
07/07/2026,J SMITH RENT FLAT 2,1150.00
12/07/2026,PARAGON MORTGAGE,-612.40
22/07/2026,HMRC SELF ASSESSMENT,-1840.00
07/08/2026,J SMITH RENT FLAT 2,1150.00
12/08/2026,PARAGON MORTGAGE,-612.40
14/08/2026,SCREWFIX,-46.85
07/09/2026,J SMITH RENT FLAT 2,1150.00
12/09/2026,PARAGON MORTGAGE,-612.40
30/09/2026,AMAZON MARKETPLACE,-23.99
02/10/2026,ABC ACCOUNTANTS,-150.00
07/10/2026,J SMITH RENT FLAT 2,1150.00
"""

PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Landlord MTD quarterly update: your figures from a bank statement</title>
<meta name="description" content="Load your bank statement CSV and get the rent and expense totals for your 7 November MTD quarterly update, in HMRC's property categories.">
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
<h1>Your Making Tax Digital quarterly update: landlord figures from a bank statement</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed __REVIEWED__. <a href="#sources">Sources</a> below.</p>
<p><strong>The next quarterly update is due by 7 November 2026 and covers 6 April to 5 October 2026. It is a running total of your rent and expenses for the year so far, in HMRC's property categories.</strong> Load the CSV your bank lets you download, check how each line is sorted, and copy the totals into your MTD software. Your statement is read in this browser and never uploaded.</p>

<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="qu-h">
<h2 id="qu-h" style="margin-top:0">Work out your figures</h2>
<label class="qu-drop" id="drop" for="file"><p><strong>Choose your bank statement CSV</strong> or drop it here</p>
<p class="mut" style="font-size:14px">Any UK bank: Monzo, Starling, Barclays, HSBC, Lloyds, Halifax, NatWest, Santander, Nationwide, Revolut. Use the account your rent goes into, from 6 April 2026.</p>
<input type="file" id="file" accept=".csv,text/csv" class="sr"></label>
<div class="qu-btns"><button type="button" id="sample">Try it with a sample statement</button></div>
<div class="qu-opts">
<label>Which update?<select class="dl-sel" id="q"><option value="0">Due 7 August 2026</option><option value="1" selected>Due 7 November 2026</option><option value="2">Due 7 February 2027</option><option value="3">Due 7 May 2027</option></select></label>
<label>Your software's update periods<select class="dl-sel" id="type"><option value="standard">Standard: to the 5th</option><option value="calendar">Calendar: to the month end</option></select></label>
<label>Your share of the property<select class="dl-sel" id="share"><option value="100">All of it (100%)</option><option value="50">Half (50%, joint owners)</option><option value="33.3333">A third</option><option value="25">A quarter</option></select></label>
</div>
<div class="who-out" id="out" aria-live="polite"><b>Load a statement to see your figures</b><p>Or try the sample to see what you will get.</p></div>
<div id="res" hidden>
<div class="wrap"><table class="qu-sum" id="sum"></table></div>
<div class="qu-btns"><button type="button" class="go" id="dl">Download figures (CSV)</button><button type="button" id="dlines">Download sorted lines (CSV)</button></div>
<h3>Every line, and where it went</h3>
<p class="mut" style="font-size:14px;margin-top:0">Change any category and the totals update. Lines shaded amber need you to choose. Faded lines fall outside this update's dates.</p>
<div class="qu-lines"><table id="lines"></table></div>
</div>
<form class="remind wait dl-rem" id="rem" novalidate><p><strong>Email me two weeks before the next quarterly update.</strong> One email, nothing else. No account.</p>
<div class="remind-row"><label class="sr" for="rem-email">Email address</label><input type="email" id="rem-email" autocomplete="email" placeholder="you@example.com" required>
<button type="submit" class="go">Remind me</button></div>
<p class="mut remind-f">We keep only your email and the deadline date. Your bank statement never leaves your browser. <a href="../privacy.html#reminders">How to be removed</a>.</p><p class="remind-msg" id="rem-msg" role="status"></p></form>
</section>

<h2>What goes in each box</h2>
<div class="wrap"><table><thead><tr><th>Box in your software</th><th>What belongs there</th></tr></thead><tbody>
<tr><td>Rents from property</td><td>Rent your tenants paid you, or that your agent collected for you before deducting fees. Not the tenancy deposit.</td></tr>
<tr><td>Rent, rates, insurance, ground rents</td><td>Landlord insurance, ground rent, service charges, and council tax, energy and water when you pay them for the property.</td></tr>
<tr><td>Property repairs and maintenance</td><td>Repairs that put things back as they were: plumbers, boiler repairs, decorating between tenants, materials. Not improvements such as an extension.</td></tr>
<tr><td>Legal, management and other professional fees</td><td>Letting agent and management fees, tenant referencing, inventories, accountants, legal fees for a tenancy (not for buying the property).</td></tr>
<tr><td>Loan interest and other financial costs</td><td>Interest on loans that are not for a residential let (for example a furnished holiday let before April 2025, or commercial property).</td></tr>
<tr><td>Other allowable property expenses</td><td>Gas safety records, EICRs, EPCs, advertising, the landlord database fee, bank charges on the rent account.</td></tr>
<tr><td>Residential finance costs</td><td>Mortgage interest on a residential let. Kept separate because it gives a 20% tax reduction instead of being deducted. Only the interest, never the capital.</td></tr>
</tbody></table></div>
<p>If your UK property income for the year is under £90,000, gov.uk lets you skip the expense categories and record each line just as income or expense. You still have to keep residential finance costs separate. The tool shows both forms.</p>

<h2>The 2026-27 quarterly updates</h2>
<div class="wrap"><table><thead><tr><th>Due</th><th>Standard periods cover</th><th>Calendar periods cover</th></tr></thead><tbody>
<tr><td>7 August 2026</td><td>6 April to 5 July</td><td>6 April to 30 June</td></tr>
<tr><td>7 November 2026</td><td>6 April to 5 October</td><td>6 April to 30 September</td></tr>
<tr><td>7 February 2027</td><td>6 April to 5 January</td><td>6 April to 31 December</td></tr>
<tr><td>7 May 2027</td><td>The whole year to 5 April</td><td>The whole year to 31 March</td></tr>
</tbody></table></div>
<p>In your first Making Tax Digital year, calendar periods also start on 6 April. HMRC will not give penalty points for late quarterly updates in 2026-27; late tax returns still get them. If HMRC signed you up without asking, <a href="hmrc-signed-me-up-making-tax-digital.html">check whether it got your income right</a> first.</p>

<h2>The other compulsory deadline for landlords</h2>
<p>England's landlord database opens on 15 December 2026, with a deadline for each region, from 14 March 2027 in the West Midlands. The fee is an allowable expense. <a href="https://genzagents.github.io/rentready/">Check your properties are ready in two minutes</a>, or see <a href="landlord-deadlines-calendar.html">every landlord deadline to 2028</a>.</p>

<h2>Questions</h2>
__FAQ_HTML__
<h2 id="sources">Sources</h2>
<ul class="mut">
<li><a href="https://www.gov.uk/guidance/use-making-tax-digital-for-income-tax/send-quarterly-updates">gov.uk: send quarterly updates (updated 16 October 2026: cumulative totals, periods, deadlines, 2026-27 penalty points)</a></li>
<li><a href="https://www.gov.uk/guidance/use-making-tax-digital-for-income-tax/create-digital-records">gov.uk: create digital records (updated 16 October 2026: simpler categorisation under £90,000, restricted finance costs)</a></li>
<li><a href="https://developer.service.hmrc.gov.uk/api-documentation/docs/api/service/property-business-api/6.0">HMRC developer hub: Property Business API v6.0, UK property cumulative period summary (the categories)</a></li>
</ul>
<p class="mut">Not tax advice. rentready is not MTD software and is not recognised by HMRC; send your update from software that is. Check the figures, or ask an accountant, before relying on them. Last checked __REVIEWED__.</p>
<script src="../remind.js"></script>
<script id="qu-logic">__LOGIC__</script>
<script>
(function(){
var RM=window.rentreadyRemind,data=null,cats=[],last=null,SAMPLE=__SAMPLE__;
function $(i){return document.getElementById(i);}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
function gbp(p){var v=Math.abs(p)/100;return (p<0?"-":"")+"£"+v.toLocaleString("en-GB",{minimumFractionDigits:2,maximumFractionDigits:2});}
function dd(d){return new Date(d+"T12:00:00Z").toLocaleDateString("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"});}
function label(c){for(var i=0;i<CATS.length;i++)if(CATS[i][0]===c)return CATS[i][2];return c;}
var OPTS=CATS.map(function(c){return '<option value="'+c[0]+'">'+esc(c[2])+'</option>';}).join("");
function load(text,name){data=readCsv(text);
 if(data.error||!data.lines.length){$("res").hidden=true;$("out").className="who-out who-later";
  $("out").innerHTML="<b>That file could not be read</b><p>"+(data.error==="columns"?"It needs a date column, a description and either an amount or money in / money out columns. Download the statement as CSV, not PDF.":"No dated transactions were found in it.")+"</p>";return;}
 cats=data.lines.map(function(l){return categorise(l.desc,l.pence);});
 $("drop").querySelector("strong").textContent=name||"Statement loaded";renderLines();go();}
function renderLines(){var end=PERIODS[$("type").value][+$("q").value][0];
 $("lines").innerHTML="<thead><tr><th>Date</th><th>Description</th><th style='text-align:right'>Amount</th><th>Category</th></tr></thead><tbody>"+data.lines.map(function(l,i){
  var out=l.date<START||l.date>end;
  return "<tr class='"+(out?"qu-out":cats[i]==="unsorted"?"qu-un":"")+"'><td class='d'>"+l.date.split("-").reverse().join("/")+"</td><td class='desc' title='"+esc(l.desc)+"'>"+esc(l.desc||"(no description)")+"</td><td class='a"+(l.pence>0?" pos":"")+"'>"+gbp(l.pence)+"</td><td><select data-i='"+i+"' aria-label='Category'>"+OPTS.replace('value="'+cats[i]+'"','value="'+cats[i]+'" selected')+"</select></td></tr>";}).join("")+"</tbody>";}
function go(){if(!data)return;var r=last=summarise(data.lines,cats,$("type").value,+$("q").value,+$("share").value);
 var rows=CATS.filter(function(c){return c[1]!=="none";}).map(function(c){var v=r.totals[c[0]];return "<tr class='"+(v?"":"qu-zero")+"'><td>"+esc(c[2])+"</td><td>"+gbp(v)+"</td></tr>";}).join("");
 $("sum").innerHTML="<thead><tr><th>Box in your MTD software, 6 April to "+dd(r.end)+"</th><th>Year to date</th></tr></thead><tbody>"+rows+
  "<tr class='qu-tot'><td>Total income</td><td>"+gbp(r.income)+"</td></tr><tr class='qu-tot'><td>Total expenses, if you use one figure (under £90,000)</td><td>"+gbp(r.expenses)+"</td></tr><tr><td>Plus residential finance costs, always separate</td><td>"+gbp(r.finance)+"</td></tr></tbody>";
 var n=r.counts,warn=[];
 if(n.unsorted)warn.push(n.unsorted+" line"+(n.unsorted>1?"s need":" needs")+" a category (shaded below) and "+(n.unsorted>1?"are":"is")+" not counted yet.");
 if(r.totals.residentialFinancialCost)warn.push("Mortgage payments are counted in full. Only the interest belongs here, so use the interest figure from your lender if it is lower.");
 if(n.wrongWay)warn.push(n.wrongWay+" line"+(n.wrongWay>1?"s go":" goes")+" the opposite way to "+(n.wrongWay>1?"their":"its")+" category (for example a refund) and "+(n.wrongWay>1?"reduce":"reduces")+" that total.");
 if(!r.simpler)warn.push("At this rate your property income will be £90,000 or more this year, so send the expense categories, not one total.");
 if(n.after)warn.push(n.after+" line"+(n.after>1?"s are":" is")+" after "+dd(r.end)+" and belong"+(n.after>1?"":"s")+" in a later update.");
 $("out").className="who-out"+(n.unsorted?" who-later":" who-yes");
 $("out").innerHTML="<b>Rent "+gbp(r.income)+", expenses "+gbp(r.expenses)+(r.finance?", finance costs "+gbp(r.finance):"")+"</b><p>Year to date for the update due "+dd(r.due)+", from "+n.inRange+" lines"+(+$("share").value<100?", at your share":"")+". "+warn.join(" ")+"</p>";
 $("res").hidden=false;}
function csv(rows){return rows.map(function(r){return r.map(function(v){v=String(v);return /[",\\n]/.test(v)?'"'+v.replace(/"/g,'""')+'"':v;}).join(",");}).join("\\r\\n");}
function save(name,text){var a=document.createElement("a");a.href=URL.createObjectURL(new Blob([text],{type:"text/csv"}));a.download=name;document.body.appendChild(a);a.click();a.remove();}
$("dl").addEventListener("click",function(){if(!last)return;var rows=[["HMRC field","Box","Pounds (6 April 2026 to "+last.end+")"]];
 CATS.forEach(function(c){if(c[1]!=="none")rows.push([c[0],c[2],(last.totals[c[0]]/100).toFixed(2)]);});
 rows.push(["consolidatedExpenses","Total expenses (one figure, under £90,000)",(last.expenses/100).toFixed(2)]);
 save("quarterly-update-"+last.end+".csv",csv(rows));});
$("dlines").addEventListener("click",function(){if(!data)return;save("sorted-lines.csv",csv([["Date","Description","Amount","Category"]].concat(data.lines.map(function(l,i){return [l.date,l.desc,(l.pence/100).toFixed(2),label(cats[i])];}))));});
$("lines").addEventListener("change",function(e){var i=e.target.getAttribute("data-i");if(i===null)return;cats[+i]=e.target.value;e.target.closest("tr").className=cats[+i]==="unsorted"?"qu-un":"";go();});
["q","type"].forEach(function(id){$(id).addEventListener("change",function(){if(data){renderLines();go();}});});
$("share").addEventListener("change",go);
$("file").addEventListener("change",function(){var f=this.files[0];if(!f)return;var rd=new FileReader();rd.onload=function(){load(rd.result,f.name);};rd.readAsText(f);});
var dz=$("drop");["dragenter","dragover"].forEach(function(t){dz.addEventListener(t,function(e){e.preventDefault();dz.classList.add("on");});});
["dragleave","drop"].forEach(function(t){dz.addEventListener(t,function(e){e.preventDefault();dz.classList.remove("on");});});
dz.addEventListener("drop",function(e){var f=e.dataTransfer.files[0];if(!f)return;var rd=new FileReader();rd.onload=function(){load(rd.result,f.name);};rd.readAsText(f);});
$("sample").addEventListener("click",function(){load(SAMPLE,"Sample statement (one flat, 6 April to 7 October)");});
function nextDue(){var today=new Date().toISOString().slice(0,10),p=PERIODS.standard;for(var i=0;i<p.length;i++)if(p[i][1]>=today)return p[i][1];return null;}
var r=$("rem"),m=$("rem-msg");
r.addEventListener("submit",async function(ev){ev.preventDefault();var due=nextDue();
var d=RM&&due&&RM.mtd($("rem-email").value,due,"quarterly figures");
if(!d){m.textContent="Please enter a valid email address.";return;}
m.textContent="Sending...";try{await RM.send(d);m.textContent="Done. We will email you two weeks before "+dd(due)+".";r.querySelector("button").disabled=true;}
catch(x){m.textContent="That did not send. Please try again in a moment.";}});
})();
</script>
__FOOTER__"""


def faq_ld() -> str:
    return json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]},
        ensure_ascii=False, indent=1)


def build() -> str:
    src = (ROOT / "docs/guides/landlord-database-first-year-cost.html").read_text(encoding="utf-8")
    header = src[src.index("<header"):src.index("</header>") + 9]
    footer = src[src.index("<footer"):]
    faq_html = "\n".join(f"<h3>{html.escape(q)}</h3>\n<p>{html.escape(a)}</p>" for q, a in FAQ)
    j = lambda v: json.dumps(v, separators=(",", ":"), ensure_ascii=False)  # noqa: E731
    logic = (LOGIC.replace("__CATS__", j([list(c) for c in CATS])).replace("__PERIODS__", j(PERIODS))
             .replace("__RULES__", j([list(r) for r in RULES])))
    t = PAGE
    for k, v in {"__URL__": URL, "__FAQ__": faq_ld(), "__HEADER__": header, "__REVIEWED__": REVIEWED,
                 "__FAQ_HTML__": faq_html, "__LOGIC__": logic, "__SAMPLE__": j(SAMPLE), "__FOOTER__": footer}.items():
        t = t.replace(k, v)
    return t


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT.relative_to(ROOT))

"""What ministers told Parliament about the landlord database (docs/guides/landlord-database-what-ministers-said.html).

The draft PRS Database Regulations 2026 were debated on 28 October 2026 in the Commons Fourth Delegated Legislation
Committee (Matthew Pennycook, agreed 11 to 6) and the Lords Grand Committee (Baroness Taylor of Stevenage), and the
Lords approved them on 4 November. The ministers' answers settle questions landlords keep asking (bulk upload, agents
starting the registration, one payment for many homes, re-entering everything each year, licensing duplication) and
nobody has written them up for landlords. Each answer below is a paraphrase of the Hansard record, with the source.

Run this, then `python3 tools/schema.py`; tests/test_parliament_guide.py checks the page.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs/guides/landlord-database-what-ministers-said.html"
URL = "https://genzagents.github.io/rentready/guides/landlord-database-what-ministers-said.html"
REVIEWED = "4 November 2026"
COMMONS = "https://hansard.parliament.uk/Commons/2026-10-28/debates/2f279768-5750-4061-86fe-a43557fa8443/"
LORDS = "https://hansard.parliament.uk/Lords/2026-10-28/debates/65E1EB59-7102-4823-9BB5-9F4CF5E400AE/"
LORDS_VOTE = "https://hansard.parliament.uk/Lords/2026-11-04/debates/7361E571-CEE5-49CB-929E-79C99DF5FC02/"
GUIDE = "https://www.gov.uk/guidance/register-your-rental-property-service-guidance-for-landlords"
SRC = {"C": ("Commons committee, 28 Oct 2026 (Matthew Pennycook)", COMMONS),
       "L": ("Lords Grand Committee, 28 Oct 2026 (Baroness Taylor)", LORDS)}

# (question, what the minister said, what it means for you, sources)
ANSWERS = [
    ("Can I bulk upload my properties?",
     "No. Pennycook said the government looked at bulk uploads, including Excel files, and decided against them "
     "because of data validation and error handling problems; asked to commit to bulk upload, he said he could not. "
     "Organisations will be able to add several employees to one account, and the government is \"looking at\" a "
     "secure connection that property management software could use instead. No date was given for it.",
     "Plan to enter every home by hand. Gather each property's details and certificate dates in one place before "
     "your window opens, so each entry is copy and paste rather than a hunt through files.", "CL"),
    ("Does each flat in a block need its own entry? What about HMOs?",
     "Each dwelling is registered separately, even when one landlord owns a whole building of rented flats, because "
     "rent, occupants and gas and electrical certificates differ from flat to flat. Baroness Taylor added that in an "
     "HMO the individual rooms do not need to be registered.",
     "Count homes, not buildings and not rooms: a block of 12 flats is 12 entries and 12 fees; a five-bedroom HMO "
     "is one.", "L"),
    ("Can I pay for all my properties in one go?",
     "Not confirmed. Lord Fuller said each property is paid for by a separate card transaction. Baroness Taylor said "
     "her understanding was that one payment could cover several, called the point fair, and promised to reply in "
     "writing.",
     "Assume one card payment per property until the service or the minister's letter says otherwise, and check "
     "your card's daily limit if you have many homes.", "L"),
    ("Can my letting agent register my properties for me?",
     "No. Both ministers said the landlord must start each registration, so that landlords engage with their duties, "
     "and stays responsible for registration, payment, renewal and accuracy. Once you have started, you can let an "
     "agent who agrees add the tenancy and health and safety details. Agents have no mandatory role and are not "
     "registered themselves.",
     "Start the entry yourself, then hand the property link to your agent for the certificates and tenancy details. "
     "You are fined if it is wrong, so check what they enter.", "CL"),
    ("Will I have to enter everything again every year?",
     "No. Pennycook said landlords update only what has changed; the annual renewal is a prompt to confirm the entry "
     "is still right, like a register of interests. The regulations say out-of-date details must generally be "
     "corrected within 28 days.",
     "Keep a note of each certificate's expiry: a new gas safety record or EICR is a change you must add within 28 "
     "days, renewal or not.", "CL"),
    ("I already have a council licence. Do I register twice?",
     "Yes, for now. Both ministers said the database will not replace or duplicate selective licensing because they "
     "have different purposes, and that the government will keep reviewing how the two interact, with a view to "
     "reducing duplication.",
     "In a licensing area you pay the licence fee and £65 a property a year. See "
     "<a href=\"selective-licensing-councils-england.html\">which councils license</a>.", "CL"),
    ("Why is the fee £65 when it was meant to be about £20?",
     "Baroness Taylor said £65 a year a property is needed to run the database and fund enforcement, part of the fee "
     "goes to councils for enforcement, the operator sets it rather than the regulations, and it is not meant to pay "
     "for costs outside private renting. No breakdown was given. Peers quoted the earlier impact assessment figure "
     "of £28.58 every three years.",
     "Budget £65 a property a year from 15 December 2027, with a small pro rata first payment before that. "
     "<a href=\"landlord-database-fee.html#first-payment\">Work out your first payment</a>.", "LC"),
    ("How do I log in, and is it secure?",
     "Organisational landlords log in with GOV.UK One Login. The minister said the service is being assessed against "
     "the National Cyber Security Centre's framework and will be penetration tested. Peers objected that agents get a "
     "per-property web link that does not change from year to year.",
     "Treat each property link you send an agent like a password: send it only to the person who needs it.", "L"),
    ("Has it been tested?",
     "Baroness Taylor said user research with landlords began in 2023 and formal testing in May 2026: almost 90% of "
     "organisational landlords tested found the service easy or very easy, and 80% found the guidance clear. Peers "
     "asked who was tested and whether anyone tried a large portfolio; she promised more detail.",
     "Expect it to work for a single property and to be slow for a large portfolio.", "L"),
    ("How will landlords who never register be caught?",
     "Once a later set of regulations makes part of the database public, tenants will be able to check a property "
     "and report one that is not registered to the council. That public side is a second instrument, due after the "
     "rollout ends.",
     "Councils see every entry from day one. See <a href=\"can-you-search-landlord-database.html\">what the public "
     "will see, and when</a>.", "L"),
]

FAQ = [
    ("Can landlords bulk upload properties to the PRS database?",
     "No. The Housing Minister told the Commons committee on 28 October 2026 that bulk upload, including Excel files, "
     "was ruled out over data validation and error handling, and he would not commit to it. Each dwelling needs its "
     "own entry. Organisations can add several employees to one account, and the government is looking at a secure "
     "connection for property management software, with no date."),
    ("Can a letting agent register a property on the landlord database?",
     "No. The landlord must start each registration and remains responsible for it. After that the landlord can "
     "delegate the tenancy and health and safety details to an agent who agrees."),
    ("Do HMO rooms need to be registered separately on the landlord database?",
     "No. The minister told the Lords Grand Committee that individual rooms in an HMO do not need to be registered. "
     "Each separate dwelling, such as each flat in a block, does."),
    ("Do landlords re-enter their details every year?",
     "No. Only changed details need updating; the annual renewal confirms the entry is still correct. Out-of-date "
     "details must generally be corrected within 28 days."),
]


def build() -> str:
    faq_ld = json.dumps({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": a, "acceptedAnswer": {"@type": "Answer", "text": b}} for a, b in FAQ]},
        ensure_ascii=False, indent=1)
    cards = []
    for i, (q, said, means, src) in enumerate(ANSWERS, 1):
        links = " · ".join(f'<a href="{SRC[k][1]}" rel="noopener">{html.escape(SRC[k][0])}</a>' for k in src)
        cards.append(f'<li class="card vis" id="q{i}"><b>{html.escape(q)}</b><p>{html.escape(said)}</p>'
                     f'<p class="said-means"><strong>For you:</strong> {means}</p>'
                     f'<p class="mut">Source: {links}</p></li>')
    src = (ROOT / "docs/guides/landlord-database-first-year-cost.html").read_text(encoding="utf-8")
    header = src[src.index("<header"):src.index("</header>") + 9]
    footer = src[src.index("<footer"):]
    t = PAGE
    for k, v in {"__URL__": URL, "__FAQ__": faq_ld, "__HEADER__": header, "__FOOTER__": footer,
                 "__REVIEWED__": REVIEWED, "__CARDS__": "\n".join(cards), "__COMMONS__": COMMONS, "__LORDS__": LORDS,
                 "__LORDS_VOTE__": LORDS_VOTE, "__GUIDE__": GUIDE,
                 "__FAQ_HTML__": "\n".join(f"<h3>{html.escape(a)}</h3>\n<p>{html.escape(b)}</p>" for a, b in FAQ)}.items():
        t = t.replace(k, v)
    return t


PAGE = """<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Landlord database: what ministers told Parliament (bulk upload)</title>
<meta name="description" content="No bulk upload, one entry per flat (not per HMO room), the landlord starts each registration: what ministers told Parliament in October 2026.">
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
<h1>What ministers told Parliament about the landlord database</h1>
<p class="mut byline">Written by <a href="https://genzagents.github.io/rentready/about.html">GenZAgents</a>, reviewed __REVIEWED__, from the Hansard record of both debates on the draft regulations. <a href="#sources">Sources</a> below.</p>
<p><strong>There will be no bulk upload: every rented home needs its own entry, the landlord (not the agent) must start each one, and each is paid for separately unless the minister's promised letter says otherwise.</strong> That is what the Housing Minister, Matthew Pennycook, told a Commons committee and Baroness Taylor of Stevenage told the Lords on 28 October 2026, when MPs and peers pressed them on the questions below. The good news: you do not re-enter everything each year, and HMO rooms do not need separate entries.</p>

<div class="kpis">
<div><b>No</b><span>bulk upload; each home entered on its own</span></div>
<div><b>1 per home</b><span>every flat in a block; not each HMO room</span></div>
<div><b>28 days</b><span>to correct details that go out of date</span></div>
<div><b>11 to 6</b><span>Commons committee vote for the regulations</span></div>
</div>

<h2>The questions, and the answers on the record</h2>
<ol class="vis-list">
__CARDS__
</ol>

<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="est-h">
<h2 id="est-h" style="margin-top:0">How long will your portfolio take?</h2>
<p>The government assumed about 10 minutes a property; Lord Fuller told the Lords that letting professionals had not yet finished one in under 20. Enter how many homes you let (count each flat, not each HMO room).</p>
<form class="est" id="est" onsubmit="return false">
<label>Homes you let <input class="dl-sel" id="n" type="number" min="1" max="100000" value="3" inputmode="numeric"></label>
</form>
<p id="est-out" aria-live="polite"></p>
<p style="margin-bottom:0"><a class="btn" href="../#check">Check every property is ready</a> <span class="mut">Free, two minutes, no account. It lists each property's details and certificate dates in one place, so each entry is copy and paste.</span></p>
</section>

<h2>Where the regulations are now</h2>
<p>The Commons committee approved the draft regulations on 28 October by 11 votes to 6 and the Lords Grand Committee considered them the same day. The full House of Lords approved them on <a href="__LORDS_VOTE__" rel="noopener">4 November 2026</a>; the Commons decision was deferred to a vote on 4 November. <a href="landlord-database-regulations-status.html">The live status page</a> shows the result as soon as Parliament publishes it. Ministers said a second set of regulations, after the rollout, will decide what the public can see.</p>

<h2>Questions</h2>
__FAQ_HTML__
<h2 id="sources">Sources</h2>
<ul class="mut">
<li><a href="__COMMONS__" rel="noopener">Hansard: Fourth Delegated Legislation Committee, Draft Private Rented Sector Database Regulations 2026</a>, 28 October 2026 (Matthew Pennycook, Minister for Housing and Planning)</li>
<li><a href="__LORDS__" rel="noopener">Hansard: Lords Grand Committee, Private Rented Sector Database Regulations 2026</a>, 28 October 2026 (Baroness Taylor of Stevenage)</li>
<li><a href="__LORDS_VOTE__" rel="noopener">Hansard: House of Lords, motion to approve agreed</a>, 4 November 2026</li>
<li><a href="__GUIDE__">gov.uk: Register your rental property service, guidance for landlords</a> (29 October 2026)</li>
</ul>
<p class="mut">The answers are our plain-English summaries of what was said; follow the links for the exact words. Contains Parliamentary information licensed under the Open Parliament Licence v3.0. Not legal advice. Last checked __REVIEWED__.</p>
<script>
(function(){
var n=document.getElementById("n"),o=document.getElementById("est-out");
function h(m){var x=m/60;return x<1?Math.round(m)+" minutes":(x<10?x.toFixed(1).replace(/\\.0$/,""):Math.round(x).toLocaleString("en-GB"))+(x===1?" hour":" hours");}
function go(){var k=Math.max(1,Math.min(100000,Math.floor(+n.value||1)));
 var days=k*20/60/7.5;
 o.innerHTML="<b>"+h(k*10)+" to "+h(k*20)+"</b> of data entry for "+k.toLocaleString("en-GB")+" home"+(k>1?"s":"")+
 (days>=1?" (about "+Math.ceil(days).toLocaleString("en-GB")+" working day"+(Math.ceil(days)>1?"s":"")+" at the slower rate)":"")+
 ", and <b>£"+(k*65).toLocaleString("en-GB")+" a year</b> in fees from 15 December 2027 (<a href=\\"landlord-database-fee.html#first-payment\\">first payment</a> is far smaller).";}
n.addEventListener("input",go);go();
})();
</script>
__FOOTER__"""


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT.relative_to(ROOT))

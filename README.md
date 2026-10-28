# rentready

**Is your rental ready for England's landlord database?**

From 15 December 2026 every private landlord in England must register each let property on the government's
"Register your rental property" service (Renters' Rights Act 2025), region by region, at **£65 per property per year**,
uploading the gas safety record, EICR and EPC. Unoccupied properties need not be registered yet, and landlords of supported
exempt accommodation are excluded ([official guidance](https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/)). Without an active entry the court cannot make a possession
order, except on Ground 7A or Ground 14 ([section 90](https://www.legislation.gov.uk/ukpga/2025/26/section/90)). Penalties are up to £7,000 for a breach
([section 91](https://www.legislation.gov.uk/ukpga/2025/26/section/91)) and up to £40,000 for the offences in [section 92](https://www.legislation.gov.uk/ukpga/2025/26/section/92): false information, continuing a breach
after a penalty, or a repeat within five years. `rentready` tells you your region's window and deadline, whether
your certificates will still be in date, what to book, what to upload and what it costs. Zero dependencies, one file,
also an MCP server and a Claude Code plugin, so your own agent can run it.

**No install: check in your browser at https://genzagents.github.io/rentready/** (0.7.0: now with the registration pack). Add your properties or
paste a CSV, see every property's window, deadline and certificate state, then download one `.ics` with every date and
reminder. It runs `docs/rentready.js`, a line-for-line port of the Python that `tests/test_web.py` holds to identical
answers and an identical calendar on five dates; the only network call is the postcode lookup at postcodes.io, and
your list stays in your browser.

```bash
curl -sL https://raw.githubusercontent.com/genzagents/rentready/main/rentready/__init__.py | python3 - check "B3 2TA" --gas=2026-02-01 --eicr=2023-06-01 --eicr-due=2028-06-01 --epc=2017-05-01 --epc-rating=D
```

```
rentready 0.8.1  B3 2TA  region: West Midlands
Window: requirement starts 2026-12-15, deadline 2027-03-14 (137 days from 2026-10-28); the service opens for everyone on 2026-12-15
  PASS registration deadline: West Midlands requirement starts 2026-12-15, deadline 2027-03-14; you can register from 2026-12-15
  WARN gas safety record: expires 2027-02-01, before the 2027-03-14 deadline (96 days)
  PASS EICR: valid to 2028-06-01
  PASS EPC: valid to 2027-05-01
  INFO EPC rating: rating D meets today's E minimum; it would not meet the C minimum set for all tenancies from 1 October 2030 (government response, 21 Jan 2026; not yet law)
Do next:
  - Book before 2027-02-01: annual gas safety check by a Gas Safe engineer; upload the record and issue date
Fee: £65 a year (65 per property); renewal every 12 months: the renewal date is the last day of the 12 months from your first entry, one date for the whole portfolio (draft regulation 10); later properties pay pro rata
Upload at registration (within 28 days of the entry, or it becomes inactive):
  - Latest gas safety record (CP12) and its issue date, if the property has gas
  - EICR (or EIC if no EICR yet) and its expiry date
  - Latest EPC, and any MEES exemption; if the EPC has lapsed, the start date of the current tenancy
READY: nothing expires before your deadline. Gather the details above and register when your window opens.
```

## The timetable

| Region | Requirement starts | Deadline (midnight) |
|---|---|---|
| West Midlands | 15 Dec 2026 | 14 Mar 2027 |
| East of England | 15 Jan 2027 | 14 Apr 2027 |
| East Midlands | 15 Feb 2027 | 14 May 2027 |
| South East | 15 Mar 2027 | 14 Jun 2027 |
| Yorkshire and Humber | 15 Apr 2027 | 14 Jul 2027 |
| North West | 15 May 2027 | 14 Aug 2027 |
| North East | 15 Jun 2027 | 14 Sep 2027 |
| London | 15 Jul 2027 | 14 Oct 2027 |
| South West | 15 Aug 2027 | 14 Nov 2027 |

Registration opens for all of England on 15 December 2026. Source: the draft
[Private Rented Sector Database Regulations 2026](https://www.legislation.gov.uk/ukdsi/2026/9780348286861), laid before Parliament on 9 September 2026 and not yet
approved: the Lords Secondary Legislation Scrutiny Committee drew them to the special attention of the House ([13th report](https://publications.parliament.uk/pa/ld5902/ldselect/ldsecleg/68/6803.htm), 22 October 2026)
and committees of both Houses debated them on 28 October 2026 ([Parliament record](https://api.parliament.uk/procedure-browser/work-packages/mNlSJVmc)), as summarised by the [NRLA](https://www.nrla.org.uk/resources/renters-rights/landlord-database-register-your-rental-property-service)
and [HCR Law](https://www.hcrlaw.com/news-and-insights/renters-rights-act-2025-private-rented-sector-database-to-go-live-from-15-december-2026/);
the same dates are in the official guidance at [housinghub.campaign.gov.uk](https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/), which names the region "Yorkshire and Humber".
Upload within 28 days of the entry and one renewal date for every property are in the draft regulations
([regulation 6(2)](https://www.legislation.gov.uk/ukdsi/2026/9780348286861/regulation/6), [regulation 10](https://www.legislation.gov.uk/ukdsi/2026/9780348286861/regulation/10)) and reported by the NRLA; the official guidance
says the fee is pro-rated during the rollout, and the method for later properties is reported by the NRLA. The £65 fee is
from the official guidance; the draft leaves the amount to the database operator ([regulation 14](https://www.legislation.gov.uk/ukdsi/2026/9780348286861/regulation/14)).
Miss the 28-day upload and the entry becomes inactive ([regulation 11(2)(a)](https://www.legislation.gov.uk/ukdsi/2026/9780348286861/regulation/11)); any later change
must be updated within 28 days ([regulation 9(4)](https://www.legislation.gov.uk/ukdsi/2026/9780348286861/regulation/9)). The two 28-day rules and the single renewal date
are not in the official guidance yet. Check gov.uk before relying on a date.

## Install

```bash
pip install git+https://github.com/genzagents/rentready        # or copy rentready/__init__.py anywhere
rentready regions
rentready check "SW1A 1AA" --no-gas --eicr=2024-01-01 --epc=2020-01-01 --properties=3 --json
```

Exit code 0 when nothing fails, 1 otherwise, so it works in a cron or a CI step.

### A whole portfolio from one CSV (0.2.0)

```bash
rentready portfolio properties.csv          # one line per property, every FAIL/WARN, total fee, earliest deadline
rentready portfolio properties.csv --json
```

`properties.csv` has a header row with any of `name, postcode, gas, no_gas, eicr, eicr_due, epc, epc_rating, tenancy_start, region`
(`eicr` is the report's issue date, `eicr_due` the date it gives for the next inspection)
(common spellings like `Address`, `Post Code`, `Gas safety`, `Rating` are accepted; a JSON list of objects works too):

```csv
name,postcode,gas,no_gas,eicr,epc,epc_rating
12 Example St,B3 2TA,2026-02-01,,2023-06-01,2017-05-01,D
Flat 4,SW1A 1AA,,yes,2024-01-01,2020-01-01,C
```

### Dates in your calendar, with reminders (0.2.0)

```bash
rentready calendar properties.csv --out=rentready.ics             # whole portfolio
rentready calendar "B3 2TA" --gas=2026-02-01 --eicr=2023-06-01 --epc=2017-05-01 --out=rentready.ics
rentready calendar properties.csv --reminders=90,30,7 > rentready.ics
```

One all-day event per dated thing: the day your region's window opens, the registration deadline, and each gas safety,
EICR and EPC expiry, each with reminders 60 and 14 days before (change with `--reminders`). Import the file into Google,
Apple or Outlook calendar; UIDs are deterministic, so re-importing after a renewal updates the events instead of duplicating them.
This is the free, serverless version of the monthly watch: nothing is stored anywhere but your own calendar.

### The registration pack (0.5.0; in the browser from 0.7.0)

```bash
rentready pack properties.csv --out=pack.md          # add --organisation for a company or trust
```

No terminal? On https://genzagents.github.io/rentready/ press **Show my registration pack** after a check: the same pack
(docs/rentready.js, parity-tested against pack.py), printable or saved as `registration-pack.md` for your agent. Extra
columns pasted in the CSV are kept with your list in the browser.

Every question *Register your rental property* asks, in the service's own words (gov.uk "Get ready to register", Oct 2026):
you as the landlord once, then per property the dwelling, tenancy, rent and health-and-safety sections. Answers come
pre-filled from the CSV, a GATHER line marks each gap, and the pack tells you which columns to add to fill them
(`ownership, dwelling_type, bedrooms, let, occupants, households, licence, furnished, rent, rent_frequency, bills`,
optional `freeholder, manager`). Each certificate gets a file name to scan it as (`12-example-st_eicr_2023-06-01.pdf`) and
a state: READY, RENEW SOON (expires before your deadline), RENEW (lapsed: renew before you upload) or GATHER. A lapsed EPC
is accepted with the current tenancy's start date, and an F or G rating adds the MEES exemption question. A property is
**ready to register** only when every answer and file is in hand. Nothing registers for you: you start the entry with
GOV.UK One Login.

### Watch

A certificate that lapses in month four is the thing nobody notices until the deadline. The watch is the alarm, and it
runs for free as a GitHub Action in a private repo of yours that holds `properties.csv`: on the first of every month it
re-checks every property, keeps one issue up to date with the full table, and **comments on that issue only when
something needs action**: a gas safety record, EICR or EPC within 60 days of expiring, your region's window opening,
a deadline nearing or passing, or a property no longer ready. GitHub emails the comment to you. No server, no account
beyond GitHub, no dependencies; your dates never leave your repo except for the postcode lookup. Example:
[issue #1](https://github.com/genzagents/rentready/issues/1) watches [`docs/example.csv`](docs/example.csv).

Copy [`docs/watch.yml`](docs/watch.yml) to `.github/workflows/rentready-watch.yml`:

```yaml
on:
  schedule: [{ cron: "23 7 1 * *" }]   # the 1st of each month
  workflow_dispatch:
  push: { paths: [properties.csv] }
permissions: { issues: write, contents: read }
jobs:
  watch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: genzagents/rentready@v0.8.1
        with:
          portfolio: properties.csv
          # warn-days: 90
          # always-comment: "true"    # a monthly "all fine" email too
```

The same command runs from cron on your own machine with a local state file instead of an issue:

```bash
rentready watch properties.csv --state=rentready-state.json      # exit 1 when something needs action
```

### As an MCP server / Claude Code plugin

```bash
claude plugin marketplace add genzagents/marketplace
claude plugin install rentready@genzagents
```

Or add to any MCP client: `uvx rentready mcp` (from PyPI) or `python3 /path/to/rentready/__init__.py mcp` (stdio). Four tools: `check_property`, `check_portfolio` (CSV or JSON text in, one table out), `make_calendar` (returns the .ics text for one property or a portfolio) and `registration_pack` (the markdown checklist above).

Listed in the [official MCP registry](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.genzagents/rentready) as `io.github.genzagents/rentready`.

mcp-name: io.github.genzagents/rentready

## What it checks

- Region from the postcode (postcodes.io, no key; `--region=` to skip the lookup). Wales and Scotland are flagged out of scope.
- Registration window and deadline for that region; whether it is open, upcoming or missed.
- Gas safety record (annual), EICR, EPC (ten-yearly): valid at the deadline, expiring before it, expired, or missing.
- EICR: the law requires an inspection at least every 5 years, or by an earlier date if the last report says so
  ([SI 2020/312, regulation 3(2)](https://www.legislation.gov.uk/uksi/2020/312/regulation/3)), and the service asks for the report's expiry date.
  Give the report's next-inspection date (`--eicr-due`, CSV column `eicr_due`) and rentready uses it; with only the
  issue date it assumes 5 years and says so in the result.
- EPC rating against the current E minimum and the C minimum for all tenancies from 1 October 2030
  ([government response, 21 Jan 2026](https://www.gov.uk/government/consultations/improving-the-energy-performance-of-privately-rented-homes-2025-update/outcome/improving-the-energy-performance-of-privately-rented-homes-government-response-html); not yet law).
- The fee for N properties, the renewal rule, the full list of details the service asks for, and the penalties.

### Hosted monthly watch (0.4.0)

The paid step for landlords who do not want a GitHub repo: pay once a year, paste your properties into the checkout,
and get the same alerts in your inbox. The runner is in this repo and needs no server:

```bash
rentready hosted run --dry-run        # polls Polar for subscribers, prints every email it would send
rentready hosted run                  # sends through Resend: first report within the hour, alerts on change, a monthly digest
rentready hosted replay ~/.rentready-hosted/<id>.json   # re-runs a stored report from its stored inputs: IDENTICAL or DIFFERENT
```

Every email is reproducible from the inputs and date stored beside it. Setup and prices: [docs/HOSTED.md](docs/HOSTED.md).
Letting agents can run it for their landlords from a file with `--subscribers=subs.json`, no payment provider needed.

## What it does not do

It does not register for you, fetch certificates, or hold any data. It never sends your dates anywhere. Not legal advice.

## Privacy

The check runs on your machine or, on the website, in your browser. The one network call sends the postcode (and nothing
else) to [postcodes.io](https://postcodes.io/) to find the region, so postcodes.io sees that postcode and your IP address;
pass `--region=` to skip it. The website is hosted on GitHub Pages, which may log visitors' IP addresses; it sets no
cookies and runs no analytics. Details: [privacy](https://genzagents.github.io/rentready/privacy.html). Made by
GenZAgents, London ([about](https://genzagents.github.io/rentready/about.html)); questions and corrections via
[GitHub issues](https://github.com/genzagents/rentready/issues).

## Changes

**0.8.1** (packaging only, no behaviour change)
- Listed in the official MCP registry as `io.github.genzagents/rentready` (`server.json`, published from GitHub Actions
  with GitHub OIDC); the README carries the registry's `mcp-name` ownership line. `uvx rentready mcp` runs the server.

**0.8.0** (EICR correctness)
- EICR expiry comes from the report's own next-inspection date when you give it (`--eicr-due`, CSV `eicr_due`, MCP
  `eicr_due`, a column in the browser), capped at 5 years from issue. Before, a report recommending 3 years got a false
  PASS because expiry was always issue date + 5 years. Issue + 5 years is now only a fallback, labelled as an assumption
  in the finding, in `assumptions`, and in the registration pack. Same logic in Python, the browser and the MCP server
  (parity-tested).

**0.7.1** (accuracy fixes, no new features)
- EPC: the C minimum applies to all private tenancies from 1 October 2030; the government dropped the proposed 2028 date
  for new tenancies ([government response, 21 Jan 2026](https://www.gov.uk/government/consultations/improving-the-energy-performance-of-privately-rented-homes-2025-update/outcome/improving-the-energy-performance-of-privately-rented-homes-government-response-html); not yet law).
- Penalties: up to £40,000 covers the [section 92](https://www.legislation.gov.uk/ukpga/2025/26/section/92) offences (false information, continuing a breach after a
  penalty, a repeat within five years), not only repeats; no possession order without an active entry except on
  Ground 7A or Ground 14 ([section 90](https://www.legislation.gov.uk/ukpga/2025/26/section/90)).
- Renewal: the last day of the 12 months from your first entry ([draft regulation 10](https://www.legislation.gov.uk/ukdsi/2026/9780348286861/regulation/10)); the program text now
  says the regulations are a draft (laid 9 September 2026, not yet approved).

## Roadmap

`rentready calendar` puts every date in your calendar and `rentready watch` emails you from GitHub when something needs action, both free. The hosted monthly watch (no repo, no CSV to keep, the same alerts to your inbox) is the
paid step, £12 a year for up to 10 properties; the runner shipped in 0.4.0 and the checkout opens when payments are set up. EPC lookup by address from the official open-data register is next (the register's API moved to get-energy-performance-data.communities.gov.uk in 2026 and needs a free key). Press the button on the [project page](https://genzagents.github.io/rentready/) if you want it.

MIT. Built by [genzagents](https://github.com/genzagents); sibling of [citable](https://github.com/genzagents/citable).

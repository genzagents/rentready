# rentready

**Is your rental ready for England's landlord database?**

From 15 December 2026 every private landlord in England must register each property on the government's
"Register your rental property" service (Renters' Rights Act 2025), region by region, at **£65 per property per year**,
uploading the gas safety record, EICR and EPC. Without an active entry there is no possession order from the court,
and penalties run to £7,000 (£40,000 for a repeat). `rentready` tells you your region's window and deadline, whether
your certificates will still be in date, what to book, what to upload and what it costs. Zero dependencies, one file,
also an MCP server and a Claude Code plugin, so your own agent can run it.

```bash
curl -sL https://raw.githubusercontent.com/genzagents/rentready/main/rentready/__init__.py | python3 - check "B3 2TA" --gas=2026-02-01 --eicr=2023-06-01 --epc=2017-05-01 --epc-rating=D
```

```
rentready 0.3.0  B3 2TA  region: West Midlands
Window: requirement starts 2026-12-15, deadline 2027-03-14 (139 days from 2026-10-26); the service opens for everyone on 2026-12-15
  PASS registration deadline: West Midlands requirement starts 2026-12-15, deadline 2027-03-14; you can register from 2026-12-15
  WARN gas safety record: expires 2027-02-01, before the 2027-03-14 deadline (98 days)
  PASS EICR: valid to 2028-06-01
  PASS EPC: valid to 2027-05-01
  INFO EPC rating: rating D meets today's E minimum; the proposed C minimum for new tenancies from 2028 and all tenancies from 2030 would not be met
Do next:
  - Book before 2027-02-01: annual gas safety check by a Gas Safe engineer; upload the record and issue date
Fee: £65 a year (65 per property); renewal annual, on the anniversary of the first property registered (one date for the whole portfolio); later properties pay pro rata
Upload at registration (within 28 days of the entry):
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
| Yorkshire and The Humber | 15 Apr 2027 | 14 Jul 2027 |
| North West | 15 May 2027 | 14 Aug 2027 |
| North East | 15 Jun 2027 | 14 Sep 2027 |
| London | 15 Jul 2027 | 14 Oct 2027 |
| South West | 15 Aug 2027 | 14 Nov 2027 |

Registration opens for all of England on 15 December 2026. Source: the Private Rented Sector Database Regulations 2026 as
summarised by the [NRLA](https://www.nrla.org.uk/resources/renters-rights/landlord-database-register-your-rental-property-service.)
and [HCR Law](https://www.hcrlaw.com/news-and-insights/renters-rights-act-2025-private-rented-sector-database-to-go-live-from-15-december-2026/);
official guidance at [housinghub.campaign.gov.uk](https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/). Check gov.uk before relying on a date.

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

`properties.csv` has a header row with any of `name, postcode, gas, no_gas, eicr, epc, epc_rating, tenancy_start, region`
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
      - uses: genzagents/rentready@v0.3.0
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

Or add to any MCP client: `python3 /path/to/rentready/__init__.py mcp` (stdio). Three tools: `check_property`, `check_portfolio` (CSV or JSON text in, one table out) and `make_calendar` (returns the .ics text for one property or a portfolio).

## What it checks

- Region from the postcode (postcodes.io, no key; `--region=` to skip the lookup). Wales and Scotland are flagged out of scope.
- Registration window and deadline for that region; whether it is open, upcoming or missed.
- Gas safety record (annual), EICR (five-yearly), EPC (ten-yearly): valid at the deadline, expiring before it, expired, or missing.
- EPC rating against the current E minimum and the proposed C minimum.
- The fee for N properties, the renewal rule, the full list of details the service asks for, and the penalties.

## What it does not do

It does not register for you, fetch certificates, or hold any data. It never sends your dates anywhere; the only network call
is the postcode lookup. Not legal advice.

## Roadmap

`rentready calendar` puts every date in your calendar and `rentready watch` emails you from GitHub when something needs action, both free. A hosted monthly watch (no repo, no CSV to keep, the same alerts to your inbox) is the
paid step, a few pounds a year. EPC lookup by address from the official open-data register is next (the register's API moved to get-energy-performance-data.communities.gov.uk in 2026 and needs a free key). Press the button on the [project page](https://genzagents.github.io/rentready/) if you want it.

MIT. Built by [genzagents](https://github.com/genzagents); sibling of [citable](https://github.com/genzagents/citable).

---
name: rentready
description: Use when a landlord or letting agent in England asks about the landlord database, "Register your rental property", the Renters' Rights Act register, the £65 fee, when their region must register, or whether their gas safety record, EICR or EPC are in date for it. Runs the rentready check and turns it into dated actions.
---

# rentready

England's private rented sector database opens on 15 December 2026 and each region gets a three-month window
(West Midlands first, deadline 14 March 2027; London 15 July to 14 October 2027; South West last, 14 November 2027).
Every property costs £65 a year. Gas safety record, EICR and EPC are uploaded, and a landlord without an active
entry cannot get a possession order and faces penalties up to £7,000 (£40,000 repeat).

## How to run it

- If the `rentready` MCP server is available, call `check_property` with the postcode and the certificate dates you know.
  For several properties, call `check_portfolio` with CSV text (header: name, postcode, gas, no_gas, eicr, epc, epc_rating).
  When the landlord wants reminders, call `make_calendar` (same inputs) and save the returned text as `rentready.ics` for them
  to import into Google, Apple or Outlook calendar; it holds the window-opens day, the deadline and every certificate expiry with 60- and 14-day alarms.
  When the landlord is getting ready to register, call `registration_pack` with the portfolio (and `organisation: true` for a
  company or trust): it returns every question the service asks, pre-filled where the CSV has the answer, GATHER where not,
  and the files to scan. Ask the landlord for the GATHER answers, add them as columns, and call it again until each
  property says ready to register. Never fill in the landlord's date of birth or identity details yourself.
- Otherwise from the shell (no install, Python 3.9+):

  ```bash
  curl -sL https://raw.githubusercontent.com/genzagents/rentready/main/rentready/__init__.py | python3 - check "B3 2TA" --gas=2026-02-01 --eicr=2023-06-01 --epc=2017-05-01 --epc-rating=D
  ```

  `rentready regions` prints the timetable. `rentready watch properties.csv --state=FILE` re-checks a portfolio and
  prints ALERT lines only for what changed since the last run (certificate within 60 days of expiry, window opened,
  deadline near or passed, property no longer ready); as a GitHub Action (`uses: genzagents/rentready@v0.6.0`) it
  keeps an issue and emails the landlord through issue comments. Offer it when the landlord wants reminders without a calendar. `rentready hosted` is the paid no-repo version (Polar subscribers, email via Resend, `replay` reproduces any stored report); only mention it if the landlord asks for a service rather than a tool. `--no-gas` for a property without gas. `--properties=N` for the fee.
  `rentready portfolio properties.csv` for many properties; `rentready calendar properties.csv --out=rentready.ics` for the reminders file.

## How to read the result

1. The **window** line says when the region's requirement starts and the deadline. Registration itself opens for all
   of England on 15 December 2026; registering early fixes the portfolio's renewal date, so say so.
2. **FAIL** on a certificate means it is missing or expired: book the check now, it must be uploaded.
3. **WARN** means it expires before the deadline: book it for before that date so the uploaded record is in date.
4. Ask for anything you do not know (dates, whether there is gas, EPC rating) rather than guessing; re-run with the answers.
5. Always add: each joint landlord needs their own entry, an agent cannot register for the landlord, and all details
   are due within 28 days of creating the entry. Point to https://housinghub.campaign.gov.uk/renting-is-changing/get-ready-to-register/
   and https://www.nrla.org.uk/resources/renters-rights/landlord-database-register-your-rental-property-service.

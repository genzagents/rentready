# rentready hosted: how the paid monthly watch runs

No server. One always-on machine runs `rentready hosted run` once an hour. Everything else is Polar (payments,
checkout form, receipts, VAT) and Resend (email delivery). It is the same runner shape as citable's, so one machine
and the same two accounts serve both products.

## What a subscriber sees

1. Pays on the Polar checkout. The checkout asks for one custom field: their portfolio, one property per line
   (name, postcode, gas safety date, EICR date, EPC date, EPC rating), or the same CSV `rentready portfolio` reads.
2. Within the hour: "Your first rentready report", the whole table (region, deadline, READY or not, the next dated
   thing per property), what needs attention, the fee.
3. Then: an email the moment something needs action (a gas safety record, EICR or EPC within 60 days of expiring,
   their region's window opening, a deadline nearing or passing, a property no longer ready) and a short digest once
   a month otherwise, so they know it is still watching. Improvements are reported too.
4. Replies reach the sender address; cancellation is on the Polar receipt. Nobody is in the loop.

Every email is reproducible. The state file keeps the exact inputs (with the region the postcode lookup found), the
date, the version and the report. `rentready hosted replay ~/.rentready-hosted/<id>.json` re-runs the check offline
and says IDENTICAL or DIFFERENT. If a landlord or a tribunal asks why they were told something on a given day, the
answer is one command, not a memory.

## Price

£12 a year for up to 10 properties; a second product at £36 a year for up to 50 (set `RENTREADY_PRODUCT_LIMITS`).
The register itself costs £65 a property a year; the incumbents charge £8 to £25 a month for a web app. Fixed and
yearly, never per use.

## One-time setup (about 10 minutes, needs the Polar and Resend accounts)

### Polar

1. Create a product: "rentready monthly watch", recurring, £12/year. Description: the bullets above.
2. Checkout custom field (Settings -> Custom fields, then enable it on the product). The runner reads it from
   `custom_field_data` on each subscription, keyed by slug:

   | Slug | Type | Required | Label shown at checkout |
   |---|---|---|---|
   | `portfolio` | textarea | yes | Your properties, one per line: name, postcode, gas safety date, EICR date, EPC date, EPC rating. Use - for a date you do not have and "no gas" for an all-electric property. |

   Slugs `properties`, `csv`, `property` and `rentals` also work.
3. Create an organisation access token with `subscriptions:read` (Settings -> Access tokens). Copy the product id.
   If the citable product lives in the same organisation, the same token serves both; set `POLAR_PRODUCT_ID` on each
   runner so neither sees the other's subscribers.
4. Put the checkout link on the page: replace the "I want the monthly watch" button in `docs/index.html`.

### Resend

Same account as citable: one API key with sending permission; a verified sending domain when there is one.

### The machine

```bash
export POLAR_ACCESS_TOKEN=polar_oat_...      # subscriptions:read
export POLAR_PRODUCT_ID=...                  # the rentready product
export RESEND_API_KEY=re_...
export RENTREADY_FROM="rentready <watch@yourdomain.com>"
rentready hosted run --dry-run               # prints what it would send; sends nothing
rentready hosted run                         # sends
rentready hosted launchd > ~/Library/LaunchAgents/io.genzagents.rentready.hosted.plist   # then add the secrets to the plist
launchctl load -w ~/Library/LaunchAgents/io.genzagents.rentready.hosted.plist
```

Secrets live in the plist's `EnvironmentVariables` (or a wrapper script that reads the keychain), never in the repo.
State lives in `~/.rentready-hosted/<subscription id>.json`. Delete a file to resend a first report.

## Costs per subscriber per month

- Checks: one postcode lookup per property on the first run, none after (the region is stored). Free.
- Polar: 4% + 40c per payment, VAT handled. Resend: free tier covers thousands of emails.

So the £12 is almost entirely margin and the only operational task is keeping the machine on.

## Running it for your own landlords

`rentready hosted run --subscribers=subs.json` skips Polar and reads a list of `{id, status, customer: {email, name},
custom_field_data: {portfolio}}` objects (the shape Polar returns), so a letting agent can run the watch for every
landlord they manage from one file without any payment provider.

// rentready in the browser: the same check, portfolio and calendar as rentready/__init__.py, line for line.
// Runs on the page with no server; the only network call is the postcode lookup at postcodes.io.
// tests/test_web.py runs this file under node and compares its output with the Python's.
(function (root) {
  "use strict";
  const VERSION = "0.6.0";
  const FEE_PER_PROPERTY_GBP = 65;
  const ROLLOUT = {
    "West Midlands": { opens: "2026-12-15", deadline: "2027-03-14" },
    "East of England": { opens: "2027-01-15", deadline: "2027-04-14" },
    "East Midlands": { opens: "2027-02-15", deadline: "2027-05-14" },
    "South East": { opens: "2027-03-15", deadline: "2027-06-14" },
    "Yorkshire and The Humber": { opens: "2027-04-15", deadline: "2027-07-14" },
    "North West": { opens: "2027-05-15", deadline: "2027-08-14" },
    "North East": { opens: "2027-06-15", deadline: "2027-09-14" },
    "London": { opens: "2027-07-15", deadline: "2027-10-14" },
    "South West": { opens: "2027-08-15", deadline: "2027-11-14" },
  };
  const REGION_ALIASES = { "yorkshire and humber": "Yorkshire and The Humber", "yorkshire": "Yorkshire and The Humber",
    "east": "East of England", "greater london": "London" };
  const UPLOADS = [
    "Latest gas safety record (CP12) and its issue date, if the property has gas",
    "EICR (or EIC if no EICR yet) and its expiry date",
    "Latest EPC, and any MEES exemption; if the EPC has lapsed, the start date of the current tenancy",
  ];
  const RENEWAL = "annual, on the anniversary of the first property registered (one date for the whole portfolio); later properties pay pro rata";

  // Dates are YYYY-MM-DD strings; arithmetic in UTC days so time zones never move a date.
  const DAY = 86400000;
  function ms(iso) { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d); }
  function iso(t) { return new Date(t).toISOString().slice(0, 10); }
  function days(a, b) { return Math.round((ms(b) - ms(a)) / DAY); }
  function addYears(s, n) {
    const [y, m, d] = s.split("-").map(Number);
    const dd = (m === 2 && d === 29) ? 28 : d;
    return `${String(y + n).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
  }
  function todayLocal() { const n = new Date(); return iso(Date.UTC(n.getFullYear(), n.getMonth(), n.getDate())); }
  function validDate(s) { return /^\d{4}-\d{2}-\d{2}$/.test(s || "") && iso(ms(s)) === s; }

  function normaliseRegion(region) {
    if (!region) return null;
    const r = String(region).trim();
    if (ROLLOUT[r]) return r;
    const low = r.toLowerCase();
    if (REGION_ALIASES[low]) return REGION_ALIASES[low];
    for (const k of Object.keys(ROLLOUT)) if (k.toLowerCase() === low) return k;
    return null;
  }

  async function lookupRegion(postcode) {
    try {
      const r = await fetch("https://api.postcodes.io/postcodes/" + encodeURIComponent(postcode.trim()));
      if (!r.ok) return { error: `postcode lookup failed: HTTP ${r.status}` };
      const res = (await r.json()).result || {};
      return { postcode: res.postcode || postcode, region: res.region, country: res.country };
    } catch (e) {
      return { error: `postcode lookup failed: ${e.name}: ${e.message}` };
    }
  }

  // check_property with the lookup already done: lk is {region, country, postcode} or {error} or null.
  function checkProperty(postcode, o) {
    const t = o.today || todayLocal();
    const out = { version: VERSION, today: t, postcode: postcode || null, findings: [], actions: [],
      fee_gbp_per_year: FEE_PER_PROPERTY_GBP * Math.max(1, o.properties || 1) };
    let reg = normaliseRegion(o.region);
    let country = null;
    if (!reg && postcode && o.lookup) {
      const lk = o.lookup;
      if (lk.error) {
        out.findings.push({ status: "WARN", check: "region", detail: lk.error + "; pass --region to continue" });
      } else {
        country = lk.country || null;
        reg = normaliseRegion(lk.region);
        out.postcode = lk.postcode || null;
      }
    }
    out.region = reg;
    if (country && country !== "England") {
      out.findings.push({ status: "INFO", check: "scope", detail: `${country}: the England database does not apply; Wales and Scotland have their own landlord registration schemes` });
      out.ready = null;
      return out;
    }
    if (!reg) {
      out.findings.push({ status: "FAIL", check: "region", detail: "region unknown; registration window cannot be computed" });
      out.ready = false;
      return out;
    }
    const opens = ROLLOUT[reg].opens, deadline = ROLLOUT[reg].deadline;
    out.window = { opens, deadline, days_to_deadline: days(t, deadline), service_opens_everywhere: "2026-12-15" };
    if (t > deadline) {
      out.findings.push({ status: "FAIL", check: "registration deadline", detail: `${reg} deadline ${deadline} has passed; register now, penalties up to £7,000 and no possession orders apply` });
    } else if (t >= opens) {
      out.findings.push({ status: "WARN", check: "registration deadline", detail: `${reg} window is open: register by ${deadline} (${days(t, deadline)} days)` });
    } else {
      out.findings.push({ status: "PASS", check: "registration deadline", detail: `${reg} requirement starts ${opens}, deadline ${deadline}; you can register from 2026-12-15` });
    }
    function cert(name, issued, years, missingMsg, what) {
      if (!issued) {
        out.findings.push({ status: "FAIL", check: name, detail: missingMsg });
        out.actions.push(what);
        return;
      }
      const expiry = addYears(issued, years);
      (out.expiries = out.expiries || {})[name] = expiry;
      if (expiry <= t) {
        out.findings.push({ status: "FAIL", check: name, detail: `expired ${expiry}` });
        out.actions.push(`Renew now: ${what}`);
      } else if (expiry <= deadline) {
        out.findings.push({ status: "WARN", check: name, detail: `expires ${expiry}, before the ${deadline} deadline (${days(t, expiry)} days)` });
        out.actions.push(`Book before ${expiry}: ${what}`);
      } else {
        out.findings.push({ status: "PASS", check: name, detail: `valid to ${expiry}` });
      }
    }
    if (o.no_gas) {
      out.findings.push({ status: "PASS", check: "gas safety record", detail: "no gas supply declared; not required" });
    } else {
      cert("gas safety record", o.gas, 1, "no gas safety record date given (annual CP12 is required and uploaded)", "annual gas safety check by a Gas Safe engineer; upload the record and issue date");
    }
    cert("EICR", o.eicr, 5, "no EICR date given (five-yearly report is required and uploaded with its expiry)", "EICR by a qualified electrician; upload the report and expiry date");
    cert("EPC", o.epc, 10, "no EPC date given (upload the latest EPC; if lapsed, give the current tenancy start date)", "EPC assessment; upload the certificate");
    if (o.epc && o.epc_rating) {
      const r = o.epc_rating.trim().toUpperCase().slice(0, 1);
      if (r === "F" || r === "G") {
        out.findings.push({ status: "FAIL", check: "EPC rating", detail: `rating ${r} is below the current E minimum (MEES); register an exemption or improve` });
      } else if (r === "D" || r === "E") {
        out.findings.push({ status: "INFO", check: "EPC rating", detail: `rating ${r} meets today's E minimum; the proposed C minimum for new tenancies from 2028 and all tenancies from 2030 would not be met` });
      } else {
        out.findings.push({ status: "PASS", check: "EPC rating", detail: `rating ${r}` });
      }
    }
    if (o.tenancy_start) out.tenancy_start = o.tenancy_start;
    out.uploads = UPLOADS;
    out.renewal = RENEWAL;
    out.ready = !out.findings.some(f => f.status === "FAIL");
    return out;
  }

  const COLUMN_ALIASES = { "address": "name", "property": "name", "label": "name", "post_code": "postcode", "post code": "postcode",
    "gas_date": "gas", "gas safety": "gas", "gas_safety": "gas", "cp12": "gas", "eicr_date": "eicr",
    "epc_date": "epc", "epc rating": "epc_rating", "rating": "epc_rating", "tenancy": "tenancy_start",
    "tenancy start": "tenancy_start", "no gas": "no_gas", "nogas": "no_gas" };
  function normCol(c) {
    c = (c || "").trim().toLowerCase().replace(/-/g, "_");
    return COLUMN_ALIASES[c] || c.replace(/ /g, "_");
  }
  function parseCsv(text) {
    const rows = []; let row = [], f = "", q = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (q) {
        if (c === '"' && text[i + 1] === '"') { f += '"'; i++; } else if (c === '"') q = false; else f += c;
      } else if (c === '"') q = true;
      else if (c === ",") { row.push(f); f = ""; }
      else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(f); rows.push(row); row = []; f = ""; }
      else f += c;
    }
    if (f !== "" || row.length) { row.push(f); rows.push(row); }
    return rows;
  }
  function readPortfolio(text) {
    text = text.replace(/^\ufeff/, "");
    if (text.trimStart().startsWith("[")) {
      return JSON.parse(text).map(r => Object.fromEntries(Object.entries(r).map(([k, v]) => [normCol(k), v == null ? "" : String(v)])));
    }
    const rows = parseCsv(text).filter(r => r.length > 1 || (r[0] || "").trim());
    if (!rows.length) return [];
    const head = rows[0].map(normCol);
    const out = [];
    for (const r of rows.slice(1)) {
      const row = {};
      head.forEach((h, i) => { row[h] = (r[i] || "").trim(); });
      if (Object.values(row).some(v => v)) out.push(row);
    }
    return out;
  }
  function truthy(v) { return ["1", "true", "yes", "y", "x"].includes(String(v || "").trim().toLowerCase()); }

  function nextDate(r) {
    const t = r.today;
    let c = Object.entries(r.expiries || {}).map(([name, d]) => [d, `${name} expires`]);
    const w = r.window;
    if (w) {
      if (w.opens >= t) c.push([w.opens, "registration window opens"]);
      c.push([w.deadline, "registration deadline"]);
    }
    const future = c.filter(x => x[0] >= t);
    c = future.length ? future : c;
    if (!c.length) return null;
    c.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    return { date: c[0][0], what: c[0][1], days: days(t, c[0][0]) };
  }

  // check_portfolio. lookup is async postcode -> {region, country, postcode} | {error}; injected so tests run offline.
  async function checkPortfolio(rows, today, lookup) {
    const t = today || todayLocal();
    lookup = lookup || lookupRegion;
    const props = [], cache = {};
    for (let i = 0; i < rows.length; i++) {
      const row = rows[i];
      const pc = (row.postcode || "").trim();
      let region = row.region || null;
      const key = pc.toUpperCase().replace(/ /g, "");
      if (pc && !region) {
        if (!(key in cache)) cache[key] = await lookup(pc);
        const lk = cache[key];
        if (!lk.error) {
          region = lk.region;
          if (lk.country && lk.country !== "England") region = null;
        }
      }
      // Python's check_property looks the postcode up again when region is still empty; same cached answer here.
      const lk2 = (pc && !normaliseRegion(region)) ? (cache[key] || await lookup(pc)) : null;
      const r = checkProperty(pc, { region, lookup: lk2, gas: row.gas || null, no_gas: truthy(row.no_gas), eicr: row.eicr || null,
        epc: row.epc || null, epc_rating: row.epc_rating || null, tenancy_start: row.tenancy_start || null, properties: 1, today: t });
      if (pc && !region && !row.region) {
        const lk = cache[key] || {};
        if (lk.country && lk.country !== "England") {
          r.findings = [{ status: "INFO", check: "scope", detail: `${lk.country}: the England database does not apply` }];
          r.ready = null;
        }
      }
      r.name = row.name || pc || `property ${i + 1}`;
      r.next = nextDate(r);
      props.push(r);
    }
    const inScope = props.filter(p => p.ready !== null && p.ready !== undefined);
    const deadlines = inScope.filter(p => p.window).map(p => p.window.deadline).sort();
    return { version: VERSION, today: t, properties: props, count: props.length, in_scope: inScope.length,
      fee_gbp_per_year: FEE_PER_PROPERTY_GBP * inScope.length, earliest_deadline: deadlines[0] || null,
      ready: inScope.filter(p => p.ready === true).length, not_ready: inScope.filter(p => p.ready === false).length, renewal: RENEWAL };
  }

  function calendarEvents(reports) {
    const ev = [];
    for (const r of reports) {
      const name = r.name || r.postcode || "property";
      const w = r.window;
      if (w) {
        ev.push({ date: w.opens, summary: `Landlord database: register ${name} (window opens)`,
          description: `${r.region}: the registration requirement starts today; register at gov.uk Register your rental property. Deadline ${w.deadline}. Fee £${FEE_PER_PROPERTY_GBP} per property per year. Upload: ` + UPLOADS.join("; "), property: name, kind: "opens" });
        ev.push({ date: w.deadline, summary: `Landlord database DEADLINE: ${name}`,
          description: `${r.region}: last day to register. After this: up to £7,000 penalty, no possession order.`, property: name, kind: "deadline" });
      }
      for (const [c, d] of Object.entries(r.expiries || {})) {
        const what = { "gas safety record": "book the annual Gas Safe check before this date and upload the new CP12",
          "EICR": "book an electrician for the five-yearly EICR before this date and upload the new report",
          "EPC": "book an EPC assessment before this date and upload the new certificate" }[c] || "renew before this date";
        ev.push({ date: d, summary: `${c} expires: ${name}`, description: `${what}. Update the property entry on the database within 28 days.`, property: name, kind: c });
      }
    }
    const cmp = (a, b) => (a < b ? -1 : a > b ? 1 : 0);
    ev.sort((a, b) => cmp(a.date, b.date) || cmp(a.property, b.property) || cmp(a.summary, b.summary));
    return ev;
  }

  function icsEscape(s) { return s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n"); }
  function icsFold(line) {
    const enc = new TextEncoder(), dec = new TextDecoder();
    let b = enc.encode(line); const out = [];
    while (b.length > 73) {
      let cut = 73;
      while (cut > 0 && (b[cut] & 0xC0) === 0x80) cut--;
      out.push(dec.decode(b.slice(0, cut)));
      const rest = new Uint8Array(b.length - cut + 1); rest[0] = 32; rest.set(b.slice(cut), 1); b = rest;
    }
    out.push(dec.decode(b));
    return out.join("\r\n");
  }
  async function sha1hex(s) {
    const h = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(s));
    return Array.from(new Uint8Array(h)).map(x => x.toString(16).padStart(2, "0")).join("");
  }
  async function formatIcs(events, reminders, stamp) {
    reminders = reminders == null ? [60, 14] : reminders;
    const ds = stamp || new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
    const out = ["BEGIN:VCALENDAR", "VERSION:2.0", `PRODID:-//genzagents//rentready ${VERSION}//EN`, "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH", "X-WR-CALNAME:rentready: landlord database and certificate dates"];
    for (const e of events) {
      const uid = (await sha1hex(`${e.property}|${e.kind}|${e.date}`)).slice(0, 20) + "@rentready";
      out.push("BEGIN:VEVENT", `UID:${uid}`, `DTSTAMP:${ds}`, `DTSTART;VALUE=DATE:${e.date.replace(/-/g, "")}`,
        `DTEND;VALUE=DATE:${iso(ms(e.date) + DAY).replace(/-/g, "")}`,
        `SUMMARY:${icsEscape(e.summary)}`, `DESCRIPTION:${icsEscape(e.description)}`,
        "URL:https://genzagents.github.io/rentready/", "TRANSP:TRANSPARENT");
      for (const n of reminders) {
        out.push("BEGIN:VALARM", "ACTION:DISPLAY", `TRIGGER;VALUE=DURATION:-P${n | 0}D`,
          `DESCRIPTION:${icsEscape(e.summary)} in ${n | 0} days`, "END:VALARM");
      }
      out.push("END:VEVENT");
    }
    out.push("END:VCALENDAR");
    return out.map(icsFold).join("\r\n") + "\r\n";
  }

  const api = { VERSION, ROLLOUT, FEE_PER_PROPERTY_GBP, UPLOADS, normaliseRegion, lookupRegion, checkProperty, readPortfolio,
    checkPortfolio, nextDate, calendarEvents, formatIcs, validDate, todayLocal };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.rentready = api;
})(typeof window !== "undefined" ? window : globalThis);

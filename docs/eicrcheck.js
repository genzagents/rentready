// Is my EICR OK for the landlord database? Runs in the browser on the EICR guide; nothing leaves the page.
// The service asks for a copy of the EICR (or the EIC if there is no EICR yet) and its expiry date (official guidance);
// any outstanding detail can follow within 28 days of the entry. The installation must be inspected at intervals of
// no more than five years, or sooner if the last report says so, and the report gives the date of the next inspection
// (Electrical Safety Standards in the Private Rented Sector (England) Regulations 2020, regulation 3(2) and (3)(a)).
(function (root) {
  "use strict";
  // The same windows as rentready.ROLLOUT (tests/test_eicrcheck.py checks they match).
  var ROLLOUT = [
    ["West Midlands", "2026-12-15", "2027-03-14"],
    ["East of England", "2027-01-15", "2027-04-14"],
    ["East Midlands", "2027-02-15", "2027-05-14"],
    ["South East", "2027-03-15", "2027-06-14"],
    ["Yorkshire and The Humber", "2027-04-15", "2027-07-14"],
    ["North West", "2027-05-15", "2027-08-14"],
    ["North East", "2027-06-15", "2027-09-14"],
    ["London", "2027-07-15", "2027-10-14"],
    ["South West", "2027-08-15", "2027-11-14"]
  ];
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December"];

  function iso(s) { return /^\d{4}-\d{2}-\d{2}$/.test(s || "") ? s : ""; }
  function long(s) { var p = s.split("-"); return +p[2] + " " + MONTHS[+p[1] - 1] + " " + p[0]; }
  function fmt(d) { return d.toISOString().slice(0, 10); }
  function addMonths(s, n) { // same day n months on, or the last day of a shorter month (29 Feb + 60 = 28 Feb)
    var p = s.split("-"), y = +p[0], m = +p[1] - 1 + n, d = +p[2];
    var last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    return fmt(new Date(Date.UTC(y, m, Math.min(d, last))));
  }
  function addDays(s, n) { var p = s.split("-"); return fmt(new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + n))); }
  function region(name) {
    for (var i = 0; i < ROLLOUT.length; i++) if (ROLLOUT[i][0] === name) return ROLLOUT[i];
    return ROLLOUT[0];
  }

  // o: {region, have ("eicr" | "eic" | "none"), issued (date or ""), next (next-inspection date on the report or ""), today}
  // Returns {verdict: "yes" | "no" | "later", head, lines: [...], deadline, expiry, assumed, update_by}.
  function check(o) {
    var r = region(o.region), deadline = r[2], today = iso(o.today) || fmt(new Date());
    var issued = iso(o.issued), next = iso(o.next), doc = o.have === "eic" ? "EIC" : "EICR";
    var out = { deadline: deadline, expiry: "", assumed: false, update_by: "", lines: [] }, lines = out.lines;

    if (o.have === "none" || (!issued && !next)) {
      out.verdict = "no";
      out.head = "Yes, you need one. Book an electrical inspection before you register.";
      lines.push("The service asks for a copy of the EICR, or the EIC if the wiring is new and there is no EICR yet, and its expiry date. You can submit the entry and add it within 28 days, or the entry may be deactivated.");
      lines.push("Letting a property without an electrical inspection in the last five years is already a breach of the 2020 electrical safety rules, database or not.");
      return out;
    }

    // The report's own next-inspection date wins, but never more than five years from the inspection.
    var cap = issued ? addMonths(issued, 60) : "", exp = next && (!cap || next < cap) ? next : cap;
    out.expiry = exp; out.assumed = !next; out.update_by = addDays(exp, 28);
    if (next && cap && next > cap) lines.push("Your report's date is more than five years after the inspection, so the law caps it at " + long(cap) + ".");
    if (!next) lines.push("You gave only the inspection date, so this assumes the usual five years. Look for the next-inspection date on page 1 of the report: electricians often set three years for older wiring.");

    if (exp < today) {
      out.verdict = "no";
      out.head = "Book an inspection now: your " + doc + " ran out on " + long(exp) + ".";
      lines.unshift("Without a current report you cannot give the service a valid expiry date, and a let property needs an inspection at least every five years. Give the tenant a copy of the new report within 28 days of the inspection.");
    } else if (exp > deadline) {
      out.verdict = "yes";
      out.head = "Yes. Your " + doc + " runs until " + long(exp) + ".";
      lines.unshift("That is after your " + r[0] + " deadline of " + long(deadline) + ", so upload it as it is, with that expiry date. When it is renewed, upload the new report by " + long(out.update_by) + ", within 28 days of the old one running out.");
    } else {
      out.verdict = "later";
      out.head = "It runs out on " + long(exp) + ", before your deadline.";
      lines.unshift("Your " + r[0] + " deadline is " + long(deadline) + ". Book the next inspection before " + long(exp) + " and register with the new report. If you register before it, upload the new report by " + long(out.update_by) + ", within 28 days of the old one running out.");
    }
    return out;
  }

  var api = { ROLLOUT: ROLLOUT, addMonths: addMonths, check: check };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.rentreadyEicr = api;
})(this);

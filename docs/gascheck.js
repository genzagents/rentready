// Is my gas safety record OK for the landlord database? Runs in the browser on the gas guide; nothing leaves the page.
// The service asks for evidence of the gas safety certificate if the property has a gas supply (official guidance),
// and any outstanding detail can follow within 28 days of the entry. The check itself is due within 12 months of the
// last one; a check made in the 2 months before that date counts as made on it, so the anniversary stays the same
// (Gas Safety (Installation and Use) Regulations 1998, regulation 36(3) and (3A)).
(function (root) {
  "use strict";
  // The same windows as rentready.ROLLOUT (tests/test_gascheck.py checks they match).
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
  function addMonths(s, n) { // same day n months on, or the last day of a shorter month (29 Feb + 12 = 28 Feb)
    var p = s.split("-"), y = +p[0], m = +p[1] - 1 + n, d = +p[2];
    var last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
    return fmt(new Date(Date.UTC(y, m, Math.min(d, last))));
  }
  function addDays(s, n) { var p = s.split("-"); return fmt(new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + n))); }
  function region(name) {
    for (var i = 0; i < ROLLOUT.length; i++) if (ROLLOUT[i][0] === name) return ROLLOUT[i];
    return ROLLOUT[0];
  }

  // o: {region, gas ("yes" | "no"), last (date of the last check or ""), today (date)}
  // Returns {verdict: "yes" | "no" | "later", head, lines: [...], deadline, due, book_from, update_by}.
  function check(o) {
    var r = region(o.region), deadline = r[2], last = iso(o.last), today = iso(o.today) || fmt(new Date());
    var out = { deadline: deadline, due: "", book_from: "", update_by: "", lines: [] }, lines = out.lines;

    if (o.gas === "no") {
      out.verdict = "yes";
      out.head = "No. With no gas supply there is no gas safety record to upload.";
      lines.push("The service only asks for a gas safety certificate if the property has a gas supply. Say it has none and move on to the electrical certificate and EPC.");
      return out;
    }
    if (!last || last > today) {
      out.verdict = "no";
      out.head = "Yes, you need one. Book a Gas Safe check before you register.";
      lines.push("The service asks for evidence of the gas safety certificate for any property with a gas supply. You can submit the entry and add it within 28 days, or the entry may be deactivated.");
      lines.push("Letting a property with gas appliances without a check in the last 12 months is already an offence, database or not.");
      return out;
    }

    var due = addMonths(last, 12), from = addMonths(last, 10), upd = addDays(due, 28);
    out.due = due; out.book_from = from; out.update_by = upd;
    var keep = "Book the next check between " + long(from) + " and " + long(due) + " and it counts as done on " + long(due) + ", so your anniversary date stays the same.";

    if (due < today) {
      out.verdict = "no";
      out.head = "Book a check now: your last one ran out on " + long(due) + ".";
      lines.push("A gas safety check is due within 12 months of the last one. Without a current record you cannot give the service valid evidence, and letting the property is an offence until the check is done.");
      lines.push("Give the tenant a copy of the new record within 28 days of the check.");
    } else if (due > deadline) {
      out.verdict = "yes";
      out.head = "Yes. Your record runs until " + long(due) + ".";
      lines.push("That is after your " + r[0] + " deadline of " + long(deadline) + ", so upload it as it is, with its issue date.");
      lines.push(keep + " Then upload the new record to your entry by " + long(upd) + ", within 28 days of the old one running out.");
    } else {
      out.verdict = "later";
      out.head = "It runs out on " + long(due) + ", before your deadline.";
      lines.push("Your " + r[0] + " deadline is " + long(deadline) + ". " + keep);
      lines.push("Register after the new check and upload that record. If you register before it, upload the new record by " + long(upd) + ", within 28 days of the old one running out.");
    }
    return out;
  }

  var api = { ROLLOUT: ROLLOUT, addMonths: addMonths, check: check };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.rentreadyGas = api;
})(this);

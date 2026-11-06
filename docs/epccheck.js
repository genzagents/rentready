// Is my EPC OK for the landlord database? Runs in the browser on the EPC guide; nothing leaves the page.
// The service asks for the most recent EPC, whether a valid EPC was required for the current tenant, and the tenancy
// start date if the EPC is no longer valid (official guidance, 29 October 2026). An EPC has to be valid when a
// tenancy starts, not for the whole tenancy, so a lapsed EPC is fine if it was valid when the current tenant moved in.
(function (root) {
  "use strict";
  // The same windows as rentready.ROLLOUT (tests/test_epccheck.py checks they match).
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
  var EPC_FOR_LETS = "2008-10-01"; // EPCs needed for new lets in England from 1 October 2008
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December"];

  function iso(s) { return /^\d{4}-\d{2}-\d{2}$/.test(s || "") ? s : ""; }
  function long(s) { var p = s.split("-"); return +p[2] + " " + MONTHS[+p[1] - 1] + " " + p[0]; }
  function plus10(s) { // ten years on; 29 February lapses on 1 March
    var p = s.split("-"), y = +p[0] + 10, m = p[1], d = p[2];
    if (m === "02" && d === "29" && !(y % 4 === 0 && (y % 100 !== 0 || y % 400 === 0))) { m = "03"; d = "01"; }
    return y + "-" + m + "-" + d;
  }
  function region(name) {
    for (var i = 0; i < ROLLOUT.length; i++) if (ROLLOUT[i][0] === name) return ROLLOUT[i];
    return ROLLOUT[0];
  }

  // o: {region, epc (date or ""), rating ("A".."G" or ""), tenancy ("let" | "vacant"), tenancy_start (date or ""),
  //     today (date, optional: only changes the tense)}
  // Returns {verdict: "yes" | "no" | "later", head, lines: [...], deadline, lapses}.
  function check(o) {
    var r = region(o.region), deadline = r[2], epc = iso(o.epc), ts = iso(o.tenancy_start);
    var vacant = o.tenancy === "vacant", rating = String(o.rating || "").trim().toUpperCase().slice(0, 1);
    var out = { deadline: deadline, lapses: "", lines: [] }, lines = out.lines;

    if (!epc) {
      if (!vacant && ts && ts < EPC_FOR_LETS) {
        out.verdict = "yes";
        out.head = "Yes, you can register without one.";
        lines.push("Your tenant moved in on " + long(ts) + ", before EPCs were needed for new lets (1 October 2008), so a valid EPC was not required for them. The service asks exactly that; answer no and there is nothing to upload.");
        lines.push("You will need an EPC before you let it to anyone new.");
      } else if (!vacant && !ts) {
        out.verdict = "later";
        out.head = "It depends on when your tenant moved in.";
        lines.push("If they moved in before 1 October 2008, no EPC was required for them. Otherwise get one before you register. Add the tenancy start date above.");
      } else {
        out.verdict = "no";
        out.head = "Get an EPC before you register.";
        lines.push(vacant ? "You need a valid EPC before you market or let the property, and the service asks for the most recent one."
          : "A valid EPC was required when your tenant moved in on " + long(ts) + ". Book an assessment now; most cost £60 to £120 and the certificate lasts ten years.");
      }
      return out;
    }

    var lapses = plus10(epc);
    out.lapses = lapses;
    if (lapses > deadline) {
      out.verdict = "yes";
      out.head = "Yes. It is valid until " + long(lapses) + ".";
      lines.push("That is after your " + r[0] + " deadline of " + long(deadline) + ", so upload it as it is.");
    } else if (vacant) {
      out.verdict = "no";
      out.head = "Renew it before you let the property.";
      lines.push("Its ten years " + (lapses < (o.today || "") ? "ended" : "end") + " on " + long(lapses) + ", before your deadline. A new tenancy needs a valid EPC, so book a new assessment before you market the property and upload that one.");
    } else if (!ts) {
      out.verdict = "later";
      out.head = "Probably yes: it depends on when your tenant moved in.";
      lines.push("It lapses on " + long(lapses) + ", before your " + r[0] + " deadline of " + long(deadline) + ". A lapsed EPC is accepted if it was valid when the current tenancy started. Add the tenancy start date above.");
    } else if (ts < lapses) {
      out.verdict = "yes";
      out.head = lapses < (o.today || "") ? "Yes, even though it lapsed on " + long(lapses) + "." : "Yes, even after it lapses on " + long(lapses) + ".";
      lines.push("It was valid when your tenant moved in on " + long(ts) + ", which is all the law asks. Upload it with that tenancy start date; the service asks for the date when the EPC is no longer valid.");
      lines.push("Renew it before you let to a new tenant.");
    } else {
      out.verdict = "no";
      out.head = "Get a new EPC before you register.";
      lines.push("It lapsed on " + long(lapses) + ", before your tenant moved in on " + long(ts) + ", so a valid EPC was required for this tenancy and there was not one. The service asks whether a valid EPC was required for the current tenant.");
    }

    if (rating === "F" || rating === "G") {
      if (out.verdict === "yes") { out.verdict = "later"; out.head = "The EPC is fine, but rating " + rating + " needs an exemption."; }
      lines.push("Rating " + rating + " is below the E minimum. You can only keep letting it with a registered MEES exemption, and the service asks which one.");
    } else if (rating === "D" || rating === "E") {
      lines.push("Rating " + rating + " meets today's E minimum. It would fall short of the C minimum the government plans for all tenancies from 1 October 2030 (not yet law).");
    } else if ("ABC".indexOf(rating) >= 0 && rating) {
      lines.push("Rating " + rating + " meets today's E minimum and the planned 2030 C minimum.");
    }
    return out;
  }

  var api = { ROLLOUT: ROLLOUT, plus10: plus10, check: check };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.rentreadyEpc = api;
})(this);

// Free "email me before my deadline" sign-up under every check.
// Sends only the email address, the region, how many properties and the earliest deadline (never names, postcodes
// or certificate dates) to a Google Form owned by rentready's founder. Removal goes through the same form with
// source "remove", so nobody has to answer an email for it.
(function (root) {
  "use strict";
  var FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdaHYjZVlHMNvWu-oXFgBlWJc2z1V1W0vspocc4G6NukFtHvA/formResponse";
  var FIELDS = { email: "entry.1580771986", region: "entry.2022089101", properties: "entry.1004071449",
                 deadline: "entry.282070926", source: "entry.1830375299" };

  function valid(email) {
    email = String(email || "").trim();
    return email.length <= 254 && /^[^\s@<>"]+@[^\s@<>"]+\.[A-Za-z]{2,}$/.test(email) ? email : "";
  }

  // What leaves the browser for a sign-up, built from a checkPortfolio result. partner is a cleaned co-brand or null.
  function payload(email, p, partner) {
    email = valid(email);
    if (!email) return null;
    var inScope = (p && p.properties || []).filter(function (r) { return r.window; });
    var first = inScope.slice().sort(function (a, b) { return a.window.deadline < b.window.deadline ? -1 : 1; })[0];
    var regions = inScope.map(function (r) { return r.region; }).filter(function (r, i, a) { return r && a.indexOf(r) === i; });
    var out = {};
    out[FIELDS.email] = email;
    out[FIELDS.region] = regions.join("; ");
    out[FIELDS.properties] = String(p && p.in_scope || 0);
    out[FIELDS.deadline] = first ? first.window.deadline : "";
    out[FIELDS.source] = partner && partner.by ? "firm: " + partner.by : "check";
    return out;
  }

  function removal(email) {
    email = valid(email);
    if (!email) return null;
    var out = {};
    out[FIELDS.email] = email;
    out[FIELDS.source] = "remove";
    return out;
  }

  // Google Forms sends no CORS headers, so the response is opaque: a resolved promise means the request left.
  function send(data) {
    var body = new URLSearchParams();
    Object.keys(data).forEach(function (k) { body.append(k, data[k]); });
    return fetch(FORM, { method: "POST", mode: "no-cors", body: body });
  }

  var api = { FORM: FORM, FIELDS: FIELDS, valid: valid, payload: payload, removal: removal, send: send };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.rentreadyRemind = api;
})(this);

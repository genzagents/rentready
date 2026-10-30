// Co-branded links for the firms landlords already pay (gas, EICR and EPC engineers, agents, accountants).
// The firm's details travel in the link itself (?by=&tel=&web=&does=); nothing is stored or sent anywhere.
// Every value is checked against a strict pattern and anything else is dropped, so a link cannot inject markup
// or point the "book" button at a script; the page still says we have not checked the firm.
(function (root) {
  "use strict";
  var SERVICES = { gas: "gas safety record", eicr: "EICR", epc: "EPC" };
  var NAMES = { gas: "gas safety checks", eicr: "EICRs", epc: "EPCs" };

  // Names reported as impersonated (lower case). A link using one shows no banner.
  var BLOCKED = [];

  function clean(o) {
    o = o || {};
    var by = String(o.by || "").replace(/\s+/g, " ").trim();
    if (!/^[A-Za-z0-9][A-Za-z0-9 &'.,()\-]{1,59}$/.test(by)) return null;
    if (BLOCKED.indexOf(by.toLowerCase()) >= 0) return null;
    var tel = String(o.tel || "").replace(/\s+/g, " ").trim();
    if (!/^\+?[0-9][0-9 ]{8,17}$/.test(tel)) tel = "";
    var web = String(o.web || "").trim().toLowerCase().replace(/^https?:\/\//, "").replace(/^www\./, "").replace(/\/+$/, "");
    if (!/^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}$/.test(web) || web.length > 80) web = "";
    var does = String(o.does || "").toLowerCase().split(/[\s,]+/).filter(function (s, i, a) {
      return SERVICES[s] && a.indexOf(s) === i;
    });
    return { by: by, tel: tel, web: web, does: does };
  }

  function parse(search) {
    var q = new URLSearchParams(search || "");
    return clean({ by: q.get("by"), tel: q.get("tel"), web: q.get("web"), does: q.get("does") });
  }

  function link(o, base) {
    var p = clean(o);
    if (!p) return "";
    var q = new URLSearchParams();
    q.set("by", p.by);
    if (p.tel) q.set("tel", p.tel);
    if (p.web) q.set("web", p.web);
    if (p.does.length) q.set("does", p.does.join(","));
    return (base || "https://genzagents.github.io/rentready/") + "?" + q.toString() + "#tool";
  }

  // The firm offers this check (a finding's `check` name) and the finding needs action.
  function offers(p, finding) {
    if (!p || !finding || (finding.status !== "FAIL" && finding.status !== "WARN")) return false;
    return p.does.some(function (s) { return SERVICES[s] === finding.check; });
  }

  function telHref(tel) { return "tel:" + tel.replace(/ /g, ""); }
  function services(p) {
    var n = p.does.map(function (s) { return NAMES[s]; });
    return n.length > 1 ? n.slice(0, -1).join(", ") + " and " + n[n.length - 1] : n[0] || "";
  }

  var api = { clean: clean, parse: parse, link: link, offers: offers, telHref: telHref, services: services, SERVICES: SERVICES };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.rentreadyPartner = api;
})(this);

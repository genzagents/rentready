// Landlord database deadline card for other people's websites (letting agents, landlord blogs, councils).
// The snippet is a plain link inside <div class="rentready-deadline" data-region="...">; this script turns it into a
// card with the region's window and days left. The original link stays in the page (it is slotted into the card), so
// the snippet still works, and reads the same, with scripts off. No cookies, no storage, no network calls.
(function () {
  "use strict";
  var BASE = "https://genzagents.github.io/rentready/";
  // The same windows as rentready.ROLLOUT (tests/test_embed.py checks they match).
  var ROLLOUT = [
    ["West Midlands", "west-midlands.html", "2026-12-15", "2027-03-14"],
    ["East of England", "east-of-england.html", "2027-01-15", "2027-04-14"],
    ["East Midlands", "east-midlands.html", "2027-02-15", "2027-05-14"],
    ["South East", "south-east.html", "2027-03-15", "2027-06-14"],
    ["Yorkshire and The Humber", "yorkshire-and-the-humber.html", "2027-04-15", "2027-07-14"],
    ["North West", "north-west.html", "2027-05-15", "2027-08-14"],
    ["North East", "north-east.html", "2027-06-15", "2027-09-14"],
    ["London", "london.html", "2027-07-15", "2027-10-14"],
    ["South West", "south-west.html", "2027-08-15", "2027-11-14"]
  ];
  var SERVICE_OPENS = "2026-12-15";
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December"];

  function day(iso) { var p = iso.split("-"); return Date.UTC(+p[0], +p[1] - 1, +p[2]); }
  function today() { var d = new Date(); return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()); }
  function days(from, to) { return Math.round((to - from) / 864e5); }
  function long(iso) { var p = iso.split("-"); return +p[2] + " " + MONTHS[+p[1] - 1] + " " + p[0]; }
  function plural(n, w) { return n + " " + w + (n === 1 ? "" : "s"); }

  function find(name) {
    var low = String(name || "").toLowerCase().replace(/&/g, "and").replace(/\s+/g, " ").trim();
    if (low === "yorkshire" || low === "yorkshire and humber") low = "yorkshire and the humber";
    if (low === "east" || low === "eastern") low = "east of england";
    for (var i = 0; i < ROLLOUT.length; i++) if (ROLLOUT[i][0].toLowerCase() === low) return ROLLOUT[i];
    return null;
  }

  // What to say about one region on a given day: {head, sub, big, unit, state}.
  function status(r, t) {
    var opens = day(r[2]), deadline = day(r[3]), service = day(SERVICE_OPENS);
    var out = { head: r[0] + " landlords: register by " + long(r[3]) };
    if (t > deadline) {
      out.state = "late"; out.big = "Now"; out.unit = "deadline passed";
      out.sub = "The deadline was " + long(r[3]) + ". Unregistered lets risk fines of up to £7,000.";
    } else if (t >= opens) {
      out.state = "open"; out.big = String(days(t, deadline)); out.unit = days(t, deadline) === 1 ? "day left" : "days left";
      out.sub = "The " + r[0] + " window is open. Register each let property and upload its gas, electrical and EPC certificates.";
    } else {
      out.state = "soon"; out.big = String(days(t, deadline)); out.unit = "days to the deadline";
      out.sub = (opens === service ? "Registration opens " + long(r[2]) + "." :
        "The requirement starts " + long(r[2]) + "; you can register early from " + long(SERVICE_OPENS) + ".") +
        " Each let property needs in-date gas, electrical and EPC certificates.";
    }
    return out;
  }

  var CSS = [
    ":host{all:initial;display:block;max-width:440px;font:15px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;",
    "--bg:#ffffff;--ink:#1c1a16;--mut:#6b665c;--line:#e4dfd3;--brand:#0e5a44;--brand-ink:#ffffff;--soft:#eef5f1;--warn:#9a3412}",
    ":host([data-wide]){max-width:600px}",
    ":host([data-theme=dark]){--bg:#1a1915;--ink:#f3f0e9;--mut:#a59f93;--line:#302d26;--brand:#5fc39b;--brand-ink:#0b1f17;--soft:#1f2a24;--warn:#fdba74}",
    "@media (prefers-color-scheme:dark){:host(:not([data-theme])),:host([data-theme=auto]){--bg:#1a1915;--ink:#f3f0e9;--mut:#a59f93;--line:#302d26;--brand:#5fc39b;--brand-ink:#0b1f17;--soft:#1f2a24;--warn:#fdba74}}",
    ".c{box-sizing:border-box;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-top:4px solid var(--brand);border-radius:12px;padding:16px 18px 14px}",
    ".k{font-size:12px;font-weight:650;letter-spacing:.06em;text-transform:uppercase;color:var(--mut);margin:0 0 6px}",
    ".h{font-size:18px;line-height:1.25;font-weight:750;margin:0 0 10px;letter-spacing:-.01em}",
    ".row{display:flex;gap:14px;align-items:center}",
    ".n{flex:none;min-width:84px;text-align:center;background:var(--soft);border-radius:10px;padding:8px 10px}",
    ".n b{display:block;font-size:30px;line-height:1.05;font-weight:800;color:var(--brand)}",
    ".n span{display:block;font-size:12px;color:var(--mut);line-height:1.2;margin-top:2px}",
    ".late .n b{color:var(--warn)}",
    ".s{margin:0;font-size:14px;color:var(--ink)}",
    ".go{display:inline-block;margin-top:12px;background:var(--brand);color:var(--brand-ink);text-decoration:none;font-weight:650;font-size:14px;padding:8px 14px;border-radius:999px}",
    ".go:hover{filter:brightness(1.08)}",
    "table{width:100%;border-collapse:collapse;font-size:14px;margin:2px 0 0}",
    "td{padding:6px 4px;border-bottom:1px solid var(--line);vertical-align:top}",
    "td.d{white-space:nowrap;text-align:right;color:var(--mut)}",
    "tr.next td{font-weight:700;color:var(--ink)}tr.next td.d{color:var(--brand)}",
    ".f{margin:12px 0 0;font-size:12px;color:var(--mut);display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}",
    "::slotted(a){color:var(--mut)!important;font-size:12px!important;text-decoration:underline!important}",
    ":host{container-type:inline-size}",
    "@container (max-width:420px){.row{flex-direction:column;align-items:flex-start;gap:10px}" +
      ".n{display:flex;align-items:baseline;gap:8px;min-width:0;padding:6px 12px}.n span{margin:0;font-size:13px}}"
  ].join("");

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }

  function cardFor(r, t) {
    var st = status(r, t);
    return '<div class="c ' + st.state + '"><p class="k">Landlord database · England</p>' +
      '<p class="h">' + esc(st.head) + '</p><div class="row"><div class="n"><b>' + esc(st.big) + '</b><span>' +
      esc(st.unit) + '</span></div><p class="s">' + esc(st.sub) + '</p></div>' +
      '<a class="go" href="' + BASE + '?ref=embed#tool" target="_blank" rel="noopener">Check a property free</a>' +
      '<p class="f"><slot></slot><span>rentready · no sign-up</span></p></div>';
  }

  function tableFor(t) {
    var next = -1, rows = "";
    for (var i = 0; i < ROLLOUT.length; i++) if (next < 0 && day(ROLLOUT[i][3]) >= t) next = i;
    for (var j = 0; j < ROLLOUT.length; j++) {
      var r = ROLLOUT[j], left = days(t, day(r[3]));
      rows += '<tr' + (j === next ? ' class="next"' : "") + '><td>' + esc(r[0]) + '</td><td class="d">' +
        esc(long(r[3])) + '<br>' + (left < 0 ? "passed" : esc(plural(left, "day")) + " left") + '</td></tr>';
    }
    return '<div class="c"><p class="k">Landlord database · England</p><p class="h">Registration deadlines by region</p>' +
      '<table>' + rows + '</table>' +
      '<a class="go" href="' + BASE + '?ref=embed#tool" target="_blank" rel="noopener">Check a property free</a>' +
      '<p class="f"><slot></slot><span>rentready · no sign-up</span></p></div>';
  }

  function render(el, t) {
    if (!el.attachShadow || el.shadowRoot) return;
    var want = el.getAttribute("data-region") || "all", r = find(want);
    if (!r && want.toLowerCase() !== "all") return; // unknown region: leave the plain link alone
    var theme = (el.getAttribute("data-theme") || "auto").toLowerCase();
    var root = el.attachShadow({ mode: "open" });
    if (theme === "light" || theme === "dark") el.setAttribute("data-theme", theme);
    if (!r) el.setAttribute("data-wide", "");
    root.innerHTML = "<style>" + CSS + "</style>" + (r ? cardFor(r, t) : tableFor(t));
  }

  function run() {
    var els = document.querySelectorAll(".rentready-deadline"), t = today();
    for (var i = 0; i < els.length; i++) render(els[i], t);
  }

  var api = { ROLLOUT: ROLLOUT, status: status, find: find, day: day, render: render, run: run };
  if (typeof module === "object" && module.exports) { module.exports = api; return; }
  window.rentreadyEmbed = api;
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run); else run();
})();

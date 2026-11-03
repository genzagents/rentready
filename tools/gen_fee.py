"""Write the pro-rated fee block (region table + calculator) into docs/guides/landlord-database-fee.html, between
the <!-- fee:start --> and <!-- fee:end --> markers, from rentready.fee (the official formula, 29 Oct 2026).

    python3 tools/gen_fee.py"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rentready import ROLLOUT  # noqa: E402
from rentready.fee import GUIDANCE, first_payment, renewal_date  # noqa: E402

PAGE = ROOT / "docs" / "guides" / "landlord-database-fee.html"
START, END = "<!-- fee:start -->", "<!-- fee:end -->"


def day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def money(x: float) -> str:
    return f"£{x:.2f}"


def rows() -> list:
    out = []
    for region, w in ROLLOUT.items():
        o, d = date.fromisoformat(w["opens"]), date.fromisoformat(w["deadline"])
        out.append((region, o, d, first_payment(o), first_payment(d)))
    return out


SCRIPT = """<script>
(function () {
  // The official formula (gov.uk guidance for landlords, 29 Oct 2026): (65 / year_length) * (remaining - free), rounded down.
  var DAY = 864e5, CHARGE = Date.UTC(2027, 10, 15);
  function parse(v) { var m = /^(\\d{4})-(\\d{2})-(\\d{2})$/.exec(v || ""); return m ? Date.UTC(+m[1], m[2] - 1, +m[3]) : null; }
  function addYear(t, n) { var d = new Date(t), y = d.getUTCFullYear() + n, m = d.getUTCMonth(), dd = d.getUTCDate();
    if (m === 1 && dd === 29) dd = 28; return Date.UTC(y, m, dd); }
  function pay(reg, first) {
    var renew = addYear(first, 1); while (renew <= reg) renew = addYear(renew, 1);
    var yl = Math.round((renew - addYear(renew, -1)) / DAY), rem = Math.round((renew - reg) / DAY);
    var free = Math.min(rem, Math.max(0, Math.round((CHARGE - reg) / DAY)));
    return { pence: Math.floor(6500 * (rem - free) / yl), renew: renew };
  }
  function gbp0(p) { return p % 100 ? gbp(p) : "£" + (p / 100).toLocaleString("en-GB"); }
  function gbp(p) { return "£" + (p / 100).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function fmt(t) { return new Date(t).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" }); }
  var f = document.getElementById("fee-calc"); if (!f) return;
  function run() {
    var first = parse(f.first.value), n = Math.max(1, Math.min(999, parseInt(f.n.value, 10) || 1)), later = parse(f.later.value);
    var out = document.getElementById("fee-out"), note = document.getElementById("fee-note");
    if (first === null || first < Date.UTC(2026, 11, 15)) { note.textContent = "Registration opens on 15 December 2026. Pick a date from then on."; return; }
    var a = pay(first, first), extra = "";
    if (later !== null) {
      if (later < first) extra = " The later property's date is before your first registration, so it is left out.";
      else { var b = pay(later, first); extra = " A property added on " + fmt(later) + " pays " + gbp(b.pence) + " and renews with the rest."; }
    }
    document.getElementById("fee-one").textContent = gbp(a.pence);
    document.getElementById("fee-all").textContent = gbp(a.pence * n);
    document.getElementById("fee-renew").textContent = fmt(a.renew);
    note.textContent = "Then £65 a property from " + fmt(a.renew) + " (" + gbp0(6500 * n) + " a year for " + n + (n === 1 ? " property" : " properties") + ")." + extra;
    out.hidden = false;
  }
  f.addEventListener("input", run); run();
})();
</script>"""


def block() -> str:
    trs = "".join(
        f'<tr><td>{r}</td><td><strong>{money(a)}</strong><br><small class="mut">{day(o)}</small></td>'
        f'<td>{money(b)}<br><small class="mut">{day(d)}</small></td></tr>'
        for r, o, d, a, b in rows())
    wm = rows()[0]
    return f"""{START}
<h2 id="first-payment">What you actually pay the first time</h2>
<p>The official guidance (<a href="{GUIDANCE}">29 October 2026</a>) sets out how the service pro-rates the fee. Nobody is charged for any day before <strong>15 November 2027</strong>, the date by which every landlord in England has to be registered. Your first payment covers only the days from 15 November 2027 to your renewal date, and your renewal date is one year after you register your first property. After that you pay the full £65 a property each year.</p>
<p>So a landlord who registers on the first day, {day(wm[1])}, pays <strong>{money(wm[3])}</strong> a property, then £65 on {day(renewal_date(wm[1]))}. The latest you can register in the rollout is the South West deadline, and even then the first payment is under £65.</p>
<div class="wrap"><table>
<tr><th>Region</th><th>First payment if you register on the first day</th><th>On the last day (the deadline)</th></tr>
{trs}
</table></div>
<p class="mut">Per property, from the official formula: £65 ÷ days in the year × (days to your renewal date − days before 15 November 2027), rounded down to the penny. It reproduces both of the guidance's worked examples (£5.34 on 15 December 2026, £39.60 on 25 June 2027). You can register properties in any region from 15 December 2026.</p>
<section class="card" style="padding:18px 20px;margin:18px 0" aria-labelledby="fee-calc-h">
<h3 id="fee-calc-h" style="margin-top:0">Work out your first payment</h3>
<p class="calc-note mut">Same formula as the service. Nothing leaves your browser.</p>
<form class="firm-form" id="fee-calc" onsubmit="return false">
<label>Day you register your first property<input type="date" name="first" value="2026-12-15" min="2026-12-15"></label>
<label>Properties registered that day<input type="number" name="n" min="1" max="999" value="1" inputmode="numeric"></label>
<label>Adding one later? <small class="mut" style="font-weight:400">optional</small><input type="date" name="later" min="2026-12-15"></label>
</form>
<div class="summary calc-out" id="fee-out" aria-live="polite">
<div class="stat"><b id="fee-one">{money(wm[3])}</b><span>First payment, each</span></div>
<div class="stat"><b id="fee-all">{money(wm[3])}</b><span>First payment, all</span></div>
<div class="stat"><b id="fee-renew">{day(renewal_date(wm[1]))}</b><span>Renewal date</span></div>
</div>
<p class="calc-note mut" id="fee-note">Then £65 a property from {day(renewal_date(wm[1]))}.</p>
</section>
{SCRIPT}
{END}"""


def write() -> bool:
    t = PAGE.read_text()
    i, j = t.index(START), t.index(END) + len(END)
    new = t[:i] + block() + t[j:]
    if new != t:
        PAGE.write_text(new)
    return new != t


if __name__ == "__main__":
    print("changed" if write() else "unchanged")

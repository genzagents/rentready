"""Co-branded links (docs/partner.js): only clean values survive, so a shared link cannot inject markup or a script URL."""
import json, shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = str(ROOT / "docs" / "partner.js")
NODE = shutil.which("node")
RUN = "const P=require(process.argv[1]);let i=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
      "console.log(JSON.stringify(i.map(([f,a])=>f==='offers'?P.offers(P.clean(a[0]),a[1]):P[f](...a))))"


@unittest.skipUnless(NODE, "node not installed")
class PartnerTest(unittest.TestCase):
    def call(self, *calls):
        out = subprocess.run([NODE, "-e", RUN, JS], input=json.dumps(calls), capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_clean_values_pass_and_round_trip(self):
        good = {"by": "Smith Gas & Heating", "tel": "0121 496 0000", "web": "https://www.SmithGas.co.uk/", "does": "gas,EICR,gas"}
        c, link, parsed = self.call(["clean", [good]], ["link", [good]],
                                    ["parse", ["?by=Smith+Gas+%26+Heating&tel=0121+496+0000&web=smithgas.co.uk&does=gas%2Ceicr"]])
        self.assertEqual(c, {"by": "Smith Gas & Heating", "tel": "0121 496 0000", "web": "smithgas.co.uk", "does": ["gas", "eicr"]})
        self.assertTrue(link.startswith("https://genzagents.github.io/rentready/?by=Smith+Gas+%26+Heating&"))
        self.assertTrue(link.endswith("#tool"))
        self.assertEqual(parsed, c)

    def test_hostile_values_are_dropped(self):
        r = self.call(["clean", [{"by": "<img src=x onerror=alert(1)>"}]],
                      ["clean", [{"by": "Acme", "tel": "javascript:alert(1)", "web": "javascript:alert(1)", "does": "gas,<b>"}]],
                      ["clean", [{"by": "Acme", "web": "evil.com/\"><script>"}]],
                      ["clean", [{"by": "x" * 61}]], ["clean", [{}]], ["link", [{"by": ""}]])
        self.assertIsNone(r[0])
        self.assertEqual(r[1], {"by": "Acme", "tel": "", "web": "", "does": ["gas"]})
        self.assertEqual(r[2]["web"], "")
        self.assertIsNone(r[3]); self.assertIsNone(r[4]); self.assertEqual(r[5], "")

    def test_book_line_only_on_covered_findings_needing_action(self):
        p = {"by": "Acme", "does": "gas,epc"}
        r = self.call(["offers", [p, {"status": "WARN", "check": "gas safety record"}]],
                      ["offers", [p, {"status": "FAIL", "check": "EPC"}]],
                      ["offers", [p, {"status": "PASS", "check": "gas safety record"}]],
                      ["offers", [p, {"status": "FAIL", "check": "EICR"}]],
                      ["offers", [p, {"status": "FAIL", "check": "EPC rating"}]])
        self.assertEqual(r, [True, True, False, False, False])

    def test_calendar_reminders_carry_the_firm_on_covered_certificates_only(self):
        run = "const P=require(process.argv[1]);const [p,e]=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
              "console.log(JSON.stringify([P.decorate(e,P.clean(p)),P.decorate(e,null)]))"
        ev = [{"date": "2027-01-10", "summary": "gas safety record expires: 1 Oak St", "description": "book it.", "property": "1 Oak St", "kind": "gas safety record"},
              {"date": "2027-03-14", "summary": "Landlord database DEADLINE: 1 Oak St", "description": "last day.", "property": "1 Oak St", "kind": "deadline"},
              {"date": "2028-01-01", "summary": "EICR expires: 1 Oak St", "description": "book.", "property": "1 Oak St", "kind": "EICR"}]
        firm = {"by": "Smith Gas", "tel": "0121 496 0000", "web": "smithgas.co.uk", "does": "gas"}
        out = subprocess.run([NODE, "-e", run, JS], input=json.dumps([firm, ev]), capture_output=True, text=True, check=True)
        dec, plain = json.loads(out.stdout)
        self.assertEqual(dec[0]["summary"], "gas safety record expires: 1 Oak St (book: Smith Gas 0121 496 0000)")
        self.assertIn("Book with Smith Gas, 0121 496 0000, smithgas.co.uk.", dec[0]["description"])
        self.assertEqual(dec[0]["kind"], "gas safety record")  # UID input unchanged, so re-imports still update
        self.assertEqual(dec[1:], ev[1:])
        self.assertEqual(plain, ev)
        self.assertNotIn("Smith", ev[0]["summary"])  # input not mutated

    def test_pages_wire_it_in(self):
        home = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="partner.js"></script>', home)
        self.assertIn("We have not checked this firm", home)
        self.assertIn("for-firms.html", home)
        self.assertIn("PT.decorate(ev,partner)", home)
        firms = (ROOT / "docs" / "for-firms.html").read_text(encoding="utf-8")
        self.assertIn('id="f-link"', firms)
        self.assertIn("for-firms.html", (ROOT / "docs" / "sitemap.xml").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

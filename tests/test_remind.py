"""Deadline reminder sign-up (docs/remind.js): only the email, regions, count and earliest deadline leave the browser."""
import json, re, shutil, subprocess, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
JS = str(DOCS / "remind.js")
NODE = shutil.which("node")
RUN = "const R=require(process.argv[1]);let i=JSON.parse(require('fs').readFileSync(0,'utf8'));" \
      "console.log(JSON.stringify(i.map(([f,a])=>f==='FIELDS'?R.FIELDS:R[f](...a))))"

PORTFOLIO = {"in_scope": 2, "properties": [
    {"name": "Flat 1", "postcode": "B3 2TA", "region": "West Midlands",
     "window": {"opens": "2026-12-15", "deadline": "2027-03-14"}},
    {"name": "Flat 2", "postcode": "N1 9GU", "region": "London",
     "window": {"opens": "2027-07-15", "deadline": "2027-10-14"}},
    {"name": "Cardiff", "postcode": "CF10 1AA", "region": None, "window": None}]}


@unittest.skipUnless(NODE, "node not installed")
class RemindTest(unittest.TestCase):
    def call(self, *calls):
        out = subprocess.run([NODE, "-e", RUN, JS], input=json.dumps(calls), capture_output=True, text=True, check=True)
        return json.loads(out.stdout)

    def test_payload_carries_no_property_details(self):
        fields, d = self.call(["FIELDS", []], ["payload", [" a@b.co.uk ", PORTFOLIO, None]])
        self.assertEqual(set(d), set(fields.values()))
        self.assertEqual(d[fields["email"]], "a@b.co.uk")
        self.assertEqual(d[fields["region"]], "West Midlands; London")
        self.assertEqual(d[fields["properties"]], "2")
        self.assertEqual(d[fields["deadline"]], "2027-03-14")
        self.assertEqual(d[fields["source"]], "check")
        flat = json.dumps(d)
        for secret in ("Flat 1", "B3 2TA", "N1 9GU", "CF10"):
            self.assertNotIn(secret, flat)

    def test_firm_source_bad_email_and_removal(self):
        fields, firm, bad, rem, rembad = self.call(
            ["FIELDS", []], ["payload", ["x@y.com", PORTFOLIO, {"by": "Acme Gas"}]],
            ["payload", ["not an email", PORTFOLIO, None]], ["removal", ["x@y.com"]], ["removal", ["<x>@y.com"]])
        self.assertEqual(firm[fields["source"]], "firm: Acme Gas")
        self.assertIsNone(bad); self.assertIsNone(rembad)
        self.assertEqual(rem, {fields["email"]: "x@y.com", fields["source"]: "remove"})


class RemindPagesTest(unittest.TestCase):
    def test_form_wired_and_explained(self):
        js = (DOCS / "remind.js").read_text(encoding="utf-8")
        self.assertRegex(js, r'https://docs\.google\.com/forms/d/e/[\w-]+/formResponse')
        self.assertEqual(len(re.findall(r'entry\.\d+', js)), 5)
        index = (DOCS / "index.html").read_text(encoding="utf-8")
        self.assertIn('<script src="remind.js"></script>', index)
        self.assertIn("Email me before my deadline", index)
        privacy = (DOCS / "privacy.html").read_text(encoding="utf-8")
        for s in ('id="reminders"', "Google Form", "never sends property names, postcodes or certificate dates", 'id="remove"'):
            self.assertIn(s, privacy)


if __name__ == "__main__":
    unittest.main()

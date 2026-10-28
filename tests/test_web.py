"""The browser checker (docs/rentready.js) must give the same answers as the Python. Runs the JS under node, offline."""
import json, os, shutil, subprocess, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rentready as rr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "docs", "rentready.js")
NODE = shutil.which("node")
# Fake postcodes.io answers, shared by both sides so nothing touches the network.
LOOKUP = {
    "B32TA": {"postcode": "B3 2TA", "region": "West Midlands", "country": "England"},
    "SW1A1AA": {"postcode": "SW1A 1AA", "region": "London", "country": "England"},
    "M11AE": {"postcode": "M1 1AE", "region": "North West", "country": "England"},
    "CF101AA": {"postcode": "CF10 1AA", "region": None, "country": "Wales"},
    "LS11UR": {"postcode": "LS1 1UR", "region": "Yorkshire and The Humber", "country": "England"},
}
def fake_lookup(pc, timeout=8.0):
    return LOOKUP.get(pc.upper().replace(" ", ""), {"error": "postcode lookup failed: HTTPError: HTTP Error 404: Not Found"})

CSV = """name,postcode,gas,no_gas,eicr,epc,epc_rating,tenancy_start,region
12 Example St,B3 2TA,2026-02-01,,2023-06-01,2017-05-01,D,,
Flat 4,SW1A 1AA,,yes,2024-01-01,2020-01-01,C,,
"The Old Mill, Unit 2",M1 1AE,2026-05-01,,2022-04-01,2019-09-01,E,,
Leap,LS1 1UR,2024-02-29,,2020-02-29,2016-02-29,F,2025-01-01,
Cardiff,CF10 1AA,2026-06-01,,2024-01-01,2020-01-01,B,,
Typo,ZZ9 9ZZ,2026-06-01,,2024-01-01,2020-01-01,B,,
By region,,,x,2019-01-01,,,,south east
Empty,,,,,,,,
"""
KEYS = ["name", "postcode", "region", "findings", "actions", "window", "expiries", "ready", "next", "tenancy_start", "fee_gbp_per_year"]
RUNNER = r"""
const rr = require(process.argv[1]);
const [csv, today, lookup] = JSON.parse(require("fs").readFileSync(0, "utf8"));
const look = async pc => lookup[pc.toUpperCase().replace(/ /g, "")] || {error: "postcode lookup failed: HTTPError: HTTP Error 404: Not Found"};
(async () => {
  const p = await rr.checkPortfolio(rr.readPortfolio(csv), today, look);
  const ics = await rr.formatIcs(rr.calendarEvents(p.properties), [60, 14], "20261028T050000Z");
  process.stdout.write(JSON.stringify({p, ics}));
})();
"""

@unittest.skipUnless(NODE, "node not installed")
class WebParity(unittest.TestCase):
    def run_both(self, today):
        orig = rr.lookup_region
        rr.lookup_region = fake_lookup
        try:
            py = rr.check_portfolio(rr.read_portfolio(CSV), today=today)
        finally:
            rr.lookup_region = orig
        ics = rr.format_ics(rr.calendar_events(py["properties"]), [60, 14], stamp="20261028T050000Z")
        out = subprocess.run([NODE, "-e", RUNNER, JS], input=json.dumps([CSV, today, LOOKUP]), capture_output=True, text=True, check=True)
        return py, ics, json.loads(out.stdout)

    def test_same_answers_on_many_dates(self):
        for today in ("2026-10-28", "2026-12-20", "2027-03-15", "2027-12-01", "2036-01-01"):
            py, ics, js = self.run_both(today)
            for k in ("count", "in_scope", "fee_gbp_per_year", "earliest_deadline", "ready", "not_ready", "renewal", "today"):
                self.assertEqual(py[k], js["p"][k], f"{k} on {today}")
            self.assertEqual(len(py["properties"]), len(js["p"]["properties"]))
            for a, b in zip(py["properties"], js["p"]["properties"]):
                for k in KEYS:
                    self.assertEqual(a.get(k), b.get(k), f"{a['name']} {k} on {today}")
            self.assertEqual(ics, js["ics"], f"ics on {today}")

    def test_cases_cover_what_they_claim(self):
        py, _, _ = self.run_both("2026-10-28")
        by = {p["name"]: p for p in py["properties"]}
        self.assertIsNone(by["Cardiff"]["ready"])
        self.assertEqual(by["Leap"]["expiries"]["EICR"], "2025-02-28")
        self.assertEqual(by["Typo"]["findings"][0]["check"], "region")
        self.assertEqual(by["By region"]["region"], "South East")
        self.assertEqual(by["Empty"]["ready"], False)

    def test_versions_match(self):
        with open(JS) as f:
            self.assertIn(f'const VERSION = "{rr.__version__}"', f.read())

if __name__ == "__main__":
    unittest.main()

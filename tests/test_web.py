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

CSV = """name,postcode,gas,no_gas,eicr,epc,epc_rating,tenancy_start,region,eicr_due
12 Example St,B3 2TA,2026-02-01,,2023-06-01,2017-05-01,D,,,
Flat 4,SW1A 1AA,,yes,2024-01-01,2020-01-01,C,,,
"The Old Mill, Unit 2",M1 1AE,2026-05-01,,2022-04-01,2019-09-01,E,,,
Leap,LS1 1UR,2024-02-29,,2020-02-29,2016-02-29,F,2025-01-01,,
Cardiff,CF10 1AA,2026-06-01,,2024-01-01,2020-01-01,B,,,
Typo,ZZ9 9ZZ,2026-06-01,,2024-01-01,2020-01-01,B,,,
By region,,,x,2019-01-01,,,,south east,
Empty,,,,,,,,,
Three-year EICR,B3 2TA,2026-06-01,,2024-06-01,2020-01-01,C,,,2027-02-01
Due only,SW1A 1AA,2026-06-01,,,2020-01-01,C,,,2029-01-01
Due beyond five years,M1 1AE,2026-06-01,,2023-01-01,2020-01-01,C,,,2030-01-01
"""
KEYS = ["name", "postcode", "region", "findings", "actions", "window", "expiries", "ready", "next", "tenancy_start", "fee_gbp_per_year",
        "assumptions", "eicr_due"]
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

PACK_CSV = """name,postcode,gas,no_gas,eicr,epc,epc_rating,tenancy_start,ownership,dwelling_type,bedrooms,let,freeholder,occupants,households,licence,furnished,rent,rent_frequency,bills
12 Example St,B3 2TA,2026-02-01,,2023-06-01,2017-05-01,D,,freehold,house,3,Y,,4,1,none,unfurnished,1200,monthly,none
Flat 4,SW1A 1AA,,yes,2024-01-01,2020-01-01,C,,leasehold,flat,1,no,"Acme Freeholds, a@b.c",1,1,,furnished,"1,850",monthly,"water, council tax"
HMO,M1 1AE,2026-05-01,,2019-04-01,2015-09-01,G,,freehold,house,6,yes,,6,5,hmo,part,3000,monthly,all
Lapsed EPC,LS1 1UR,2026-08-01,,2024-01-01,2014-01-01,E,2023-05-01,freehold,flat,2,yes,,2,1,no,unfurnished,900,monthly,
Lapsed no tenancy,LS1 1UR,2026-08-01,,2024-01-01,2014-01-01,E,,,,,,,,,,,,,
Cardiff,CF10 1AA,2026-06-01,,2024-01-01,2020-01-01,B,,,,,,,,,,,,,
Typo,ZZ9 9ZZ,,,,,,,,,,,,,,,,,,
"!!! ---  The   Very Long Property Name That Goes On And On",,,x,2019-01-01,,,,,,,,,,,,,,,
"""
PACK_CSV_DUE = """name,postcode,gas,no_gas,eicr,eicr_due,epc,epc_rating
Short EICR,B3 2TA,2026-06-01,,2024-06-01,2027-02-01,2020-01-01,C
Due only,SW1A 1AA,2026-06-01,,,2029-01-01,2020-01-01,C
Due only region unknown,ZZ9 9ZZ,2026-06-01,,,2029-01-01,2020-01-01,C
Issue only,M1 1AE,2026-06-01,,2024-06-01,,2020-01-01,C
"""
PACK_RUNNER = r"""
const rr = require(process.argv[1]);
const [csv, today, org, lookup] = JSON.parse(require("fs").readFileSync(0, "utf8"));
const look = async pc => lookup[pc.toUpperCase().replace(/ /g, "")] || {error: "postcode lookup failed: HTTPError: HTTP Error 404: Not Found"};
(async () => {
  const pk = await rr.buildPack(rr.readPortfolio(csv), today, org, look);
  process.stdout.write(JSON.stringify({pk, md: rr.formatPack(pk)}));
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
        # The report's own next-inspection date wins over issue + 5 years: a 3-year report is not a false PASS.
        self.assertEqual(by["Three-year EICR"]["expiries"]["EICR"], "2027-02-01")
        self.assertIn("WARN", [f["status"] for f in by["Three-year EICR"]["findings"] if f["check"] == "EICR"])
        self.assertEqual(by["Due only"]["expiries"]["EICR"], "2029-01-01")
        self.assertEqual(by["Due beyond five years"]["expiries"]["EICR"], "2028-01-01")
        self.assertIn("EICR: assumed", by["12 Example St"]["assumptions"][0])
        self.assertNotIn("assumptions", by["Three-year EICR"])

    def run_pack(self, csv, today, org):
        from rentready import pack
        orig = rr.lookup_region
        rr.lookup_region = fake_lookup
        try:
            py = pack.build_pack(rr.read_portfolio(csv), today=today, organisation=org)
        finally:
            rr.lookup_region = orig
        out = subprocess.run([NODE, "-e", PACK_RUNNER, JS], input=json.dumps([csv, today, org, LOOKUP]), capture_output=True, text=True, check=True)
        js = json.loads(out.stdout)
        return py, pack.format_pack(py), js["pk"], js["md"]

    def test_same_registration_pack(self):
        for csv in (PACK_CSV, CSV, PACK_CSV_DUE):
            for today in ("2026-10-28", "2027-03-15", "2030-01-01"):
                for org in (False, True):
                    py, md, js, jmd = self.run_pack(csv, today, org)
                    self.assertEqual(json.loads(json.dumps(py)), js, f"pack on {today} org={org}")
                    self.assertEqual(md, jmd, f"markdown on {today} org={org}")

    def test_pack_cases_cover_what_they_claim(self):
        py, md, _, _ = self.run_pack(PACK_CSV, "2026-10-28", False)
        by = {p["name"]: p for p in py["properties"]}
        self.assertTrue(by["12 Example St"]["ready_to_register"])
        self.assertIn("MEES exemption", [f["item"] for f in by["HMO"]["files"]])
        self.assertIn("Licence details", [f["item"] for f in by["HMO"]["files"]])
        self.assertEqual(by["Lapsed EPC"]["files"][-1]["state"], "READY")
        self.assertEqual(by["Lapsed no tenancy"]["files"][-1]["state"], "GATHER")
        self.assertFalse(by["Cardiff"]["in_scope"])
        self.assertIn("Acme Freeholds, a@b.c", md)

    def test_versions_match(self):
        with open(JS) as f:
            self.assertIn(f'const VERSION = "{rr.__version__}"', f.read())

class RegistryMetadata(unittest.TestCase):
    """server.json (MCP registry) must name the PyPI release being published and the README must carry mcp-name."""

    def test_server_json_matches_release(self):
        with open(os.path.join(ROOT, "server.json")) as f:
            srv = json.load(f)
        self.assertEqual(srv["name"], "io.github.genzagents/rentready")
        self.assertEqual(srv["version"], rr.__version__)
        pkg = srv["packages"][0]
        self.assertEqual((pkg["registryType"], pkg["identifier"], pkg["version"]), ("pypi", "rentready", rr.__version__))
        with open(os.path.join(ROOT, "README.md")) as f:
            self.assertIn("\nmcp-name: io.github.genzagents/rentready\n", f.read())

if __name__ == "__main__":
    unittest.main()

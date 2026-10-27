import json, subprocess, sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rentready as rr

T = "2026-10-26"

class Rollout(unittest.TestCase):
    def test_nine_regions_three_month_windows(self):
        self.assertEqual(len(rr.ROLLOUT), 9)
        for v in rr.ROLLOUT.values():
            o, d = rr._d(v["opens"]), rr._d(v["deadline"])
            m = o.month + 3; y = o.year + (m - 1) // 12; m = (m - 1) % 12 + 1
            self.assertEqual(d, o.replace(year=y, month=m) - rr.timedelta(days=1))  # 15th to the 14th three months on
    def test_first_region_is_west_midlands(self):
        self.assertEqual(min(rr.ROLLOUT.items(), key=lambda kv: kv[1]["opens"])[0], "West Midlands")
    def test_alias(self):
        self.assertEqual(rr.normalise_region("yorkshire and humber"), "Yorkshire and The Humber")
        self.assertEqual(rr.normalise_region("london"), "London")
        self.assertIsNone(rr.normalise_region("Wales"))

class Check(unittest.TestCase):
    def test_ready_london(self):
        r = rr.check_property(region="London", gas="2026-09-01", eicr="2024-03-01", epc="2020-01-01", epc_rating="C", today=T)
        self.assertTrue(r["ready"]); self.assertEqual(r["window"]["deadline"], "2027-10-14")
        self.assertEqual(r["fee_gbp_per_year"], 65)
    def test_gas_expires_before_deadline_is_warn(self):
        r = rr.check_property(region="West Midlands", gas="2026-02-01", eicr="2024-03-01", epc="2020-01-01", today=T)
        f = {x["check"]: x["status"] for x in r["findings"]}
        self.assertEqual(f["gas safety record"], "WARN"); self.assertTrue(r["ready"]); self.assertTrue(any("Book before 2027-02-01" in a for a in r["actions"]))
    def test_missing_eicr_fails(self):
        r = rr.check_property(region="South West", gas="2026-09-01", epc="2020-01-01", today=T)
        self.assertFalse(r["ready"]); self.assertIn("EICR", [x["check"] for x in r["findings"] if x["status"] == "FAIL"])
    def test_expired_epc_fails(self):
        r = rr.check_property(region="South West", gas="2026-09-01", eicr="2024-01-01", epc="2015-01-01", today=T)
        self.assertEqual([x["status"] for x in r["findings"] if x["check"] == "EPC"], ["FAIL"])
    def test_no_gas(self):
        r = rr.check_property(region="North East", no_gas=True, eicr="2024-01-01", epc="2020-01-01", today=T)
        self.assertTrue(r["ready"])
    def test_rating_f_fails(self):
        r = rr.check_property(region="London", gas="2026-09-01", eicr="2024-01-01", epc="2020-01-01", epc_rating="F", today=T)
        self.assertFalse(r["ready"])
    def test_fee_scales(self):
        r = rr.check_property(region="London", no_gas=True, eicr="2024-01-01", epc="2020-01-01", properties=4, today=T)
        self.assertEqual(r["fee_gbp_per_year"], 260)
    def test_past_deadline_fails(self):
        r = rr.check_property(region="West Midlands", no_gas=True, eicr="2024-01-01", epc="2020-01-01", today="2027-04-01")
        self.assertFalse(r["ready"])
    def test_window_open_is_warn(self):
        r = rr.check_property(region="West Midlands", no_gas=True, eicr="2024-01-01", epc="2020-01-01", today="2027-01-10")
        self.assertEqual([x["status"] for x in r["findings"] if x["check"] == "registration deadline"], ["WARN"])
    def test_unknown_region(self):
        r = rr.check_property(region="Narnia", today=T)
        self.assertFalse(r["ready"])
    def test_report_text(self):
        r = rr.check_property(region="London", gas="2026-09-01", eicr="2024-03-01", epc="2020-01-01", today=T)
        s = rr.format_report(r); self.assertIn("READY", s); self.assertIn("£65", s)

class Cli(unittest.TestCase):
    def run_cli(self, *args, inp=None):
        return subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rentready", "__init__.py"), *args],
                              capture_output=True, text=True, input=inp)
    def test_regions(self):
        p = self.run_cli("regions"); self.assertEqual(p.returncode, 0); self.assertIn("West Midlands", p.stdout)
    def test_check_json_exit_codes(self):
        p = self.run_cli("check", "--region=London", "--gas=2026-09-01", "--eicr=2024-01-01", "--epc=2020-01-01", f"--today={T}", "--json")
        self.assertEqual(p.returncode, 0); self.assertTrue(json.loads(p.stdout)["ready"])
        p = self.run_cli("check", "--region=London", f"--today={T}"); self.assertEqual(p.returncode, 1)
    def test_mcp(self):
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "check_property", "arguments": {"region": "London", "no_gas": True, "eicr": "2024-01-01", "epc": "2020-01-01"}}}]
        p = self.run_cli("mcp", inp="\n".join(json.dumps(m) for m in msgs) + "\n")
        out = [json.loads(l) for l in p.stdout.splitlines() if l.strip()]
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "rentready")
        self.assertEqual(out[1]["result"]["tools"][0]["name"], "check_property")
        self.assertTrue(out[2]["result"]["structuredContent"]["ready"])

if __name__ == "__main__":
    unittest.main()


PORTFOLIO_CSV = """name,postcode,region,gas,no_gas,eicr,epc,epc_rating
12 Example St,B3 2TA,West Midlands,2026-02-01,,2023-06-01,2017-05-01,D
Flat 4,SW1A 1AA,London,,yes,2024-01-01,2020-01-01,C
Old cottage,CF10 1AA,Wales,2026-01-01,,2022-01-01,2016-01-01,E
"""

class Portfolio(unittest.TestCase):
    def test_csv_and_aliases(self):
        rows = rr.read_portfolio("Address,Post Code,Gas Safety,EICR date,EPC date,Rating\nA,B3 2TA,2026-01-01,2024-01-01,2020-01-01,C\n")
        self.assertEqual(rows[0]["name"], "A"); self.assertEqual(rows[0]["postcode"], "B3 2TA")
        self.assertEqual(rows[0]["gas"], "2026-01-01"); self.assertEqual(rows[0]["epc_rating"], "C")
    def test_json_input(self):
        rows = rr.read_portfolio('[{"name":"A","postcode":"B3 2TA","gas":"2026-01-01"}]')
        self.assertEqual(rows[0]["gas"], "2026-01-01")
    def test_portfolio_offline_regions(self):
        p = rr.check_portfolio(rr.read_portfolio(PORTFOLIO_CSV), today=T)
        self.assertEqual(p["count"], 3)
        names = {x["name"]: x for x in p["properties"]}
        self.assertTrue(names["12 Example St"]["ready"]); self.assertEqual(names["12 Example St"]["window"]["deadline"], "2027-03-14")
        self.assertEqual(names["12 Example St"]["next"], {"date": "2026-12-15", "what": "registration window opens", "days": 50})
        self.assertTrue(names["Flat 4"]["ready"])
        self.assertIsNone(names["Old cottage"]["ready"])  # Wales: out of scope, not counted in the fee
        self.assertEqual(p["in_scope"], 2); self.assertEqual(p["fee_gbp_per_year"], 130); self.assertEqual(p["earliest_deadline"], "2027-03-14")
        txt = rr.format_portfolio(p)
        self.assertIn("Fee: £130 a year for 2 properties", txt); self.assertIn("Earliest deadline: 2027-03-14", txt)
    def test_not_ready_counts(self):
        p = rr.check_portfolio(rr.read_portfolio("name,region,gas,eicr,epc\nX,London,2026-01-01,,2020-01-01\n"), today=T)
        self.assertEqual(p["not_ready"], 1)

class Calendar(unittest.TestCase):
    def test_events_and_ics(self):
        r = rr.check_property(region="West Midlands", gas="2026-02-01", eicr="2023-06-01", epc="2017-05-01", today=T); r["name"] = "12 Example St"
        ev = rr.calendar_events([r])
        self.assertEqual([e["date"] for e in ev], ["2026-12-15", "2027-02-01", "2027-03-14", "2027-05-01", "2028-06-01"])
        ics = rr.format_ics(ev, [60, 14], stamp="20261026T000000Z")
        self.assertTrue(ics.startswith("BEGIN:VCALENDAR\r\n")); self.assertTrue(ics.endswith("END:VCALENDAR\r\n"))
        self.assertEqual(ics.count("BEGIN:VEVENT"), 5); self.assertEqual(ics.count("BEGIN:VALARM"), 10)
        self.assertIn("DTSTART;VALUE=DATE:20270314", ics); self.assertIn("TRIGGER;VALUE=DURATION:-P60D", ics)
        for line in ics.split("\r\n"):
            self.assertLessEqual(len(line.encode()), 75)
        # deterministic UIDs: same input, same calendar
        self.assertEqual(ics, rr.format_ics(rr.calendar_events([r]), [60, 14], stamp="20261026T000000Z"))
    def test_escape(self):
        self.assertEqual(rr._ics_escape("a,b;c\nd"), "a\\,b\\;c\\nd")
    def test_cli_calendar_single(self):
        out = subprocess.run([sys.executable, "-m", "rentready", "calendar", "--region=London", "--gas=2026-09-01", "--eicr=2024-03-01", "--epc=2020-01-01", "--today=" + T, "--reminders=30"],
                             capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(out.returncode, 0); self.assertIn("BEGIN:VCALENDAR", out.stdout); self.assertIn("-P30D", out.stdout); self.assertNotIn("-P60D", out.stdout)

class McpTools(unittest.TestCase):
    def test_three_tools_and_portfolio_call(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "check_portfolio", "arguments": {"portfolio": "name,region,gas,eicr,epc\nX,London,2026-09-01,2024-01-01,2020-01-01\n", "today": T}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "make_calendar", "arguments": {"region": "London", "gas": "2026-09-01", "eicr": "2024-01-01", "epc": "2020-01-01", "name": "X"}}}]
        out = subprocess.run([sys.executable, "-m", "rentready", "mcp"], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, cwd=root)
        res = [json.loads(l) for l in out.stdout.strip().splitlines()]
        self.assertEqual([t["name"] for t in res[1]["result"]["tools"]], ["check_property", "check_portfolio", "make_calendar"])
        self.assertEqual(res[2]["result"]["structuredContent"]["fee_gbp_per_year"], 65)
        self.assertIn("BEGIN:VCALENDAR", res[3]["result"]["content"][0]["text"]); self.assertEqual(len(res[3]["result"]["structuredContent"]["events"]), 5)

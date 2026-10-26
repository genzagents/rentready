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

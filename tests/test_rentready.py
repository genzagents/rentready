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

class FindIssueTests(unittest.TestCase):
    """find_issue reads the label listing first (search lags new issues) and picks the oldest duplicate."""

    def _run(self, by_label, by_search):
        from rentready import watch
        calls = []

        def fake_gh(*args, input_=None):
            calls.append(args)
            return json.dumps(by_label if "--label" in args else by_search)

        orig, watch.gh = watch.gh, fake_gh
        try:
            return watch.find_issue("o/r", "rentready watch: x", "rentready"), calls
        finally:
            watch.gh = orig

    def test_oldest_duplicate_from_label_listing(self):
        dup = [{"number": n, "title": "rentready watch: x", "body": "", "state": "OPEN"} for n in (2, 1)]
        it, calls = self._run(dup, [])
        self.assertEqual(it["number"], 1)
        self.assertEqual(len(calls), 1)

    def test_falls_back_to_search_when_label_removed(self):
        it, calls = self._run([], [{"number": 7, "title": "rentready watch: X", "body": "", "state": "CLOSED"}])
        self.assertEqual(it["number"], 7)
        self.assertEqual(len(calls), 2)

    def test_none_when_absent(self):
        it, _ = self._run([{"number": 3, "title": "other", "body": "", "state": "OPEN"}], [])
        self.assertIsNone(it)


class PackTests(unittest.TestCase):
    """rentready pack: pre-filled answers, GATHER gaps, files to renew before upload (no network: region given)."""
    FULL = {"name": "2 Full Rd", "postcode": "B3 2TA", "region": "West Midlands", "gas": "2026-09-01", "eicr": "2024-06-01",
            "epc": "2019-05-01", "epc_rating": "C", "ownership": "freehold", "dwelling_type": "terraced house", "bedrooms": "3",
            "let": "y", "occupants": "4", "households": "1", "licence": "none", "furnished": "unfurnished", "rent": "1100",
            "rent_frequency": "monthly", "bills": "none"}

    def _pack(self, rows, **kw):
        from rentready.pack import build_pack
        return build_pack(rows, today="2026-10-27", **kw)

    def test_full_row_is_ready_to_register(self):
        pk = self._pack([self.FULL])
        x = pk["properties"][0]
        self.assertTrue(x["ready_to_register"])
        self.assertEqual(pk["missing_columns"], [])
        self.assertIn("Currently let?", [a["question"] for a in x["answers"] if a["answer"] == "yes"])
        self.assertEqual(x["files"][0]["file"], "2-full-rd_gas-safety-record_2026-09-01.pdf")

    def test_check_only_row_lists_columns_to_add(self):
        pk = self._pack([{"name": "A", "region": "London", "no_gas": "yes", "eicr": "2024-01-01", "epc": "2020-01-01"}])
        x = pk["properties"][0]
        self.assertFalse(x["ready_to_register"])
        self.assertIn("bedrooms", pk["missing_columns"])
        self.assertNotIn("freeholder", pk["missing_columns"])
        self.assertEqual(x["files"][0]["state"], "N/A")

    def test_expired_eicr_renew_lapsed_epc_needs_tenancy_start_and_f_needs_mees(self):
        row = dict(self.FULL, eicr="2019-01-01", epc="2014-05-01", epc_rating="F")
        files = {f["item"].split(" ")[0]: f for f in self._pack([row])["properties"][0]["files"]}
        self.assertEqual(files["EICR"]["state"], "RENEW")
        self.assertEqual(files["Most"]["state"], "GATHER")
        self.assertIn("tenancy start", files["Most"]["note"])
        self.assertIn("MEES", files)
        row["tenancy_start"] = "2023-02-01"
        files = {f["item"].split(" ")[0]: f for f in self._pack([row])["properties"][0]["files"]}
        self.assertEqual(files["Most"]["state"], "READY")

    def test_markdown_and_organisation(self):
        from rentready.pack import format_pack
        md = format_pack(self._pack([self.FULL], organisation=True))
        self.assertIn("Companies House", md)
        self.assertIn("**ready to register**", md)
        self.assertIn("`2-full-rd_eicr_2024-06-01.pdf`", md)

    def test_mcp_tool_listed(self):
        self.assertIn("registration_pack", [t["name"] for t in rr.MCP_TOOLS])


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
    def test_four_tools_and_portfolio_call(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "check_portfolio", "arguments": {"portfolio": "name,region,gas,eicr,epc\nX,London,2026-09-01,2024-01-01,2020-01-01\n", "today": T}}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "make_calendar", "arguments": {"region": "London", "gas": "2026-09-01", "eicr": "2024-01-01", "epc": "2020-01-01", "name": "X"}}}]
        out = subprocess.run([sys.executable, "-m", "rentready", "mcp"], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True, cwd=root)
        res = [json.loads(l) for l in out.stdout.strip().splitlines()]
        self.assertEqual([t["name"] for t in res[1]["result"]["tools"]], ["check_property", "check_portfolio", "make_calendar", "registration_pack"])
        self.assertEqual(res[2]["result"]["structuredContent"]["fee_gbp_per_year"], 65)
        self.assertIn("BEGIN:VCALENDAR", res[3]["result"]["content"][0]["text"]); self.assertEqual(len(res[3]["result"]["structuredContent"]["events"]), 5)


class Watch(unittest.TestCase):
    """rentready watch: snapshot, diff and the issue body round trip (no network: --region given)."""
    ROWS = [
        {"name": "A", "region": "West Midlands", "gas": "2026-02-01", "eicr": "2023-06-01", "epc": "2017-05-01", "epc_rating": "D"},
        {"name": "B", "region": "London", "no_gas": "yes", "eicr": "2024-01-01", "epc": "2020-01-01", "epc_rating": "C"},
    ]

    def snap(self, today, rows=None, warn=60):
        from rentready import watch
        return watch.snapshot(rr.check_portfolio(rows or self.ROWS, today=today), warn)

    def test_first_run_is_silent(self):
        from rentready import watch
        self.assertEqual(watch.diff(None, self.snap("2026-10-27")), ([], []))

    def test_unchanged_is_silent(self):
        from rentready import watch
        self.assertEqual(watch.diff(self.snap("2026-10-27"), self.snap("2026-10-28")), ([], []))

    def test_window_opens_and_cert_comes_due(self):
        from rentready import watch
        alerts, better = watch.diff(self.snap("2026-10-27"), self.snap("2026-12-20"))
        self.assertEqual(better, [])
        self.assertTrue(any("West Midlands registration window is open" in a for a in alerts), alerts)
        self.assertTrue(any("gas safety record expires 2027-02-01 (43 days)" in a for a in alerts), alerts)
        self.assertFalse(any("registration deadline is now" in a for a in alerts), alerts)  # no duplicate wording
        self.assertEqual(len(alerts), 2)

    def test_deadline_passes_and_cert_expires(self):
        from rentready import watch
        alerts, _ = watch.diff(self.snap("2026-12-20"), self.snap("2027-03-20"))
        self.assertTrue(any("A: no longer READY" in a for a in alerts), alerts)
        self.assertTrue(any("gas safety record is now FAIL" in a for a in alerts), alerts)
        self.assertTrue(any("deadline 2027-03-14 has passed" in a for a in alerts), alerts)

    def test_renewal_is_better_and_removal_and_addition(self):
        from rentready import watch
        prev = self.snap("2027-03-20")
        rows = [dict(self.ROWS[0], gas="2027-03-15"), {"name": "C", "region": "North West", "eicr": "2024-01-01", "epc": "2020-01-01"}]
        alerts, better = watch.diff(prev, self.snap("2027-03-21", rows))
        self.assertTrue(any("A: gas safety record is now PASS" in b for b in better), better)
        self.assertTrue(any("B: removed" in b for b in better), better)
        self.assertTrue(any("C: added to the portfolio (NOT READY)" in a for a in alerts), alerts)  # no gas date

    def test_body_round_trip_and_comment(self):
        from rentready import watch
        p = rr.check_portfolio(self.ROWS, today="2026-10-27")
        snap = watch.snapshot(p)
        body = watch.render_body("properties.csv", p, snap, "https://example/run")
        self.assertTrue(body.startswith("## rentready watch: properties.csv"))
        self.assertIn("| A | West Midlands | 2027-03-14 | READY |", body)
        self.assertEqual(watch.parse_state(body), json.loads(json.dumps(snap)))
        c = watch.render_comment(["A: x"], ["B: y"], p, "@me", "")
        self.assertTrue(c.startswith("@me **Action needed**")); self.assertIn("- B: y", c)
        self.assertIn("nothing changed", watch.render_comment([], [], p, "", ""))

    def test_cli_state_file_and_outputs(self):
        import tempfile
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as d:
            csv = os.path.join(d, "p.csv"); st = os.path.join(d, "state.json"); outp = os.path.join(d, "out.txt")
            with open(csv, "w") as fh:
                fh.write("name,region,gas,eicr,epc\nA,West Midlands,2026-02-01,2023-06-01,2017-05-01\n")
            env = dict(os.environ, GITHUB_OUTPUT=outp)
            r1 = subprocess.run([sys.executable, "-m", "rentready", "watch", csv, f"--state={st}", "--today=2026-10-27"], capture_output=True, text=True, cwd=root, env=env)
            self.assertEqual(r1.returncode, 0, r1.stderr); self.assertTrue(os.path.isfile(st))
            r2 = subprocess.run([sys.executable, "-m", "rentready", "watch", csv, f"--state={st}", "--today=2026-12-20"], capture_output=True, text=True, cwd=root, env=env)
            self.assertEqual(r2.returncode, 1); self.assertIn("ALERT: A: the West Midlands registration window is open", r2.stdout)
            self.assertIn("regressed=true", open(outp).read())
            r3 = subprocess.run([sys.executable, "-m", "rentready", "watch", csv, f"--state={st}", "--today=2026-12-20", "--no-fail-on-regression"], capture_output=True, text=True, cwd=root, env=env)
            self.assertEqual(r3.returncode, 0); self.assertNotIn("ALERT", r3.stdout)

import io, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rentready as rr
from rentready import hosted as H
from rentready import watch as W

T = "2026-10-27"
NOW = 1_800_000_000.0
CSV = "name,postcode,region,gas,no_gas,eicr,epc,epc_rating\nFlat 1,B3 2TA,West Midlands,2026-02-01,,2023-06-01,2017-05-01,D\nFlat 2,SW1A 1AA,London,,yes,2024-01-01,2020-01-01,C\n"
LINES = "Flat 1, B3 2TA, 2026-02-01, 2023-06-01, 2017-05-01, D\nFlat 2 | SW1A 1AA | no gas | 2024-01-01 | 2020-01-01 | C\n"


def sub(portfolio=CSV, status="active", email="l@example.com", **extra):
    s = {"id": "sub_1", "status": status, "customer": {"email": email, "name": "Lee"},
         "custom_field_data": {"portfolio": portfolio}, "current_period_end": "2027-10-27T00:00:00Z"}
    s.update(extra)
    return s


class Parse(unittest.TestCase):
    def test_csv_with_header(self):
        rows = H.parse_portfolio_text(CSV)
        self.assertEqual([r["name"] for r in rows], ["Flat 1", "Flat 2"]); self.assertEqual(rows[1]["no_gas"], "yes")
    def test_headerless_lines(self):
        rows = H.parse_portfolio_text(LINES)
        self.assertEqual(rows[0], {"name": "Flat 1", "postcode": "B3 2TA", "gas": "2026-02-01", "eicr": "2023-06-01", "epc": "2017-05-01", "epc_rating": "D"})
        self.assertEqual(rows[1]["no_gas"], "yes"); self.assertNotIn("gas", rows[1]); self.assertEqual(rows[1]["postcode"], "SW1A 1AA")
    def test_dash_means_missing(self):
        rows = H.parse_portfolio_text("Flat 3, M1 1AE, -, -, 2019-09-01, E")
        self.assertEqual(set(rows[0]), {"name", "postcode", "epc", "epc_rating"})
    def test_json(self):
        rows = H.parse_portfolio_text(json.dumps([{"name": "x", "postcode": "B3 2TA", "gas": "2026-01-01"}]))
        self.assertEqual(rows[0]["postcode"], "B3 2TA")
    def test_empty(self):
        self.assertEqual(H.parse_portfolio_text(""), []); self.assertEqual(H.parse_portfolio_text(None), [])


class Normalise(unittest.TestCase):
    def test_active_with_portfolio(self):
        s = H.normalise(sub())
        self.assertEqual(s["email"], "l@example.com"); self.assertEqual(len(s["rows"]), 2); self.assertEqual(s["limit"], 10)
    def test_inactive_or_empty_skipped(self):
        self.assertIsNone(H.normalise(sub(status="canceled"))); self.assertIsNone(H.normalise(sub(portfolio="")))
        self.assertIsNone(H.normalise(sub(email="")))
    def test_alias_slug_and_limit(self):
        s = {"id": "s", "status": "active", "customer": {"email": "a@b.c"}, "custom_field_data": {"properties": LINES}}
        n = H.normalise(s, limit=1)
        self.assertEqual(len(n["rows"]), 1); self.assertEqual(n["dropped"], 1)
    def test_product_limits_env(self):
        os.environ["RENTREADY_PRODUCT_LIMITS"] = "prod_big=50,prod_small=5"
        try:
            self.assertEqual(H.limit_for({"product_id": "prod_big"}), 50)
            self.assertEqual(H.limit_for({"product": {"id": "prod_small"}}), 5)
            self.assertEqual(H.limit_for({"product_id": "other"}), 10)
        finally:
            del os.environ["RENTREADY_PRODUCT_LIMITS"]


class Decide(unittest.TestCase):
    def test_first_then_silence_then_alert_then_monthly(self):
        self.assertEqual(H.decide(None, [], [], NOW), "first")
        st = {"last_report_at": NOW}
        self.assertEqual(H.decide(st, [], [], NOW + 3600), "")
        self.assertEqual(H.decide(st, ["x"], [], NOW + 3600), "alert")
        self.assertEqual(H.decide(st, [], ["y"], NOW + 3600), "alert")
        self.assertEqual(H.decide(st, [], [], NOW + H.MONTH), "digest")


class EndToEnd(unittest.TestCase):
    """The whole hosted loop offline: regions are given in the CSV so no postcode lookup happens."""
    def setUp(self):
        self.tmp = tempfile.mkdtemp(); os.environ["RENTREADY_STATE_DIR"] = self.tmp
    def tearDown(self):
        del os.environ["RENTREADY_STATE_DIR"]

    def test_first_report_then_silence_then_alert_then_digest(self):
        s = H.normalise(sub())
        out = io.StringIO()
        H.run([s], dry_run=True, now=NOW, today=T, out=out)
        text = out.getvalue()
        self.assertIn("would send [first] to l@example.com: Your first rentready report: 2 ready, 0 not ready", text)
        self.assertIn("Flat 1", text); self.assertIn("Flat 2", text); self.assertIn("gas safety record", text)
        st = H.load_state("sub_1")
        self.assertEqual(st["last_kind"], "first"); self.assertEqual(st["inputs"][0]["region"], "West Midlands")
        self.assertEqual(st["last_email"]["kind"], "first"); self.assertEqual(st["today"], T)
        # same day, an hour later: nothing
        out = io.StringIO(); H.run([s], dry_run=True, now=NOW + 3600, today=T, out=out)
        self.assertIn("no change", out.getvalue()); self.assertNotIn("would send", out.getvalue())
        # 2026-12-15: the West Midlands window opens, and Flat 1's gas record is within 60 days
        out = io.StringIO(); H.run([s], dry_run=True, now=NOW + 49 * 86400, today="2026-12-15", out=out)
        text = out.getvalue()
        self.assertIn("would send [alert]", text); self.assertIn("registration window is open", text)
        self.assertIn("gas safety record expires 2027-02-01", text)
        # 26 days later with nothing new (the deadline is still more than 60 days away): the monthly digest
        out = io.StringIO(); H.run([s], dry_run=True, now=NOW + 80 * 86400, today="2027-01-10", out=out)
        self.assertIn("would send [digest]", out.getvalue()); self.assertIn("rentready monthly: ", out.getvalue())

    def test_replay_reproduces_the_stored_report(self):
        s = H.normalise(sub(portfolio=LINES.replace("B3 2TA", "B3 2TA")))
        # headerless lines carry no region; give it through state so the test stays offline
        H.save_state("sub_1", {"inputs": [{"postcode": "B3 2TA", "region": "West Midlands"}, {"postcode": "SW1A 1AA", "region": "London"}]})
        H.run([s], dry_run=True, now=NOW, today=T, out=io.StringIO())
        path = os.path.join(self.tmp, "sub_1.json")
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
        self.assertEqual(st["inputs"][1]["region"], "London")  # the lookup result is stored with the inputs
        res = H.replay(st)
        self.assertTrue(res["same_snapshot"]); self.assertTrue(res["same_report"])
        self.assertEqual(res["last_email"]["kind"], "first")
        # the CLI form exits 0 on an identical replay and 1 when the stored report has been tampered with
        buf = io.StringIO(); old, sys.stdout = sys.stdout, buf
        try:
            self.assertEqual(rr.main(["hosted", "replay", path]), 0)
            st["report"] = st["report"].replace("READY", "READY?", 1)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(st, f)
            self.assertEqual(rr.main(["hosted", "replay", path]), 1)
        finally:
            sys.stdout = old
        self.assertIn("IDENTICAL", buf.getvalue()); self.assertIn("DIFFERENT (snapshot same, report differs)", buf.getvalue())

    def test_subscribers_file_cli_and_limit_note(self):
        os.environ["RENTREADY_LIMIT"] = "1"
        try:
            src = os.path.join(self.tmp, "subs.json")
            with open(src, "w", encoding="utf-8") as f:
                json.dump({"items": [sub(), sub(status="canceled")]}, f)
            buf = io.StringIO(); old, sys.stdout = sys.stdout, buf
            with _Silence():
                try:
                    rc = rr.main(["hosted", "run", f"--subscribers={src}", "--dry-run", f"--today={T}", f"--now={NOW}"])
                finally:
                    sys.stdout = old
            self.assertEqual(rc, 0)
            st = H.load_state("sub_1")
            self.assertIn("your plan covers 1 properties; 1 more", st["last_email"]["text"])
        finally:
            del os.environ["RENTREADY_LIMIT"]

    def test_one_bad_subscriber_does_not_stop_the_others(self):
        bad = {"id": "bad", "email": "bad@example.com", "name": "", "rows": [{"postcode": "B3 2TA", "region": "West Midlands", "gas": "not-a-date"}], "dropped": 0, "limit": 10}
        good = H.normalise(sub())
        out = io.StringIO()
        with self.assertLogs() if False else _Silence():
            H.run([bad, good], dry_run=True, now=NOW, today=T, out=out)
        self.assertIn("would send [first] to l@example.com", out.getvalue())


class _Silence:
    def __enter__(self):
        self._err, sys.stderr = sys.stderr, io.StringIO()
    def __exit__(self, *a):
        sys.stderr = self._err


class Launchd(unittest.TestCase):
    def test_plist_mentions_module(self):
        buf = io.StringIO(); old, sys.stdout = sys.stdout, buf
        try:
            H.main(["launchd"])
        finally:
            sys.stdout = old
        self.assertIn("rentready.hosted", buf.getvalue()); self.assertIn("<integer>3600</integer>", buf.getvalue())


if __name__ == "__main__":
    unittest.main()

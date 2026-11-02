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


class Sponsors(unittest.TestCase):
    def test_one_time_buys_a_year_once(self):
        led = {}
        new = H.update_ledger(led, [{"login": "Lee", "monthly": 16, "one_time": True}], NOW)
        self.assertEqual(new, ["lee"]); self.assertEqual(led["lee"]["paid_until"], NOW + H.YEAR)
        # GitHub keeps listing it for 30 days: no second year
        self.assertEqual(H.update_ledger(led, [{"login": "Lee", "monthly": 16, "one_time": True}], NOW + 86400), [])
        self.assertEqual(led["lee"]["paid_until"], NOW + H.YEAR)
    def test_renewal_after_the_year(self):
        led = {}
        H.update_ledger(led, [{"login": "lee", "monthly": 16, "one_time": True}], NOW)
        later = NOW + H.YEAR + 10
        self.assertEqual(H.update_ledger(led, [{"login": "lee", "monthly": 20, "one_time": True}], later), [])
        self.assertEqual(led["lee"]["paid_until"], later + H.YEAR)
    def test_too_little_is_ignored_and_monthly_has_grace(self):
        led = {}
        self.assertEqual(H.update_ledger(led, [{"login": "a", "monthly": 5, "one_time": True},
                                               {"login": "b", "monthly": 1}, {"login": "c", "monthly": 2}], NOW), ["c"])
        self.assertGreater(led["c"]["paid_until"], NOW + H.MONTH); self.assertEqual(led["c"]["plan"], "monthly")
    def test_welcome_example_parses_back(self):
        body = H.welcome_body("lee")
        example = body.split("```")[1]
        rows, cid = H.latest_portfolio([{"id": 5, "author": "Lee", "body": "```\n" + example + "```"}], "lee")
        self.assertEqual(cid, "5"); self.assertEqual([r["postcode"] for r in rows], ["B15 2TT", "CV37 6BB"])
        self.assertEqual(rows[1].get("no_gas"), "yes")
        copied = "name, postcode, gas safety date, EICR date, EPC date, EPC rating, tenancy start\n" + example
        self.assertEqual(len(H.latest_portfolio([{"id": 6, "author": "lee", "body": copied}], "lee")[0]), 2)
    def test_latest_comment_by_sponsor_wins(self):
        cs = [{"id": 1, "author": "lee", "body": LINES}, {"id": 2, "author": "genzagents-bot", "body": CSV},
              {"id": 3, "author": "lee", "body": "thanks!"}, {"id": 4, "author": "lee", "body": "Flat 9, M1 1AE, -, -, 2019-09-01, E"}]
        rows, cid = H.latest_portfolio(cs, "LEE")
        self.assertEqual(cid, "4"); self.assertEqual(rows[0]["postcode"], "M1 1AE")
        self.assertEqual(H.latest_portfolio(cs[:3][1:], "lee")[0], [])
    def test_own_reports_and_prose_are_never_read_as_a_list(self):
        # the gh token's account can be the sponsor too (our own dogfood repo): reports must be skipped
        report = H.comment_text("lee", "Your first rentready report: 2 ready", H.format_portfolio(rr.check_portfolio(H.parse_portfolio_text(CSV), today=T)))
        cs = [{"id": 1, "author": "lee", "body": "Test list (sample, not real):\n" + LINES}, {"id": 2, "author": "lee", "body": report}]
        rows, cid = H.latest_portfolio(cs, "lee")
        self.assertEqual(cid, "1"); self.assertEqual([r["postcode"] for r in rows], ["B3 2TA", "SW1A 1AA"])
        self.assertIn(H.BOT, H.welcome_body("lee"))
    def test_repo_name_is_safe(self):
        self.assertEqual(H.repo_name("genzagents", "Lee_O.K"), "genzagents/rentready-lee_o.k")


class GithubPass(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); os.environ["RENTREADY_STATE_DIR"] = self.tmp.name
        self.calls = []
        self.comments = []
        def fake(method, path, body=None):
            self.calls.append((method, path, body))
            if path == "/graphql":
                return {"data": {"organization": {"sponsorshipsAsMaintainer": {"nodes": [
                    {"tier": {"monthlyPriceInDollars": 16, "isOneTime": True}, "sponsorEntity": {"login": "Lee"}}]}}}}
            if path.endswith("/issues") and method == "POST":
                return {"number": 1}
            if "/comments" in path and method == "GET":
                return self.comments
            if "/comments" in path and method == "POST":
                return {"html_url": "https://github.com/x#c"}
            return {}
        self._old = H._gh; H._gh = fake
    def tearDown(self):
        H._gh = self._old; del os.environ["RENTREADY_STATE_DIR"]; self.tmp.cleanup()
    def test_new_sponsor_gets_private_repo_invite_and_issue_then_report(self):
        out = io.StringIO()
        self.assertEqual(H.github_pass("genzagents", NOW, False, out), [])
        paths = [(m, p) for m, p, _ in self.calls]
        self.assertIn(("POST", "/orgs/genzagents/repos"), paths)
        self.assertTrue([b for m, p, b in self.calls if p == "/orgs/genzagents/repos"][0]["private"])
        self.assertIn(("PUT", "/repos/genzagents/rentready-lee/collaborators/Lee"), paths)
        self.assertIn("waiting for their properties", out.getvalue())
        # they reply with their list; the next pass reports on the issue
        self.comments = [{"id": 9, "user": {"login": "Lee"}, "body": CSV}]
        self.calls.clear()
        subs = H.github_pass("genzagents", NOW + 3600, False, out)
        self.assertEqual(len(subs), 1); self.assertEqual(subs[0]["repo"], "genzagents/rentready-lee")
        self.assertNotIn(("POST", "/orgs/genzagents/repos"), [(m, p) for m, p, _ in self.calls])
        H.run(subs, dry_run=False, now=NOW + 3600, today=T, out=out)
        posted = [b for m, p, b in self.calls if m == "POST" and p.endswith("/issues/1/comments")]
        self.assertEqual(len(posted), 1); self.assertTrue(posted[0]["body"].startswith("@Lee **Your first rentready report"))
        self.assertIn("Post your whole list again here", posted[0]["body"]); self.assertNotIn("Polar", posted[0]["body"])
    def test_expired_year_posts_one_notice(self):
        out = io.StringIO()
        H.github_pass("genzagents", NOW, False, out)
        H._gh_saved = H._gh
        self.calls.clear()
        later = NOW + H.YEAR + 40 * 86400
        real = H._gh
        H._gh = lambda m, p, b=None: ({"data": {"organization": {"sponsorshipsAsMaintainer": {"nodes": []}}}}
                                      if p == "/graphql" else real(m, p, b))
        H.github_pass("genzagents", later, False, out); H.github_pass("genzagents", later + 3600, False, out)
        notices = [b for m, p, b in self.calls if m == "POST" and "comments" in p]
        self.assertEqual(len(notices), 1); self.assertIn("year has ended", notices[0]["body"])


if __name__ == "__main__":
    unittest.main()

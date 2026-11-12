import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core import db_manager, dime_data, webull_data
from core.theme import money

SYNC_KEY = "webull_sync"


def live_rows(scale=1.0):
    rows = [{"Symbol": "AAPL", "Quantity": 10.0, "Avg Cost": 150.0, "Last Price": 200.0 * scale, "Currency": "USD"},
            {"Symbol": "TSLA", "Quantity": 4.0, "Avg Cost": 300.0, "Last Price": 250.0 * scale, "Currency": "USD"}]
    day = {"AAPL": {"pct": 1.0, "change": 2.0}, "TSLA": {"pct": -2.0, "change": -5.0}}
    return rows, day, {"cash": 1000.0, "market_value": None, "open_pnl": None, "currency": "USD"}


def live_orders():
    return [{"Time": pd.Timestamp("2026-11-10T14:30:00Z"), "Symbol": "AAPL", "Side": "BUY", "Status": "FILLED",
             "Order Type": "LIMIT", "Quantity": 10.0, "Filled Qty": 10.0, "Filled Price": 150.0, "Amount": 1500.0,
             "Order ID": "O-1"},
            {"Time": pd.Timestamp("2026-11-11T15:00:00Z"), "Symbol": "TSLA", "Side": "SELL", "Status": "CANCELLED",
             "Order Type": "LIMIT", "Quantity": 1.0, "Filled Qty": 0.0, "Filled Price": 0.0, "Amount": 0.0,
             "Order ID": "O-2"}]


class WebullSyncTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db)
        # Any SDK access outside an explicit sync is a bug: page loads must only read SQLite.
        self.connect = MagicMock(side_effect=AssertionError("Webull SDK used without Sync"))
        self.patches = [
            patch.object(db_manager, "DB_PATH", self.db),
            patch.object(webull_data, "_connect", self.connect),
            patch.object(dime_data, "get_prices", lambda syms: {}),
            patch.object(dime_data, "get_usd_thb", lambda: (35.0, True)),
            patch.object(webull_data, "get_dividend_history",
                         lambda syms: pd.DataFrame(columns=["Date", "Symbol", "Dividend"])),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        if os.path.exists(self.db):
            os.remove(self.db)

    def allow_sync(self, rows=None, orders=None, orders_error=None):
        self.connect.side_effect = None
        self.connect.return_value = (object(), object(), "ACC-1")
        fetch_orders = MagicMock(side_effect=orders_error, return_value=orders if orders is not None else live_orders())
        return [patch.object(webull_data, "_fetch_account", lambda *a: rows or live_rows()),
                patch.object(webull_data, "_fetch_orders", fetch_orders)]

    def run_page(self, path="../pages/2_Webull.py", app=None):
        app = app or AppTest.from_file(path)
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_sync_saves_snapshot_and_reads_it_back(self):
        expected_positions, expected_metrics = webull_data.compute_snapshot(*live_rows())
        result = self.sync()
        self.assertEqual(result, {"account_id": "ACC-1", "positions": 2, "orders": 2, "warnings": []})

        cached = webull_data.get_portfolio()
        self.assertFalse(cached["is_mock"])
        self.assertEqual(cached["account_id"], "ACC-1")
        self.assertLess(datetime.now(timezone.utc) - cached["last_synced"], timedelta(minutes=1))
        for key, value in expected_metrics.items():
            self.assertAlmostEqual(cached["metrics"][key], value, msg=key)
        pd.testing.assert_frame_equal(cached["positions"], expected_positions, check_dtype=False)

        orders = webull_data.get_order_history()["orders"]
        self.assertEqual(list(orders["Order ID"]), ["O-2", "O-1"])  # newest first
        self.assertEqual(str(orders["Time"].dt.tz), "UTC")

    def sync(self, **kwargs):
        patches = self.allow_sync(**kwargs)
        for p in patches:
            p.start()
        try:
            return webull_data.sync_from_webull()
        finally:
            for p in patches:
                p.stop()

    def test_resync_replaces_data_and_order_failure_keeps_old_orders(self):
        self.sync()
        result = self.sync(rows=live_rows(scale=2.0), orders_error=RuntimeError("history down"))
        self.assertIsNone(result["orders"])
        self.assertIn("history down", result["warnings"][0])
        prices = webull_data.get_portfolio()["positions"].set_index("Symbol")["Last Price"].to_dict()
        self.assertEqual(prices, {"AAPL": 400.0, "TSLA": 500.0})
        self.assertEqual(len(webull_data.get_order_history()["orders"]), 2)  # previous orders retained

    def test_page_loads_read_cache_without_sdk(self):
        app = self.run_page()
        self.assertTrue(any("never synced" in i.value.lower() or "No Webull data saved" in i.value for i in app.info))
        self.run_page("../app.py")  # Executive Dashboard is the default page

        positions, metrics = webull_data.compute_snapshot(*live_rows())
        db_manager.save_webull_data({**metrics, "account_id": "ACC-9"}, positions.rename(columns=webull_data.POSITION_DB),
                                    pd.DataFrame(columns=db_manager.WEBULL_ORDER_FIELDS),
                                    synced_at=datetime.now(timezone.utc) - timedelta(hours=3))
        app = self.run_page()
        self.assertEqual(app.tabs[0].metric[0].value, money(metrics["total_value"]))
        header = "".join(md.value for md in app.markdown)
        self.assertIn("Last synced", header)
        self.assertIn("3 h ago", header)
        self.assertIn("ACC-9", header)
        self.assertFalse([i for i in app.info if "sample data" in i.value])  # demo banner gone once cached
        exec_app = self.run_page("../app.py")  # Executive Dashboard is the default page
        self.assertEqual(exec_app.metric[1].value, money(metrics["total_value"]))
        self.connect.assert_not_called()

    def test_sync_button_saves_and_reruns_with_new_data(self):
        app = self.run_page()
        patches = self.allow_sync()
        for p in patches:
            p.start()
        try:
            app.button(key=SYNC_KEY).click()
            self.run_page(app=app)
        finally:
            for p in patches:
                p.stop()
        self.assertEqual(self.connect.call_count, 1)
        self.assertTrue(any("Synced 2 positions, 2 orders" in s.value for s in app.success))
        self.assertEqual(app.tabs[0].metric[0].value, money(webull_data.compute_snapshot(*live_rows())[1]["total_value"]))
        self.assertIsNotNone(db_manager.get_webull_data()["summary"])

    def test_sync_failure_keeps_cached_data(self):
        positions, metrics = webull_data.compute_snapshot(*live_rows())
        db_manager.save_webull_data({**metrics, "account_id": "ACC-1"}, positions.rename(columns=webull_data.POSITION_DB),
                                    pd.DataFrame(columns=db_manager.WEBULL_ORDER_FIELDS))
        before = db_manager.get_webull_data()["summary"]
        self.connect.side_effect = RuntimeError("401 UNAUTHORIZED")
        app = self.run_page()
        app.button(key=SYNC_KEY).click()
        self.run_page(app=app)
        self.assertTrue(any("401 UNAUTHORIZED" in e.value and "kept" in e.value for e in app.error))
        self.assertEqual(db_manager.get_webull_data()["summary"], before)

    def test_missing_secrets_message(self):
        self.connect.side_effect = KeyError("Webull")
        app = self.run_page()
        app.button(key=SYNC_KEY).click()
        self.run_page(app=app)
        self.assertTrue(any("credentials not found" in e.value for e in app.error))
        self.assertIsNone(db_manager.get_webull_data()["summary"])


class SeedTokenTest(unittest.TestCase):
    def test_verified_token_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(webull_data, "TOKEN_DIR", webull_data.Path(tmp)):
            token = webull_data.Path(tmp) / "token.txt"
            webull_data._seed_token("SECRET-1")
            self.assertTrue(token.read_text().startswith("SECRET-1"))
            token.write_text("SDK-VERIFIED\n1893456000000\nNORMAL\n")  # what the SDK saves after approval
            webull_data._seed_token("SECRET-1")
            self.assertTrue(token.read_text().startswith("SDK-VERIFIED"))
            webull_data._seed_token("SECRET-2")  # a rotated secret is seeded again
            self.assertTrue(token.read_text().startswith("SECRET-2"))


if __name__ == "__main__":
    unittest.main()

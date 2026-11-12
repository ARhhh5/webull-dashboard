import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core import db_manager, dime_data, fx, webull_data
from core.theme import money

AS_OF = datetime(2026, 11, 12, 1, 27, tzinfo=timezone.utc)
FX = fx.FxRate(rate=33.65, source="test quote", as_of=AS_OF)


def no_fx():
    raise AssertionError("FX looked up although every amount is USD")


def pos(symbol, qty, avg, last, ccy="USD"):
    return {"Symbol": symbol, "Quantity": qty, "Avg Cost": avg, "Last Price": last, "Currency": ccy}


def webull_app_case():
    """Webull App 2026-11-12: 34 positions, Account Value USD 8,049.98, Open PnL -USD 5,844.96 (-42.13%),
    Cash USD 20.47, while account totals are reported in THB."""
    rows = [pos(f"S{i:02d}", 1.0, 400.0, 200.0) for i in range(33)] + [pos("LAST", 1.0, 674.47, 1429.51)]
    balance = {"total_asset_currency": "THB", "total_market_value": str(8029.51 * FX.rate),
               "total_cash_balance": str(20.47 * FX.rate), "total_unrealized_profit_loss": str(-5844.96 * FX.rate),
               "account_currency_assets": [{"currency": "USD", "cash_balance": "20.47"}]}
    return rows, {}, balance


class ComputeSnapshotTest(unittest.TestCase):
    def test_webull_app_reference_case(self):
        df, m = webull_data.compute_snapshot(*webull_app_case(), fx_lookup=lambda: FX)
        self.assertEqual(m["positions"], 34)
        self.assertAlmostEqual(m["total_value"], 8049.98, places=2)
        self.assertAlmostEqual(m["market_value"], 8029.51, places=2)
        self.assertAlmostEqual(m["open_pnl"], -5844.96, places=2)
        self.assertEqual(round(m["open_pnl_pct"], 2), -42.13)
        self.assertAlmostEqual(m["cash"], 20.47, places=2)
        self.assertEqual(m["cash_status"], "USD")
        self.assertEqual((m["base_currency"], m["account_currency"]), ("USD", "THB"))
        self.assertEqual((m["fx_rate"], m["fx_source"], m["fx_as_of"]), (33.65, "test quote", AS_OF))
        self.assertAlmostEqual(m["reconciliation_diff_pct"], 0.0, places=6)
        self.assertEqual(m["warnings"], [])
        # The old bug: THB account totals were shown with a $ sign (~33.6x too large).
        self.assertLess(m["total_value"], float(webull_app_case()[2]["total_market_value"]) / 30)

    def test_usd_account_needs_no_fx(self):
        rows = [pos("AAPL", 10, 150, 200)]
        balance = {"total_asset_currency": "USD", "account_currency_assets": [{"currency": "USD", "cash_balance": "50"}]}
        df, m = webull_data.compute_snapshot(rows, {}, balance, fx_lookup=no_fx)
        self.assertEqual((m["total_value"], m["cash"], m["fx_rate"]), (2050.0, 50.0, None))
        self.assertEqual(df.loc[0, "FX to USD"], 1.0)

    def test_thb_cash_converted_once(self):
        balance = {"total_asset_currency": "THB", "account_currency_assets": [{"currency": "THB", "cash_balance": "3365"}]}
        _, m = webull_data.compute_snapshot([pos("AAPL", 1, 100, 100)], {}, balance, fx_lookup=lambda: FX)
        self.assertAlmostEqual(m["cash"], 100.0)
        self.assertEqual(m["cash_status"], "converted")
        self.assertIn("THB 3,365.00 → USD 100.00", m["cash_detail"])

    def test_mixed_cash_and_positions(self):
        rows = [pos("AAPL", 2, 100, 150), pos("PTT", 100, 30, 33.65, "THB")]
        balance = {"total_asset_currency": "THB", "account_currency_assets": [
            {"currency": "USD", "cash_balance": "10"}, {"currency": "THB", "cash_balance": "336.5"}]}
        df, m = webull_data.compute_snapshot(rows, {}, balance, fx_lookup=lambda: FX)
        ptt = df.set_index("Symbol").loc["PTT"]
        self.assertAlmostEqual(ptt["Market Value"], 100.0)
        self.assertAlmostEqual(ptt["Avg Cost"], 30 / 33.65)
        self.assertEqual(ptt["Currency"], "THB")  # original currency kept for audit
        self.assertAlmostEqual(m["cash"], 20.0)
        self.assertAlmostEqual(m["market_value"], 400.0)
        self.assertAlmostEqual(m["total_value"], 420.0)

    def test_account_total_cash_without_breakdown(self):
        balance = {"total_asset_currency": "THB", "total_cash_balance": "673"}
        _, m = webull_data.compute_snapshot([pos("AAPL", 1, 100, 100)], {}, balance, fx_lookup=lambda: FX)
        self.assertAlmostEqual(m["cash"], 20.0)
        self.assertIn("account total", m["cash_detail"])

    def test_cash_without_currency_is_unverified(self):
        balance = {"total_cash_balance": "500"}  # no total_asset_currency, no breakdown
        _, m = webull_data.compute_snapshot([pos("AAPL", 1, 100, 100)], {}, balance, fx_lookup=lambda: FX)
        self.assertIsNone(m["cash"])
        self.assertEqual(m["cash_status"], "unverified")
        self.assertEqual(m["total_value"], 100.0)  # cash excluded, never guessed as USD
        self.assertTrue(any("Cash balance not verified" in w for w in m["warnings"]))

    def test_position_without_currency_is_excluded(self):
        rows = [pos("AAPL", 1, 100, 100), pos("MYST", 5, 10, 10, None)]
        df, m = webull_data.compute_snapshot(rows, {}, {"total_asset_currency": "USD"}, fx_lookup=no_fx)
        self.assertEqual(list(df["Symbol"]), ["AAPL"])
        self.assertTrue(any("MYST (unknown currency)" in w for w in m["warnings"]))

    def test_missing_fx_uses_labelled_estimate(self):
        rows, day, balance = webull_app_case()
        balance = {**balance, "account_currency_assets": [{"currency": "THB", "cash_balance": str(20.47 * 33.65)}]}
        _, m = webull_data.compute_snapshot(rows, day, balance, fx_lookup=lambda: None, now=AS_OF)
        self.assertTrue(m["fx_estimated"])
        self.assertAlmostEqual(m["fx_rate"], 33.65)
        self.assertEqual(m["fx_source"], fx.ESTIMATED_SOURCE)
        self.assertAlmostEqual(m["cash"], 20.47, places=2)
        self.assertIsNone(m["reconciliation_diff_pct"])  # an estimate cannot reconcile against itself
        self.assertTrue(any("Estimated FX" in w for w in m["warnings"]))

    def test_missing_fx_without_estimate_excludes_thb(self):
        balance = {"total_asset_currency": "THB", "account_currency_assets": [{"currency": "THB", "cash_balance": "100"}]}
        _, m = webull_data.compute_snapshot([pos("AAPL", 1, 100, 100)], {}, balance, fx_lookup=lambda: None)
        self.assertIsNone(m["cash"])
        self.assertEqual(m["total_value"], 100.0)
        self.assertTrue(any("rate unavailable" in w for w in m["warnings"]))

    def test_reconciliation_warning(self):
        rows, day, balance = webull_app_case()
        balance = {**balance, "total_market_value": str(9000 * FX.rate)}
        _, m = webull_data.compute_snapshot(rows, day, balance, fx_lookup=lambda: FX)
        self.assertLess(m["reconciliation_diff_pct"], -2)
        self.assertTrue(any("differs from Webull" in w for w in m["warnings"]))


class FxTest(unittest.TestCase):
    def test_conversions(self):
        self.assertEqual(fx.to_usd(10, "USD", None), 10.0)
        self.assertAlmostEqual(fx.to_usd(33.65, "THB", FX), 1.0)
        self.assertIsNone(fx.to_usd(33.65, "THB", None))
        self.assertIsNone(fx.to_usd(1, None, FX))
        self.assertIsNone(fx.to_usd(1, "EUR", FX))
        self.assertAlmostEqual(fx.from_usd(fx.to_usd(1000, "THB", FX), "THB", FX), 1000)
        self.assertIsNone(fx.from_usd(1, "THB", None))
        self.assertIn("test quote", FX.label())
        fallback = fx.rate_or_fallback(None)
        self.assertTrue(fallback.estimated)
        self.assertIn("Estimated FX", fallback.label())


class CachedSnapshotTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db)
        self.patches = [patch.object(db_manager, "DB_PATH", self.db),
                        patch.object(dime_data, "get_prices", lambda syms: {}),
                        patch.object(dime_data, "get_usd_thb", lambda: FX),
                        patch.object(fx, "fetch_usd_thb", lambda: FX)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        os.path.exists(self.db) and os.remove(self.db)

    def save(self, case=webull_app_case):
        df, m = webull_data.compute_snapshot(*case(), fx_lookup=lambda: FX)
        db_manager.save_webull_data({**m, "account_id": "ACC"}, df.rename(columns=webull_data.POSITION_DB),
                                    pd.DataFrame(columns=db_manager.WEBULL_ORDER_FIELDS))
        return df, m

    def test_cache_round_trip_is_not_converted_again(self):
        df, m = self.save()
        cached = webull_data.get_portfolio()
        self.assertFalse(cached["legacy"])
        for key in webull_data.METRIC_KEYS:
            self.assertAlmostEqual(cached["metrics"][key], m[key], msg=key)
        self.assertEqual(cached["metrics"]["fx_source"], "test quote")
        self.assertEqual(cached["metrics"]["warnings"], [])
        pd.testing.assert_frame_equal(cached["positions"], df, check_dtype=False)
        log = db_manager.get_sync_log()
        self.assertEqual(len(log), 1)
        self.assertIn("total_market_value", log.loc[0, "raw_balance"])

    def test_unverified_cash_reads_back_as_none(self):
        self.save(lambda: ([pos("AAPL", 1, 100, 100)], {}, {"total_cash_balance": "5"}))
        m = webull_data.get_portfolio()["metrics"]
        self.assertIsNone(m["cash"])
        self.assertEqual(m["total_value"], 100.0)

    def test_legacy_snapshot_is_rebuilt_from_positions(self):
        # Pre-fix rows: THB totals stored as if USD, no currency metadata.
        db_manager.init_db()
        with db_manager._connect() as conn:
            conn.execute("INSERT INTO webull_summary (id, total_value, market_value, cash, cost_basis, open_pnl, "
                         "open_pnl_pct, positions, last_synced) VALUES (1, 270883, 270194, 689, 400, -9, -1, 1, "
                         "'2026-11-12T01:27:00+00:00')")
            conn.execute("INSERT INTO webull_positions (symbol, quantity, avg_cost, last_price, currency) "
                         "VALUES ('AAPL', 2, 200, 150, 'USD')")
        data = webull_data.get_portfolio()
        self.assertTrue(data["legacy"])
        self.assertEqual(data["metrics"]["total_value"], 300.0)
        self.assertIsNone(data["metrics"]["cash"])
        self.assertTrue(any("before the USD currency fix" in w for w in data["metrics"]["warnings"]))

    def run_page(self, path, ccy=None):
        app = AppTest.from_file(path).run(timeout=30)
        if ccy:
            app.segmented_control(key="exec_ccy").set_value(ccy).run(timeout=30)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_pages_show_usd_and_convert_thb_for_display_only(self):
        self.save()
        webull = self.run_page("../pages/2_Webull.py")
        self.assertEqual(webull.tabs[0].metric[0].value, "$8,049.98")
        self.assertEqual(webull.tabs[0].metric[2].value, "-$5,844.96")
        self.assertEqual(webull.tabs[0].metric[3].value, "$20.47")
        audit = " ".join(c.value for c in webull.caption)
        self.assertIn("Webull account currency **THB**", audit)
        self.assertIn("test quote", audit)

        usd = self.run_page("../pages/1_Executive_Dashboard.py")
        self.assertEqual(usd.metric[1].value, "$8,049.98")
        thb = self.run_page("../pages/1_Executive_Dashboard.py", ccy="THB")
        self.assertEqual(thb.metric[1].value, money(8049.98 * 33.65, "฿"))

    def test_pages_flag_unverified_cash(self):
        self.save(lambda: ([pos("AAPL", 1, 100, 100)], {}, {"total_cash_balance": "5"}))
        webull = self.run_page("../pages/2_Webull.py")
        self.assertEqual(webull.tabs[0].metric[3].value, "—")
        self.assertTrue(any("Cash balance not verified" in w.value for w in webull.warning))
        dash = self.run_page("../pages/1_Executive_Dashboard.py")
        self.assertTrue(any("Cash is unverified" in w.value for w in dash.warning))


if __name__ == "__main__":
    unittest.main()

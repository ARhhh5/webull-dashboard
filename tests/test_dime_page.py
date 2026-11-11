import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core import db_manager, dime_data

PRICES = {"AAPL": 200.0, "PTT.BK": 30.0}
TABS = ["✍️ Trade Entry", "📊 Dashboard", "📈 Performance", "📝 History", "💰 Dividends"]


class DimePageTest(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.db)
        self.patches = [
            patch.object(db_manager, "DB_PATH", self.db),
            # Unknown symbols are omitted, like a Yahoo miss, so they fall back to avg cost.
            patch.object(dime_data, "get_prices", lambda syms: {s: PRICES[s] for s in syms if s in PRICES}),
            patch.object(dime_data, "get_usd_thb", lambda: (35.0, True)),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        if os.path.exists(self.db):
            os.remove(self.db)

    def app(self):
        app = AppTest.from_file("../pages/3_Dime.py").run(timeout=30)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def submit_trade(self, app, account, action, symbol, qty, price):
        app.selectbox(key="f_account").select(account)
        app.radio(key="f_action").set_value(action)
        app.text_input(key="f_symbol").input(symbol)
        app.number_input(key="f_qty").set_value(qty)
        app.number_input(key="f_price").set_value(price)
        app.button(key="FormSubmitter:dime_trade_form-💾 Save trade").click()
        app.run(timeout=30)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        return app

    def test_form_saves_and_views_split_accounts(self):
        app = self.app()
        self.assertEqual([t.label for t in app.tabs], TABS)
        self.submit_trade(app, "Dime US", "Buy", "aapl", 10, 150)
        self.submit_trade(app, "Dime TH", "Buy", "ptt.bk", 1000, 33)
        self.submit_trade(app, "Dime US", "Sell", "AAPL", 99, 210)  # oversell must be rejected

        trades = db_manager.fetch_trades()
        self.assertEqual(list(zip(trades.account_type, trades.symbol)), [("Dime US", "AAPL"), ("Dime TH", "PTT")])
        self.assertTrue(any("Cannot sell" in e.value for e in app.error))

        app = self.app()
        perf = app.tabs[2].dataframe[0].value
        self.assertEqual(list(perf.columns), ["Symbol", "Account", "Quantity", "Average Cost", "Current Price",
                                              "Market Value", "Unrealized PnL", "Unrealized PnL %", "Ccy",
                                              "Price Source"])
        aapl = perf.set_index("Symbol").loc["AAPL"]
        self.assertEqual((aapl["Current Price"], aapl["Unrealized PnL"]), (200.0, 500.0))
        ptt = perf.set_index("Symbol").loc["PTT"]
        self.assertEqual((ptt["Current Price"], ptt["Unrealized PnL"], ptt["Ccy"]), (30.0, -3000.0, "THB"))

        # All Dime consolidates in USD: 10*200 + 1000*30/35.
        self.assertEqual(app.tabs[1].metric[0].value, "$2,857.14")

        app.pills(key="dime_view").set_value("Dime TH").run(timeout=30)
        self.assertEqual(list(app.tabs[2].dataframe[0].value["Account"]), ["Dime TH"])
        self.assertEqual(app.tabs[1].metric[0].value, "฿30,000.00")
        self.assertEqual(list(app.tabs[3].dataframe[0].value["account_type"]), ["Dime TH"])

    def test_survives_holdings_without_derived_columns(self):
        # Mirrors the production KeyError: an older core.dime_data returned no *_usd columns.
        db_manager.insert_trade("Dime US", "Buy", "AAPL", 10, 150)
        db_manager.insert_trade("Dime TH", "Buy", "PTT", 1000, 33)
        legacy = db_manager.get_holdings().assign(last_price=[30.0, 200.0])
        with patch.object(dime_data, "get_dime_portfolio", lambda: legacy):
            app = self.app()
            self.assertEqual(app.tabs[1].metric[0].value, "$2,857.14")  # 10*200 + 1000*30/35
            self.assertEqual(app.tabs[1].metric[2].value, "$2,442.86")  # 1500 + 33000/35
            perf = app.tabs[2].dataframe[0].value.set_index("Symbol")
            self.assertEqual(perf.loc["AAPL", "Unrealized PnL"], 500.0)

    def test_empty_database_and_empty_filtered_view(self):
        for frame in (pd.DataFrame(), None):
            with patch.object(dime_data, "get_dime_portfolio", lambda f=frame: f):
                app = self.app()
                self.assertEqual(app.tabs[1].metric[0].value, "$0.00")
        db_manager.insert_trade("Dime TH", "Buy", "PTT", 100, 33)
        app = self.app()
        app.pills(key="dime_view").set_value("Dime US").run(timeout=30)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        self.assertEqual(app.tabs[1].metric[0].value, "$0.00")
        self.assertTrue(any("No open positions" in i.value for i in app.tabs[2].info))

    def test_history_delete_requires_confirmation(self):
        db_manager.insert_trade("Dime US", "Buy", "AAPL", 1, 100)
        app = self.app()
        self.assertTrue(app.button(key="del_trade_btn").disabled)
        app.checkbox(key="del_trade_ok").check().run(timeout=30)
        app.button(key="del_trade_btn").click().run(timeout=30)
        self.assertTrue(db_manager.fetch_trades().empty)

    def test_dividend_form_and_history(self):
        app = self.app()
        app.selectbox(key="dv_account").select("Dime TH")
        app.text_input(key="dv_symbol").input("ptt.bk")
        app.number_input(key="dv_amount").set_value(120.5)
        app.button(key="FormSubmitter:dime_dividend_form-💰 Save dividend").click().run(timeout=30)
        divs = db_manager.fetch_dividends()
        self.assertEqual(list(zip(divs.account_type, divs.symbol, divs.amount, divs.currency)),
                         [("Dime TH", "PTT", 120.5, "THB")])
        table = app.tabs[4].dataframe[0].value
        self.assertEqual(list(table["symbol"]), ["PTT"])

        with self.assertRaises(ValueError):
            db_manager.insert_dividend("Dime XX", "PTT", 1)
        with self.assertRaises(ValueError):
            db_manager.insert_dividend("Dime US", "AAPL", 0)


if __name__ == "__main__":
    unittest.main()

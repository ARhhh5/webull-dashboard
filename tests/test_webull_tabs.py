import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from core import webull_data


class WebullTabsTest(unittest.TestCase):
    def render(self, empty=False, missing_prices=False):
        rows, day, summary = webull_data._mock()
        positions, metrics = webull_data.compute_snapshot([] if empty else rows, {} if missing_prices else day, summary)
        portfolio = dict(positions=positions, metrics=metrics, is_mock=True, error="Missing secrets",
                         account_id="DEMO-ACCOUNT", fetched_at=datetime.now())
        orders = pd.DataFrame(webull_data._mock_orders(180), columns=webull_data.ORDER_COLUMNS)
        if empty:
            orders = orders.iloc[:0]
        dividends = pd.DataFrame(columns=["Date", "Symbol", "Dividend"])
        with patch.object(webull_data, "get_portfolio", return_value=portfolio), \
                patch.object(webull_data, "get_order_history", return_value=dict(
                    orders=orders, is_mock=True, error="Missing secrets")), \
                patch.object(webull_data, "get_dividend_history", return_value=dividends):
            app = AppTest.from_file("../pages/2_Webull.py").run(timeout=30)
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([t.label for t in app.tabs], [
            "📊 Dashboard Overview", "📈 Position Performance", "📝 Trade History", "💰 Dividends"])
        return app

    def test_tab_contents(self):
        app = self.render()
        overview, positions, history, dividends = app.tabs
        self.assertEqual([m.label for m in overview.metric],
                         ["Total Account Value", "Day PnL", "Open PnL", "Cash Balance"])
        self.assertEqual(list(positions.dataframe[0].value.columns), [
            "Symbol", "Quantity", "Average Cost", "Current Price", "Day PnL", "Day PnL %",
            "Open PnL", "Open PnL %", "Previous Close", "Price Change (USD)", "Price Change (%)"])
        table = positions.dataframe[0].value
        for row in table.to_dict("records"):
            change = row["Price Change (USD)"]
            self.assertAlmostEqual(change * row["Quantity"], row["Day PnL"])
            self.assertAlmostEqual(row["Previous Close"] + change, row["Current Price"])
            self.assertAlmostEqual(change / row["Previous Close"] * 100, row["Price Change (%)"])
        self.assertTrue((table["Price Change (USD)"] > 0).any())
        self.assertTrue((table["Price Change (USD)"] < 0).any())
        orders = history.dataframe[0].value
        self.assertEqual(list(orders.columns), ["Symbol", "Side", "Quantity", "Price", "Date"])
        self.assertEqual(set(orders.Side), {"Buy", "Sell"})
        self.assertTrue(orders.Price.isna().any())
        self.assertTrue(any("DEMO" in info.value for info in history.info))
        self.assertTrue(any("estimated" in text.value for text in dividends.caption))
        self.assertEqual(len(overview.dataframe), 0)
        self.assertEqual(len(history.metric), 0)

    def test_missing_market_data_stays_blank(self):
        table = self.render(missing_prices=True).tabs[1].dataframe[0].value
        self.assertTrue(table[["Previous Close", "Price Change (USD)", "Price Change (%)"]].isna().all().all())

    def test_empty_positions_and_orders(self):
        app = self.render(empty=True)
        self.assertEqual(len(app.tabs[1].dataframe), 0)
        self.assertEqual(len(app.tabs[2].dataframe), 0)
        self.assertTrue(any("No orders" in info.value for info in app.tabs[2].info))


if __name__ == "__main__":
    unittest.main()

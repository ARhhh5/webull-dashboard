"""Dime holdings (from SQLite) valued with cached market prices, plus USD/THB conversion."""
import pandas as pd
import streamlit as st

from core import db_manager

DEFAULT_USD_THB = 35.0


def _yf_symbol(symbol, account_type):
    return f"{symbol}.BK" if account_type == "Dime TH" else symbol


@st.cache_data(ttl=900, show_spinner=False)
def get_prices(yf_symbols):
    """Latest close per Yahoo symbol; missing symbols are omitted (caller falls back to avg cost)."""
    prices = {}
    if not yf_symbols:
        return prices
    try:
        import yfinance as yf

        data = yf.download(list(yf_symbols), period="5d", interval="1d", progress=False,
                           auto_adjust=False, group_by="ticker", threads=True)
        tickers = set(data.columns.get_level_values(0)) if isinstance(data.columns, pd.MultiIndex) else set()
        for sym in yf_symbols:
            try:
                closes = (data[sym] if sym in tickers else data)["Close"].squeeze().dropna()
            except Exception:
                continue
            if not closes.empty:
                prices[sym] = float(closes.iloc[-1])
    except Exception:
        pass
    return prices


@st.cache_data(ttl=900, show_spinner=False)
def get_usd_thb():
    try:
        import yfinance as yf

        rate = yf.Ticker("THB=X").fast_info.last_price
        if rate and rate > 0:
            return float(rate), True
    except Exception:
        pass
    return DEFAULT_USD_THB, False


def get_dime_portfolio():
    """Holdings with Last Price, Market Value (native currency) and Market Value USD."""
    holdings = db_manager.get_holdings()
    fx, _ = get_usd_thb()
    if holdings.empty:
        return holdings.assign(last_price=[], market_value=[], unrealized_pnl=[], unrealized_pct=[],
                               market_value_usd=[], cost_basis_usd=[], unrealized_pnl_usd=[], price_source=[])

    yf_syms = [_yf_symbol(s, a) for s, a in zip(holdings["symbol"], holdings["account_type"])]
    prices = get_prices(tuple(sorted(set(yf_syms))))
    holdings["last_price"] = [prices.get(y, avg) for y, avg in zip(yf_syms, holdings["avg_cost"])]
    holdings["price_source"] = ["Market" if y in prices else "Avg cost" for y in yf_syms]
    holdings["market_value"] = holdings["shares"] * holdings["last_price"]
    holdings["unrealized_pnl"] = holdings["market_value"] - holdings["cost_basis"]
    holdings["unrealized_pct"] = (holdings["unrealized_pnl"] / holdings["cost_basis"] * 100).where(
        holdings["cost_basis"] > 0, 0.0)
    to_usd = holdings["currency"].map({"USD": 1.0, "THB": 1 / fx})
    holdings["market_value_usd"] = holdings["market_value"] * to_usd
    holdings["cost_basis_usd"] = holdings["cost_basis"] * to_usd
    holdings["unrealized_pnl_usd"] = holdings["unrealized_pnl"] * to_usd
    return holdings


def summarize(df, account_type):
    sub = df[df["account_type"] == account_type] if not df.empty else df
    if sub.empty:
        return {"market_value": 0.0, "market_value_usd": 0.0, "cost_basis": 0.0, "unrealized_pnl": 0.0,
                "unrealized_pct": 0.0, "positions": 0}
    cost = float(sub["cost_basis"].sum())
    pnl = float(sub["unrealized_pnl"].sum())
    return {"market_value": float(sub["market_value"].sum()),
            "market_value_usd": float(sub["market_value_usd"].sum()),
            "cost_basis": cost, "unrealized_pnl": pnl,
            "unrealized_pct": pnl / cost * 100 if cost else 0.0, "positions": int(len(sub))}

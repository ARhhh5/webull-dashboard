"""Market data via yfinance (used for Dime holdings, FX and chart candles)."""
import pandas as pd
import streamlit as st
import yfinance as yf

DEFAULT_USD_THB = 35.0


def yf_symbol(symbol, broker):
    return f"{symbol}.BK" if broker == "Dime TH" and not symbol.endswith(".BK") else symbol


@st.cache_data(ttl=60, show_spinner=False)
def fetch_quotes(symbols):
    """symbols (tuple) -> {symbol: {"price", "prev_close"}} using one batched download."""
    symbols = tuple(s for s in dict.fromkeys(symbols) if s)
    quotes = {}
    if not symbols:
        return quotes
    try:
        data = yf.download(list(symbols), period="5d", interval="1d", progress=False,
                           auto_adjust=False, group_by="ticker", threads=True)
    except Exception:
        data = pd.DataFrame()
    for sym in symbols:
        try:
            closes = data[sym]["Close"].dropna() if len(symbols) > 1 else data["Close"].squeeze().dropna()
        except Exception:
            closes = pd.Series(dtype=float)
        if closes.empty:
            continue
        quotes[sym] = {
            "price": float(closes.iloc[-1]),
            "prev_close": float(closes.iloc[-2]) if len(closes) > 1 else float(closes.iloc[-1]),
        }
    return quotes


@st.cache_data(ttl=3600, show_spinner=False)
def get_usd_thb():
    try:
        rate = yf.Ticker("THB=X").fast_info.last_price
        if rate and rate > 0:
            return float(rate)
    except Exception:
        pass
    return DEFAULT_USD_THB


@st.cache_data(ttl=300, show_spinner=False)
def get_ohlc(symbol, period="6mo", interval="1d"):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=False)
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
    return df

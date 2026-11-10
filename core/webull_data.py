"""Webull data layer: live data via the Webull OpenAPI SDK, with a mock fallback.

Credentials come from st.secrets["Webull"]: AppKey, AppSecret, AccessToken, AccountId.
Any failure (missing secrets, auth, network, API errors) returns mock data so the UI always renders.
"""
import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

REGION = "th"
DEFAULT_HOST = "api.webull.co.th"
TOKEN_DIR = Path(tempfile.gettempdir()) / "webull_openapi_token"
# The SDK polls for 2FA approval when the token is not yet verified; keep that short in a web app.
TOKEN_CHECK_SECONDS = 20

POSITION_COLUMNS = ["Symbol", "Quantity", "Avg Cost", "Last Price", "Market Value", "Cost Basis",
                    "Open PnL", "Open PnL %", "Day Change %", "Day PnL", "Weight %", "Currency"]


def _num(value, default=0.0):
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def _load_credentials():
    cfg = st.secrets["Webull"]  # KeyError / StreamlitSecretNotFoundError when absent
    creds = {
        "app_key": str(cfg["AppKey"]).strip(),
        "app_secret": str(cfg["AppSecret"]).strip(),
        "access_token": str(cfg.get("AccessToken", "")).strip(),
        "account_id": str(cfg.get("AccountId", "")).strip(),
        "host": str(cfg.get("Host", DEFAULT_HOST)).strip() or DEFAULT_HOST,
    }
    if not creds["app_key"] or not creds["app_secret"]:
        raise KeyError("Webull.AppKey / Webull.AppSecret are empty")
    return creds


def _seed_token(access_token):
    """Pre-load AccessToken so the SDK reuses it instead of starting a new 2FA flow."""
    if not access_token:
        return
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_file = TOKEN_DIR / "token.txt"
    if token_file.exists() and token_file.read_text(encoding="utf-8").split("\n", 1)[0].strip() == access_token:
        return  # keep the verified token/expiry the SDK already saved
    token_file.write_text(f"{access_token}\n0\nNORMAL\n", encoding="utf-8")


def _api_client(creds):
    from webull.core.client import ApiClient

    client = ApiClient(creds["app_key"], creds["app_secret"], REGION, timeout=15, connect_timeout=10,
                       token_check_duration_seconds=TOKEN_CHECK_SECONDS, token_check_interval_seconds=5)
    client.add_endpoint(REGION, creds["host"])
    client.set_token_dir(str(TOKEN_DIR))
    # Setting a stream logger stops the SDK from writing log files into the app directory.
    client.set_stream_logger(log_level=logging.WARNING, stream=sys.stderr)
    return client


def _json_or_raise(response, what):
    if response.status_code != 200:
        raise RuntimeError(f"{what} failed: HTTP {response.status_code}")
    data = response.json()
    if isinstance(data, dict) and isinstance(data.get("data"), (list, dict)):
        data = data["data"]
    return data


def _connect():
    """Returns (api_client, trade_client, account_id). Raises on missing secrets or API errors."""
    from webull.trade.trade_client import TradeClient

    creds = _load_credentials()
    _seed_token(creds["access_token"])
    api_client = _api_client(creds)
    trade = TradeClient(api_client)

    account_id = creds["account_id"]
    if not account_id:
        accounts = _json_or_raise(trade.account_v2.get_account_list(), "Account list")
        if not accounts:
            raise RuntimeError("No Webull accounts returned for these credentials")
        account_id = str(accounts[0]["account_id"])
    return api_client, trade, account_id


def _fetch_live():
    from webull.data.data_client import DataClient

    api_client, trade, account_id = _connect()

    balance = _json_or_raise(trade.account_v2.get_account_balance(account_id), "Account balance") or {}
    positions = _json_or_raise(trade.account_v2.get_account_position(account_id), "Positions") or []

    rows = []
    for p in positions:
        if "OPTION" in str(p.get("instrument_type", "")).upper():
            continue
        qty = _num(p.get("quantity"))
        if qty <= 0:
            continue
        cost = _num(p.get("cost_price"))
        rows.append({"Symbol": str(p.get("symbol", "")).upper(), "Quantity": qty, "Avg Cost": cost,
                     "Last Price": _num(p.get("last_price"), cost),
                     "Currency": str(p.get("currency") or "USD").upper()})

    # Day change needs market data permission; positions still render without it.
    day_change = {}
    if rows:
        try:
            data_client = DataClient(api_client)
            snaps = _json_or_raise(data_client.market_data.get_snapshot(
                ",".join(r["Symbol"] for r in rows), "US_STOCK"), "Snapshot")
            for s in snaps or []:
                day_change[str(s.get("symbol", "")).upper()] = _num(s.get("change_ratio")) * 100
        except Exception:
            day_change = {}

    cash = _num(balance.get("total_cash_balance"))
    return rows, day_change, cash, account_id


def _build(rows, day_change, cash):
    df = pd.DataFrame(rows, columns=["Symbol", "Quantity", "Avg Cost", "Last Price", "Currency"])
    df["Market Value"] = df["Quantity"] * df["Last Price"]
    df["Cost Basis"] = df["Quantity"] * df["Avg Cost"]
    df["Open PnL"] = df["Market Value"] - df["Cost Basis"]
    df["Open PnL %"] = np.where(df["Cost Basis"] > 0, df["Open PnL"] / df["Cost Basis"] * 100, 0.0)
    df["Day Change %"] = df["Symbol"].map(day_change).astype(float)
    prev_value = df["Market Value"] / (1 + df["Day Change %"] / 100)
    df["Day PnL"] = df["Market Value"] - prev_value
    total_mv = df["Market Value"].sum()
    df["Weight %"] = df["Market Value"] / total_mv * 100 if total_mv else 0.0
    df = df[POSITION_COLUMNS].sort_values("Market Value", ascending=False).reset_index(drop=True)

    cost = df["Cost Basis"].sum()
    open_pnl = df["Open PnL"].sum()
    has_day = df["Day Change %"].notna().any()
    day_pnl = df["Day PnL"].sum() if has_day else None
    prev_total = total_mv - (day_pnl or 0)
    metrics = {
        "total_value": total_mv + cash,
        "market_value": total_mv,
        "cash": cash,
        "cost_basis": cost,
        "open_pnl": open_pnl,
        "open_pnl_pct": open_pnl / cost * 100 if cost else 0.0,
        "day_pnl": day_pnl,
        "day_pnl_pct": (day_pnl / prev_total * 100) if has_day and prev_total else None,
        "positions": int(len(df)),
    }
    return df, metrics


def _mock():
    rows = [
        ("NVDA", 40, 98.50, 182.40, 2.31), ("AAPL", 55, 171.20, 228.15, -0.84),
        ("MSFT", 18, 389.00, 431.60, 0.57), ("TSLA", 22, 268.30, 241.75, -3.12),
        ("AMZN", 30, 152.80, 201.10, 1.12), ("GOOGL", 35, 139.40, 176.25, 0.36),
        ("NU", 300, 12.10, 14.30, 4.05), ("PLTR", 120, 24.60, 71.80, 5.48),
        ("VOO", 12, 455.00, 548.90, 0.21), ("SOFI", 400, 9.85, 7.92, -1.95),
    ]
    data = [{"Symbol": s, "Quantity": q, "Avg Cost": c, "Last Price": p, "Currency": "USD"} for s, q, c, p, _ in rows]
    return data, {s: d for s, _, _, _, d in rows}, 4_825.37


@st.cache_data(ttl=900, show_spinner="Fetching Webull portfolio...")
def get_portfolio():
    """Returns dict(positions, metrics, is_mock, error, account_id, fetched_at)."""
    try:
        rows, day_change, cash, account_id = _fetch_live()
        is_mock, error = False, None
    except Exception as exc:  # KeyError, missing secrets file, SDK/auth/network errors
        rows, day_change, cash = _mock()
        account_id, is_mock = "DEMO-ACCOUNT", True
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
    positions, metrics = _build(rows, day_change, cash)
    return {"positions": positions, "metrics": metrics, "is_mock": is_mock, "error": error,
            "account_id": account_id, "fetched_at": datetime.now()}


ORDER_COLUMNS = ["Time", "Symbol", "Side", "Status", "Order Type", "Quantity", "Filled Qty", "Filled Price",
                 "Amount", "Order ID"]
MAX_ORDER_PAGES = 20  # API pages through history; cap to protect rate limits


def _fetch_orders_live(days):
    from datetime import timedelta, timezone

    _, trade, account_id = _connect()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=min(days, 180))  # API look-back limit is 6 months
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    rows, key = [], None
    for _ in range(MAX_ORDER_PAGES):
        resp = trade.order_v3.list_order_history(account_id, start_time=start.strftime(fmt),
                                                 end_time=end.strftime(fmt), pagination_key=key)
        if resp.status_code != 200:
            raise RuntimeError(f"Order history failed: HTTP {resp.status_code}")
        payload = resp.json() or {}
        groups = payload.get("data", payload) if isinstance(payload, dict) else payload
        for group in groups or []:
            for o in group.get("orders", []) or []:
                if "OPTION" in str(o.get("instrument_type", "")).upper():
                    continue
                filled_qty = _num(o.get("filled_quantity"))
                filled_price = _num(o.get("filled_price"))
                rows.append({
                    "Time": pd.to_datetime(o.get("filled_time") or o.get("place_time"), errors="coerce", utc=True),
                    "Symbol": str(o.get("symbol", "")).upper(), "Side": str(o.get("side", "")).upper(),
                    "Status": str(o.get("status", "")).upper(), "Order Type": o.get("order_type", ""),
                    "Quantity": _num(o.get("total_quantity")), "Filled Qty": filled_qty,
                    "Filled Price": filled_price, "Amount": filled_qty * filled_price,
                    "Order ID": str(o.get("order_id", "")),
                })
        key = payload.get("pagination_key") if isinstance(payload, dict) else None
        if not key:
            break
    return rows


def _mock_orders(days):
    from datetime import timedelta

    rows, now = [], datetime.now()
    rng = np.random.default_rng(7)
    base = {s: c for s, _, c, _, _ in [
        ("NVDA", 0, 98.50, 0, 0), ("AAPL", 0, 171.20, 0, 0), ("MSFT", 0, 389.00, 0, 0), ("TSLA", 0, 268.30, 0, 0),
        ("AMZN", 0, 152.80, 0, 0), ("GOOGL", 0, 139.40, 0, 0), ("NU", 0, 12.10, 0, 0), ("PLTR", 0, 24.60, 0, 0),
        ("VOO", 0, 455.00, 0, 0), ("SOFI", 0, 9.85, 0, 0)]}
    for i in range(36):
        sym = list(base)[i % len(base)]
        side = "SELL" if i % 5 == 4 else "BUY"
        qty = float(rng.integers(1, 25))
        price = round(base[sym] * float(rng.uniform(0.85, 1.6)), 2)
        status = "CANCELLED" if i % 11 == 10 else "FILLED"
        filled = qty if status == "FILLED" else 0.0
        rows.append({"Time": pd.Timestamp(now - timedelta(days=int(i * days / 36), hours=int(rng.integers(0, 6))),
                                          tz="UTC"),
                     "Symbol": sym, "Side": side, "Status": status, "Order Type": "LIMIT", "Quantity": qty,
                     "Filled Qty": filled, "Filled Price": price if filled else 0.0, "Amount": filled * price,
                     "Order ID": f"DEMO{1000 + i}"})
    return rows


@st.cache_data(ttl=900, show_spinner="Fetching Webull order history...")
def get_order_history(days=180):
    """Returns dict(orders DataFrame, is_mock, error)."""
    try:
        rows, is_mock, error = _fetch_orders_live(days), False, None
    except Exception as exc:
        rows, is_mock = _mock_orders(days), True
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
    df = pd.DataFrame(rows, columns=ORDER_COLUMNS)
    if not df.empty:
        df = df.sort_values("Time", ascending=False).reset_index(drop=True)
    return {"orders": df, "is_mock": is_mock, "error": error}


@st.cache_data(ttl=86400, show_spinner="Loading dividend history...")
def get_dividend_history(symbols):
    """Per-share cash dividends from Yahoo Finance for the last 2 years. symbols: tuple."""
    import yfinance as yf

    frames = []
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=730)
    for sym in symbols:
        try:
            divs = yf.Ticker(sym).dividends
        except Exception:
            continue
        if divs is None or divs.empty:
            continue
        divs.index = pd.to_datetime(divs.index, utc=True)
        divs = divs[divs.index >= cutoff]
        frames.append(pd.DataFrame({"Date": divs.index, "Symbol": sym, "Dividend": divs.values}))
    if not frames:
        return pd.DataFrame(columns=["Date", "Symbol", "Dividend"])
    return pd.concat(frames, ignore_index=True).sort_values("Date", ascending=False)

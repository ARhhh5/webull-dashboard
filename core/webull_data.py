"""Webull data layer.

Page loads read the SQLite cache only (get_portfolio / get_order_history) and never touch the SDK, so
browsing the app cannot trigger a Webull mobile approval. The SDK runs only in sync_from_webull(), called
from the explicit "Sync" button; it fetches everything over one connection and saves it to SQLite.
Credentials come from st.secrets["Webull"]: AppKey, AppSecret, AccessToken, AccountId.
"""
import hashlib
import logging
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from core import db_manager

REGION = "th"
DEFAULT_HOST = "api.webull.co.th"
TOKEN_DIR = Path(tempfile.gettempdir()) / "webull_openapi_token"
# Sync is user-initiated, so allow time to approve the 2FA prompt on the phone.
TOKEN_CHECK_SECONDS = 120

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
    """Seed the SDK token file from AccessToken once per secret value.

    After the first approval the SDK rewrites token.txt with its own verified token. Re-seeding the
    secret on every connect would discard that token and force a new mobile approval each time.
    """
    if not access_token:
        return
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    token_file, marker = TOKEN_DIR / "token.txt", TOKEN_DIR / "seeded_secret.sha256"
    digest = hashlib.sha256(access_token.encode("utf-8")).hexdigest()
    if token_file.exists() and marker.exists() and marker.read_text(encoding="utf-8").strip() == digest:
        return
    token_file.write_text(f"{access_token}\n0\nNORMAL\n", encoding="utf-8")
    marker.write_text(digest, encoding="utf-8")


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


def _fetch_account(api_client, trade, account_id):
    """Balance, positions and day change over an already-authenticated connection."""
    from webull.data.quotes.market_data import MarketData

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

    # Day change needs market-data permission; positions still render without it.
    # ETFs (e.g. VOO) are only returned under the US_ETF category.
    day_change = {}
    if rows:
        try:
            # MarketData directly: DataClient() would run the SDK token handshake a second time.
            market_data = MarketData(api_client)
            wanted = {r["Symbol"] for r in rows}
            for category in ("US_STOCK", "US_ETF"):
                missing = sorted(wanted - set(day_change))
                if not missing:
                    break
                try:
                    snaps = _json_or_raise(market_data.get_snapshot(",".join(missing), category),
                                           f"Snapshot {category}")
                except Exception:
                    continue
                for s in snaps or []:
                    day_change[str(s.get("symbol", "")).upper()] = {
                        "pct": _num(s.get("change_ratio")) * 100, "change": _num(s.get("change"), None)}
        except Exception:
            day_change = {}

    summary = {
        "cash": _num(balance.get("total_cash_balance")),
        "market_value": _num(balance.get("total_market_value"), None),
        "open_pnl": _num(balance.get("total_unrealized_profit_loss"), None),
        "currency": balance.get("total_asset_currency") or "USD",
    }
    return rows, day_change, summary


def _build(rows, day_change, summary):
    df = pd.DataFrame(rows, columns=["Symbol", "Quantity", "Avg Cost", "Last Price", "Currency"])
    df["Market Value"] = df["Quantity"] * df["Last Price"]
    df["Cost Basis"] = df["Quantity"] * df["Avg Cost"]
    df["Open PnL"] = df["Market Value"] - df["Cost Basis"]
    df["Open PnL %"] = np.where(df["Cost Basis"] > 0, df["Open PnL"] / df["Cost Basis"] * 100, 0.0)
    df["Day Change %"] = df["Symbol"].map(lambda s: day_change.get(s, {}).get("pct")).astype(float)
    change = df["Symbol"].map(lambda s: day_change.get(s, {}).get("change")).astype(float)
    # Prefer the absolute per-share change; derive it from change % when the API omits it.
    derived = df["Market Value"] - df["Market Value"] / (1 + df["Day Change %"] / 100)
    df["Day PnL"] = (df["Quantity"] * change).fillna(derived)
    total_mv = df["Market Value"].sum()
    df["Weight %"] = df["Market Value"] / total_mv * 100 if total_mv else 0.0
    df = df[POSITION_COLUMNS].sort_values("Market Value", ascending=False).reset_index(drop=True)

    # Account Summary totals are authoritative when the API returns them.
    market_value = summary["market_value"] if summary.get("market_value") is not None else total_mv
    open_pnl = summary["open_pnl"] if summary.get("open_pnl") is not None else df["Open PnL"].sum()
    cash = summary["cash"]
    cost = df["Cost Basis"].sum()
    has_day = df["Day PnL"].notna().any()
    day_pnl = df["Day PnL"].sum() if has_day else None
    prev_total = market_value - (day_pnl or 0)
    metrics = {
        "total_value": market_value + cash,
        "market_value": market_value,
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
    day = {s: {"pct": d, "change": None} for s, _, _, _, d in rows}
    return data, day, {"cash": 4_825.37, "market_value": None, "open_pnl": None, "currency": "USD"}


METRIC_KEYS = ["total_value", "market_value", "cash", "cost_basis", "open_pnl", "open_pnl_pct", "day_pnl",
               "day_pnl_pct", "positions"]
POSITION_DB = dict(zip(POSITION_COLUMNS, ["symbol", "quantity", "avg_cost", "last_price", "market_value",
                                          "cost_basis", "open_pnl", "open_pnl_pct", "day_change_pct", "day_pnl",
                                          "weight_pct", "currency"]))


def _parse_synced(value):
    return pd.Timestamp(value).tz_convert("UTC").to_pydatetime() if value else None


def get_portfolio():
    """Portfolio from the SQLite cache (no SDK call).

    Returns dict(positions, metrics, is_mock, error, account_id, fetched_at, last_synced). Before the first
    sync there is nothing cached, so demo data is returned with is_mock=True and last_synced=None.
    """
    cache = db_manager.get_webull_data()
    summary = cache["summary"]
    if summary is None:
        rows, day_change, demo_summary = _mock()
        positions, metrics = _build(rows, day_change, demo_summary)
        return {"positions": positions, "metrics": metrics, "is_mock": True, "error": None,
                "account_id": "DEMO-ACCOUNT", "fetched_at": None, "last_synced": None}

    positions = cache["positions"].rename(columns={v: k for k, v in POSITION_DB.items()})
    positions = positions.reindex(columns=POSITION_COLUMNS)
    for col in POSITION_COLUMNS:
        if col not in ("Symbol", "Currency"):
            positions[col] = pd.to_numeric(positions[col], errors="coerce")
    metrics = {k: summary.get(k) for k in METRIC_KEYS}
    metrics["positions"] = int(metrics["positions"] or 0)
    synced = _parse_synced(cache["last_synced"])
    return {"positions": positions.reset_index(drop=True), "metrics": metrics, "is_mock": False, "error": None,
            "account_id": summary.get("account_id") or "-", "fetched_at": synced, "last_synced": synced}


ORDER_COLUMNS = ["Time", "Symbol", "Side", "Status", "Order Type", "Quantity", "Filled Qty", "Filled Price",
                 "Amount", "Order ID"]
ORDER_DB = dict(zip(ORDER_COLUMNS, ["time", "symbol", "side", "status", "order_type", "quantity", "filled_qty",
                                    "filled_price", "amount", "order_id"]))
MAX_ORDER_PAGES = 20  # API pages through history; cap to protect rate limits


def _fetch_orders(trade, account_id, days=180):
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


def get_order_history(days=180):
    """Order history from the SQLite cache (no SDK call). Returns dict(orders DataFrame, is_mock, error)."""
    cache = db_manager.get_webull_data()
    if cache["summary"] is None:
        df, is_mock = pd.DataFrame(_mock_orders(days), columns=ORDER_COLUMNS), True
    else:
        df = cache["orders"].rename(columns={v: k for k, v in ORDER_DB.items()}).reindex(columns=ORDER_COLUMNS)
        df["Time"] = pd.to_datetime(df["Time"], errors="coerce", utc=True)
        for col in ("Quantity", "Filled Qty", "Filled Price", "Amount"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        is_mock = False
    if not df.empty:
        df = df.sort_values("Time", ascending=False).reset_index(drop=True)
    return {"orders": df, "is_mock": is_mock, "error": None}


def sync_from_webull():
    """Fetch live data from Webull and replace the SQLite cache. May trigger a mobile approval.

    Raises on credential/auth/account errors, leaving the existing cache untouched. An order-history
    failure keeps the previously cached orders and is reported in "warnings".
    """
    api_client, trade, account_id = _connect()
    rows, day_change, summary = _fetch_account(api_client, trade, account_id)
    positions, metrics = _build(rows, day_change, summary)

    warnings = []
    try:
        orders = pd.DataFrame(_fetch_orders(trade, account_id), columns=ORDER_COLUMNS)
        orders_db = orders.rename(columns=ORDER_DB)
        orders_db["time"] = [t.isoformat() if pd.notna(t) else None for t in orders["Time"]]
    except Exception as exc:
        orders, orders_db = None, None
        warnings.append(f"Order history was not updated ({type(exc).__name__}: {str(exc)[:200]})")

    db_manager.save_webull_data({**metrics, "account_id": account_id}, positions.rename(columns=POSITION_DB),
                                orders_db)
    return {"account_id": account_id, "positions": len(positions),
            "orders": None if orders is None else len(orders), "warnings": warnings}


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

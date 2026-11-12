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

from core import db_manager, fx

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
    """Balance (raw API dict), positions and day change over an already-authenticated connection."""
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
                     # Never default to USD: an unknown currency is excluded from USD totals with a warning.
                     "Currency": str(p.get("currency") or "").upper() or None})

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
    return rows, day_change, balance


RECONCILE_TOLERANCE_PCT = 2.0


def _ccy(value):
    return str(value or "").strip().upper() or None


def _cash_usd(balance, account_ccy, cash_items, rate):
    """(cash_usd | None, status, detail). Per-currency cash is preferred over the account-currency total."""
    if cash_items:
        parts, total, failed, converted = [], 0.0, [], False
        for item in cash_items:
            ccy, amount = _ccy(item.get("currency")), _num(item.get("cash_balance"), None)
            if amount is None:
                failed.append(f"{ccy or 'unknown currency'} (no amount)")
                continue
            if amount == 0:
                continue
            usd = fx.to_usd(amount, ccy, rate)
            if usd is None:
                failed.append(f"{ccy or 'unknown currency'} {amount:,.2f}")
                continue
            total += usd
            if ccy == "USD":
                parts.append(f"USD {amount:,.2f}")
            else:
                converted = True
                parts.append(f"{ccy} {amount:,.2f} → USD {usd:,.2f}")
        if failed:
            return None, "unverified", "Could not convert cash: " + ", ".join(failed)
        return total, ("converted" if converted else "USD"), " + ".join(parts) or "USD 0.00"

    amount = _num(balance.get("total_cash_balance"), None)
    if amount is None:
        return None, "unverified", "Webull did not report a cash balance"
    if account_ccy is None:
        return None, "unverified", f"Cash {amount:,.2f} was reported without a currency"
    usd = fx.to_usd(amount, account_ccy, rate)
    if usd is None:
        return None, "unverified", f"{account_ccy} {amount:,.2f} could not be converted to USD"
    if account_ccy == "USD":
        return usd, "USD", f"USD {amount:,.2f} (account total)"
    return usd, "converted", f"{account_ccy} {amount:,.2f} → USD {usd:,.2f} (account total)"


def compute_snapshot(rows, day_change, balance, fx_lookup=None, now=None):
    """Pure calculation of the Webull snapshot in USD (base currency).

    rows: positions in their own currency; balance: raw /trading/assets/balances/get dict;
    fx_lookup: callable returning fx.FxRate | None, called at most once and only if a non-USD
    amount is present. Every amount is converted to USD exactly once here.
    Returns (positions DataFrame in USD, metrics dict incl. currency metadata and warnings).
    """
    balance, warnings = balance or {}, []
    account_ccy = _ccy(balance.get("total_asset_currency"))
    cash_items = [i for i in (balance.get("account_currency_assets") or []) if isinstance(i, dict)]
    value_ccys = {_ccy(r.get("Currency")) for r in rows} | {_ccy(i.get("currency")) for i in cash_items
                                                             if _num(i.get("cash_balance"), None) != 0}
    if not cash_items and _num(balance.get("total_cash_balance"), None) not in (None, 0):
        value_ccys.add(account_ccy)
    needs_fx = bool(value_ccys - {"USD"})
    reported_mv = _num(balance.get("total_market_value"), None)

    rate = fx_lookup() if fx_lookup and (needs_fx or (account_ccy and account_ccy != "USD")) else None
    if rate is None and needs_fx:
        usd_rows = [r for r in rows if _ccy(r.get("Currency")) == "USD"]
        usd_mv = sum(r["Quantity"] * r["Last Price"] for r in usd_rows)
        # Fallback only, and only when every position is USD so the ratio is a clean THB/USD.
        rate = fx.estimate_fx(reported_mv, account_ccy, usd_mv, now) if rows and len(usd_rows) == len(rows) else None
        if rate is not None:
            warnings.append(f"Live USD/THB unavailable: using {rate.label()}. Treat converted figures as estimates.")
        else:
            warnings.append("USD/THB rate unavailable: non-USD amounts could not be converted and are excluded.")

    out, excluded = [], []
    for r in rows:
        ccy = _ccy(r.get("Currency"))
        factor = fx.usd_factor(ccy, rate)
        if factor is None:
            excluded.append(f"{r['Symbol']} ({ccy or 'unknown currency'})")
            continue
        day = day_change.get(r["Symbol"], {})
        change = day.get("change")
        out.append({"Symbol": r["Symbol"], "Quantity": r["Quantity"], "Avg Cost": r["Avg Cost"] * factor,
                    "Last Price": r["Last Price"] * factor, "Currency": ccy, "FX to USD": factor,
                    "_pct": day.get("pct"), "_change": None if change is None else change * factor})
    if excluded:
        warnings.append("Excluded from USD totals (currency could not be converted): " + ", ".join(excluded))

    df = pd.DataFrame(out, columns=["Symbol", "Quantity", "Avg Cost", "Last Price", "Currency", "FX to USD",
                                    "_pct", "_change"])
    df["Market Value"] = df["Quantity"] * df["Last Price"]
    df["Cost Basis"] = df["Quantity"] * df["Avg Cost"]
    df["Open PnL"] = df["Market Value"] - df["Cost Basis"]
    df["Open PnL %"] = np.where(df["Cost Basis"] > 0, df["Open PnL"] / df["Cost Basis"] * 100, 0.0)
    df["Day Change %"] = df["_pct"].astype(float)
    # Prefer the absolute per-share change; derive it from change % when the API omits it.
    derived = df["Market Value"] - df["Market Value"] / (1 + df["Day Change %"] / 100)
    df["Day PnL"] = (df["Quantity"] * df["_change"].astype(float)).fillna(derived)
    market_value = float(df["Market Value"].sum())
    df["Weight %"] = df["Market Value"] / market_value * 100 if market_value else 0.0
    df = df[POSITION_COLUMNS + ["FX to USD"]].sort_values("Market Value", ascending=False).reset_index(drop=True)

    cash, cash_status, cash_detail = _cash_usd(balance, account_ccy, cash_items, rate)
    if cash is None:
        warnings.append(f"Cash balance not verified ({cash_detail}). Total Account Value excludes cash.")

    cost = float(df["Cost Basis"].sum())
    open_pnl = float(df["Open PnL"].sum())
    has_day = bool(df["Day PnL"].notna().any())
    day_pnl = float(df["Day PnL"].sum()) if has_day else None
    prev_total = market_value - (day_pnl or 0.0)

    reported_usd = fx.to_usd(reported_mv, account_ccy, rate) if reported_mv is not None else None
    recon = None
    if reported_usd and market_value and not (rate is not None and rate.estimated):
        recon = (market_value - reported_usd) / reported_usd * 100
        if abs(recon) > RECONCILE_TOLERANCE_PCT:
            warnings.append(f"Positions total differs from Webull's reported holdings by {recon:+.2f}% "
                            f"(${market_value:,.2f} vs {account_ccy} {reported_mv:,.2f} ≈ ${reported_usd:,.2f}).")

    metrics = {
        "total_value": market_value + (cash or 0.0),
        "market_value": market_value,
        "cash": cash,
        "cost_basis": cost,
        "open_pnl": open_pnl,
        "open_pnl_pct": open_pnl / cost * 100 if cost else 0.0,
        "day_pnl": day_pnl,
        "day_pnl_pct": (day_pnl / prev_total * 100) if has_day and prev_total else None,
        "positions": int(len(df)),
        "base_currency": fx.BASE_CURRENCY,
        "account_currency": account_ccy,
        "cash_status": cash_status,
        "cash_detail": cash_detail,
        "fx_rate": rate.rate if rate else None,
        "fx_source": rate.source if rate else None,
        "fx_as_of": rate.as_of if rate else None,
        "fx_estimated": bool(rate.estimated) if rate else None,
        "reported_market_value": reported_mv,
        "reported_open_pnl": _num(balance.get("total_unrealized_profit_loss"), None),
        "reported_cash": _num(balance.get("total_cash_balance"), None),
        "reconciliation_diff_pct": recon,
        "warnings": warnings,
        "raw_balance": balance,
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
    balance = {"total_asset_currency": "USD",
               "account_currency_assets": [{"currency": "USD", "cash_balance": "4825.37"}]}
    return data, day, balance


METRIC_KEYS = ["total_value", "market_value", "cash", "cost_basis", "open_pnl", "open_pnl_pct", "day_pnl",
               "day_pnl_pct", "positions"]
POSITION_DB = dict(zip(POSITION_COLUMNS + ["FX to USD"],
                       ["symbol", "quantity", "avg_cost", "last_price", "market_value", "cost_basis", "open_pnl",
                        "open_pnl_pct", "day_change_pct", "day_pnl", "weight_pct", "currency", "fx_to_usd"]))


def _parse_ts(value):
    return pd.Timestamp(value).tz_convert("UTC").to_pydatetime() if value else None


def fx_from_metrics(metrics):
    """The FX quote recorded with a snapshot (for display/audit), or None."""
    if not metrics.get("fx_rate"):
        return None
    as_of = metrics.get("fx_as_of")
    as_of = as_of if isinstance(as_of, datetime) else _parse_ts(as_of)
    return fx.FxRate(rate=float(metrics["fx_rate"]), source=metrics.get("fx_source") or "unknown",
                     as_of=as_of or datetime.now(timezone.utc), estimated=bool(metrics.get("fx_estimated")))


def _legacy_snapshot(cache):
    """Snapshot synced before the USD fix: totals/cash have no recorded currency, so rebuild from positions."""
    cached = cache["positions"]
    rows = [{"Symbol": r.symbol, "Quantity": r.quantity, "Avg Cost": r.avg_cost, "Last Price": r.last_price,
             "Currency": r.currency} for r in cached.itertuples()]
    day = {r.symbol: {"pct": r.day_change_pct,
                      "change": (r.day_pnl / r.quantity) if pd.notna(r.day_pnl) and r.quantity else None}
           for r in cached.itertuples() if pd.notna(r.day_change_pct)}
    positions, metrics = compute_snapshot(rows, day, {})
    metrics["cash_detail"] = "Synced before the currency fix: cash currency was not recorded"
    metrics["warnings"] = ["This Webull snapshot was saved before the USD currency fix. Totals are rebuilt from "
                           "positions and cash is excluded. Press Sync to refresh."] + [
        w for w in metrics["warnings"] if not w.startswith("Cash balance not verified")]
    return positions, metrics


def get_portfolio():
    """Portfolio from the SQLite cache (no SDK call). All money in USD.

    Returns dict(positions, metrics, is_mock, legacy, error, account_id, fetched_at, last_synced).
    Before the first sync there is nothing cached, so demo data is returned with is_mock=True.
    """
    cache = db_manager.get_webull_data()
    summary = cache["summary"]
    if summary is None:
        positions, metrics = compute_snapshot(*_mock())
        return {"positions": positions, "metrics": metrics, "is_mock": True, "legacy": False, "error": None,
                "account_id": "DEMO-ACCOUNT", "fetched_at": None, "last_synced": None}

    synced = _parse_ts(cache["last_synced"])
    base = {"is_mock": False, "error": None, "account_id": summary.get("account_id") or "-",
            "fetched_at": synced, "last_synced": synced}
    if summary.get("base_currency") is None:
        positions, metrics = _legacy_snapshot(cache)
        return {**base, "positions": positions, "metrics": metrics, "legacy": True}

    positions = cache["positions"].rename(columns={v: k for k, v in POSITION_DB.items()})
    positions = positions.reindex(columns=POSITION_COLUMNS + ["FX to USD"])
    for col in POSITION_COLUMNS + ["FX to USD"]:
        if col not in ("Symbol", "Currency"):
            positions[col] = pd.to_numeric(positions[col], errors="coerce")
    metrics = {k: summary.get(k) for k in [*METRIC_KEYS, *db_manager.WEBULL_CURRENCY_FIELDS]}
    metrics["positions"] = int(metrics["positions"] or 0)
    metrics["fx_estimated"] = None if metrics["fx_estimated"] is None else bool(metrics["fx_estimated"])
    if metrics["cash_status"] == "unverified":
        metrics["cash"] = None
    return {**base, "positions": positions.reset_index(drop=True), "metrics": metrics, "legacy": False}


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
    rows, day_change, balance = _fetch_account(api_client, trade, account_id)
    # Uncached quote so the stored FX timestamp matches this sync.
    positions, metrics = compute_snapshot(rows, day_change, balance, fx_lookup=fx.fetch_usd_thb)

    warnings = list(metrics["warnings"])
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

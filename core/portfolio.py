"""Unified holdings loader. Each broker keeps its own data source:

- Webull  -> Webull TH OpenAPI (fallback: Webull_Order_History sheet)
- Dime US -> Google Sheets "Dime_Portfolio"      + yfinance prices
- Dime TH -> Google Sheets "Dime_TH_Portfolio"   + yfinance prices (.BK)
"""
import pandas as pd
import streamlit as st

from core import market, sheets
from core.webull_api import WebullAPIError, WebullClient, WebullConfig, normalize_positions, to_float

WEBULL, DIME_US, DIME_TH = "Webull", "Dime US", "Dime TH"
BROKERS = (WEBULL, DIME_US, DIME_TH)

BROKER_META = {
    WEBULL: {"icon": "⚡", "color": "#38bdf8", "market": "US", "currency": "USD", "group": "Webull"},
    DIME_US: {"icon": "💵", "color": "#facc15", "market": "US", "currency": "USD", "group": "Dime"},
    DIME_TH: {"icon": "🇹🇭", "color": "#f59e0b", "market": "TH", "currency": "THB", "group": "Dime"},
}

HOLDING_COLUMNS = ["Broker", "Symbol", "Qty", "Cost", "Price", "PrevClose", "Currency", "Source",
                   "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct", "DayChange_Pct", "DayPnL_USD"]

# Shown only when neither Webull API nor Google Sheets is configured.
DEMO_HOLDINGS = [
    {"Broker": WEBULL, "Symbol": "NVDA", "Qty": 12, "Cost": 118.4},
    {"Broker": WEBULL, "Symbol": "TSLA", "Qty": 5, "Cost": 265.0},
    {"Broker": WEBULL, "Symbol": "NU", "Qty": 150, "Cost": 12.1},
    {"Broker": DIME_US, "Symbol": "AAPL", "Qty": 20, "Cost": 182.5},
    {"Broker": DIME_US, "Symbol": "MSFT", "Qty": 8, "Cost": 402.0},
    {"Broker": DIME_US, "Symbol": "VOO", "Qty": 6, "Cost": 470.0},
    {"Broker": DIME_TH, "Symbol": "PTT", "Qty": 2000, "Cost": 33.5},
    {"Broker": DIME_TH, "Symbol": "CPALL", "Qty": 600, "Cost": 58.0},
]


def _secrets():
    try:
        return st.secrets
    except Exception:
        return {}


def _secret_section(name):
    try:
        return dict(st.secrets.get(name, {}))
    except Exception:
        return {}


def webull_config():
    return WebullConfig.from_mapping(_secret_section("Webull"))


def webull_client():
    cfg = webull_config()
    return WebullClient(cfg) if cfg.is_configured else None


def google_configured():
    try:
        return sheets.has_google_credentials(st.secrets)
    except Exception:
        return False


@st.cache_data(ttl=60, show_spinner=False)
def get_webull_balance():
    client = webull_client()
    if not client:
        return None, "ยังไม่ได้ตั้งค่า Webull API ใน secrets"
    try:
        return client.get_balance(), None
    except WebullAPIError as exc:
        return None, str(exc)


def _load_webull(sh):
    """Returns (records, source_label, error)."""
    client = webull_client()
    if client:
        try:
            rows = normalize_positions(client.get_positions())
            for r in rows:
                r.update({"Broker": WEBULL, "Source": "Webull API"})
            return rows, "Webull API", None
        except WebullAPIError as exc:
            api_error = str(exc)
    else:
        api_error = None
    if sh is not None:
        rows = sheets.read_webull_order_history(sh)
        for r in rows:
            r["Source"] = "Sheet: Webull_Order_History"
        return rows, "Google Sheets (fallback)" if api_error else "Google Sheets", api_error
    return [], "-", api_error or "ไม่ได้ตั้งค่า Webull API และ Google Sheets"


@st.cache_data(ttl=60, show_spinner=False)
def load_holdings():
    """Returns (holdings DataFrame, status dict, is_demo)."""
    secrets = _secrets()
    status = {}
    gc = sheets.get_client(secrets) if google_configured() else None
    sh = None
    sheet_error = None
    if gc is not None:
        try:
            sh = sheets.open_spreadsheet(gc, secrets)
        except Exception as exc:
            sheet_error = f"เปิด Google Sheet ไม่สำเร็จ: {exc}"

    records, wb_source, wb_error = _load_webull(sh)
    status[WEBULL] = {"source": wb_source, "error": wb_error, "count": len(records)}

    for broker, ws in ((DIME_US, sheets.WS_DIME_US), (DIME_TH, sheets.WS_DIME_TH)):
        rows = sheets.read_dime_holdings(sh, ws, broker) if sh is not None else []
        for r in rows:
            r["Source"] = f"Sheet: {ws}"
        records.extend(rows)
        status[broker] = {
            "source": f"Google Sheets ({ws})" if sh is not None else "-",
            "error": sheet_error or (None if sh is not None else "ยังไม่ได้ตั้งค่า Google credentials"),
            "count": len(rows),
        }

    is_demo = not records and not webull_config().is_configured and gc is None
    if is_demo:
        records = [dict(r, Source="DEMO") for r in DEMO_HOLDINGS]

    return price_holdings(records), status, is_demo


def price_holdings(records):
    if not records:
        return pd.DataFrame(columns=HOLDING_COLUMNS)
    df = pd.DataFrame(records)
    for col in ("Price", "Currency"):
        if col not in df.columns:
            df[col] = None

    yf_syms = tuple(market.yf_symbol(s, b) for s, b in zip(df["Symbol"], df["Broker"]))
    quotes = market.fetch_quotes(yf_syms)
    fx = market.get_usd_thb()

    rows = []
    for (_, r), yf_sym in zip(df.iterrows(), yf_syms):
        quote = quotes.get(yf_sym, {})
        api_price = to_float(r.get("Price"), 0.0)
        price = api_price or quote.get("price") or r["Cost"]
        prev_close = quote.get("prev_close") or price
        currency = r.get("Currency") or BROKER_META[r["Broker"]]["currency"]
        to_usd = (1 / fx) if currency == "THB" else 1.0

        invested = r["Qty"] * r["Cost"]
        mkt = r["Qty"] * price
        pnl = mkt - invested
        rows.append({
            "Broker": r["Broker"], "Symbol": r["Symbol"], "Qty": r["Qty"], "Cost": r["Cost"],
            "Price": price, "PrevClose": prev_close, "Currency": currency, "Source": r.get("Source", ""),
            "Invested_USD": invested * to_usd, "Market_Value_USD": mkt * to_usd, "PnL_USD": pnl * to_usd,
            "PnL_Pct": (pnl / invested * 100) if invested > 0 else 0.0,
            "DayChange_Pct": ((price / prev_close - 1) * 100) if prev_close else 0.0,
            "DayPnL_USD": r["Qty"] * (price - prev_close) * to_usd,
        })
    return pd.DataFrame(rows, columns=HOLDING_COLUMNS)


@st.cache_data(ttl=300, show_spinner=False)
def load_history():
    secrets = _secrets()
    gc = sheets.get_client(secrets) if google_configured() else None
    if gc is None:
        return pd.DataFrame()
    try:
        return sheets.read_history(sheets.open_spreadsheet(gc, secrets))
    except Exception:
        return pd.DataFrame()


def sync_snapshot(df):
    """Append the current totals to Portfolio_History. Returns (ok, message)."""
    if df.empty:
        return False, "ไม่มีข้อมูลพอร์ตที่จะซิงค์"
    secrets = _secrets()
    gc = sheets.get_client(secrets)
    if gc is None:
        return False, "ไม่พบการเชื่อมต่อ Google Sheets Credentials"
    inv, mkt = df["Invested_USD"].sum(), df["Market_Value_USD"].sum()
    pnl = mkt - inv
    try:
        sheets.append_history(sheets.open_spreadsheet(gc, secrets), inv, mkt, pnl,
                              (pnl / inv * 100) if inv else 0.0)
    except Exception as exc:
        return False, f"เขียน Google Sheets ไม่สำเร็จ: {exc}"
    load_history.clear()
    return True, "บันทึก Snapshot ลง Portfolio_History สำเร็จ"


def summarize(df):
    inv = float(df["Invested_USD"].sum()) if not df.empty else 0.0
    mkt = float(df["Market_Value_USD"].sum()) if not df.empty else 0.0
    day = float(df["DayPnL_USD"].sum()) if not df.empty else 0.0
    pnl = mkt - inv
    prev = mkt - day
    return {
        "invested": inv, "market": mkt, "pnl": pnl,
        "pnl_pct": (pnl / inv * 100) if inv else 0.0,
        "day_pnl": day, "day_pct": (day / prev * 100) if prev else 0.0,
        "count": int(len(df)),
    }

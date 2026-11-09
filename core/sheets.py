"""Google Sheets data source (Dime US / Dime TH holdings, Webull order-history fallback)."""
import base64
import json
from datetime import datetime

import pandas as pd

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

DEFAULT_SPREADSHEET = "หุ้นของเรา"
WS_DIME_US = "Dime_Portfolio"
WS_DIME_TH = "Dime_TH_Portfolio"
WS_WEBULL_ORDERS = "Webull_Order_History"
WS_HISTORY = "Portfolio_History"


def has_google_credentials(secrets):
    google = secrets.get("Google", {}) if secrets else {}
    return bool(google.get("credentials_base64")) or "gcp_service_account" in (secrets or {})


def get_client(secrets):
    if not HAS_GSPREAD or not secrets:
        return None
    try:
        cred_b64 = secrets.get("Google", {}).get("credentials_base64", "")
        if cred_b64:
            return gspread.service_account_from_dict(json.loads(base64.b64decode(cred_b64).decode("utf-8")))
        if "gcp_service_account" in secrets:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(dict(secrets["gcp_service_account"]), scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None


def open_spreadsheet(gc, secrets):
    title = secrets.get("SPREADSHEET_NAME", DEFAULT_SPREADSHEET)
    if "connections" in secrets and "gsheets" in secrets["connections"]:
        title = secrets["connections"]["gsheets"].get("spreadsheet", title)
    try:
        return gc.open(title)
    except Exception:
        return gc.open_by_key(title) if len(title) > 20 and not title.startswith("http") else gc.open_by_url(title)


def clean_val(val):
    if val is None or (isinstance(val, float) and pd.isna(val)) or val == "":
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("%", "").replace("$", "").replace("฿", "").strip())
    except ValueError:
        return 0.0


def read_dime_holdings(sh, ws_name, broker):
    """Dime sheet (one row per lot) -> aggregated holdings per symbol."""
    records = []
    try:
        data = sh.worksheet(ws_name).get_all_values()
    except Exception:
        return records
    if len(data) <= 1:
        return records

    def is_sym(cell):
        return "หุ้น" in cell or "Ticker" in cell or "Sym" in cell

    header_idx = next((i for i, row in enumerate(data[:5]) if any(is_sym(str(c)) for c in row)), 0)
    df = pd.DataFrame(data[header_idx + 1:], columns=[str(h).strip() for h in data[header_idx]])
    sym_col = next((c for c in df.columns if is_sym(c)), None)
    qty_col = next((c for c in df.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), None)
    cost_col = next((c for c in df.columns if "ต้นทุน" in c or "Avg" in c or "Cost" in c), None)
    if not (sym_col and qty_col and cost_col):
        return records

    for sym, grp in df.groupby(sym_col):
        symbol = str(sym).strip().upper()
        if not symbol or symbol in ("NAN", "NONE"):
            continue
        qty = cost_cash = 0.0
        for _, row in grp.iterrows():
            q, c = clean_val(row.get(qty_col)), clean_val(row.get(cost_col))
            if q > 0:
                qty += q
                cost_cash += q * c
        if qty > 0.0001:
            records.append({"Broker": broker, "Symbol": symbol, "Qty": qty, "Cost": cost_cash / qty})
    return records


def read_webull_order_history(sh):
    """Net Webull positions rebuilt from the order-history sheet (used when the API is not configured)."""
    records = []
    try:
        data = sh.worksheet(WS_WEBULL_ORDERS).get_all_values()
    except Exception:
        return records
    if len(data) <= 1:
        return records

    df = pd.DataFrame(data[1:], columns=data[0])
    cols = list(df.columns)

    def find(keys, fallback_idx):
        col = next((c for c in cols if any(k in c for k in keys)), None)
        if col is None and fallback_idx is not None and len(cols) > fallback_idx:
            col = cols[fallback_idx]
        return col

    sym_col = find(("Sym", "Ticker", "หุ้น"), 2) or cols[0]
    side_col = find(("Side", "ประเภท", "Action"), 3)
    qty_col = find(("Qty", "Volume", "จำนวน"), 4)
    cost_col = find(("Pr", "Cost", "ต้นทุน", "Avg"), 5)
    status_col = find(("สถานะ", "Status"), 6)

    for sym, grp in df.groupby(sym_col):
        symbol = str(sym).strip().upper()
        if not symbol or symbol in ("NAN", "NONE"):
            continue
        net_qty = buy_qty = buy_cost = 0.0
        for _, r in grp.iterrows():
            if status_col and str(r.get(status_col, "")).strip().upper() == "C":  # cancelled
                continue
            q, c = clean_val(r.get(qty_col)), clean_val(r.get(cost_col))
            side = str(r.get(side_col, "BUY")).strip().upper() if side_col else "BUY"
            if "BUY" in side or "ซื้อ" in side:
                net_qty += q
                buy_qty += q
                buy_cost += q * c
            elif "SELL" in side or "ขาย" in side:
                net_qty -= q
        if net_qty > 0.0001:
            records.append({"Broker": "Webull", "Symbol": symbol, "Qty": net_qty,
                            "Cost": buy_cost / buy_qty if buy_qty else 0.0})
    return records


def read_history(sh):
    """Portfolio_History snapshots -> DataFrame[Timestamp, Invested, MarketValue, PnL, PnLPct, Parsed_Date]."""
    try:
        data = sh.worksheet(WS_HISTORY).get_all_values()
    except Exception:
        return pd.DataFrame()
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    first = str(df.iloc[0, 0]).strip()
    if "วัน" in first or "Date" in first or "Timestamp" in first:
        df = df.iloc[1:].reset_index(drop=True)
    cols = ["Timestamp", "Invested", "MarketValue", "PnL", "PnLPct"]
    df = df.iloc[:, :len(cols)]
    df.columns = cols[:len(df.columns)]
    for col in cols[1:len(df.columns)]:
        df[col] = df[col].apply(clean_val)
    df = df[df["MarketValue"] > 0]
    df["Parsed_Date"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    return df.dropna(subset=["Parsed_Date"]).sort_values("Parsed_Date").reset_index(drop=True)


def append_history(sh, invested, market_value, pnl, pnl_pct):
    try:
        ws = sh.worksheet(WS_HISTORY)
    except Exception:
        ws = sh.add_worksheet(title=WS_HISTORY, rows="1000", cols="5")
        ws.append_row(["วันที่", "มูลค่าตั้งต้น", "มูลค่าปัจจุบัน", "กำไรขาดทุน", "กำไรขาดทุน%"])
    ws.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), round(invested, 2),
                   round(market_value, 2), round(pnl, 2), f"{pnl_pct:.2f}%"])

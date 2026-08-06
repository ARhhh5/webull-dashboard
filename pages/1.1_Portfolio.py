import os
import json
import base64
import urllib.parse
import http.client
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ==========================================
# 1. SHARED DATA PIPELINE & HELPERS
# ==========================================
@st.cache_data(ttl=60)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0

def get_gspread_client():
    if not HAS_GSPREAD: return None
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            return gspread.service_account_from_dict(cred_dict)
        elif "gcp_service_account" in st.secrets:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def fetch_webull_strict_openapi_positions():
    wb_secrets = st.secrets.get("Webull", {})
    app_key = wb_secrets.get("AppKey", "")
    app_secret = wb_secrets.get("AppSecret", "")
    access_token = wb_secrets.get("AccessToken", "")
    account_id = wb_secrets.get("AccountId", "")

    if not (app_key and app_secret and access_token and account_id):
        return None, "Missing Webull Credentials in Secrets"

    try:
        host = "openapi.webull.com"
        path = "/openapi/assets/positions"
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        nonce = str(uuid.uuid4())

        sign_params = {
            "app_key": app_key,
            "signature_version": "1.0",
            "signature_algorithm": "HMAC-SHA1",
            "timestamp": timestamp,
            "nonce": nonce,
            "account_id": account_id
        }
        sorted_keys = sorted(sign_params.keys())
        canonical_query = "&".join([f"{k}={sign_params[k]}" for k in sorted_keys])
        string_to_sign = f"GET\n{path}\n{canonical_query}"

        signature = hmac.new(app_secret.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        headers = {
            "x-app-key": app_key,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "x-version": "1.0",
            "x-signature": signature_b64,
            "x-access-token": access_token
        }

        conn = http.client.HTTPSConnection(host, timeout=10)
        full_path = f"{path}?account_id={account_id}"
        conn.request("GET", full_path, headers=headers)
        response = conn.getresponse()
        
        if response.status == 200:
            data = json.loads(response.read().decode('utf-8'))
            positions = data.get("positions", []) or data.get("data", {}).get("positions", [])
            
            holdings = []
            for p in positions:
                sym = p.get("symbol", "").strip().upper()
                qty = float(p.get("quantity", 0))
                cost = float(p.get("costPrice", 0) or p.get("cost", 0))
                if qty > 0 and sym:
                    holdings.append({
                        "Symbol": sym, 
                        "Qty": qty, 
                        "Cost": cost, 
                        "Broker": "Webull",
                        "Source": "Webull API (Live)"
                    })
            return holdings, "OK"
        else:
            return None, f"HTTP Error {response.status}: {response.reason}"
    except Exception as e:
        return None, f"Connection Failed: {str(e)}"

def load_dime_us_from_gsheet():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                        "Broker": "Dime US",
                        "Source": "Google Sheet",
                        "Manual_Price": r.get("ราคาปัจจุบันล็อก (Manual Price)", "")
                    })
        except: pass
    return holdings

def load_dime_th_from_gsheet():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_TH_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                        "Broker": "Dime TH",
                        "Source": "Google Sheet"
                    })
        except: pass
    return holdings

@st.cache_data(ttl=60)
def fetch_full_portfolio_df():
    fx_rate = get_usd_thb_rate()
    
    # Strictly Webull Live OpenAPI (No GSheet Fallback)
    w_holdings, api_status = fetch_webull_strict_openapi_positions()
    webull_source = "Webull API (Live)" if api_status == "OK" else f"API Error: {api_status}"
    
    if not w_holdings:
        w_holdings = []

    d_us_holdings = load_dime_us_from_gsheet()
    d_th_holdings = load_dime_th_from_gsheet()
    
    all_holdings = w_holdings + d_us_holdings + d_th_holdings
    if not all_holdings:
        return pd.DataFrame(), fx_rate, webull_source, datetime.now().strftime("%H:%M:%S")

    df_raw = pd.DataFrame(all_holdings)
    live_prices = {}

    for index, row in df_raw.iterrows():
        sym = row['Symbol']
        broker = row['Broker']
        
        if broker == "Dime US" and row.get("Manual_Price") != "" and row.get("Manual_Price") is not None:
            try: live_prices[sym] = float(row["Manual_Price"])
            except: live_prices[sym] = 0.0

        if sym not in live_prices or live_prices[sym] == 0.0:
            yf_sym = f"{sym}.BK" if broker == "Dime TH" and not sym.endswith(".BK") else sym
            try:
                t_data = yf.Ticker(yf_sym)
                p = t_data.info.get('currentPrice') or t_data.info.get('regularMarketPrice') or t_data.fast_info.get('last_price')
                if not p:
                    h = t_data.history(period="1d")
                    if not h.empty: p = h['Close'].iloc[-1]
                live_prices[sym] = float(p) if p else 0.0
            except:
                live_prices[sym] = 0.0

    portfolio_rows = []
    for index, row in df_raw.iterrows():
        sym = row['Symbol']
        qty = row['Qty']
        cost_in = row['Cost']
        broker = row['Broker']
        source = row.get('Source', 'Google Sheet')
        
        price_raw = live_prices.get(sym, 0)
        if price_raw == 0: price_raw = cost_in

        if broker == "Dime TH":
            invested_usd = (qty * cost_in) / fx_rate
            market_val_usd = (qty * price_raw) / fx_rate
        else:
            invested_usd = qty * cost_in
            market_val_usd = qty * price_raw

        pnl_usd = market_val_usd - invested_usd
        pnl_pct = (pnl_usd / invested_usd * 100) if invested_usd > 0 else 0.0

        portfolio_rows.append({
            "Symbol": sym,
            "Broker": broker,
            "Qty": qty,
            "Cost": cost_in,
            "Price": price_raw,
            "Invested_USD": invested_usd,
            "Market_Value_USD": market_val_usd,
            "PnL_USD": pnl_usd,
            "PnL_Pct": pnl_pct,
            "Source": source
        })

    df_port = pd.DataFrame(portfolio_rows)
    sync_time = datetime.now().strftime("%H:%M:%S")

    st.session_state["all_holdings_df"] = df_port
    st.session_state["usd_thb_rate"] = fx_rate
    st.session_state["webull_source"] = webull_source
    st.session_state["sync_time"] = sync_time

    return df_port, fx_rate, webull_source, sync_time

# ==========================================
# 2. MAIN PAGE RENDER
# ==========================================
df_port, fx_rate, webull_source, sync_time = fetch_full_portfolio_df()

c_title, c_status, c_sync = st.columns([2.0, 1.5, 0.9])

with c_title:
    st.title("Portfolio Overview")
    st.caption("วิเคราะห์สัดส่วนการถือครองและผลตอบแทนรายโบรกเกอร์ (หุ้นล้วน ไม่รวมเงินสด)")

with c_status:
    st.markdown("<br>", unsafe_allow_html=True)
    if "Live" in webull_source:
        st.markdown(
            f'''<div style="text-align: right;">
                <span class="source-badge-api">🟢 Webull API (Live)</span>
                <div style="font-size:0.72rem; color:#6b7280; margin-top:4px;">Updated: {sync_time}</div>
            </div>''', 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'''<div style="text-align: right;">
                <span class="source-badge-error">🔴 {webull_source}</span>
                <div style="font-size:0.72rem; color:#f87171; margin-top:4px;">Updated: {sync_time}</div>
            </div>''', 
            unsafe_allow_html=True
        )

with c_sync:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔄 Sync Portfolio Data", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.success("อัปเดตข้อมูลพอร์ตหุ้นสดเรียบร้อยแล้ว!")
        st.rerun()

c_curr, _ = st.columns([1, 3])
with c_curr:
    currency_selected = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

is_usd = "USD" in currency_selected
multiplier = 1.0 if is_usd else fx_rate
symbol = "$" if is_usd else "฿"

if "port_tab" not in st.session_state:
    st.session_state["port_tab"] = "All In One"

tabs_list = ["All In One", "Webull US", "Dime US", "Dime TH", "US Consolidated"]
t_cols = st.columns(len(tabs_list))

for idx, t_name in enumerate(tabs_list):
    with t_cols[idx]:
        btn_kind = "primary" if st.session_state["port_tab"] == t_name else "secondary"
        if st.button(t_name, key=f"port_tab_btn_{t_name}", type=btn_kind, use_container_width=True):
            st.session_state["port_tab"] = t_name
            st.rerun()

current_tab = st.session_state["port_tab"]
st.markdown("<br>", unsafe_allow_html=True)

if df_port.empty:
    st.warning("⚠️ ไม่พบข้อมูลพอร์ตโฟลิโอ หรือ Webull API เกิดข้อผิดพลาด กรุณาตรวจสอบสถานะมุมขวาบน")
else:
    if current_tab == "Webull US":
        sub_df = df_port[df_port["Broker"] == "Webull"].copy()
    elif current_tab == "Dime US":
        sub_df = df_port[df_port["Broker"] == "Dime US"].copy()
    elif current_tab == "Dime TH":
        sub_df = df_port[df_port["Broker"] == "Dime TH"].copy()
    elif current_tab == "US Consolidated":
        sub_df = df_port[df_port["Broker"].isin(["Webull", "Dime US"])].copy()
        if not sub_df.empty:
            sub_df = sub_df.groupby("Symbol").apply(lambda x: pd.Series({
                "Broker": "US Consolidated",
                "Qty": x["Qty"].sum(),
                "Cost": (x["Invested_USD"].sum() / x["Qty"].sum()) if x["Qty"].sum() > 0 else 0,
                "Price": x["Price"].iloc[0],
                "Invested_USD": x["Invested_USD"].sum(),
                "Market_Value_USD": x["Market_Value_USD"].sum(),
                "PnL_USD": x["Market_Value_USD"].sum() - x["Invested_USD"].sum(),
                "PnL_Pct": ((x["Market_Value_USD"].sum() - x["Invested_USD"].sum()) / x["Invested_USD"].sum() * 100) if x["Invested_USD"].sum() > 0 else 0,
                "Source": x["Source"].iloc[0]
            })).reset_index()
    else:
        sub_df = df_port.copy()

    if sub_df.empty:
        st.warning(f"ไม่พบรายการถือครองในหมวด {current_tab}")
    else:
        tot_inv = sub_df["Invested_USD"].sum() * multiplier
        tot_mkt = sub_df["Market_Value_USD"].sum() * multiplier
        tot_pnl = tot_mkt - tot_inv
        tot_pnl_pct = (tot_pnl / tot_inv * 100) if tot_inv > 0 else 0.0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Invested Capital", f"{symbol}{tot_inv:,.2f}")
        m2.metric("Market Value", f"{symbol}{tot_mkt:,.2f}")
        m3.metric("Total Return ($)", f"{symbol}{tot_pnl:,.2f}", delta=f"{tot_pnl:,.2f}")
        m4.metric("Total Return (%)", f"{tot_pnl_pct:.2f}%", delta=f"{tot_pnl_pct:.2f}%")

        st.markdown("<hr style='border-color: #1f232d;'>", unsafe_allow_html=True)

        disp_df = sub_df.copy()
        disp_df["Qty"] = disp_df["Qty"].map("{:,.4f}".format)
        disp_df["Cost"] = disp_df["Cost"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["Price"] = disp_df["Price"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["Invested"] = disp_df["Invested_USD"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["Market Value"] = disp_df["Market_Value_USD"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["PnL ($)"] = disp_df["PnL_USD"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["PnL (%)"] = disp_df["PnL_Pct"].map("{:,.2f}%".format)

        show_cols = ["Symbol", "Broker", "Qty", "Cost", "Price", "Invested", "Market Value", "PnL ($)", "PnL (%)", "Source"]
        st.dataframe(disp_df[show_cols], use_container_width=True, hide_index=True)

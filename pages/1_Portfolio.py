import os
import json
import base64
import urllib.parse
import http.client
import uuid
import hmac
import hashlib
import streamlit as st
import pandas as pd
import plotly.express as px
import yfinance as yf
import gspread
from datetime import datetime, timezone

st.set_page_config(page_title="Portfolio Overview", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
        margin-bottom: 15px;
    }
    .metric-label {
        color: #848e9c;
        font-size: 14px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: bold;
        color: #ffffff;
    }
    .text-green { color: #00c853 !important; }
    .text-red { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("💼 สรุปภาพรวมพอร์ตการลงทุน (Total Portfolio Overview)")
st.markdown("---")

# ==========================================
# 🎯 เพิ่มปุ่มสลับสกุลเงิน (USD / THB)
# ==========================================
currency_mode = st.radio(
    "💱 เลือกสกุลเงินหลักในการแสดงผล Portfolio Overview:",
    ("แสดงเป็นดอลลาร์ ($ USD)", "แสดงเป็นเงินบาท (฿ THB)"),
    horizontal=True
)

# ==========================================
# 1. Config & API Setup
# ==========================================
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

@st.cache_data(ttl=60)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0

fx_rate = get_usd_thb_rate()

def get_webull_live_prices():
    path = "/openapi/assets/positions"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
    
    prices = {}
    try:
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                prices[str(p.get("symbol")).upper()] = float(p.get("last_price", 0))
    except:
        pass
    return prices

def get_webull_holdings():
    path = "/openapi/assets/positions"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
    
    holdings = []
    try:
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                if p.get("instrument_type") == "EQUITY":
                    holdings.append({
                        "Symbol": str(p.get("symbol", "")).strip().upper(),
                        "Qty": float(p.get("quantity", 0)),
                        "Cost": float(p.get("cost_price", 0)),
                        "Broker": "Webull"
                    })
    except:
        pass
    return holdings

def get_dime_us_holdings():
    holdings = []
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
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
                        "Manual_Price": r.get("ราคาปัจจุบันล็อก (Manual Price)", "")
                    })
    except:
        pass
    return holdings

def get_dime_th_holdings():
    holdings = []
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
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
                        "Broker": "Dime TH"
                    })
    except:
        pass
    return holdings

# ==========================================
# 2. โหลดและรวมข้อมูลพอร์ต
# ==========================================
with st.spinner("⏳ กำลังรวบรวมข้อมูลพอร์ตรวม..."):
    webull_prices = get_webull_live_prices()
    w_holdings = get_webull_holdings()
    d_us_holdings = get_dime_us_holdings()
    d_th_holdings = get_dime_th_holdings()
    
    all_holdings = w_holdings + d_us_holdings + d_th_holdings
    
    if all_holdings:
        df_raw = pd.DataFrame(all_holdings)
        live_prices = {}
        
        for index, row in df_raw.iterrows():
            sym = row['Symbol']
            broker = row['Broker']
            
            if broker == "Webull" and sym in webull_prices and webull_prices[sym] > 0:
                live_prices[sym] = webull_prices[sym]
            elif broker == "Dime US" and row.get("Manual_Price") != "" and row.get("Manual_Price") is not None:
                try:
                    live_prices[sym] = float(row["Manual_Price"])
                except:
                    live_prices[sym] = 0.0
            
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
                "PnL_Pct": pnl_pct
            })
            
        df_port = pd.DataFrame(portfolio_rows)
    else:
        df_port = pd.DataFrame()

# ==========================================
# 🎨 ฟังก์ชันแต่งสีกำไร/ขาดทุนในตาราง (Conditional Formatting)
# ==========================================
def highlight_pnl(val):
    try:
        val_float = float(str(val).replace('$', '').replace('฿', '').replace(',', '').replace('%', '').replace('+', ''))
        if val_float > 0:
            return 'background-color: #063219; color: #00c853; font-weight: bold;'
        elif val_float < 0:
            return 'background-color: #3b0d0d; color: #ff3d00; font-weight: bold;'
    except:
        pass
    return ''

# ==========================================
# 3. โครงสร้าง 5 แท็บ (5-Tab Layout)
# ==========================================
tab_all, tab_webull, tab_dime_us, tab_dime_th, tab_consolidated = st.tabs([
    "📊 1. ภาพรวมทั้งหมด (All In One)", 
    "🦅 2. Webull", 
    "💵 3. Dime US", 
    "🇹🇭 4. Dime TH",
    "🧩 5. รวมหุ้นทุกตัว (US Only)"
])

# ------------------------------------------
# TAB 1: ALL IN ONE OVERVIEW
# ------------------------------------------
with tab_all:
    is_thb = "เงินบาท" in currency_mode
    multiplier = fx_rate if is_thb else 1.0
    curr_symbol = "฿" if is_thb else "$"
    curr_text = "THB" if is_thb else "USD"
    
    st.subheader(f"🌐 รวมสถิติพอร์ตการลงทุนทุกโบรกเกอร์ (แสดงในสกุลเงิน {curr_text})")
    
    if not df_port.empty:
        grand_invested = df_port['Invested_USD'].sum() * multiplier
        grand_market = df_port['Market_Value_USD'].sum() * multiplier
        grand_pnl = grand_market - grand_invested
        grand_pnl_pct = (grand_pnl / grand_invested * 100) if grand_invested > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">💵 เงินลงทุนรวมทั้งสิ้น</div><div class="metric-value">{curr_symbol}{grand_invested:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">📈 มูลค่าตลาดรวมพอร์ตทั้งหมด</div><div class="metric-value">{curr_symbol}{grand_market:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            pnl_class = "text-green" if grand_pnl >= 0 else "text-red"
            pnl_prefix = "+" if grand_pnl >= 0 else ""
            st.markdown(f'<div class="metric-card"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิรวม</div><div class="metric-value {pnl_class}">{pnl_prefix}{curr_symbol}{grand_pnl:,.2f} ({grand_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

        st.caption(f"ℹ️ อัตราแลกเปลี่ยนอ้างอิง: 1 USD = {fx_rate:.2f} THB")
        st.markdown("---")
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            df_broker_summary = df_port.groupby("Broker")["Market_Value_USD"].sum().reset_index()
            df_broker_summary["Value"] = df_broker_summary["Market_Value_USD"] * multiplier
            fig1 = px.pie(df_broker_summary, names="Broker", values="Value", title=f"สัดส่วนมูลค่าพอร์ตแยกตามโบรกเกอร์ ({curr_text})", hole=0.4, template="plotly_dark")
            st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            df_symbol_summary = df_port.groupby("Symbol")["Market_Value_USD"].sum().reset_index()
            df_symbol_summary["Value"] = df_symbol_summary["Market_Value_USD"] * multiplier
            fig2 = px.pie(df_symbol_summary, names="Symbol", values="Value", title=f"สัดส่วนการถือครองหุ้นทุกตัวในพอร์ต ({curr_text})", template="plotly_dark")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("ยังไม่มีข้อมูลหุ้นในพอร์ตโฟลิโอ")

# ------------------------------------------
# TAB 2: WEBULL PORTFOLIO
# ------------------------------------------
with tab_webull:
    st.subheader("🦅 พอร์ตการลงทุน Webull (Live API Data)")
    df_w = df_port[df_port["Broker"] == "Webull"] if not df_port.empty else pd.DataFrame()
    if not df_w.empty:
        df_w_disp = df_w[["Symbol", "Qty", "Cost", "Price", "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct"]].copy()
        df_w_disp.columns = ["Symbol", "Qty", "Avg Cost ($)", "Market Price ($)", "Total Cost ($)", "Market Value ($)", "Unrealized P/L ($)", "P/L (%)"]
        
        # Formatting
        formatted_df = df_w_disp.style.format({
            "Qty": "{:,.4f}", "Avg Cost ($)": "${:,.2f}", "Market Price ($)": "${:,.2f}",
            "Total Cost ($)": "${:,.2f}", "Market Value ($)": "${:,.2f}",
            "Unrealized P/L ($)": "${:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).applymap(highlight_pnl, subset=["Unrealized P/L ($)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Webull")

# ------------------------------------------
# TAB 3: DIME US PORTFOLIO
# ------------------------------------------
with tab_dime_us:
    st.subheader("💵 พอร์ตการลงทุน Dime US")
    df_dus = df_port[df_port["Broker"] == "Dime US"] if not df_port.empty else pd.DataFrame()
    if not df_dus.empty:
        df_dus_disp = df_dus[["Symbol", "Qty", "Cost", "Price", "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct"]].copy()
        df_dus_disp.columns = ["Symbol", "Qty", "Avg Cost ($)", "Market Price ($)", "Total Cost ($)", "Market Value ($)", "Unrealized P/L ($)", "P/L (%)"]
        
        formatted_df = df_dus_disp.style.format({
            "Qty": "{:,.4f}", "Avg Cost ($)": "${:,.2f}", "Market Price ($)": "${:,.2f}",
            "Total Cost ($)": "${:,.2f}", "Market Value ($)": "${:,.2f}",
            "Unrealized P/L ($)": "${:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).applymap(highlight_pnl, subset=["Unrealized P/L ($)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime US")

# ------------------------------------------
# TAB 4: DIME TH PORTFOLIO (เน้นปรับสีกำไร/ขาดทุนตามภาพ)
# ------------------------------------------
with tab_dime_th:
    st.subheader("🇹🇭 พอร์ตการลงทุน Dime TH (หุ้นไทย)")
    df_dth = df_port[df_port["Broker"] == "Dime TH"] if not df_port.empty else pd.DataFrame()
    if not df_dth.empty:
        df_dth_disp = df_dth.copy()
        df_dth_disp["Total_Cost_THB"] = df_dth_disp["Qty"] * df_dth_disp["Cost"]
        df_dth_disp["Market_Value_THB"] = df_dth_disp["Qty"] * df_dth_disp["Price"]
        df_dth_disp["PnL_THB"] = df_dth_disp["Market_Value_THB"] - df_dth_disp["Total_Cost_THB"]
        
        df_dth_disp = df_dth_disp[["Symbol", "Qty", "Cost", "Price", "Total_Cost_THB", "Market_Value_THB", "PnL_THB", "PnL_Pct"]]
        df_dth_disp.columns = ["Symbol", "Qty", "Avg Cost (฿)", "Market Price (฿)", "Total Cost (฿)", "Market Value (฿)", "Unrealized P/L (฿)", "P/L (%)"]
        
        formatted_df = df_dth_disp.style.format({
            "Qty": "{:,.0f}", "Avg Cost (฿)": "฿{:,.2f}", "Market Price (฿)": "฿{:,.2f}",
            "Total Cost (฿)": "฿{:,.2f}", "Market Value (฿)": "฿{:,.2f}",
            "Unrealized P/L (฿)": "฿{:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).applymap(highlight_pnl, subset=["Unrealized P/L (฿)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime TH")

# ------------------------------------------
# TAB 5: CONSOLIDATED HOLDINGS (เฉพาะหุ้นสหรัฐฯ)
# ------------------------------------------
with tab_consolidated:
    st.subheader("🧩 รวมหุ้นทุกตัวเฉพาะหุ้นสหรัฐฯ (US Consolidated Holdings)")
    st.markdown("นำหุ้นสหรัฐฯ ตัวเดียวกันจาก Webull และ Dime US มารวมจำนวนหุ้นและคิดราคาต้นทุนเฉลี่ยถัวน้ำหนัก (Weighted Avg Cost)")
    
    df_us_only = df_port[df_port["Broker"].isin(["Webull", "Dime US"])] if not df_port.empty else pd.DataFrame()
    
    if not df_us_only.empty:
        grouped_rows = []
        for sym, group in df_us_only.groupby("Symbol"):
            tot_qty = group["Qty"].sum()
            tot_cost = group["Invested_USD"].sum()
            tot_market = group["Market_Value_USD"].sum()
            tot_pnl = tot_market - tot_cost
            pnl_pct = (tot_pnl / tot_cost * 100) if tot_cost > 0 else 0.0
            avg_cost = tot_cost / tot_qty if tot_qty > 0 else 0.0
            market_price = group["Price"].iloc[0]
            sources = ", ".join(group["Broker"].unique())
            
            grouped_rows.append({
                "Symbol": sym,
                "Total_Qty": tot_qty,
                "Avg_Cost_USD": avg_cost,
                "Market_Price": market_price,
                "Total_Cost_USD": tot_cost,
                "Market_Value_USD": tot_market,
                "Unrealized_PL_USD": tot_pnl,
                "Unrealized_PL_Pct": pnl_pct,
                "Sources": sources
            })
            
        df_grouped = pd.DataFrame(grouped_rows)
        df_grouped.columns = ["Symbol", "Total Qty", "Avg Cost ($)", "Market Price ($)", "Total Cost ($)", "Market Value ($)", "Unrealized P/L ($)", "P/L (%)", "Sources"]
        
        formatted_df = df_grouped.style.format({
            "Total Qty": "{:,.4f}", "Avg Cost ($)": "${:,.2f}", "Market Price ($)": "${:,.2f}",
            "Total Cost ($)": "${:,.2f}", "Market Value ($)": "${:,.2f}",
            "Unrealized P/L ($)": "${:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).applymap(highlight_pnl, subset=["Unrealized P/L ($)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบรายการถือครองหุ้นสหรัฐฯ ในระบบ")

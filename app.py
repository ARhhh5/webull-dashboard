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

# 1. ตั้งค่าหน้าตา Dashboard
st.set_page_config(page_title="Master Portfolio Dashboard", layout="wide")

st.markdown("""
    <style>
    .metric-container {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        text-align: center;
    }
    .metric-label { color: #848e9c; font-size: 16px; font-weight: 500; margin-bottom: 8px; }
    .metric-value { color: #ffffff; font-size: 32px; font-weight: 700; }
    .pnl-positive { color: #00c853 !important; }
    .pnl-negative { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Master Dashboard: วิเคราะห์พอร์ตโฟลิโอรวม")
st.markdown("---")

# 🎯 เพิ่มปุ่มสลับสกุลเงิน (USD / THB)
currency_mode = st.radio(
    "💱 เลือกสกุลเงินหลักในการแสดงผล Master Dashboard:",
    ("แสดงเป็นดอลลาร์ ($ USD)", "แสดงเป็นเงินบาท (฿ THB)"),
    horizontal=True
)

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

DEFAULT_SECTORS = {
    "QQQM": "Technology", "SCHG": "Technology", "PG": "Consumer Defensive", 
    "YMAG": "Technology", "KKP": "Financial Services", "CYN": "Technology",
    "ETOR": "Technology", "IMN": "Technology", "SLDE": "Technology"
}

with st.spinner("⏳ กำลังรวบรวมข้อมูลพอร์ตรวมและดึงราคาล่าสุดแบบปลอดภัย..."):
    webull_prices = get_webull_live_prices()
    all_holdings = get_webull_holdings() + get_dime_us_holdings() + get_dime_th_holdings()
    
    if all_holdings:
        df_raw = pd.DataFrame(all_holdings)
        
        live_prices = {}
        sectors = {}
        
        for index, row in df_raw.iterrows():
            sym = row['Symbol']
            broker = row['Broker']
            
            sectors[sym] = DEFAULT_SECTORS.get(sym, "Unknown (ETF/Other)")
            
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
                    
        portfolio_data = []
        for index, row in df_raw.iterrows():
            sym = row['Symbol']
            qty = row['Qty']
            cost_in = row['Cost']
            broker = row['Broker']
            
            price_raw = live_prices.get(sym, 0)
            if price_raw == 0:
                price_raw = cost_in
            
            # คำนวณฐาน USD ก่อน
            if broker == "Dime TH":
                invested_usd = (qty * cost_in) / fx_rate
                market_val_usd = (qty * price_raw) / fx_rate
            else:
                invested_usd = qty * cost_in
                market_val_usd = qty * price_raw
                
            pnl_usd = market_val_usd - invested_usd
            
            portfolio_data.append({
                "Symbol": sym,
                "Sector": sectors.get(sym, "Unknown"),
                "Broker": broker,
                "Invested_USD": invested_usd,
                "Market_Value_USD": market_val_usd,
                "PnL_USD": pnl_usd
            })
            
        df_port = pd.DataFrame(portfolio_data)
        
        # 🎯 ตรรกะแปลงสกุลเงินตามปุ่มเลือก
        is_thb = "เงินบาท" in currency_mode
        multiplier = fx_rate if is_thb else 1.0
        curr_symbol = "฿" if is_thb else "$"
        curr_text = "THB" if is_thb else "USD"
        
        df_port['Invested'] = df_port['Invested_USD'] * multiplier
        df_port['Market Value'] = df_port['Market_Value_USD'] * multiplier
        df_port['PnL'] = df_port['PnL_USD'] * multiplier

        grand_invested = df_port['Invested'].sum()
        grand_market = df_port['Market Value'].sum()
        grand_pnl = grand_market - grand_invested
        grand_pnl_pct = (grand_pnl / grand_invested * 100) if grand_invested > 0 else 0
        
        pnl_class = "pnl-positive" if grand_pnl >= 0 else "pnl-negative"
        pnl_prefix = "+" if grand_pnl >= 0 else ""
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💵 เงินลงทุนรวมทั้งสิ้น</div><div class="metric-value">{curr_symbol}{grand_invested:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📈 มูลค่าตลาดรวมพอร์ตทั้งหมด</div><div class="metric-value">{curr_symbol}{grand_market:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิรวม</div><div class="metric-value {pnl_class}">{pnl_prefix}{curr_symbol}{grand_pnl:,.2f} ({grand_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
        
        # --- กราฟแท่งแนวนอน ---
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        df_sector = df_port.groupby("Sector").sum(numeric_only=True).reset_index()
        df_sector = df_sector.sort_values(by="Market Value", ascending=True)
        
        with col1:
            st.subheader("🪵 สัดส่วนขนาดพอร์ตแยกตามอุตสาหกรรม")
            fig_asset_bar = px.bar(
                df_sector, 
                x='Market Value', 
                y='Sector', 
                orientation='h',
                text_auto='.2s',
                title=f"มูลค่าถือครองปัจจุบัน ({curr_symbol} {curr_text})",
                color='Sector',
                color_discrete_map={
                    "Technology": "#0052FF",
                    "Financial Services": "#FF9900",
                    "Consumer Defensive": "#00C853",
                    "Unknown (ETF/Other)": "#7F8C8D"
                }
            )
            fig_asset_bar.update_traces(textposition='inside', insidetextanchor='end')
            fig_asset_bar.update_layout(
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)", 
                font=dict(color="white", size=13),
                xaxis=dict(title=f"มูลค่ารวม ({curr_symbol})", showgrid=True, gridcolor="#2a2e39"),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_asset_bar, use_container_width=True)
            
        df_pnl_sector = df_port.groupby("Sector").sum(numeric_only=True).reset_index()
        df_pnl_sector = df_pnl_sector.sort_values(by="PnL", ascending=True)
        df_pnl_sector['Color'] = df_pnl_sector['PnL'].apply(lambda x: 'Profit' if x >= 0 else 'Loss')
        
        with col2:
            st.subheader("📊 ยอดกำไร / ขาดทุนสุทธิแยกตามอุตสาหกรรม")
            fig_pnl_bar = px.bar(
                df_pnl_sector, 
                x='PnL', 
                y='Sector', 
                orientation='h',
                text_auto='.2s',
                title=f"กำไรหรือขาดทุนที่เกิดขึ้นจริง ({curr_symbol} {curr_text})",
                color='Color', 
                color_discrete_map={'Profit': '#00c853', 'Loss': '#ff3d00'}
            )
            fig_pnl_bar.update_traces(textposition='outside')
            fig_pnl_bar.update_layout(
                showlegend=False, 
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)", 
                font=dict(color="white", size=13),
                xaxis=dict(title=f"กำไร/ขาดทุนสุทธิ ({curr_symbol})", showgrid=True, gridcolor="#2a2e39"),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_pnl_bar, use_container_width=True)
    else:
        st.info("ยังไม่มีข้อมูลหุ้นในพอร์ตโฟลิโอ")

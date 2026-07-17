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

# ดึงราคาตลาดล่าสุดจาก Webull OpenAPI (ปลอดภัย ไม่โดนบล็อก IP)
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
        res = conn.getcall = conn.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                if p.get("instrument_type") == "EQUITY":
                    holdings.append({
                        "Symbol": str(p.get("symbol", "")).upper(),
                        "Qty": float(p.get("quantity", 0)),
                        "Cost": float(p.get("cost_price", 0)),
                        "Broker": "Webull"
                    })
    except:
        pass
    return holdings

def get_dime_holdings():
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
                        "Broker": "Dime!"
                    })
    except:
        pass
    return holdings

# ตารางคู่มือจัดกลุ่มอุตสาหกรรมในพอร์ตอัตโนมัติกรณี Yahoo บล็อกข้อมูล
DEFAULT_SECTORS = {
    "QQQM": "Technology", "SCHG": "Technology", "PG": "Consumer Defensive", 
    "YMAG": "Technology", "KKP.BK": "Financial Services", "CYN": "Technology",
    "ETOR": "Technology", "IMN": "Technology", "SLDE": "Technology"
}

with st.spinner("⏳ กำลังรวบรวมข้อมูลพอร์ตรวมและดึงราคาล่าสุดแบบปลอดภัย..."):
    webull_prices = get_webull_live_prices()
    all_holdings = get_webull_holdings() + get_dime_holdings()
    
    if all_holdings:
        df_raw = pd.DataFrame(all_holdings)
        unique_symbols = df_raw['Symbol'].unique().tolist()
        
        sectors = {}
        live_prices = {}
        
        # วิ่งหาข้อมูลราคาสดสลับท่อป้องกันการเอ๋อ
        for sym in unique_symbols:
            # 1. จัดสรรกลุ่มอุตสาหกรรมดักไว้ล่วงหน้า
            sectors[sym] = DEFAULT_SECTORS.get(sym, "Unknown (ETF/Other)")
            
            # 2. ค้นหาราคาจาก Webull ก่อน ถ้าไม่มีค่อยขอ Yahoo หรือขอดึงด่วนย้อนหลัง
            if sym in webull_prices and webull_prices[sym] > 0:
                live_prices[sym] = webull_prices[sym]
            else:
                try:
                    t_data = yf.Ticker(sym)
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
            
            # ตรวจสอบเรื่องสกุลเงินหุ้นไทย
            is_thai = sym.endswith(".BK")
            price_raw = live_prices.get(sym, cost_in) if live_prices.get(sym, 0) > 0 else cost_in
            
            if is_thai:
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
                "Invested": invested_usd,
                "Market Value": market_val_usd,
                "PnL": pnl_usd
            })
            
        df_port = pd.DataFrame(portfolio_data)
        
        grand_invested = df_port['Invested'].sum()
        grand_market = df_port['Market Value'].sum()
        grand_pnl = grand_market - grand_invested
        grand_pnl_pct = (grand_pnl / grand_invested * 100) if grand_invested > 0 else 0
        
        pnl_class = "pnl-positive" if grand_pnl >= 0 else "pnl-negative"
        pnl_prefix = "+" if grand_pnl >= 0 else ""
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-container"><div class="metric-label">💵 เงินลงทุนรวมทั้งสิ้น</div><div class="metric-value">${grand_invested:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📈 มูลค่าตลาดรวม (Webull + Dime)</div><div class="metric-value">${grand_market:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-container"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิรวม</div><div class="metric-value {pnl_class}">{pnl_prefix}${grand_pnl:,.2f} ({grand_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
        
        st.markdown("<br><br>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        df_sector = df_port.groupby("Sector").sum(numeric_only=True).reset_index()
        
        with col1:
            st.subheader("🥧 สัดส่วนพอร์ตแยกตามอุตสาหกรรม (Sector)")
            fig_pie = px.pie(df_sector, values='Market Value', names='Sector', hole=0.4, 
                             color_discrete_sequence=px.colors.sequential.Teal)
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col2:
            st.subheader("📊 กำไร/ขาดทุน แยกตามอุตสาหกรรม (PnL by Sector)")
            df_sector['Color'] = df_sector['PnL'].apply(lambda x: 'Profit' if x >= 0 else 'Loss')
            color_map = {'Profit': '#00c853', 'Loss': '#ff3d00'}
            
            fig_bar = px.bar(df_sector, x='Sector', y='PnL', color='Color', color_discrete_map=color_map, text_auto='.2s')
            fig_bar.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("ยังไม่มีข้อมูลหุ้นในพอร์ตโฟลิโอ")

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

# โหลด Secrets
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

# ฟังก์ชันโหลดข้อมูลจาก Webull
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
        res = conn.getcall = conn.getcall if hasattr(conn, 'getcall') else conn.getresponse()
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

# ฟังก์ชันโหลดข้อมูลจาก Dime (Google Sheet)
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

with st.spinner("⏳ กำลังรวบรวมข้อมูลจาก Webull, Dime และสแกน Sector อุตสาหกรรม..."):
    # 1. รวมพอร์ต 2 โบรกเกอร์
    all_holdings = get_webull_holdings() + get_dime_holdings()
    
    if all_holdings:
        # รวมหุ้นตัวเดียวกันที่อยู่คนละโบรกเกอร์เข้าด้วยกัน
        df_raw = pd.DataFrame(all_holdings)
        df_raw['Total_Cost'] = df_raw['Qty'] * df_raw['Cost']
        
        # 2. ค้นหาราคาและกลุ่มอุตสาหกรรมผ่าน yfinance
        unique_symbols = df_raw['Symbol'].unique().tolist()
        sectors = {}
        live_prices = {}
        
        try:
            # ใช้ yfinance ดึง info เพื่อหา Sector
            for sym in unique_symbols:
                ticker = yf.Ticker(sym)
                info = ticker.info
                sectors[sym] = info.get('sector', 'Unknown (ETF/Other)')
                
                # พยายามดึงราคาสด ถ้าไม่เจอไปดึงจาก fast_info
                current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                if not current_price:
                    current_price = ticker.fast_info.get('last_price', 0)
                live_prices[sym] = float(current_price)
        except Exception as e:
            st.warning("⚠️ มีปัญหาในการดึง Sector บางส่วนจาก Yahoo Finance")
        
        # 3. คำนวณมูลค่ารวม
        portfolio_data = []
        for index, row in df_raw.iterrows():
            sym = row['Symbol']
            qty = row['Qty']
            invested = row['Total_Cost']
            price = live_prices.get(sym, row['Cost']) # ถ้าราคาไม่มา ให้ใช้ทุนเดิม
            sector = sectors.get(sym, 'Unknown')
            
            market_val = qty * price
            pnl = market_val - invested
            
            portfolio_data.append({
                "Symbol": sym,
                "Sector": sector,
                "Broker": row['Broker'],
                "Invested": invested,
                "Market Value": market_val,
                "PnL": pnl
            })
            
        df_port = pd.DataFrame(portfolio_data)
        
        # --- สรุปตัวเลขด้านบนสุด ---
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
        
        # --- กราฟวิเคราะห์ ---
        col1, col2 = st.columns(2)
        
        # Group by Sector
        df_sector = df_port.groupby("Sector").sum(numeric_only=True).reset_index()
        
        with col1:
            st.subheader("🥧 สัดส่วนพอร์ตแยกตามอุตสาหกรรม (Sector)")
            fig_pie = px.pie(df_sector, values='Market Value', names='Sector', hole=0.4, 
                             color_discrete_sequence=px.colors.sequential.Teal)
            fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col2:
            st.subheader("📊 กำไร/ขาดทุน แย่งตามอุตสาหกรรม (PnL by Sector)")
            # สร้างสีเขียวถ้ากำไร สีแดงถ้าขาดทุน
            df_sector['Color'] = df_sector['PnL'].apply(lambda x: 'Profit' if x >= 0 else 'Loss')
            color_map = {'Profit': '#00c853', 'Loss': '#ff3d00'}
            
            fig_bar = px.bar(df_sector, x='Sector', y='PnL', color='Color', color_discrete_map=color_map, text_auto='.2s')
            fig_bar.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
            st.plotly_chart(fig_bar, use_container_width=True)
            
    else:
        st.info("ยังไม่มีข้อมูลหุ้นในพอร์ตโฟลิโอ ทั้งจาก Webull และ Dime!")

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
# --- 📊 ระบบวิเคราะห์พอร์ตด้วยกราฟแท่งแนวนอน (ดูง่ายสุดๆ ไม่บดบังกัน) ---
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        # 1. จัดการข้อมูลสำหรับสัดส่วนอุตสาหกรรม (เรียงจากมากไปน้อย)
        df_sector = df_port.groupby("Sector").sum(numeric_only=True).reset_index()
        df_sector = df_sector.sort_values(by="Market Value", ascending=True) # เรียงเพื่อให้แท่งยาวอยู่บน
        
        with col1:
            st.subheader("🪵 สัดส่วนขนาดพอร์ตแยกตามอุตสาหกรรม")
            fig_asset_bar = px.bar(
                df_sector, 
                x='Market Value', 
                y='Sector', 
                orientation='h',
                text_auto='.2s',
                title="มูลค่าถือครองปัจจุบัน ($ USD)",
                color='Sector',
                color_discrete_map={
                    "Technology": "#0052FF",           # น้ำเงินเด่น
                    "Financial Services": "#FF9900",    # ทอง/ส้ม
                    "Consumer Defensive": "#00C853",    # เขียวเหนี่ยวทรัพย์
                    "Unknown (ETF/Other)": "#7F8C8D"    # เทา
                }
            )
            fig_asset_bar.update_traces(textposition='inside', insidetextanchor='end')
            fig_asset_bar.update_layout(
                showlegend=False,
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)", 
                font=dict(color="white", size=13),
                xaxis=dict(title="มูลค่ารวม ($)", showgrid=True, gridcolor="#2a2e39"),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_asset_bar, use_container_width=True)
            
        # 2. จัดการข้อมูลสำหรับกำไร/ขาดทุน
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
                title="กำไรหรือขาดทุนที่เกิดขึ้นจริง ($ USD)",
                color='Color', 
                color_discrete_map={'Profit': '#00c853', 'Loss': '#ff3d00'}
            )
            # ตั้งให้ตัวเลขอยู่ข้างนอกแท็บถ้าติดลบ หรืออยู่ข้างในถ้าแท่งยาว
            fig_pnl_bar.update_traces(textposition='outside')
            fig_pnl_bar.update_layout(
                showlegend=False, 
                paper_bgcolor="rgba(0,0,0,0)", 
                plot_bgcolor="rgba(0,0,0,0)", 
                font=dict(color="white", size=13),
                xaxis=dict(title="กำไร/ขาดทุนสุทธิ ($)", showgrid=True, gridcolor="#2a2e39"),
                yaxis=dict(title="")
            )
            st.plotly_chart(fig_pnl_bar, use_container_width=True)

import os
import uuid
import hmac
import hashlib
import base64
import urllib.parse
import http.client
import json
import streamlit as st
import pandas as pd
from datetime import datetime, timezone  # <-- เติมบรรทัดนี้เข้าไปครับเพื่อน

# =====================================================================
# 1. ตั้งค่าหน้าตา Dashboard & ธีมสีสไตล์เทรดเดอร์
# =====================================================================
st.set_page_config(page_title="Webull Portfolio Pro 2026", layout="wide")

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
    .metric-label {
        color: #848e9c;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #ffffff;
        font-size: 28px;
        font-weight: 700;
    }
    .pnl-positive { color: #00c853 !important; }
    .pnl-negative { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Webull Live Portfolio Dashboard")
st.markdown("---")

# =====================================================================
# 2. โหลดกุญแจสำคัญจากระบบ Secrets ของ Streamlit Cloud (ปลอดภัย 100%)
# =====================================================================
webull_config = st.secrets.get("Webull", {})

APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

# =====================================================================
# 3. ฟังก์ชันดึงข้อมูลพอร์ตจาก Webull (ถอดสูตรจาก C#)
# =====================================================================
def get_webull_positions():
    path = "/openapi/assets/positions"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    signing_values = {
        "host": HOST,
        "x-app-key": APP_KEY,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "x-signature-version": "1.0",
        "x-timestamp": timestamp,
        "account_id": ACCOUNT_ID
    }

    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    string_3 = f"{path}&{string_1}"
    encoded_string = urllib.parse.quote(string_3, safe="")
    secret_key = f"{APP_SECRET}&".encode("utf-8")

    signature = base64.b64encode(
        hmac.new(secret_key, encoded_string.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-app-key": APP_KEY,
        "x-timestamp": timestamp,
        "x-signature-version": "1.0",
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "x-version": "v2",
        "x-signature": signature,
        "x-access-token": ACCESS_TOKEN
    }

    try:
        request_path = f"{path}?account_id={ACCOUNT_ID}"
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", request_path, "", headers)
        response = conn.getresponse()
        if response.status == 200:
            return json.loads(response.read().decode("utf-8"))
        else:
            return {"error_http": response.status}
    except Exception as e:
        return {"error": str(e)}

# =====================================================================
# 4. ส่วนการแสดงผลดีไซน์
# =====================================================================
st.sidebar.markdown("### 🛠️ API Control Panel")
st.sidebar.info(f"**Account ID:**\n`{ACCOUNT_ID}`")

if ACCESS_TOKEN and ACCOUNT_ID:
    positions_data = get_webull_positions()

    if positions_data and isinstance(positions_data, list):
        equity_positions = [p for p in positions_data if p.get("instrument_type") == "EQUITY"]
        
        if equity_positions:
            total_invested = 0.0
            total_market_value = 0.0
            table_rows = []
            
            for pos in equity_positions:
                symbol = pos.get("symbol", "-")
                qty = float(pos.get("quantity", 0))
                cost = float(pos.get("cost_price", 0))
                last_price = float(pos.get("last_price", 0))
                
                invested = qty * cost
                market_value = qty * last_price
                pnl = market_value - invested
                pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
                
                total_invested += invested
                total_market_value += market_value
                pnl_sign = "🟢" if pnl >= 0 else "🔴"
                
                table_rows.append({
                    "คีย์หุ้น": symbol,
                    "จำนวนหุ้น (Volume)": f"{qty:,.2f}",
                    "ต้นทุนเฉลี่ย (Avg Cost)": f"${cost:,.2f}",
                    "ราคาปัจจุบัน (Last)": f"${last_price:,.2f}",
                    "เงินลงทุนรวม": f"${invested:,.2f}",
                    "มูลค่าตลาดรวม": f"${market_value:,.2f}",
                    "กำไร/ขาดทุน": f"{pnl_sign} ${pnl:,.2f} ({pnl_pct:+.2f}%)"
                })
            
            total_pnl = total_market_value - total_invested
            total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
            pnl_class = "pnl-positive" if total_pnl >= 0 else "pnl-negative"
            pnl_prefix = "+" if total_pnl >= 0 else ""

            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f'<div class="metric-container"><div class="metric-label">💵 เงินลงทุนทั้งหมด</div><div class="metric-value">${total_invested:,.2f}</div></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div class="metric-container"><div class="metric-label">📈 มูลค่าตลาดปัจจุบัน</div><div class="metric-value">${total_market_value:,.2f}</div></div>', unsafe_allow_html=True)
            with col3:
                st.markdown(f'<div class="metric-container"><div class="metric-label">📊 กำไร / ขาดทุนสุทธิ</div><div class="metric-value {pnl_class}">{pnl_prefix}${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.subheader("📋 รายการสินทรัพย์ที่ถือครอง")
            df = pd.DataFrame(table_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("ไม่พบสินทรัพย์ประเภทหุ้นในพอร์ตโฟลิโอนี้")
    else:
        st.error("🚨 ไม่สามารถดึงข้อมูลพอร์ตได้ กรุณาตรวจสอบค่าใน Advanced Settings (Secrets)")

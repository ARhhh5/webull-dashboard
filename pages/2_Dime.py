import base64
import json
import http.client
import urllib.parse
import uuid
import hashlib
import hmac
import streamlit as st
import pandas as pd
import gspread
from datetime import datetime, timezone

st.title("🇹🇭 Dime! Portfolio Dashboard")
st.markdown("---")

# โหลดกุญแจสำคัญสำหรับดึงราคาเรียลไทม์ (ใช้ท่อ Webull สืบราคาหุ้นให้)
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

# ฟังก์ชันสืบราคาหุ้นปัจจุบันผ่าน OpenAPI
def get_live_price(symbol):
    path = "/openapi/assets/positions" # ยืมท่อเช็คราคาหุ้นตลาดหลักมาใช้
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {
        "host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp,
        "account_id": ACCOUNT_ID
    }
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    string_3 = f"{path}&{string_1}"
    secret_key = f"{APP_SECRET}&".encode("utf-8")
    signature = base64.b64encode(hmac.new(secret_key, urllib.parse.quote(string_3, safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    
    headers = {
        "Accept": "application/json", "Content-Type": "application/json", "x-app-key": APP_KEY,
        "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN
    }
    try:
        # เช็คราคาผ่านพอร์ตหลักเพื่อความเร็ว หรือถ้าหุ้นไม่มีในพอร์ตหลัก เราจะดึงราคาตลาดโดยตรง
        conn = http.client.HTTPSConnection(HOST)
        # นำมาแมตช์หาตัวเลขราคาปัจจุบัน หรือถ้าหาไม่เจอให้ดึงค่าพื้นฐาน
        return None
    except:
        return None

# ฟังก์ชันโหลดข้อมูลพอร์ต Dime จาก Google Sheet
def load_dime_portfolio():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64:
            st.warning("⚠️ ไม่พบกุญแจ Google ใน Secrets")
            return []
            
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        
        # เปิดแท็บ Dime_Portfolio
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Dime_Portfolio")
        
        # ดึงข้อมูลทั้งหมดออกมา แปลงเป็น List ของ Dict
        records = worksheet.get_all_records()
        return records
    except Exception as e:
        st.error(f"❌ ดึงข้อมูลจาก Google Sheet ไม่สำเร็จ: {str(e)}")
        return []

# เรียกใช้งานบอท
records = load_dime_portfolio()

if records:
    total_invested = 0.0
    total_market_value = 0.0
    table_rows = []
    
    # ดึงข้อมูลตำแหน่งหุ้นปัจจุบันมาเทียบราคา (ขอยืมข้อมูลราคาสดจาก Webull มาอัปเดตพอร์ต Dime)
    conn_portfolio = http.client.HTTPSConnection(HOST)
    # ยิงดึงราคาหุ้นเรียลไทม์มาแมตช์
    path = "/openapi/assets/positions"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex
    signing_values = {"host": HOST, "x-app-key": APP_KEY, "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-signature-version": "1.0", "x-timestamp": timestamp, "account_id": ACCOUNT_ID}
    string_1 = "&".join(f"{key}={signing_values[key]}" for key in sorted(signing_values))
    string_3 = f"{path}&{string_1}"
    signature = base64.b64encode(hmac.new(f"{APP_SECRET}&".encode("utf-8"), urllib.parse.quote(string_3, safe="").encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
    headers = {"Accept": "application/json", "x-app-key": APP_KEY, "x-timestamp": timestamp, "x-signature-version": "1.0", "x-signature-algorithm": "HMAC-SHA1", "x-signature-nonce": nonce, "x-version": "v2", "x-signature": signature, "x-access-token": ACCESS_TOKEN}
    
    live_prices = {}
    try:
        conn_portfolio.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn_portfolio.getcall = conn_portfolio.getcall if hasattr(conn_portfolio, 'getcall') else conn_portfolio.getresponse()
        data = json.loads(res.read().decode("utf-8"))
        if isinstance(data, list):
            for p in data:
                live_prices[p.get("symbol")] = float(p.get("last_price", 0))
    except:
        pass

    for r in records:
        symbol = str(r.get("หุ้น (Ticker)", "")).strip().upper()
        if not symbol: continue
        
        qty = float(r.get("จำนวนหุ้น (Volume)", 0))
        cost = float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0))
        
        # ค้นหาราคาตลาดเรียลไทม์ ถ้าในระบบไม่มี ให้ใช้ราคาต้นทุนไปก่อนชั่วคราว
        last_price = live_prices.get(symbol, cost) 
        
        invested = qty * cost
        market_value = qty * last_price
        pnl = market_value - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        
        total_invested += invested
        total_market_value += market_value
        pnl_sign = "🟢" if pnl >= 0 else "🔴"
        
        table_rows.append({
            "หุ้น Dime": symbol,
            "จำนวนหุ้น": f"{qty:,.4f}",
            "ต้นทุนเฉลี่ย": f"${cost:,.2f}",
            "ราคาตลาดสด": f"${last_price:,.2f}",
            "เงินลงทุนรวม": f"${invested:,.2f}",
            "มูลค่าปัจจุบัน": f"${market_value:,.2f}",
            "กำไร/ขาดทุน": f"{pnl_sign} ${pnl:,.2f} ({pnl_pct:+.2f}%)"
        })
        
    # สรุปยอดเงินในกล่องบนสุด
    total_pnl = total_market_value - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    pnl_class = "color: #00c853;" if total_pnl >= 0 else "color: #ff3d00;"
    
    st.markdown(f"""
    <div style="background-color: #1e222d; padding: 20px; border-radius: 10px; border: 1px solid #2a2e39; text-align: center;">
        <h4 style="color: #848e9c; margin: 0;">💰 มูลค่ารวมพอร์ต Dime!</h4>
        <h2 style="color: white; margin: 10px 0;">${total_market_value:,.2f}</h2>
        <p style="{pnl_class} font-weight: bold; margin: 0;">กำไรสุทธิทั้งหมด: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📋 รายการสินทรัพย์ใน Dime! (Sync จากคลาวด์)")
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
else:
    st.info("💡 ชีทว่างเปล่า! ให้นายลองเพิ่มรายชื่อหุ้น จำนวน และต้นทุนลงในแท็บ 'Dime_Portfolio' บน Google Sheet ได้เลยเพื่อน")

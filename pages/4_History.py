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
import json
import base64
import gspread

st.set_page_config(page_title="Trade History & Closed Positions", layout="wide")

st.markdown("""
    <style>
    .metric-container {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
    }
    .metric-label { color: #848e9c; font-size: 16px; font-weight: 500; margin-bottom: 8px; }
    .metric-value { color: #ffffff; font-size: 32px; font-weight: 700; }
    .pnl-positive { color: #00c853 !important; }
    .pnl-negative { color: #ff3d00 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📜 ประวัติการเทรด & หุ้นที่ขายปิดจบแล้ว")
st.markdown("---")

# ==========================================
# ฟังก์ชันสำหรับ Sync ข้อมูลจาก Webull ลง Google Sheet
# ==========================================
def sync_webull_to_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64:
            return False, "❌ ไม่พบกุญแจ Google ใน Secrets"
            
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
    except Exception as e:
        return False, f"❌ ไม่สามารถเชื่อมต่อ Google Sheet ได้: {str(e)}"

    existing_records = worksheet.get_all_records()
    df_existing = pd.DataFrame(existing_records)
    
    existing_ids = set()
    existing_combos = set()
    
    if not df_existing.empty:
        for _, row in df_existing.iterrows():
            oid = str(row.get("Order ID", "")).strip()
            if oid:
                existing_ids.add(oid)
            
            combo = f"{str(row.get('Time',''))}_{str(row.get('Symbol',''))}_{str(row.get('Side',''))}_{str(row.get('Qty',''))}_{str(row.get('Price',''))}"
            existing_combos.add(combo)

    webull_config = st.secrets.get("Webull", {})
    APP_KEY = webull_config.get("AppKey", "").strip() or webull_config.get("app_key", "").strip()
    APP_SECRET = webull_config.get("AppSecret", "").strip() or webull_config.get("app_secret", "").strip()
    ACCOUNT_ID = webull_config.get("AccountId", "").strip() or webull_config.get("account_id", "").strip()
    HOST = "api.webull.co.th"

    if not APP_KEY or not APP_SECRET or not ACCOUNT_ID:
        return False, "❌ ไม่พบข้อมูล Webull API Key ใน Secrets"

    try:
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
        signature = base64.b64encode(
            hmac.new(
                f"{APP_SECRET}&".encode("utf-8"),
                urllib.parse.quote(f"{path}&{string_1}", safe="").encode("utf-8"),
                hashlib.sha1
            ).digest()
        ).decode("utf-8")

        headers = {
            "Accept": "application/json",
            "x-app-key": APP_KEY,
            "x-timestamp": timestamp,
            "x-signature-version": "1.0",
            "x-signature-algorithm": "HMAC-SHA1",
            "x-signature-nonce": nonce,
            "x-version": "v2",
            "x-signature": signature,
            "x-access-token": webull_config.get("AccessToken", "").strip()
        }

        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", f"{path}?account_id={ACCOUNT_ID}", "", headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        orders = json.loads(data.decode("utf-8"))
        if not isinstance(orders, list):
            orders = []

    except Exception as e:
        return False, f"⚠️ ยิง Webull API ไม่สำเร็จ: {str(e)}"

    new_rows = []
    for order in orders:
        order_id = str(order.get("order_id", order.get("orderId", uuid.uuid4().hex[:8])))
        symbol = str(order.get("symbol", "")).upper()
        action = str(order.get("action", order.get("side", ""))).upper()
        side_formatted = "BUY" if "BUY" in action else ("SELL" if "SELL" in action else action)
        
        qty = float(order.get("quantity", order.get("filledQuantity", 0)))
        price = float(order.get("cost_price", order.get("avgFilledPrice", 0)))
        order_time = order.get("create_time", datetime.now().strftime("%Y-%m-%d"))

        full_order_id = f"{order_id}_{symbol}_{side_formatted}"
        combo_check = f"{order_time}_{symbol}_{side_formatted}_{qty}_{price}"

        if full_order_id not in existing_ids and combo_check not in existing_combos:
            if qty > 0 and price > 0:
                new_rows.append([full_order_id, order_time, symbol, side_formatted, qty, price])

    if new_rows:
        worksheet.append_rows(new_rows)
        return True, f"✅ Auto Sync สำเร็จ! เพิ่มรายการใหม่ลง Google Sheet ทั้งหมด {len(new_rows)} รายการ"
    else:
        return True, "ℹ️ ข้อมูลล่าสุดตรงกันแล้ว ไม่มีรายการใหม่ต้องเพิ่ม"

# ==========================================
# 🎯 ส่วนปุ่ม Auto Sync ด้านบนสุดของหน้า History
# ==========================================
with st.expander("🔄 แผงควบคุม Auto Sync ข้อมูลจาก Webull API", expanded=False):
    col_sync1, col_sync2 = st.columns([3, 1])
    with col_sync1:
        st.write("กดปุ่มเพื่อดึงออเดอร์ล่าสุดจาก Webull บันทึกเติมลง Google Sheet อัตโนมัติ (เช็ครายการซ้ำให้เรียบร้อย)")
    with col_sync2:
        if st.button("🚀 กด Sync ตอนนี้", type="primary", use_container_width=True):
            with st.spinner("⏳ กำลัง Sync ออเดอร์..."):
                success, msg = sync_webull_to_gsheet()
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# ดึงข้อมูลจาก Google Sheet
# ==========================================
@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception as e:
        return None

def load_all_history_sheets():
    gc = init_gsheet()
    if not gc:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), set()
    
    df_webull_orders = pd.DataFrame()
    df_dime_closed = pd.DataFrame()
    df_dime_us_port = pd.DataFrame()
    df_dime_th_port = pd.DataFrame()
    active_symbols = set()
    
    try:
        sh = gc.open("หุ้นของเรา")
        
        try:
            ws1 = sh.worksheet("Webull_Order_History")
            df_webull_orders = pd.DataFrame(ws1.get_all_records())
        except: pass
        
        try:
            ws2 = sh.worksheet("Dime_Closed_Orders")
            df_dime_closed = pd.DataFrame(ws2.get_all_records())
        except: pass
        
        try:
            ws3 = sh.

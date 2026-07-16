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
from datetime import datetime, timezone

st.set_page_config(page_title="Order History", layout="wide")
st.title("📜 ประวัติการซื้อขายย้อนหลัง (Order History)")
st.markdown("---")

# โหลดกุญแจสำคัญจากระบบ Secrets ร่วมกัน
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

def get_webull_orders():
    path = "/openapi/trade/order/list"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    signing_values = {
        "host": HOST,
        "x-app-key": APP_KEY,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "x-signature-version": "1.0",
        "x-timestamp": timestamp,
        "account_id": ACCOUNT_ID,
        "status": "FILLED"
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
        request_path = f"{path}?account_id={ACCOUNT_ID}&status=FILLED"
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", request_path, "", headers)
        response = conn.getresponse()
        if response.status == 200:
            return json.loads(response.read().decode("utf-8"))
        
        # ลองสลับไปใช้ v2 order list เผื่อระบบเปลี่ยนโครงสร้าง
        path_v2 = "/openapi/trade/v2/order/list"
        string_3_v2 = f"{path_v2}&{string_1}"
        encoded_string_v2 = urllib.parse.quote(string_3_v2, safe="")
        signature_v2 = base64.b64encode(hmac.new(secret_key, encoded_string_v2.encode("utf-8"), hashlib.sha1).digest()).decode("utf-8")
        headers["x-signature"] = signature_v2
        conn.request("GET", f"{path_v2}?account_id={ACCOUNT_ID}&status=FILLED", "", headers)
        response_v2 = conn.getresponse()
        if response_v2.status == 200:
            return json.loads(response_v2.read().decode("utf-8"))
        return None
    except Exception:
        return None

if ACCESS_TOKEN and ACCOUNT_ID:
    orders_data = get_webull_orders()
    orders_list = []
    
    if isinstance(orders_data, list):
        orders_list = orders_data
    elif isinstance(orders_data, dict):
        orders_list = orders_data.get("orders") or orders_data.get("data") or []
        
    if orders_list:
        order_rows = []
        for order in orders_list:
            symbol = order.get("symbol", "-")
            side = order.get("action") or order.get("side", "-")
            filled_qty = float(order.get("filled_quantity") or order.get("quantity", 0))
            filled_price = float(order.get("filled_price") or order.get("price", 0))
            total_amount = filled_qty * filled_price
            time_str = order.get("filled_time") or order.get("placed_time") or "-"
            
            side_emoji = "🟢 BUY" if "BUY" in side.upper() else "🔴 SELL"
            
            order_rows.append({
                "เวลาที่สำเร็จ": time_str,
                "หุ้น": symbol,
                "ประเภทคำสั่ง": side_emoji,
                "จำนวนหุ้น": f"{filled_qty:,.2f}",
                "ราคาต่อหุ้น": f"${filled_price:,.2f}",
                "มูลค่ารวม (USD)": f"${total_amount:,.2f}"
            })
            
        st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)
    else:
        st.info("ไม่พบประวัติคำสั่งซื้อขายย้อนหลัง หรือ API ดึงข้อมูลส่วนนี้ของเซิร์ฟเวอร์ไทยต่างออกไป")
        if orders_data:
            st.json(orders_data)

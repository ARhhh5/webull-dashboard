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
import gspread
from datetime import datetime, timezone

st.title("📜 ประวัติการซื้อขายย้อนหลัง (Order History)")
st.markdown("---")
st.subheader("🕵️‍♂️ รายการคำสั่งซื้อขายในรอบ 7 วันล่าสุด พร้อมระบบ Auto-Sync Google Sheet")

# โหลดกุญแจสำคัญจากระบบ Secrets
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

# ฟังก์ชันเชื่อมต่อและบันทึกข้อมูลลง Google Sheet
def sync_to_google_sheet(order_rows):
    try:
        # ดึงกุญแจ Base64 ป้องกัน TOML พัง
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        
        if not cred_base64:
            st.warning("⚠️ ยังไม่ได้ใส่กุญแจ credentials_base64 ในระบบ Secrets")
            return
            
        # ถอดรหัส Base64 กลับมาเป็น JSON ดิบ
        cred_json_str = base64.b64decode(cred_base64).decode("utf-8")
        cred_dict = json.loads(cred_json_str)
        
        # ล็อกอินเข้า Google Sheet
        gc = gspread.service_account_from_dict(cred_dict)
        
        # เปิดชีทผ่านชื่อไฟล์ที่นายตั้งไว้
        sh = gc.open("Webull_Order_History")
        worksheet = sh.get_worksheet(0)
        
        # ดึงข้อมูล Order ID ทั้งหมดที่มีอยู่แล้วในชีทมาเช็คซ้ำ
        existing_ids = worksheet.col_values(1)
        
        new_rows_count = 0
        for row in order_rows:
            if str(row["Order ID"]) not in existing_ids:
                worksheet.append_row([
                    str(row["Order ID"]),
                    row["เวลาที่สำเร็จ"],
                    row["หุ้น"],
                    row["ประเภทคำสั่ง"],
                    row["จำนวนหุ้น"],
                    row["ราคาต่อหุ้น"]
                ])
                new_rows_count += 1
                
        if new_rows_count > 0:
            st.success(f"🚀 บันทึกออเดอร์ใหม่เข้า Google Sheet เรียบร้อยแล้ว {new_rows_count} รายการ!")
        else:
            st.info("🔄 ข้อมูลใน Google Sheet อัปเดตล่าสุดแล้ว ไม่มีรายการซ้ำซ้อน")
            
    except Exception as e:
        st.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheet ได้: {str(e)}")

def get_webull_orders():
    path = "/openapi/trade/order/history"
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
        response = conn.getcall = conn.getresponse()
        res_body = response.read().decode("utf-8")
        if response.status == 200:
            return json.loads(res_body)
        else:
            return {"error_status": response.status, "msg": res_body}
    except Exception as e:
        return {"error": str(e)}

if ACCESS_TOKEN and ACCOUNT_ID:
    with st.spinner("⏳ กำลังดึงประวัติออเดอร์จาก Webull..."):
        orders_data = get_webull_orders()
    
    combo_list = []
    if isinstance(orders_data, list):
        combo_list = orders_data
    elif isinstance(orders_data, dict):
        combo_list = orders_data.get("orders") or orders_data.get("data") or []
        
    if combo_list:
        raw_rows = []
        display_rows = []
        
        for combo in combo_list:
            inner_orders = combo.get("orders", []) if isinstance(combo, dict) else []
            if not inner_orders and isinstance(combo, dict):
                inner_orders = [combo]
                
            for order in inner_orders:
                symbol = order.get("symbol") or order.get("ticker") or "-"
                action = str(order.get("side") or order.get("action") or "").upper()
                side_emoji = "🟢 BUY" if "BUY" in action else "🔴 SELL"
                
                qty = float(order.get("filled_quantity") or order.get("quantity") or 0)
                price = float(order.get("filled_price") or order.get("price") or 0)
                total_amount = qty * price
                
                time_str = order.get("filled_time") or order.get("placed_time") or "-"
                
                order_id = combo.get("client_order_id") or order.get("order_id") or time_str
                
                raw_rows.append({
                    "Order ID": order_id,
                    "เวลาที่สำเร็จ": time_str,
                    "หุ้น": symbol,
                    "ประเภทคำสั่ง": side_emoji,
                    "จำนวนหุ้น": qty,
                    "ราคาต่อหุ้น": price
                })
                
                display_rows.append({
                    "อ้างอิงออเดอร์": order_id,
                    "เวลาที่สำเร็จ": time_str,
                    "หุ้น": symbol,
                    "ประเภทคำสั่ง": side_emoji,
                    "จำนวนหุ้น": f"{qty:,.2f}",
                    "ราคาต่อหุ้น": f"${price:,.2f}",
                    "มูลค่ารวม (USD)": f"${total_amount:,.2f}"
                })
        
        if display_rows:
            st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
            sync_to_google_sheet(raw_rows)
        else:
            st.info("ℹ️ ไม่พบคำสั่งซื้อขายย่อย")
    else:
        st.info("ℹ️ ไม่พบประวัติคำสั่งซื้อขาย")

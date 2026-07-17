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

st.title("📜 ประวัติการซื้อขายย้อนหลัง (Order History)")
st.markdown("---")
st.subheader("🕵️‍♂️ รายการคำสั่งซื้อขายในรอบ 7 วันล่าสุด (Filled Orders)")

# โหลดกุญแจสำคัญจากระบบ Secrets ร่วมกัน
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

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
        response = conn.getcall = conn.getcall if hasattr(conn, 'getcall') else conn.getcall = conn.getresponse()
        res_body = response.read().decode("utf-8")
        if response.status == 200:
            return json.loads(res_body)
        else:
            return {"error_status": response.status, "msg": res_body}
    except Exception as e:
        return {"error": str(e)}

if ACCESS_TOKEN and ACCOUNT_ID:
    with st.spinner("⏳ กำลังแกะกล่องประวัติออเดอร์ย้อนหลัง..."):
        orders_data = get_webull_orders()
    
    # ดึงลิสต์ชั้นนอกสุดออกมาก่อน
    combo_list = []
    if isinstance(orders_data, list):
        combo_list = orders_data
    elif isinstance(orders_data, dict):
        combo_list = orders_data.get("orders") or orders_data.get("data") or []
        
    if combo_list:
        order_rows = []
        
        # วิ่งลูปแกะกล่องชั้นนอกสุด (Combo Order / Normal Order)
        for combo in combo_list:
            # ดึงคำสั่งย่อยชั้นในสุดที่ Webull ซ่อนไว้
            inner_orders = combo.get("orders", []) if isinstance(combo, dict) else []
            
            # หากโครงสร้างเรียบไม่มี orders ซ่อน ให้ถอยมารับค่า combo ตัวมันเอง
            if not inner_orders and isinstance(combo, dict):
                inner_orders = [combo]
                
            for order in inner_orders:
                symbol = order.get("symbol") or order.get("ticker") or "-"
                
                # เช็คฝั่ง BUY / SELL
                action = str(order.get("side") or order.get("action") or "").upper()
                side_emoji = "🟢 BUY" if "BUY" in action else "🔴 SELL"
                
                # ดักจับจำนวนและราคาสรุป
                qty = float(order.get("filled_quantity") or order.get("quantity") or 0)
                price = float(order.get("filled_price") or order.get("price") or 0)
                total_amount = qty * price
                
                time_str = order.get("filled_time") or order.get("placed_time") or "-"
                
                order_rows.append({
                    "เวลาที่สำเร็จ": time_str,
                    "หุ้น": symbol,
                    "ประเภทคำสั่ง": side_emoji,
                    "จำนวนหุ้น": f"{qty:,.2f}",
                    "ราคาต่อหุ้น": f"${price:,.2f}",
                    "มูลค่ารวม (USD)": f"${total_amount:,.2f}"
                })
        
        if order_rows:
            st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)
        else:
            st.info("ℹ️ โครงสร้างซ้อนกันแต่ไม่พบคำสั่งย่อย")
    else:
        st.info("ℹ️ ไม่พบประวัติคำสั่งซื้อขาย")
        
    st.markdown("---")
    with st.expander("🔍 ดูกล่องข้อความดิบ (Raw JSON) เพื่อเช็คชื่อคีย์"):
        st.json(orders_data)

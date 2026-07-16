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
st.subheader("🕵️‍♂️ รายการซื้อมาขายไป (Filled Orders)")

# โหลดกุญแจสำคัญจากระบบ Secrets ร่วมกัน
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

def try_webull_orders_api(path, extra_params={}):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    # ประกอบพารามิเตอร์พื้นฐาน + พารามิเตอร์พิเศษ
    signing_values = {
        "host": HOST,
        "x-app-key": APP_KEY,
        "x-signature-algorithm": "HMAC-SHA1",
        "x-signature-nonce": nonce,
        "x-signature-version": "1.0",
        "x-timestamp": timestamp,
        "account_id": ACCOUNT_ID
    }
    for k, v in extra_params.items():
        signing_values[k] = str(v)

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
        # แปลงพารามิเตอร์สำหรับ Query String
        query_dict = {"account_id": ACCOUNT_ID}
        for k, v in extra_params.items():
            query_dict[k] = str(v)
            
        queryString = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in query_dict.items())
        request_path = f"{path}?{queryString}"
        
        conn = http.client.HTTPSConnection(HOST)
        conn.request("GET", request_path, "", headers)
        response = conn.getresponse()
        res_body = response.read().decode("utf-8")
        
        return {
            "status": response.status,
            "body": json.loads(res_body) if response.status == 200 else res_body
        }
    except Exception as e:
        return {"status": "Error", "body": str(e)}

if ACCESS_TOKEN and ACCOUNT_ID:
    
    # ยิงทดสอบ 3 รูปแบบเพื่อเช็คว่าเซิร์ฟเวอร์ไทยเปิดรับท่อไหน
    st.markdown("### 🔍 ผลการทดสอบดึงข้อมูลผ่าน Endpoint ต่างๆ")
    
    # แบบที่ 1: ยิงผ่านออเดอร์ลิสต์มาตรฐานสากล
    with st.spinner("กำลังทดสอบ Endpoint 1..."):
        res1 = try_webull_orders_api("/openapi/trade/order/list", {"status": "FILLED"})
    
    # แบบที่ 2: ยิงผ่านออเดอร์ลิสต์เวอร์ชัน 2
    with st.spinner("กำลังทดสอบ Endpoint 2..."):
        res2 = try_webull_orders_api("/openapi/trade/v2/order/list", {"status": "FILLED"})
        
    # แบบที่ 3: ยิงผ่านประวัติธุรกรรมโดยตรง (บางประเทศใช้ที่อยู่ asset/v2/account/transaction)
    with st.spinner("กำลังทดสอบ Endpoint 3..."):
        res3 = try_webull_orders_api("/openapi/trade/order/list") # ดึงรวมทุกสถานะ

    # กางผลลัพธ์ดิบให้เห็นเพื่อนำไปวิเคราะห์ฟิลด์ที่ถูกต้อง
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**Endpoint 1 (/trade/order/list):**")
        st.write(f"Status Code: {res1['status']}")
        st.json(res1['body'])
        
    with col2:
        st.write("**Endpoint 2 (/trade/v2/order/list):**")
        st.write(f"Status Code: {res2['status']}")
        st.json(res2['body'])
        
    with col3:
        st.write("**Endpoint 3 (ดึงออเดอร์ทั้งหมด):**")
        st.write(f"Status Code: {res3['status']}")
        st.json(res3['body'])

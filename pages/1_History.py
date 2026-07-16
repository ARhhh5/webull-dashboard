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

st.title("📜 ประวัติทรานแซกชันและการซื้อขาย (Transactions Log)")
st.markdown("---")
st.subheader("🕵️‍♂️ แกะรอยสมุดบัญชีรายวัน (Account Journal)")

# โหลดกุญแจสำคัญจากระบบ Secrets ร่วมกัน
webull_config = st.secrets.get("Webull", {})
APP_KEY = webull_config.get("AppKey", "").strip()
APP_SECRET = webull_config.get("AppSecret", "").strip()
ACCESS_TOKEN = webull_config.get("AccessToken", "").strip()
ACCOUNT_ID = webull_config.get("AccountId", "").strip()
HOST = "api.webull.co.th"

def try_webull_journal_api(path):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nonce = uuid.uuid4().hex

    # ประกอบพารามิเตอร์พื้นฐานส่งไปให้เซิร์ฟเวอร์
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
        res_body = response.read().decode("utf-8")
        
        return {
            "status": response.status,
            "body": json.loads(res_body) if response.status == 200 else res_body
        }
    except Exception as e:
        return {"status": "Error", "body": str(e)}

if ACCESS_TOKEN and ACCOUNT_ID:
    
    with st.spinner("กำลังเจาะสมุดบัญชีรายวันจาก Webull..."):
        # ลองยิงเวอร์ชัน 1
        res_v1 = try_webull_journal_api("/openapi/assets/account/journal")
        # ลองยิงเวอร์ชัน 2
        res_v2 = try_webull_journal_api("/openapi/v2/assets/account/journal")

    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**สมุดบัญชีรายวัน v1 (`/openapi/assets/account/journal`):**")
        st.write(f"HTTP Status: {res_v1['status']}")
        if res_v1['status'] == 200 and isinstance(res_v1['body'], list):
            # ถ้าเป็นตารางข้อมูล ให้แปลงเป็น DataFrame ให้ดูง่ายๆ เลย
            st.dataframe(pd.DataFrame(res_v1['body']), use_container_width=True)
        else:
            st.json(res_v1['body'])
            
    with col2:
        st.write("**สมุดบัญชีรายวัน v2 (`/openapi/v2/assets/account/journal`):**")
        st.write(f"HTTP Status: {res_v2['status']}")
        if res_v2['status'] == 200 and isinstance(res_v2['body'], list):
            st.dataframe(pd.DataFrame(res_v2['body']), use_container_width=True)
        else:
            st.json(res_v2['body'])

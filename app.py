import pandas as pd
import json
import base64
import gspread
import streamlit as st

@st.cache_data(ttl=300) # โหลดเก็บไว้ 5 นาที จะได้ไม่หน่วงแอป
def get_webull_realized_pnl():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return 0.0
        
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        
        # ดึงประวัติ Webull จาก Sheet
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
        records = worksheet.get_all_records()
        
        df = pd.DataFrame(records)
        if df.empty: return 0.0
        
        # กรองเฉพาะ BUY/SELL และแปลงค่าให้พร้อมคำนวณ
        df = df[df['Side'].str.upper().isin(['BUY', 'SELL'])]
        df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
        # เรียงจากอดีตมาปัจจุบัน (ถ้าคอลัมน์เวลาของนายชื่อ Time หรือ Date ให้เปลี่ยนตรงนี้นะ)
        if 'Time' in df.columns:
            df = df.sort_values(by="Time", ascending=True)
            
        total_realized_pnl = 0.0
        
        # จับคู่ FIFO ทีละตัว
        for symbol, group in df.groupby("Symbol"):
            buy_queue = []
            for _, row in group.iterrows():
                side = row["Side"].upper()
                qty = row["Qty"]
                price = row["Price"]
                
                if side == "BUY":
                    buy_queue.append({"qty": qty, "price": price})
                elif side == "SELL":
                    sell_qty = qty
                    while sell_qty > 0 and buy_queue:
                        first_buy = buy_queue[0]
                        matched_qty = min(sell_qty, first_buy["qty"])
                        buy_price = first_buy["price"]
                        
                        # คำนวณกำไรไม้ที่ปิด
                        total_realized_pnl += matched_qty * (price - buy_price)
                        
                        sell_qty -= matched_qty
                        first_buy["qty"] -= matched_qty
                        
                        if first_buy["qty"] <= 0:
                            buy_queue.pop(0)
                            
        return total_realized_pnl
        
    except Exception as e:
        st.error(f"พังจ้า คำนวณ Realized PnL ไม่ได้: {e}")
        return 0.0

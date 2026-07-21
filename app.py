import pandas as pd
import json
import base64
import gspread

# ---------------------------------------------------------
# ฟังก์ชันพิเศษ: ดึงกำไรที่ปิดไปแล้ว (Realized PnL) จากประวัติ
# ---------------------------------------------------------
@st.cache_data(ttl=300) # Cache ไว้ 5 นาทีจะได้ไม่โหลดช้า
def get_total_realized_pnl():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return 0.0
        
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
        records = worksheet.get_all_records()
        
        df_orders = pd.DataFrame(records)
        if df_orders.empty: return 0.0
        
        # กรองเฉพาะ Buy/Sell
        df_orders = df_orders[df_orders['Side'].isin(['BUY', 'SELL'])]
        df_orders['Qty'] = pd.to_numeric(df_orders['Qty'], errors='coerce').fillna(0)
        df_orders['Price'] = pd.to_numeric(df_orders['Price'], errors='coerce').fillna(0)
        df_orders = df_orders.sort_values(by="Time", ascending=True)
        
        total_pnl = 0.0
        # จำลองระบบ FIFO แบบรวบรัด
        for symbol, group in df_orders.groupby("Symbol"):
            buy_queue = []
            for _, row in group.iterrows():
                side = row["Side"].upper()
                qty = row["Qty"]
                price = row["Price"]
                
                if side == "BUY":
                    buy_queue.append({"qty": qty, "price": price})
                elif side == "SELL":
                    sell_qty_left = qty
                    while sell_qty_left > 0 and buy_queue:
                        first_buy = buy_queue[0]
                        matched_qty = min(sell_qty_left, first_buy["qty"])
                        buy_price = first_buy["price"]
                        
                        total_pnl += matched_qty * (price - buy_price)
                        
                        sell_qty_left -= matched_qty
                        first_buy["qty"] -= matched_qty
                        
                        if first_buy["qty"] <= 0:
                            buy_queue.pop(0)
                            
        return total_pnl
    except Exception as e:
        st.warning(f"ไม่สามารถคำนวณ Realized PnL ได้: {e}")
        return 0.0

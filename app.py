import streamlit as st
import pandas as pd
import json
import base64
import gspread

# ==========================================
# ตั้งค่าหน้าเพจ Dashboard
# ==========================================
st.set_page_config(page_title="Master Portfolio Dashboard", layout="wide")

# ==========================================
# 1. ฟังก์ชันเชื่อมต่อ Google Sheets (ใช้สำหรับ History และ Dime)
# ==========================================
@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets["Google"]
        cred_base64 = google_secrets["credentials_base64"]
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception as e:
        st.error(f"เชื่อมต่อ Google Sheets ล้มเหลว: {e}")
        return None

# ==========================================
# 2. ฟังก์ชันคำนวณ Realized PnL (ดึงอดีตจาก Sheet Webull_Order_History)
# ==========================================
@st.cache_data(ttl=300)
def get_webull_realized_pnl():
    gc = init_gsheet()
    if not gc: return 0.0
    
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Webull_Order_History")
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        
        if df.empty: return 0.0
        
        # กรองเฉพาะ Buy/Sell และทำข้อมูลให้พร้อมคำนวณ
        df = df[df['Side'].str.upper().isin(['BUY', 'SELL'])]
        df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
        
        # เรียงตามเวลา (ถ้าชื่อคอลัมน์เวลาของนายคือ Date ให้เปลี่ยนตรงคำว่า Time)
        if 'Time' in df.columns:
            df = df.sort_values(by="Time", ascending=True)
            
        total_realized_pnl = 0.0
        
        # คำนวณ FIFO แบบ 1-Row-per-Ticker
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
                        
                        total_realized_pnl += matched_qty * (price - buy_price)
                        
                        sell_qty -= matched_qty
                        first_buy["qty"] -= matched_qty
                        
                        if first_buy["qty"] <= 0:
                            buy_queue.pop(0)
                            
        return total_realized_pnl
    except Exception as e:
        st.error(f"พังจ้า คำนวณ Realized PnL ไม่ได้: {e}")
        return 0.0

# ==========================================
# 3. ฟังก์ชันดึงข้อมูลพอร์ตปัจจุบัน (Webull OpenAPI)
# ==========================================
@st.cache_data(ttl=60)
def get_webull_positions():
    # ---------------------------------------------------------
    # [!] ใส่โค้ดเชื่อมต่อ Webull OpenAPI ของนายตรงนี้ครับ [!]
    # ---------------------------------------------------------
    # โค้ดด้านล่างนี้คือ Mockup เพื่อให้แอปไม่พังเวลายังไม่ได้ใส่ API จริง
    # ถ้านายมี DataFrame ตัวเดิม ให้เอามาแทนที่ df ด้านล่างได้เลย
    
    data = {
        "Symbol": ["ULTY", "MSTY"],
        "Qty": [115, 10],
        "AvgPrice": [57.72, 109.12],
        "CurrentPrice": [28.90, 12.23],
    }
    df = pd.DataFrame(data)
    df["Unrealized_PnL"] = (df["CurrentPrice"] - df["AvgPrice"]) * df["Qty"]
    
    # คำนวณผลรวมพอร์ตปัจจุบันที่ติดลบ/บวกอยู่
    total_unrealized_pnl = df["Unrealized_PnL"].sum() 
    
    return df, total_unrealized_pnl

# ==========================================
# 4. ฟังก์ชันดึงข้อมูลพอร์ต Dime จาก Sheet
# ==========================================
@st.cache_data(ttl=300)
def get_dime_portfolio():
    gc = init_gsheet()
    if not gc: return pd.DataFrame()
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Dime_Portfolio")
        records = worksheet.get_all_records()
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()

# ==========================================
# 5. การแสดงผล UI (Master Dashboard)
# ==========================================
def main():
    st.title("📊 Master Portfolio Dashboard")
    
    # --- ส่วนที่ 1: สรุปความจริงของ Webull ---
    st.header("🦅 Webull Portfolio (Real-time True Net PnL)")
    
    # ดึงค่ามาคำนวณ
    df_webull, webull_unrealized_pnl = get_webull_positions()
    webull_realized_pnl = get_webull_realized_pnl()
    
    # ฟิวชั่นความจริง!
    true_net_pnl = webull_unrealized_pnl + webull_realized_pnl
    
    # กำหนดสี
    color_net = "green" if true_net_pnl >= 0 else "red"
    color_unrealized = "green" if webull_unrealized_pnl >= 0 else "red"
    color_realized = "green" if webull_realized_pnl >= 0 else "red"
    
    # โชว์ Dashboard 3 ช่อง
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**💰 กำไรอดีต (Realized)**")
        st.markdown(f"<h3 style='color: {color_realized};'>${webull_realized_pnl:,.2f}</h3>", unsafe_allow_html=True)
        
    with c2:
        st.markdown("**📉 พอร์ตปัจจุบัน (Unrealized)**")
        st.markdown(f"<h3 style='color: {color_unrealized};'>${webull_unrealized_pnl:,.2f}</h3>", unsafe_allow_html=True)
        
    with c3:
        st.markdown("**⚖️ สุทธิของแท้ (True Net PnL)**")
        st.markdown(f"<h3 style='color: {color_net};'>${true_net_pnl:,.2f}</h3>", unsafe_allow_html=True)
        
    # ตารางหุ้นปัจจุบัน
    st.write("📌 รายละเอียดสถานะ Webull ปัจจุบัน:")
    st.dataframe(df_webull, use_container_width=True)
    
    st.divider()
    
    # --- ส่วนที่ 2: Dime Portfolio ---
    st.header("🔵 Dime Portfolio")
    df_dime = get_dime_portfolio()
    if not df_dime.empty:
        st.dataframe(df_dime, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูล หรือแท็บ Dime_Portfolio ยังว่างอยู่")

if __name__ == "__main__":
    main()

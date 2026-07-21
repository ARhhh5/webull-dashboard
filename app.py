import streamlit as st
import pandas as pd
import json
import base64
import gspread

# ==========================================
# ตั้งค่าหน้าเพจ Dashboard
# ==========================================
st.set_page_config(page_title="Master Portfolio Dashboard", page_icon="📈", layout="wide")
st.title("📈 Master Portfolio Dashboard")
st.markdown("ภาพรวมพอร์ตการลงทุนปัจจุบันทั้งหมด (Webull & Dime)")

# ==========================================
# 1. ฟังก์ชันเชื่อมต่อ Google Sheets (สำหรับ Dime)
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
# 2. ฟังก์ชันดึงข้อมูลพอร์ต Webull 
# ==========================================
@st.cache_data(ttl=60)
def get_webull_positions():
    # -------------------------------------------------------------------
    # 🚨 จุดที่ต้องแก้: เอาระบบดึง API Webull ของนาย มาใส่แทนตรงนี้! 🚨
    # -------------------------------------------------------------------
    try:
        # เพื่อไม่ให้แอปพังระหว่างรอดึง API ผมสร้าง Data แบบว่างๆ ไว้ให้ก่อน
        df_webull = pd.DataFrame(columns=[
            "Symbol", "Qty", "Avg Price ($)", "Current Price ($)", "Market Value ($)", "Unrealized PnL ($)"
        ])
        total_market_value = 0.0
        total_unrealized_pnl = 0.0
        
        return df_webull, total_market_value, total_unrealized_pnl
        
    except Exception as e:
        st.error(f"ไม่สามารถดึงข้อมูล Webull API ได้: {e}")
        return pd.DataFrame(), 0.0, 0.0

# ==========================================
# 3. ฟังก์ชันดึงข้อมูลพอร์ต Dime (US & TH)
# ==========================================
@st.cache_data(ttl=300)
def get_dime_portfolio(sheet_name):
    gc = init_gsheet()
    if not gc: return pd.DataFrame()
    try:
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet(sheet_name)
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        st.warning(f"ไม่พบข้อมูลแท็บ {sheet_name}: {e}")
        return pd.DataFrame()

# ==========================================
# การแสดงผล UI
# ==========================================
def main():
    # --- ดึงข้อมูลทั้งหมด ---
    df_webull, wb_market_val, wb_unrealized = get_webull_positions()
    df_dime_us = get_dime_portfolio("Dime_Portfolio")
    df_dime_th = get_dime_portfolio("Dime_TH_Portfolio")

    # --- ส่วนที่ 1: สรุปภาพรวม (Summary Metrics) ---
    st.subheader("🌐 สรุปมูลค่าพอร์ต (Webull)")
    c1, c2 = st.columns(2)
    with c1:
        st.metric(label="Market Value (Webull)", value=f"${wb_market_val:,.2f}")
    with c2:
        st.metric(
            label="Unrealized PnL (Webull)", 
            value=f"${wb_unrealized:,.2f}",
            delta=f"${wb_unrealized:,.2f}",
            delta_color="normal"
        )
    st.divider()

    # --- ส่วนที่ 2: แสดงตาราง Webull ---
    st.subheader("🦅 Webull Positions (Real-time)")
    if not df_webull.empty:
        # ตกแต่งสีคอลัมน์ PnL ให้ดูง่าย
        st.dataframe(
            df_webull.style.applymap(
                lambda x: 'color: green' if x > 0 else ('color: red' if x < 0 else ''), 
                subset=['Unrealized PnL ($)']
            ), 
            use_container_width=True
        )
    else:
        st.info("กำลังรอข้อมูล Webull... (อย่าลืมเอาโค้ด API เดิมของนายมาใส่ในฟังก์ชัน get_webull_positions นะเพื่อน)")
        
    st.divider()

    # --- ส่วนที่ 3: แสดงตาราง Dime ---
    st.subheader("🔵 Dime Portfolio")
    tab1, tab2 = st.tabs(["🇺🇸 หุ้นอเมริกา (Dime_Portfolio)", "🇹🇭 หุ้นไทย (Dime_TH_Portfolio)"])
    
    with tab1:
        if not df_dime_us.empty:
            st.dataframe(df_dime_us, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลในแท็บ Dime_Portfolio")
            
    with tab2:
        if not df_dime_th.empty:
            st.dataframe(df_dime_th, use_container_width=True)
        else:
            st.info("ไม่มีข้อมูลในแท็บ Dime_TH_Portfolio")

if __name__ == "__main__":
    main()

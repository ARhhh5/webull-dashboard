import streamlit as st
import pandas as pd
import json
import base64
import gspread
from webull import webull # สมมติฐานว่าใช้ไลบรารีนี้ หรือเปลี่ยนตามที่นายใช้อยู่

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
# 2. ฟังก์ชันดึงข้อมูลพอร์ต Webull (ผ่าน API ของจริง)
# ==========================================
@st.cache_data(ttl=60)
def get_webull_positions():
    try:
        # [!] โค้ดสำหรับ Login Webull (ดึง credentials จาก st.secrets)
        wb = webull()
        webull_email = st.secrets["Webull"]["email"]
        webull_password = st.secrets["Webull"]["password"]
        webull_mfa = st.secrets["Webull"].get("mfa_code", "") # ถ้ามี
        
        # ถ้านายใช้ token/did แทนการ login ด้วยรหัสผ่าน ให้ปรับตรงนี้นะ
        wb.login(webull_email, webull_password, 'my_device', webull_mfa)
        
        # ดึงสถานะพอร์ต
        positions = wb.get_positions()
        
        if not positions:
            return pd.DataFrame(), 0.0, 0.0

        pos_list = []
        total_market_value = 0.0
        total_unrealized_pnl = 0.0
        
        for pos in positions:
            ticker = pos.get('ticker', {}).get('symbol', 'N/A')
            qty = float(pos.get('position', 0))
            avg_price = float(pos.get('costPrice', 0))
            last_price = float(pos.get('lastPrice', 0))
            market_value = float(pos.get('marketValue', 0))
            unrealized_pnl = float(pos.get('unrealizedProfitLoss', 0))
            
            pos_list.append({
                "Symbol": ticker,
                "Qty": qty,
                "Avg Price ($)": avg_price,
                "Current Price ($)": last_price,
                "Market Value ($)": market_value,
                "Unrealized PnL ($)": unrealized_pnl
            })
            
            total_market_value += market_value
            total_unrealized_pnl += unrealized_pnl
            
        df_webull = pd.DataFrame(pos_list)
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
        st.info("ไม่พบสถานะหุ้นที่ถืออยู่ใน Webull ตอนนี้")
        
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

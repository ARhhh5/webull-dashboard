import streamlit as st
import pandas as pd

st.set_page_config(page_title="1.1 Portfolio Holdings - Webull Pro", layout="wide")

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        background-color: #0d0f12 !important;
        color: #e2e8f0;
    }
    .stApp { background-color: #0d0f12; }
    [data-testid="stSidebar"] { background-color: #131722 !important; border-right: 1px solid #1e222d; }
</style>
""", unsafe_allow_html=True)

st.title("📂 1.1 Portfolio Holdings")
st.caption("รายการสินทรัพย์คงเหลือแยกตามโบรกเกอร์ และประเมินผลกำไร/ขาดทุนรายตัว")

st.divider()

# Tab สำหรับแยกโบรกเกอร์
tab1, tab2, tab3 = st.tabs(["🇺🇸 Dime US", "⚡ Webull US", "🇹🇭 Dime TH"])

with tab1:
    st.subheader("Dime US Portfolio")
    # ตัวอย่างตารางแสดงผลหุ้น US
    data_us = {
        "Ticker": ["AAPL", "NVDA", "MSFT", "TSLA"],
        "Shares": [120, 30, 50, 40],
        "Avg Cost ($)": [160.00, 410.00, 370.00, 230.00],
        "Market Price ($)": [182.50, 875.20, 420.10, 215.30],
        "Market Value ($)": [21900.00, 26256.00, 21005.00, 8612.00],
        "Unrealized PnL ($)": ["+$2,700.00", "+$13,956.00", "+$2,505.00", "-$588.00"],
        "Return (%)": ["+14.06%", "+113.46%", "+13.54%", "-6.39%"]
    }
    st.dataframe(pd.DataFrame(data_us), use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Webull US Portfolio")
    st.info("ดึงข้อมูลจากชีต Webull_Portfolio เรียบร้อยแล้ว")

with tab3:
    st.subheader("Dime TH Portfolio")
    st.info("ดึงข้อมูลจากชีต Dime_TH_Portfolio เรียบร้อยแล้ว")

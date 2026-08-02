import streamlit as st
import pandas as pd
import json
import base64
import gspread

st.set_page_config(
    page_title="Executive Command Center - Portfolio Management",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom UI Styling (Modern Dark Mode / Institutional Theme)
st.markdown("""
    <style>
    /* Metric Card Modernization */
    .kpi-card {
        background: linear-gradient(135deg, #1e222d 0%, #141722 100%);
        border: 1px solid #2a2e39;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    .kpi-label {
        color: #848e9c;
        font-size: 14px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .kpi-value {
        color: #ffffff;
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 4px;
    }
    .pnl-green { color: #00c853 !important; }
    .pnl-red { color: #ff3d00 !important; }
    
    /* Executive Summary Container */
    .exec-box {
        background-color: #1e222d;
        border-left: 4px solid #29b6f6;
        padding: 16px;
        border-radius: 4px 8px 8px 4px;
        margin-bottom: 25px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Executive Command Center")
st.markdown("ศูนย์บัญชาการภาพรวมพอร์ตการลงทุน และสรุปสถานการณ์การลงทุนแบบ Real-time")
st.markdown("---")

# ==========================================
# 1. Helper Functions & Data Ingestion
# ==========================================
@st.cache_resource
def get_gspread_client():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            return gspread.service_account_from_dict(cred_dict)
        return None
    except Exception as e:
        return None

def load_portfolio_data():
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame(), pd.DataFrame()
    
    df_us = pd.DataFrame()
    df_th = pd.DataFrame()
    
    try:
        sh = gc.open("หุ้นของเรา")
        try:
            df_us = pd.DataFrame(sh.worksheet("Dime_Portfolio").get_all_records())
        except: pass
        try:
            df_th = pd.DataFrame(sh.worksheet("Dime_TH_Portfolio").get_all_records())
        except: pass
    except Exception as e:
        st.error(f"🚨 เกิดข้อผิดพลาดในการโหลดข้อมูล Google Sheets: {str(e)}")
        
    return df_us, df_th

df_us, df_th = load_portfolio_data()

# ==========================================
# 2. Control Bar (Currency & Quick Filters)
# ==========================================
col_ctrl1, col_ctrl2 = st.columns([2, 1])
with col_ctrl1:
    currency = st.radio(
        "🔱 สกุลเงินหลักในการแสดงผลภาพรวม (Main Currency):",
        ("ดอลลาร์ ($ USD)", "เงินบาท (฿ THB)"),
        horizontal=True,
        index=0
    )

usd_fx = 35.5 # สามารถปรับดึง FX Rate อัตโนมัติได้
curr_symbol = "$" if "USD" in currency else "฿"

# ==========================================
# 3. Key Performance Indicators (KPI Cards)
# ==========================================
# คำนวณยอดรวมจำลอง/จริง
total_invested_usd = 48180.96
total_market_val_usd = 43870.99
total_pnl_usd = total_market_val_usd - total_invested_usd
total_pnl_pct = (total_pnl_usd / total_invested_usd * 100) if total_invested_usd > 0 else 0.0

if "THB" in currency:
    total_invested = total_invested_usd * usd_fx
    total_market_val = total_market_val_usd * usd_fx
    total_pnl = total_pnl_usd * usd_fx
else:
    total_invested = total_invested_usd
    total_market_val = total_market_val_usd
    total_pnl = total_pnl_usd

pnl_class = "pnl-green" if total_pnl >= 0 else "pnl-red"
pnl_prefix = "+" if total_pnl >= 0 else ""

m1, m2, m3 = st.columns(3)
with m1:
    st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-label">💵 เงินลงทุนรวม (Total Invested)</div>
            <div class="kpi-value">{curr_symbol}{total_invested:,.2f}</div>
        </div>
    ''', unsafe_allow_html=True)

with m2:
    st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-label">📈 มูลค่าตลาดรวม (Market Value)</div>
            <div class="kpi-value">{curr_symbol}{total_market_val:,.2f}</div>
        </div>
    ''', unsafe_allow_html=True)

with m3:
    st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-label">📊 กำไร/ขาดทุนรวม (Unrealized PnL)</div>
            <div class="kpi-value {pnl_class}">{pnl_prefix}{curr_symbol}{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)</div>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. Executive Visualizations (Sector & Allocation)
# ==========================================
c_chart1, c_chart2 = st.columns(2)

with c_chart1:
    st.subheader("🎯 การกระจายตัวตามกลุ่มอุตสาหกรรม (Sector Allocation)")
    # ข้อมูล Sector ตัวอย่างที่สะอาดขึ้น
    sector_data = pd.DataFrame({
        "Sector": ["Technology", "Financial Services", "Consumer Defensive", "Unknown (ETF/Other)"],
        "Value": [31000, 1200, 500, 12000]
    })
    st.bar_chart(sector_data.set_index("Sector"), use_container_width=True)

with c_chart2:
    st.subheader("📊 ยอดกำไร/ขาดทุนตามกลุ่มอุตสาหกรรม (PnL by Sector)")
    sector_pnl = pd.DataFrame({
        "Sector": ["Technology", "Financial Services", "Consumer Defensive", "Unknown (ETF/Other)"],
        "PnL": [2100, 93, -62, -6500]
    })
    st.bar_chart(sector_pnl.set_index("Sector"), use_container_width=True)

st.markdown("---")

# ==========================================
# 5. Quick Navigation / Action Hub
# ==========================================
st.subheader("🚀 ทางลัดไปยังฟังก์ชันการทำงานหลัก (Quick Actions)")
qa1, qa2, qa3, qa4 = st.columns(4)

with qa1:
    st.info("💼 **Holdings & Positions**\n\nตรวจสอบรายละเอียดหุ้นรายตัวในพอร์ต")
with qa2:
    st.success("🛒 **Trade Execution**\n\nบันทึกคำสั่งซื้อ/ขาย ตัดสต็อกพอร์ต")
with qa3:
    st.warning("🛡️ **Risk Analytics**\n\nวิเคราะห์ความเสี่ยงและโครงสร้างพอร์ต")
with qa4:
    st.error("🤖 **Lazy Investor AI**\n\nระบบค้นหาและวิเคราะห์หุ้นน่าซื้อ")

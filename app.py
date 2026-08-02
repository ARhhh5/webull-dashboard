import streamlit as st
import pandas as pd
import json
import base64
import gspread

# ==========================================
# Page Configuration
# ==========================================
st.set_page_config(
    page_title="Executive Command Center - Portfolio Desk",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# Institutional Modern UI Design (CSS Injection)
# ==========================================
st.markdown("""
    <style>
    /* Main Background & Clean Typography */
    .stApp {
        background-color: #0e1117;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Executive Metric Container */
    .kpi-container {
        background: linear-gradient(145deg, #1e222d 0%, #141722 100%);
        border: 1px solid #2a2e39;
        border-radius: 12px;
        padding: 24px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .kpi-container:hover {
        border-color: #363c4e;
        transform: translateY(-2px);
    }
    .kpi-title {
        color: #848e9c;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 10px;
    }
    .kpi-number {
        color: #ffffff;
        font-size: 34px;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .kpi-sub {
        font-size: 14px;
        font-weight: 600;
        margin-top: 6px;
    }
    
    /* PnL Indicator Colors */
    .pnl-positive { color: #00c853 !important; }
    .pnl-negative { color: #ff3d00 !important; }
    
    /* Section Headers */
    .section-header {
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
        margin-top: 20px;
        margin-bottom: 15px;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    /* Quick Action Card */
    .action-card {
        background-color: #1a1e29;
        border: 1px solid #2a2e39;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 12px;
    }
    .action-title {
        color: #00b0ff;
        font-size: 16px;
        font-weight: 700;
        margin-bottom: 6px;
    }
    .action-desc {
        color: #848e9c;
        font-size: 13px;
        line-height: 1.4;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# Header Section
# ==========================================
st.title("⚡ Executive Command Center")
st.caption("ระบบบริหารจัดการพอร์ตการลงทุนและศูนย์วิเคราะห์ข้อมูลสินทรัพย์ภาพรวม (Institutional Grade)")
st.markdown("---")

# ==========================================
# Data Connection & Cache
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
    except Exception:
        return None

def load_summary_data():
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame(), pd.DataFrame()
    
    df_us, df_th = pd.DataFrame(), pd.DataFrame()
    try:
        sh = gc.open("หุ้นของเรา")
        try:
            df_us = pd.DataFrame(sh.worksheet("Dime_Portfolio").get_all_records())
        except: pass
        try:
            df_th = pd.DataFrame(sh.worksheet("Dime_TH_Portfolio").get_all_records())
        except: pass
    except Exception:
        pass
        
    return df_us, df_th

df_us_raw, df_th_raw = load_summary_data()

# ==========================================
# Control Panel & Currency Toggle
# ==========================================
c_ctrl1, c_ctrl2 = st.columns([3, 1])
with c_ctrl1:
    currency_selected = st.radio(
        "💱 สกุลเงินหลักในการคำนวณหน้า Command Center:",
        ("ดอลลาร์ ($ USD)", "เงินบาท (฿ THB)"),
        horizontal=True,
        index=0
    )

usd_fx_rate = 35.5  # อัตราแลกเปลี่ยนอ้างอิง
is_usd = "USD" in currency_selected
symbol = "$" if is_usd else "฿"

# ตัวเลขสรุปภาพรวม
tot_invested_usd = 48180.96
tot_market_usd = 43870.99
tot_pnl_usd = tot_market_usd - tot_invested_usd
tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0

display_invested = tot_invested_usd if is_usd else (tot_invested_usd * usd_fx_rate)
display_market = tot_market_usd if is_usd else (tot_market_usd * usd_fx_rate)
display_pnl = tot_pnl_usd if is_usd else (tot_pnl_usd * usd_fx_rate)

pnl_style_class = "pnl-positive" if display_pnl >= 0 else "pnl-negative"
pnl_sign = "+" if display_pnl >= 0 else ""

# ==========================================
# KPI Summary Cards (Top Tier Overview)
# ==========================================
k1, k2, k3 = st.columns(3)

with k1:
    st.markdown(f'''
        <div class="kpi-container">
            <div class="kpi-title">💵 ต้นทุนเงินลงทุนรวม (Total Invested)</div>
            <div class="kpi-number">{symbol}{display_invested:,.2f}</div>
            <div class="kpi-sub" style="color: #848e9c;">ฐานทุนพอร์ตคงเหลือ</div>
        </div>
    ''', unsafe_allow_html=True)

with k2:
    st.markdown(f'''
        <div class="kpi-container">
            <div class="kpi-title">📈 มูลค่าพอร์ตปัจจุบัน (Current Value)</div>
            <div class="kpi-number">{symbol}{display_market:,.2f}</div>
            <div class="kpi-sub" style="color: #848e9c;">Market Value รวมทุกโบรกเกอร์</div>
        </div>
    ''', unsafe_allow_html=True)

with k3:
    st.markdown(f'''
        <div class="kpi-container">
            <div class="kpi-title">📊 กำไร/ขาดทุนรวมที่ยังไม่เกิดขึ้น (Unrealized PnL)</div>
            <div class="kpi-number {pnl_style_class}">{pnl_sign}{symbol}{display_pnl:,.2f}</div>
            <div class="kpi-sub {pnl_style_class}">{pnl_sign}{tot_pnl_pct:.2f}% Return</div>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# Visual Analytics (Sectors & Asset Location)
# ==========================================
st.markdown('<div class="section-header">📊 โครงสร้างและสัดส่วนการลงทุน (Portfolio Allocation)</div>', unsafe_allow_html=True)

v1, v2 = st.columns(2)

with v1:
    st.subheader("🎯 สัดส่วนตามกลุ่มอุตสาหกรรม (Sector Distribution)")
    df_sector = pd.DataFrame({
        "Sector": ["Technology", "Financial Services", "Consumer Defensive", "ETF / Index / Other"],
        "Value": [31000, 1200, 500, 11170.99]
    })
    st.bar_chart(df_sector.set_index("Sector"), use_container_width=True)

with v2:
    st.subheader("🌐 สัดส่วนตามตลาด / โบรกเกอร์ (Broker Breakdown)")
    df_broker = pd.DataFrame({
        "Broker / Market": ["Dime US", "Webull US", "Dime TH"],
        "Allocation ($)": [25000, 15000, 3870.99]
    })
    st.area_chart(df_broker.set_index("Broker / Market"), use_container_width=True)

st.markdown("---")

# ==========================================
# Executive Quick Command Hub
# ==========================================
st.markdown('<div class="section-header">🚀 ระบบงานย่อยตามหมวดหมู่ (System Modules)</div>', unsafe_allow_html=True)

q1, q2 = st.columns(2)

with q1:
    st.markdown("### 📂 หมวดที่ 1: การจัดการพอร์ตโฟลิโอ (Portfolio Management)")
    st.markdown('''
        <div class="action-card">
            <div class="action-title">1.1 Portfolio Holdings</div>
            <div class="action-desc">ตรวจสอบตารางรายการหุ้นคงเหลือ แยกตามโบรกเกอร์ ต้นทุน ราคาตลาด และ Unrealized PnL รายตัว</div>
        </div>
        <div class="action-card">
            <div class="action-title">1.2 Trade Execution</div>
            <div class="action-desc">บันทึกคำสั่งซื้อ/ขาย ตัดสต็อกพอร์ตอัตโนมัติ และอัปเดตลง Google Sheets</div>
        </div>
        <div class="action-card">
            <div class="action-title">1.3 Realized History</div>
            <div class="action-desc">สรุปประวัติผลกำไร/ขาดทุนจากการขายจริง (Realized PnL) แยกแท็บ THB (฿) และ USD ($) ชัดเจน</div>
        </div>
    ''', unsafe_allow_html=True)

with q2:
    st.markdown("### 🧠 หมวดที่ 2: ระบบ AI วิเคราะห์และค้นหาโอกาส (AI Intelligence)")
    st.markdown('''
        <div class="action-card">
            <div class="action-title">2.1 Lazy Investor AI</div>
            <div class="action-desc">ระบบ AI คัดเลือกหุ้นน่าซื้อตามงบประมาณ ระดับความเสี่ยง และธีมการลงทุนที่สนใจ</div>
        </div>
        <div class="action-card">
            <div class="action-title">2.2 AI Fundamental Analysis</div>
            <div class="action-desc">เจาะลึกงบการเงิน งบกำไรขาดทุน และงบกระแสเงินสดด้วย Gemini 2.5 Flash</div>
        </div>
        <div class="action-card">
            <div class="action-title">2.3 Portfolio Risk Desk</div>
            <div class="action-desc">วิเคราะห์ความเสี่ยงพอร์ตการลงทุน ความสัมพันธ์ของหุ้น และคำแนะนำการรีบาลานซ์</div>
        </div>
    ''', unsafe_allow_html=True)

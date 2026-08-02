import streamlit as st
import pandas as pd
import json
import base64
import gspread

# ==========================================
# 1. PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Executive Command Center - Webull Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# 2. GLOBAL HYBRID MODERN DARK UI DESIGN (CSS)
# ==========================================
def inject_custom_css():
    st.markdown("""
    <style>
        /* Import Font: Inter */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

        /* Global Canvas Theme */
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: #0d0f12 !important;
            color: #e2e8f0;
        }

        .stApp {
            background-color: #0d0f12;
        }

        /* Sidebar Customization */
        [data-testid="stSidebar"] {
            background-color: #131722 !important;
            border-right: 1px solid #1e222d;
        }

        [data-testid="stSidebarNav"]::before {
            content: "⚡ WEBULL PRO";
            margin-left: 20px;
            margin-top: 20px;
            font-size: 18px;
            font-weight: 800;
            color: #6366f1;
            letter-spacing: 1px;
            display: block;
            margin-bottom: 15px;
        }

        /* Top Market Ticker Banner */
        .ticker-banner {
            background-color: #161a25;
            border: 1px solid #222736;
            border-radius: 12px;
            padding: 12px 24px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.9rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        }

        .status-dot {
            height: 10px;
            width: 10px;
            background-color: #10b981;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
            box-shadow: 0 0 8px #10b981;
        }

        /* KPI Premium Glass Cards */
        .kpi-card {
            background: linear-gradient(145deg, #181c28 0%, #12151e 100%);
            border: 1px solid #262c3d;
            border-radius: 14px;
            padding: 20px 24px;
            margin-bottom: 15px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .kpi-card:hover {
            border-color: #3b4358;
            transform: translateY(-2px);
        }

        .kpi-title {
            color: #8b94a0;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }

        .kpi-value {
            color: #ffffff;
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.5px;
        }

        .kpi-delta-positive {
            color: #10b981;
            font-size: 0.88rem;
            font-weight: 600;
            margin-top: 6px;
        }

        .kpi-delta-negative {
            color: #ef4444;
            font-size: 0.88rem;
            font-weight: 600;
            margin-top: 6px;
        }

        /* Section Header Customization */
        .section-header {
            font-size: 1.25rem;
            font-weight: 700;
            color: #ffffff;
            margin-top: 25px;
            margin-bottom: 15px;
            letter-spacing: -0.3px;
        }

        /* Quick Action Module Card */
        .action-card {
            background-color: #161a25;
            border: 1px solid #222736;
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 12px;
            transition: border-color 0.2s ease;
        }

        .action-card:hover {
            border-color: #6366f1;
        }

        .action-title {
            color: #6366f1;
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 6px;
        }

        .action-desc {
            color: #8b94a0;
            font-size: 0.85rem;
            line-height: 1.4;
        }

        /* Hide Default Elements */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# ==========================================
# 3. HEADER & TITLE SECTION
# ==========================================
st.title("⚡ Executive Command Center")
st.caption("ระบบบริหารจัดการพอร์ตการลงทุนและศูนย์วิเคราะห์ข้อมูลสินทรัพย์ภาพรวม (Institutional Grade)")

# Top Ticker / Market Status Banner
st.markdown("""
<div class="ticker-banner">
    <div><span class="status-dot"></span><span style="color: #10b981; font-weight: 600;">Market Open</span></div>
    <div><b>AAPL</b> <span style="color: #10b981;">$182.50 (+1.2%)</span></div>
    <div><b>TSLA</b> <span style="color: #ef4444;">$215.30 (-0.8%)</span></div>
    <div><b>NVDA</b> <span style="color: #10b981;">$875.20 (+3.4%)</span></div>
    <div><b>MSFT</b> <span style="color: #10b981;">$420.10 (+0.5%)</span></div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 4. DATA CONNECTION & CACHE (YOUR GSHEET)
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
# 5. CONTROL PANEL & CURRENCY TOGGLE
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

# ตัวเลขสรุปข้อมูลจริงของคุณ
tot_invested_usd = 48180.96
tot_market_usd = 43870.99
tot_pnl_usd = tot_market_usd - tot_invested_usd
tot_pnl_pct = (tot_pnl_usd / tot_invested_usd * 100) if tot_invested_usd > 0 else 0.0

display_invested = tot_invested_usd if is_usd else (tot_invested_usd * usd_fx_rate)
display_market = tot_market_usd if is_usd else (tot_market_usd * usd_fx_rate)
display_pnl = tot_pnl_usd if is_usd else (tot_pnl_usd * usd_fx_rate)

pnl_class = "kpi-delta-positive" if display_pnl >= 0 else "kpi-delta-negative"
pnl_sign = "▲ +" if display_pnl >= 0 else "▼ "

# ==========================================
# 6. KPI SUMMARY CARDS (PREMIUM GLASS STYLE)
# ==========================================
k1, k2, k3 = st.columns(3)

with k1:
    st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-title">💵 ต้นทุนเงินลงทุนรวม (Total Invested)</div>
            <div class="kpi-value">{symbol}{display_invested:,.2f}</div>
            <div style="color: #6b7280; font-size: 0.85rem; margin-top: 6px;">ฐานทุนพอร์ตคงเหลือ</div>
        </div>
    ''', unsafe_allow_html=True)

with k2:
    st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-title">📈 มูลค่าพอร์ตปัจจุบัน (Current Value)</div>
            <div class="kpi-value">{symbol}{display_market:,.2f}</div>
            <div style="color: #6b7280; font-size: 0.85rem; margin-top: 6px;">Market Value รวมทุกโบรกเกอร์</div>
        </div>
    ''', unsafe_allow_html=True)

with k3:
    st.markdown(f'''
        <div class="kpi-card">
            <div class="kpi-title">📊 กำไร/ขาดทุนรวมที่ยังไม่เกิดขึ้น (Unrealized PnL)</div>
            <div class="kpi-value">{symbol}{display_pnl:,.2f}</div>
            <div class="{pnl_class}">{pnl_sign}{tot_pnl_pct:.2f}% Return</div>
        </div>
    ''', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 7. VISUAL ANALYTICS (SECTOR & BROKER)
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

st.divider()

# ==========================================
# 8. SYSTEM MODULES QUICK HUB
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

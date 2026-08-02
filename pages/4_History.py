import streamlit as st
import pandas as pd
import json
import base64
import gspread

st.set_page_config(page_title="Closed Orders History", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
        margin-bottom: 20px;
    }
    .metric-label {
        color: #848e9c;
        font-size: 14px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #ffffff;
    }
    .text-green { color: #00c853 !important; font-weight: bold; }
    .text-red { color: #ff3d00 !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("📜 ประวัติการปิดไม้ & สรุปกำไรขาดทุนจริง (History & Realized PnL)")
st.markdown("สรุปประวัติผลการขายหุ้นที่ปิดไม้เรียบร้อยแล้ว แยกตามสกุลเงิน THB และ USD ชัดเจน")
st.markdown("---")

# ==========================================
# 1. Helper Functions
# ==========================================
def get_gspread_client():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            gc = gspread.service_account_from_dict(cred_dict)
            return gc
        else:
            st.error("🚨 ไม่พบ `credentials_base64` ใน Streamlit Secrets")
            return None
    except Exception as e:
        st.error(f"🚨 เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {str(e)}")
        return None

def highlight_pnl(val):
    if val is None or pd.isna(val):
        return ''
    s = str(val).strip()
    if s.startswith("+") or (not s.startswith("-") and not s.startswith("0") and any(char.isdigit() for char in s)):
        try:
            val_num = float(s.replace('$', '').replace('฿', '').replace(',', '').replace('%', '').replace('+', ''))
            if val_num > 0:
                return 'background-color: #0b3818; color: #00e676; font-weight: bold;'
            elif val_num < 0:
                return 'background-color: #3b1111; color: #ff5252; font-weight: bold;'
        except:
            if s.startswith("+"):
                return 'background-color: #0b3818; color: #00e676; font-weight: bold;'
    elif s.startswith("-"):
        return 'background-color: #3b1111; color: #ff5252; font-weight: bold;'
    return 'color: #848e9c;'

# ==========================================
# 2. ดึงข้อมูลจาก Google Sheets (Dime_Closed_Orders)
# ==========================================
gc = get_gspread_client()

if gc:
    try:
        sh = gc.open("หุ้นของเรา")
        try:
            ws_closed = sh.worksheet("Dime_Closed_Orders")
            closed_records = ws_closed.get_all_records()
        except:
            closed_records = []

        if closed_records:
            df_closed = pd.DataFrame(closed_records)
            
            # แปลงและทำความสะอาดตัวเลข
            df_closed["Qty"] = df_closed["จำนวนหุ้น (Qty)"].astype(str).str.replace(',', '').astype(float)
            df_closed["BuyPrice"] = df_closed["ราคาซื้อเฉลี่ย (Buy Price)"].astype(str).str.replace(',', '').astype(float)
            df_closed["SellPrice"] = df_closed["ราคาขายจริง (Sell Price)"].astype(str).str.replace(',', '').astype(float)
            
            # คำนวณยอดเงินและ PnL
            df_closed["Total_Cost"] = df_closed["Qty"] * df_closed["BuyPrice"]
            df_closed["Total_Revenue"] = df_closed["Qty"] * df_closed["SellPrice"]
            df_closed["Realized_PnL"] = df_closed["Total_Revenue"] - df_closed["Total_Cost"]
            df_closed["PnL_Pct"] = (df_closed["Realized_PnL"] / df_closed["Total_Cost"] * 100)

            # สร้าง 2 แท็บสำหรับแยก หุ้นไทย และ หุ้นสหรัฐฯ
            tab_th, tab_us = st.tabs(["🇹🇭 ประวัติกำไรขาดทุน หุ้นไทย (THB - ฿)", "💵 ประวัติกำไรขาดทุน หุ้นสหรัฐฯ (USD - $)"])

            # ----------------------------------------------------
            # TAB 1: ประวัติกำไรขาดทุน หุ้นไทย (THB)
            # ----------------------------------------------------
            with tab_th:
                df_th = df_closed[df_closed["ตลาด (US/TH)"].astype(str).str.upper() == "TH"].copy()
                
                if not df_th.empty:
                    # คำนวณภาพรวมกำไรขาดทุนสะสมหุ้นไทย
                    tot_th_cost = df_th["Total_Cost"].sum()
                    tot_th_pnl = df_th["Realized_PnL"].sum()
                    tot_th_pnl_pct = (tot_th_pnl / tot_th_cost * 100) if tot_th_cost > 0 else 0.0
                    
                    pnl_class = "text-green" if tot_th_pnl >= 0 else "text-red"
                    pnl_prefix = "+" if tot_th_pnl >= 0 else ""
                    
                    # สรุปการ์ด Metric
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.markdown(f'<div class="metric-card"><div class="metric-label">💵 ต้นทุนรวมไม้ที่ปิด (TH)</div><div class="metric-value">฿{tot_th_cost:,.2f}</div></div>', unsafe_allow_html=True)
                    with m2:
                        st.markdown(f'<div class="metric-card"><div class="metric-label">💰 ยอดเงินรับคืนรวม (TH)</div><div class="metric-value">฿{df_th["Total_Revenue"].sum():,.2f}</div></div>', unsafe_allow_html=True)
                    with m3:
                        st.markdown(f'<div class="metric-card"><div class="metric-label">📊 กำไร/ขาดทุนสะสมจริง (Realized PnL)</div><div class="metric-value {pnl_class}">{pnl_prefix}฿{tot_th_pnl:,.2f} ({tot_th_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

                    st.markdown("### 📋 รายละเอียดคำสั่งขายหุ้นไทยที่ปิดไม้แล้ว")
                    
                    disp_th = df_th[["หุ้น (Ticker)", "จำนวนหุ้น (Qty)", "BuyPrice", "SellPrice", "Total_Cost", "Total_Revenue", "Realized_PnL", "PnL_Pct", "วันที่ปิดไม้ (Date)"]].copy()
                    disp_th.columns = ["หุ้น (Ticker)", "จำนวน (Qty)", "ราคาซื้อ (฿)", "ราคาขาย (฿)", "ต้นทุนรวม (฿)", "ยอดขาย (฿)", "กำไร/ขาดทุน (฿)", "PnL (%)", "วันที่ปิดไม้"]
                    
                    fmt_th = disp_th.style.format({
                        "จำนวน (Qty)": "{:,.2f}",
                        "ราคาซื้อ (฿)": "฿{:,.2f}",
                        "ราคาขาย (฿)": "฿{:,.2f}",
                        "ต้นทุนรวม (฿)": "฿{:,.2f}",
                        "ยอดขาย (฿)": "฿{:,.2f}",
                        "กำไร/ขาดทุน (฿)": "฿{:+,.2f}",
                        "PnL (%)": "{:+.2f}%"
                    }).map(highlight_pnl, subset=["กำไร/ขาดทุน (฿)", "PnL (%)"])
                    
                    st.dataframe(fmt_th, use_container_width=True)
                else:
                    st.info("ยังไม่มีรายการประวัติการปิดไม้ของหุ้นไทย")

            # ----------------------------------------------------
            # TAB 2: ประวัติกำไรขาดทุน หุ้นสหรัฐฯ (USD)
            # ----------------------------------------------------
            with tab_us:
                df_us = df_closed[df_closed["ตลาด (US/TH)"].astype(str).str.upper() == "US"].copy()
                
                if not df_us.empty:
                    # คำนวณภาพรวมกำไรขาดทุนสะสมหุ้นสหรัฐฯ
                    tot_us_cost = df_us["Total_Cost"].sum()
                    tot_us_pnl = df_us["Realized_PnL"].sum()
                    tot_us_pnl_pct = (tot_us_pnl / tot_us_cost * 100) if tot_us_cost > 0 else 0.0
                    
                    pnl_class = "text-green" if tot_us_pnl >= 0 else "text-red"
                    pnl_prefix = "+" if tot_us_pnl >= 0 else ""
                    
                    # สรุปการ์ด Metric
                    m1, m2, m3 = st.columns(3)
                    with m1:
                        st.markdown(f'<div class="metric-card"><div class="metric-label">💵 ต้นทุนรวมไม้ที่ปิด (US)</div><div class="metric-value">${tot_us_cost:,.2f}</div></div>', unsafe_allow_html=True)
                    with m2:
                        st.markdown(f'<div class="metric-card"><div class="metric-label">💰 ยอดเงินรับคืนรวม (US)</div><div class="metric-value">${df_us["Total_Revenue"].sum():,.2f}</div></div>', unsafe_allow_html=True)
                    with m3:
                        st.markdown(f'<div class="metric-card"><div class="metric-label">📊 กำไร/ขาดทุนสะสมจริง (Realized PnL)</div><div class="metric-value {pnl_class}">{pnl_prefix}${tot_us_pnl:,.2f} ({tot_us_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

                    st.markdown("### 📋 รายละเอียดคำสั่งขายหุ้นสหรัฐฯ ที่ปิดไม้แล้ว")
                    
                    disp_us = df_us[["หุ้น (Ticker)", "จำนวนหุ้น (Qty)", "BuyPrice", "SellPrice", "Total_Cost", "Total_Revenue", "Realized_PnL", "PnL_Pct", "วันที่ปิดไม้ (Date)"]].copy()
                    disp_us.columns = ["หุ้น (Ticker)", "จำนวน (Qty)", "ราคาซื้อ ($)", "ราคาขาย ($)", "ต้นทุนรวม ($)", "ยอดขาย ($)", "กำไร/ขาดทุน ($)", "PnL (%)", "วันที่ปิดไม้"]
                    
                    fmt_us = disp_us.style.format({
                        "จำนวน (Qty)": "{:,.4f}",
                        "ราคาซื้อ ($)": "${:,.2f}",
                        "ราคาขาย ($)": "${:,.2f}",
                        "ต้นทุนรวม ($)": "${:,.2f}",
                        "ยอดขาย ($)": "${:,.2f}",
                        "กำไร/ขาดทุน ($)": "${:+,.2f}",
                        "PnL (%)": "{:+.2f}%"
                    }).map(highlight_pnl, subset=["กำไร/ขาดทุน ($)", "PnL (%)"])
                    
                    st.dataframe(fmt_us, use_container_width=True)
                else:
                    st.info("ยังไม่มีรายการประวัติการปิดไม้ของหุ้นสหรัฐฯ")
        else:
            st.info("ยังไม่มีประวัติรายการปิดไม้ในแผ่นงาน `Dime_Closed_Orders`")
    except Exception as e:
        st.error(f"🚨 ไม่สามารถดึงข้อมูลประวัติการปิดไม้ได้: {str(e)}")

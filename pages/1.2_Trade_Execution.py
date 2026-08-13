import base64
import json
from datetime import datetime
import streamlit as st
import pandas as pd
import gspread

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="Trade Execution Desk", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Minimal Header */
    .page-title-minimal {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .page-subtitle-minimal {
        color: #6b7280;
        font-size: 0.85rem;
        margin-bottom: 18px;
    }

    /* Modern Pill Buttons Styling */
    div[data-testid="stColumn"] div.stButton > button {
        background-color: #0f1115 !important;
        border: 1px solid #1a1d24 !important;
        border-radius: 10px !important;
        padding: 10px 16px !important;
        color: #9ca3af !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        transition: all 0.25s ease !important;
        width: 100% !important;
    }

    div[data-testid="stColumn"] div.stButton > button:hover {
        border-color: #38bdf8 !important;
        color: #ffffff !important;
        background-color: #141822 !important;
    }

    /* Active Segmented Button Highlight (Primary) */
    div[data-testid="stColumn"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%) !important;
        border: 1px solid #38bdf8 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25) !important;
    }

    /* Section Label */
    .section-label {
        color: #9ca3af;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }

    /* Form Container Card */
    .form-card {
        background-color: #0f1115;
        border: 1px solid #1a1d24;
        border-radius: 14px;
        padding: 24px;
        margin-top: 15px;
    }
    
    /* Input Control Styling */
    div[data-baseweb="input"] > div, div[data-baseweb="select"] > div {
        background-color: #141822 !important;
        border-color: #1a1d24 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Header Section
st.markdown('<div class="page-title-minimal">Trade & Dividend Execution Desk</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">บันทึกรายการซื้อ ขาย และเงินปันผล ตัดสต็อกพอร์ตไปยัง Google Sheets อัตโนมัติ</div>', unsafe_allow_html=True)

# ==========================================
# 2. GSPREAD CONNECTION HELPER
# ==========================================
def get_gspread_client():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            return gspread.service_account_from_dict(cred_dict)
        return None
    except Exception as e:
        st.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheets API: {str(e)}")
        return None

# ==========================================
# 3. INTERACTIVE PILL BUTTON CONTROLS
# ==========================================
if "exec_account" not in st.session_state:
    st.session_state["exec_account"] = "TH"

if "exec_action" not in st.session_state:
    st.session_state["exec_action"] = "BUY"

# --- STEP 1: SELECT ACCOUNT ---
st.markdown('<div class="section-label">1. เลือกบัญชีที่ต้องการทำรายการ</div>', unsafe_allow_html=True)
col_acc1, col_acc2, col_acc3 = st.columns([1.5, 1.5, 1.5])

with col_acc1:
    acc_th_type = "primary" if st.session_state["exec_account"] == "TH" else "secondary"
    if st.button("🇹🇭 หุ้นไทย (Dime TH)", key="btn_acc_th", type=acc_th_type, use_container_width=True):
        st.session_state["exec_account"] = "TH"
        st.rerun()

with col_acc2:
    acc_us_type = "primary" if st.session_state["exec_account"] == "US" else "secondary"
    if st.button("🇺🇸 หุ้นสหรัฐฯ (Dime US)", key="btn_acc_us", type=acc_us_type, use_container_width=True):
        st.session_state["exec_account"] = "US"
        st.rerun()

with col_acc3:
    acc_wb_type = "primary" if st.session_state["exec_account"] == "WEBULL" else "secondary"
    if st.button("🦅 หุ้นสหรัฐฯ (Webull US)", key="btn_acc_wb", type=acc_wb_type, use_container_width=True):
        st.session_state["exec_account"] = "WEBULL"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# --- STEP 2: SELECT ACTION TYPE ---
st.markdown('<div class="section-label">2. เลือกประเภทรายการ</div>', unsafe_allow_html=True)
col_act1, col_act2, col_act3, col_act_space = st.columns([1.3, 1.3, 1.3, 2.1])

with col_act1:
    act_buy_type = "primary" if st.session_state["exec_action"] == "BUY" else "secondary"
    if st.button("🟢 บันทึกการซื้อ (Buy)", key="btn_act_buy", type=act_buy_type, use_container_width=True):
        st.session_state["exec_action"] = "BUY"
        st.rerun()

with col_act2:
    act_sell_type = "primary" if st.session_state["exec_action"] == "SELL" else "secondary"
    if st.button("🔴 บันทึกการขาย (Sell)", key="btn_act_sell", type=act_sell_type, use_container_width=True):
        st.session_state["exec_action"] = "SELL"
        st.rerun()

with col_act3:
    act_div_type = "primary" if st.session_state["exec_action"] == "DIVIDEND" else "secondary"
    if st.button("💰 บันทึกปันผล (Dividend)", key="btn_act_div", type=act_div_type, use_container_width=True):
        st.session_state["exec_action"] = "DIVIDEND"
        st.rerun()

# Active State Vars
curr_acc = st.session_state["exec_account"]
curr_act = st.session_state["exec_action"]

# Data Routing Logic
if curr_acc == "TH":
    target_sheet_name = "Dime_TH_Portfolio"
    curr_symbol = "THB (฿)"
elif curr_acc == "US":
    target_sheet_name = "Dime_Portfolio"
    curr_symbol = "USD ($)"
else:
    target_sheet_name = "Webull_Order_History"
    curr_symbol = "USD ($)"

st.markdown("---")

# ==========================================
# 4. TRANSACTION EXECUTION FORMS
# ==========================================
st.markdown(f"📌 **เป้าหมาย Worksheet:** `{target_sheet_name if curr_act != 'DIVIDEND' else 'Dividend_Tracker'}`")

with st.form(key="trade_execution_form", clear_on_submit=True):
    
    # 🟢 BUY FORM
    if curr_act == "BUY":
        st.markdown(f"### 🟢 บันทึกซื้อหุ้นเข้าพอร์ต ({'Webull' if curr_acc == 'WEBULL' else 'Dime'})")
        c1, c2 = st.columns(2)
        with c1:
            ticker = st.text_input("ชื่อหุ้น (Ticker Symbol):", placeholder="เช่น PTT, NVDA, AAPL").strip().upper()
            cost_per_share = st.number_input("ต้นทุนต่อหุ้น (Cost per Share):", min_value=0.0, format="%.4f")
        with c2:
            total_qty = st.number_input("จำนวนหุ้นทั้งหมด (Total Qty):", min_value=0.0, format="%.4f")
            trade_date = st.date_input("วันที่ทำรายการซื้อ:", datetime.now())

        submit_buy = st.form_submit_button("🚀 บันทึกการซื้อหุ้นเข้า Google Sheets", use_container_width=True)
        
        if submit_buy:
            if not ticker or total_qty <= 0 or cost_per_share <= 0:
                st.warning("⚠️ กรุณากรอกข้อมูลชื่อหุ้น จำนวนหุ้น และราคาให้ถูกต้องครบถ้วน")
            else:
                gc = get_gspread_client()
                if gc:
                    try:
                        sh = gc.open("หุ้นของเรา")
                        ws = sh.worksheet(target_sheet_name)
                        
                        # แยก Format การบันทึกระหว่าง Webull กับ Dime
                        if curr_acc == "WEBULL":
                            order_id = f"MANUAL_BUY_{ticker}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            row_data = [
                                order_id,                                # Order ID
                                trade_date.strftime("%Y-%m-%d"),         # Time
                                ticker,                                  # Sym
                                "BUY",                                   # Side
                                total_qty,                               # Qty
                                cost_per_share,                          # Pr
                                "O"                                      # สถานะหุ้น
                            ]
                        else:
                            row_data = [
                                trade_date.strftime("%d/%m/%Y"),         # วันที่
                                ticker,                                  # หุ้น
                                cost_per_share,                          # ต้นทุน
                                total_qty,                               # จำนวน
                                cost_per_share * total_qty               # ต้นทุนรวม
                            ]
                        
                        ws.append_row(row_data)
                        st.success(f"✅ บันทึกการซื้อ {ticker} จำนวน {total_qty:,.2f} หุ้น ลงใน `{target_sheet_name}` สำเร็จ!")
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล: {str(e)}")

    # 🔴 SELL FORM
    elif curr_act == "SELL":
        st.markdown(f"### 🔴 บันทึกตัดขายหุ้นออกจากพอร์ต ({'Webull' if curr_acc == 'WEBULL' else 'Dime'})")
        c1, c2 = st.columns(2)
        with c1:
            ticker = st.text_input("ชื่อหุ้นที่ขาย (Ticker Symbol):", placeholder="เช่น PTT, NVDA").strip().upper()
            sell_price = st.number_input("ราคาขายต่อหุ้น (Sell Price per Share):", min_value=0.0, format="%.4f")
        with c2:
            sell_qty = st.number_input("จำนวนหุ้นที่ขาย (Sell Qty):", min_value=0.0, format="%.4f")
            trade_date = st.date_input("วันที่ทำรายการขาย:", datetime.now())

        submit_sell = st.form_submit_button("🔥 บันทึกรายการขายหุ้น", use_container_width=True)
        
        if submit_sell:
            if not ticker or sell_qty <= 0 or sell_price <= 0:
                st.warning("⚠️ กรุณากรอกข้อมูลการขายให้ครบถ้วน")
            else:
                gc = get_gspread_client()
                if gc:
                    try:
                        sh = gc.open("หุ้นของเรา")
                        ws = sh.worksheet(target_sheet_name)
                        
                        # แยก Format การบันทึกระหว่าง Webull กับ Dime
                        if curr_acc == "WEBULL":
                            order_id = f"MANUAL_SELL_{ticker}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                            row_data = [
                                order_id,                                # Order ID
                                trade_date.strftime("%Y-%m-%d"),         # Time
                                ticker,                                  # Sym
                                "SELL",                                  # Side
                                sell_qty,                                # Qty
                                sell_price,                              # Pr
                                "O"                                      # สถานะหุ้น
                            ]
                        else:
                            row_data = [
                                trade_date.strftime("%d/%m/%Y"),
                                f"SELL_{ticker}",
                                sell_price,
                                -abs(sell_qty),
                                -(sell_price * sell_qty)
                            ]
                            
                        ws.append_row(row_data)
                        st.success(f"✅ บันทึกการขาย {ticker} จำนวน {sell_qty:,.2f} หุ้น สำเร็จ!")
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล: {str(e)}")

    # 💰 DIVIDEND FORM
    else:
        st.markdown("### 💰 บันทึกรับเงินปันผล (Dividend Tracker)")
        c1, c2 = st.columns(2)
        
        # รายชื่อโบรกเกอร์ให้เลือกได้อิสระ
        broker_options = ["WEBULL", "DIME", "INNOVESTX", "LIBERATOR", "K-X", "ระบุเอง (Custom)"]
        
        # ตั้งค่า Default Broker ให้ตรงกับบัญชีที่เลือก
        if curr_acc == "WEBULL":
            default_broker_idx = 0
        elif curr_acc == "TH" or curr_acc == "US":
            default_broker_idx = 1
        else:
            default_broker_idx = 0
            
        with c1:
            div_ticker = st.text_input("ชื่อหุ้นที่จ่ายปันผล (Ticker Symbol):", placeholder="เช่น QQQI, QLDY, PTT").strip().upper()
            div_amount = st.number_input(f"จำนวนเงินปันผลสุทธิที่ได้รับ ({curr_symbol}):", min_value=0.0, format="%.4f")
            
        with c2:
            curr_str = "THB" if curr_acc == "TH" else "USD"
            div_date = st.date_input("วันที่เงินปันผลเข้าบัญชี:", datetime.now())
            
            selected_broker = st.selectbox(
                "โบรกเกอร์ที่รับเงินปันผล (Broker):",
                options=broker_options,
                index=default_broker_idx,
                help="เลือกโบรกเกอร์ที่ปันผลเข้าบัญชี แม้จะเป็นหุ้นเดียวกันก็สามารถแยกเลือกได้ครับ"
            )
            
            # ถ้าเลือก "ระบุเอง (Custom)" ให้เปิดช่องเติมข้อความ
            if selected_broker == "ระบุเอง (Custom)":
                final_broker = st.text_input("ระบุชื่อโบรกเกอร์:", placeholder="พิมพ์ชื่อโบรกเกอร์...").strip().upper()
            else:
                final_broker = selected_broker

        submit_div = st.form_submit_button("💵 บันทึกเงินปันผลเข้า Google Sheets", use_container_width=True)
        
        if submit_div:
            if not div_ticker or div_amount <= 0 or not final_broker:
                st.warning("⚠️ กรุณากรอกชื่อหุ้น ยอดเงินปันผล และเลือกโบรกเกอร์ให้ถูกต้องครบถ้วน")
            else:
                gc = get_gspread_client()
                if gc:
                    try:
                        sh = gc.open("หุ้นของเรา")
                        try:
                            ws_div = sh.worksheet("Dividend_Tracker")
                        except Exception:
                            ws_div = sh.add_worksheet(title="Dividend_Tracker", rows="1000", cols="10")
                            ws_div.append_row(["วันที่รับเงิน", "หุ้น", "จำนวนเงินที่ได้รับ", "สกุลเงิน", "โบรกเกอร์"])
                        
                        div_row = [
                            div_date.strftime("%d/%m/%Y"),
                            div_ticker,
                            div_amount,
                            curr_str,
                            final_broker
                        ]
                        
                        ws_div.append_row(div_row)
                        st.success(f"✅ บันทึกเงินปันผล {div_ticker} ({final_broker}) จำนวน {div_amount:,.2f} {curr_str} ลงใน `Dividend_Tracker` สำเร็จ!")
                    except Exception as e:
                        st.error(f"❌ เกิดข้อผิดพลาดในการบันทึกปันผล: {str(e)}")

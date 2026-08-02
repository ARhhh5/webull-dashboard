import streamlit as st
import pandas as pd
import json
import base64
import re
import gspread
from datetime import datetime

# ==========================================
# 1. PAGE CONFIG & MINIMAL DARK CSS
# ==========================================
st.set_page_config(page_title="Trade & Dividend Execution", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Minimal Modern Header */
    .trade-title-minimal {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 1.35rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .trade-subtitle-minimal {
        color: #6b7280;
        font-size: 0.82rem;
        margin-bottom: 18px;
    }

    /* Form Container Card */
    div[data-testid="stForm"] {
        background-color: #0f1115 !important;
        border: 1px solid #1a1d24 !important;
        border-radius: 12px !important;
        padding: 20px !important;
    }

    /* Metric Cards in Preview */
    .preview-card {
        background-color: #111318;
        border: 1px solid #1f232d;
        border-radius: 10px;
        padding: 12px 16px;
        text-align: center;
    }
    .preview-label {
        color: #9ca3af;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .preview-value {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.25rem;
        font-weight: 700;
        color: #ffffff;
    }

    /* Custom Input Fields Styling */
    div[data-baseweb="input"] > div {
        background-color: #111318 !important;
        border-color: #1f232d !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    
    div[data-baseweb="select"] > div {
        background-color: #111318 !important;
        border-color: #1f232d !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }

    /* Primary Submit Button Styling */
    div[data-testid="stForm"] .stButton > button {
        background: linear-gradient(90deg, #0284c7 0%, #0369a1 100%) !important;
        color: #ffffff !important;
        border: 1px solid #38bdf8 !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 10px 16px !important;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15);
        transition: all 0.2s ease;
    }
    
    div[data-testid="stForm"] .stButton > button:hover {
        background: linear-gradient(90deg, #0369a1 0%, #0284c7 100%) !important;
        box-shadow: 0 6px 16px rgba(56, 189, 248, 0.3);
    }
    </style>
""", unsafe_allow_html=True)

# Minimal Header
st.markdown('<div class="trade-title-minimal">Trade & Dividend Execution Desk</div>', unsafe_allow_html=True)
st.markdown('<div class="trade-subtitle-minimal">บันทึกรายการซื้อ ขาย และเงินปันผล ตัดสต็อกพอร์ตไปยัง Google Sheets อัตโนมัติ</div>', unsafe_allow_html=True)

# ==========================================
# 2. HELPER FUNCTION: GOOGLE SHEETS CONNECTION
# ==========================================
def get_gspread_client():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            return gspread.service_account_from_dict(cred_dict)
        else:
            st.error("🚨 ไม่พบ credentials_base64 ใน Streamlit Secrets")
            return None
    except Exception as e:
        st.error(f"🚨 เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {str(e)}")
        return None

gc = get_gspread_client()

# ==========================================
# 3. ACCOUNT & BROKER SELECTION CONTROL
# ==========================================
c_market, c_space = st.columns([1.5, 2.5])

with c_market:
    market_type = st.radio(
        "เลือกบัญชีที่ต้องการทำรายการ:",
        ("หุ้นไทย (Dime TH)", "หุ้นสหรัฐฯ (Dime US)"),
        horizontal=True,
        index=0
    )

sheet_name = "Dime_TH_Portfolio" if market_type == "หุ้นไทย (Dime TH)" else "Dime_Portfolio"
market_code = "TH" if market_type == "หุ้นไทย (Dime TH)" else "US"

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. MAIN EXECUTION TABS (3-TAB LAYOUT)
# ==========================================
if gc:
    try:
        sh = gc.open("หุ้นของเรา")
        ws_port = sh.worksheet(sheet_name)
        records = ws_port.get_all_records()
        df_current_port = pd.DataFrame(records)
        
        # ดึงรายชื่อหุ้นทั้งหมดในพอร์ตทุกหน้าเพื่อทำ Dropdown สรุปหุ้นปันผล
        all_existing_tickers = []
        for s_name in ["Dime_Portfolio", "Dime_TH_Portfolio"]:
            try:
                temp_records = sh.worksheet(s_name).get_all_records()
                for r in temp_records:
                    t_sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                    if t_sym and t_sym not in all_existing_tickers:
                        all_existing_tickers.append(t_sym)
            except Exception:
                pass
        all_existing_tickers.sort()

        tab_buy, tab_sell, tab_div = st.tabs([
            "🟢 บันทึกการซื้อ (Buy)", 
            "🔴 บันทึกการขาย (Sell)", 
            "💰 บันทึกปันผล (Dividend)"
        ])
        
        # ----------------------------------------------------
        # TAB 1: BUY ORDER
        # ----------------------------------------------------
        with tab_buy:
            st.caption(f"📌 เป้าหมาย Worksheet: `{sheet_name}` (หากมีหุ้นอยู่แล้วจะลบแถวเก่าเพื่ออัปเดตใหม่)")
            
            with st.form("buy_trade_form"):
                b_c1, b_c2 = st.columns(2)
                with b_c1:
                    buy_ticker = st.text_input("ชื่อหุ้น (Ticker Symbol):", placeholder="เช่น KKP, PTT, NVDA").strip().upper()
                    buy_qty = st.number_input("จำนวนหุ้นทั้งหมด (Total Qty):", min_value=0.0001, value=100.0, step=1.0)
                
                with b_c2:
                    buy_price = st.number_input("ต้นทุนต่อหุ้น (Cost per Share):", min_value=0.0001, value=50.0, step=0.10)
                    buy_date = st.date_input("วันที่ทำรายการซื้อ:", datetime.now(), key="buy_date_picker")
                
                total_buy_cost = buy_qty * buy_price
                st.markdown(f"<div style='margin: 10px 0; color: #9ca3af; font-size: 0.85rem;'>💰 มูลค่าเงินลงทุนรวมใหม่: <b style='color: #ffffff;'>{total_buy_cost:,.2f}</b></div>", unsafe_allow_html=True)
                
                submit_buy_btn = st.form_submit_button("📥 ยืนยันการอัปเดต / เพิ่มหุ้นเข้าพอร์ต", use_container_width=True)
                
                if submit_buy_btn:
                    if not buy_ticker:
                        st.error("⚠️ กรุณาระบุชื่อหุ้น (Ticker Symbol) ก่อนบันทึกครับ")
                    else:
                        with st.spinner("⏳ กำลังบันทึกข้อมูลลง Google Sheets..."):
                            cell_pattern = re.compile(rf"^{re.escape(buy_ticker)}$", re.IGNORECASE)
                            cell = ws_port.find(cell_pattern)
                            
                            new_row_data = [buy_ticker, buy_qty, buy_price]
                            
                            if cell is not None:
                                row_idx = cell.row
                                ws_port.delete_rows(row_idx)
                                ws_port.append_row(new_row_data)
                                st.success(f"✅ อัปเดตข้อมูลหุ้น {buy_ticker} เรียบร้อย! จำนวน: {buy_qty:,.2f} หุ้น | ต้นทุน: {buy_price:,.2f}")
                            else:
                                ws_port.append_row(new_row_data)
                                st.success(f"✅ เพิ่มหุ้นใหม่ {buy_ticker} เข้าพอร์ตเรียบร้อย! จำนวน: {buy_qty:,.2f} หุ้น | ต้นทุน: {buy_price:,.2f}")
                            
                            st.toast("🎉 บันทึกการซื้อสำเร็จ!", icon="✅")
                            st.rerun()

        # ----------------------------------------------------
        # TAB 2: SELL ORDER
        # ----------------------------------------------------
        with tab_sell:
            if not df_current_port.empty and "หุ้น (Ticker)" in df_current_port.columns:
                df_available = df_current_port[df_current_port["จำนวนหุ้น (Volume)"].astype(str).str.replace(',', '').astype(float) > 0]
                ticker_list = df_available["หุ้น (Ticker)"].astype(str).str.strip().str.upper().tolist()
                
                if ticker_list:
                    selected_ticker = st.selectbox("เลือกหุ้นที่ต้องการขาย:", ticker_list)
                    
                    selected_row = df_available[df_available["หุ้น (Ticker)"].astype(str).str.strip().str.upper() == selected_ticker].iloc[0]
                    current_qty = float(str(selected_row.get("จำนวนหุ้น (Volume)", 0)).replace(',', ''))
                    avg_cost = float(str(selected_row.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)).replace(',', ''))
                    
                    st.caption(f"💡 ข้อมูลปัจจุบันในพอร์ต: ถืออยู่ **{current_qty:,.2f}** หุ้น | ต้นทุนเฉลี่ย **{avg_cost:,.2f}**")
                    
                    with st.form("sell_trade_form"):
                        s_c1, s_c2 = st.columns(2)
                        with s_c1:
                            sell_qty = st.number_input("จำนวนหุ้นที่ขาย (Qty):", min_value=0.0001, max_value=current_qty, value=float(current_qty), step=1.0)
                            sell_price = st.number_input("ราคาขายต่อหุ้น (Sell Price):", min_value=0.0001, value=float(avg_cost), step=0.10)
                        
                        with s_c2:
                            sell_date = st.date_input("วันที่ทำรายการขาย:", datetime.now(), key="sell_date_picker")
                            net_received = st.number_input("ยอดเงินสุทธิที่ได้รับคืนหลังหักค่าธรรมเนียม:", min_value=0.0, value=float(sell_qty * sell_price))
                        
                        actual_sell_price = net_received / sell_qty if net_received > 0 else sell_price
                        pnl_per_share = actual_sell_price - avg_cost
                        total_pnl = pnl_per_share * sell_qty
                        pnl_pct = (pnl_per_share / avg_cost * 100) if avg_cost > 0 else 0
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        cp1, cp2, cp3 = st.columns(3)
                        with cp1:
                            st.markdown(f'<div class="preview-card"><div class="preview-label">ต้นทุนรวม</div><div class="preview-value">${sell_qty * avg_cost:,.2f}</div></div>', unsafe_allow_html=True)
                        with cp2:
                            st.markdown(f'<div class="preview-card"><div class="preview-label">มูลค่าขายสุทธิ</div><div class="preview-value">${net_received:,.2f}</div></div>', unsafe_allow_html=True)
                        with cp3:
                            pnl_color = "#4ade80" if total_pnl >= 0 else "#f87171"
                            sign = "+" if total_pnl >= 0 else ""
                            st.markdown(f'<div class="preview-card"><div class="preview-label">Realized PnL</div><div class="preview-value" style="color:{pnl_color};">{sign}${total_pnl:,.2f} ({pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        submit_sell_btn = st.form_submit_button("🚀 ยืนยันการตัดสต็อกและบันทึกปิดไม้", use_container_width=True)
                        
                        if submit_sell_btn:
                            with st.spinner("⏳ กำลังบันทึกข้อมูลและตัดสต็อกลง Google Sheets..."):
                                cell_pattern = re.compile(rf"^{re.escape(selected_ticker)}$", re.IGNORECASE)
                                cell = ws_port.find(cell_pattern)
                                
                                if cell is None:
                                    st.error(f"🚨 ไม่พบบรรทัดหุ้น '{selected_ticker}' ใน Sheet {sheet_name}")
                                else:
                                    row_idx = cell.row
                                    
                                    try:
                                        ws_closed = sh.worksheet("Dime_Closed_Orders")
                                    except:
                                        ws_closed = sh.add_worksheet(title="Dime_Closed_Orders", rows="1000", cols="10")
                                        ws_closed.append_row(["หุ้น (Ticker)", "ตลาด (US/TH)", "จำนวนหุ้น (Qty)", "ราคาซื้อเฉลี่ย (Buy Price)", "ราคาขายจริง (Sell Price)", "วันที่ปิดไม้ (Date)"])
                                    
                                    formatted_date = sell_date.strftime("%d/%m/%Y")
                                    new_closed_row = [
                                        selected_ticker,
                                        market_code,
                                        sell_qty,
                                        avg_cost,
                                        round(actual_sell_price, 4),
                                        formatted_date
                                    ]
                                    ws_closed.append_row(new_closed_row)
                                    
                                    remaining_qty = current_qty - sell_qty
                                    if remaining_qty <= 0.0001:
                                        ws_port.delete_rows(row_idx)
                                        st.success(f"✅ ปิดไม้หุ้น {selected_ticker} เรียบร้อย! ตัดออกจากพอร์ตคงเหลือแล้ว")
                                    else:
                                        ws_port.update_cell(row_idx, 2, remaining_qty)
                                        st.success(f"✅ บันทึกคำสั่งขายเรียบร้อย! หุ้น {selected_ticker} เหลือในพอร์ต {remaining_qty:,.2f} หุ้น")
                                    
                                    st.toast("🎉 บันทึกการขายและปิดไม้สำเร็จ!", icon="✅")
                                    st.rerun()
                else:
                    st.warning("⚠️ ไม่พบรายการหุ้นที่มีจำนวนถือครองในพอร์ตนี้")
            else:
                st.warning("⚠️ ไม่พบข้อมูลในตารางพอร์ตโฟลิโอ")

        # ----------------------------------------------------
        # TAB 3: DIVIDEND TRACKER (SELECT + CUSTOM INPUT)
        # ----------------------------------------------------
        with tab_div:
            st.caption("📌 เลือกหุ้นจากพอร์ตที่มีอยู่ หรือระบุชื่อหุ้นใหม่เอง แล้วบันทึกลง `Dividend_Tracker`")
            
            # ตัวเลือก Dropdown รวมตัวเลือกคีย์เอง
            dropdown_options = ["➕ พิมพ์ชื่อหุ้นใหม่ (Custom Ticker)..."] + all_existing_tickers
            
            with st.form("dividend_execution_form"):
                d_c1, d_c2 = st.columns(2)
                
                with d_c1:
                    div_date = st.date_input("วันที่รับเงิน (Date Received):", datetime.now(), key="div_date_picker")
                    
                    selected_div_option = st.selectbox(
                        "เลือกหุ้นที่ได้รับปันผล:",
                        dropdown_options,
                        index=1 if len(dropdown_options) > 1 else 0
                    )
                    
                    # ถ้าเลือกคีย์เอง -> แสดงช่อง Input
                    if selected_div_option == "➕ พิมพ์ชื่อหุ้นใหม่ (Custom Ticker)...":
                        div_ticker = st.text_input("ระบุชื่อหุ้น (Custom Ticker):", placeholder="เช่น NVDA, AAPL, PTT").strip().upper()
                    else:
                        div_ticker = selected_div_option
                        
                    div_amount = st.number_input("จำนวนเงินที่ได้รับ (Amount Received):", min_value=0.0001, value=1.00, step=0.05)
                
                with d_c2:
                    div_currency = st.selectbox("สกุลเงิน (Currency):", ["USD", "THB"], index=0 if market_code == "US" else 1)
                    div_broker = st.selectbox("โบรกเกอร์ (Broker):", ["DIME", "WEBULL", "OTHER"], index=0)
                
                st.markdown("<br>", unsafe_allow_html=True)
                submit_div_btn = st.form_submit_button("💰 ยืนยันการบันทึกเงินปันผล", use_container_width=True)
                
                if submit_div_btn:
                    if not div_ticker:
                        st.error("⚠️ กรุณาระบุหรือเลือกชื่อหุ้น (Ticker Symbol) ก่อนบันทึกครับ")
                    else:
                        with st.spinner("⏳ กำลังบันทึกข้อมูลเงินปันผลลง Google Sheets..."):
                            try:
                                ws_div = sh.worksheet("Dividend_Tracker")
                            except Exception:
                                ws_div = sh.add_worksheet(title="Dividend_Tracker", rows="1000", cols="5")
                                ws_div.append_row(["วันที่รับเงิน (Date)", "หุ้น (Ticker)", "จำนวนเงินที่ได้รับ (Amount)", "สกุลเงิน (Currency)", "โบรกเกอร์ (Broker)"])
                            
                            formatted_div_date = div_date.strftime("%d/%m/%Y")
                            new_div_row = [
                                formatted_div_date,
                                div_ticker,
                                round(div_amount, 2),
                                div_currency,
                                div_broker
                            ]
                            
                            ws_div.append_row(new_div_row)
                            st.success(f"✅ บันทึกปันผลหุ้น {div_ticker} จำนวน {div_amount:,.2f} {div_currency} เรียบร้อยแล้ว!")
                            st.toast("🎉 บันทึกเงินปันผลลง Dividend_Tracker สำเร็จ!", icon="💰")
                            st.rerun()

    except Exception as e:
        st.error(f"🚨 เกิดข้อผิดพลาดในการประมวลผล Google Sheets: {str(e)}")

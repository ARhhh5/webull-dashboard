import streamlit as st
import pandas as pd
import json
import base64
import re
import gspread
from datetime import datetime

st.set_page_config(page_title="Trade Execution & Order Closure", layout="wide")

st.title("🛒 บันทึกการปิดไม้ & ตัดสต็อกพอร์ตอัตโนมัติ (Trade Execution)")
st.markdown("ระบบบันทึกรายการขายหุ้นลง `Dime_Closed_Orders` พร้อมตัดจำนวนหุ้นคงเหลือใน Sheet พอร์ตรวมให้อัตโนมัติ")
st.markdown("---")

# ==========================================
# 1. Helper Function: Google Sheets Connection
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

# ==========================================
# 2. Form สำหรับเลือกหุ้นและบันทึกการขาย
# ==========================================
col_market, col_form = st.columns([1, 2])

with col_market:
    st.subheader("📌 1. เลือกตลาด / โบรกเกอร์")
    market_type = st.radio(
        "เลือกว่าต้องการปิดไม้ในตลาดใด:",
        ("หุ้นไทย (Dime TH)", "หุ้นสหรัฐฯ (Dime US)"),
        index=0
    )
    
    sheet_name = "Dime_TH_Portfolio" if market_type == "หุ้นไทย (Dime TH)" else "Dime_Portfolio"
    market_code = "TH" if market_type == "หุ้นไทย (Dime TH)" else "US"

gc = get_gspread_client()

if gc:
    try:
        sh = gc.open("หุ้นของเรา")
        ws_port = sh.worksheet(sheet_name)
        records = ws_port.get_all_records()
        df_current_port = pd.DataFrame(records)
        
        with col_form:
            st.subheader("📝 2. รายละเอียดคำสั่งขาย (Sell Order)")
            
            if not df_current_port.empty and "หุ้น (Ticker)" in df_current_port.columns:
                # กรองเอาเฉพาะหุ้นที่มีจำนวนมากกว่า 0
                df_available = df_current_port[df_current_port["จำนวนหุ้น (Volume)"].astype(str).str.replace(',', '').astype(float) > 0]
                ticker_list = df_available["หุ้น (Ticker)"].astype(str).str.strip().str.upper().tolist()
                
                if ticker_list:
                    selected_ticker = st.selectbox("เลือกหุ้นที่ทำการขาย:", ticker_list)
                    
                    # ดึงข้อมูลหุ้นที่เลือก
                    selected_row = df_available[df_available["หุ้น (Ticker)"].astype(str).str.strip().str.upper() == selected_ticker].iloc[0]
                    current_qty = float(str(selected_row.get("จำนวนหุ้น (Volume)", 0)).replace(',', ''))
                    avg_cost = float(str(selected_row.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)).replace(',', ''))
                    
                    st.info(f"💡 ข้อมูลปัจจุบันในพอร์ต: ถืออยู่ **{current_qty:,.2f}** หุ้น | ต้นทุนเฉลี่ย **{avg_cost:,.2f}**")
                    
                    with st.form("trade_execution_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            sell_qty = st.number_input(
                                "จำนวนหุ้นที่ขาย (Qty):",
                                min_value=0.0001,
                                max_value=current_qty,
                                value=float(current_qty),
                                step=1.0
                            )
                            sell_price = st.number_input(
                                "ราคาขายต่อหุ้น (Sell Price):",
                                min_value=0.0001,
                                value=float(avg_cost),
                                step=0.10
                            )
                        
                        with c2:
                            trade_date = st.date_input("วันที่ทำรายการขาย:", datetime.now())
                            net_received = st.number_input(
                                "ยอดเงินสุทธิที่ได้รับคืนหลังหักค่าธรรมเนียม (Optional):",
                                min_value=0.0,
                                value=float(sell_qty * sell_price),
                                help="หากระบุยอดเงินจากสลิปจริง ระบบจะคำนวณราคาขายจริงสุทธิให้อัตโนมัติ"
                            )
                        
                        # คำนวณพรีวิวผลการขาย
                        actual_sell_price = net_received / sell_qty if net_received > 0 else sell_price
                        pnl_per_share = actual_sell_price - avg_cost
                        total_pnl = pnl_per_share * sell_qty
                        pnl_pct = (pnl_per_share / avg_cost * 100) if avg_cost > 0 else 0
                        
                        st.markdown("---")
                        st.markdown("### 📊 สรุปผลกำไร/ขาดทุนการปิดไม้ (Preview)")
                        cp1, cp2, cp3 = st.columns(3)
                        cp1.metric("ต้นทุนรวม (Cost)", f"{sell_qty * avg_cost:,.2f}")
                        cp2.metric("มูลค่าขายสุทธิ (Net Revenue)", f"{net_received:,.2f}" if net_received > 0 else f"{sell_qty * sell_price:,.2f}")
                        
                        pnl_color = "normal" if total_pnl >= 0 else "inverse"
                        cp3.metric("กำไร/ขาดทุนสุทธิ (Realized PnL)", f"{total_pnl:+,.2f} ({pnl_pct:+.2f}%)", delta_color=pnl_color)
                        
                        submit_btn = st.form_submit_button("🚀 ยืนยันการตัดสต็อกและบันทึกปิดไม้", type="primary", use_container_width=True)
                        
                        if submit_btn:
                            with st.spinner("⏳ กำลังบันทึกข้อมูลและตัดสต็อกลง Google Sheets..."):
                                # 1. ค้นหาบรรทัดหุ้นใน Sheet แบบ Case-Insensitive (ยืดหยุ่น KKP / kkp)
                                cell_pattern = re.compile(rf"^{re.escape(selected_ticker)}$", re.IGNORECASE)
                                cell = ws_port.find(cell_pattern)
                                
                                if cell is None:
                                    st.error(f"🚨 ไม่พบบรรทัดหุ้น '{selected_ticker}' ใน Sheet {sheet_name} กรุณาตรวจสอบชื่อหุ้นใน Google Sheets")
                                else:
                                    row_idx = cell.row
                                    
                                    # 2. บันทึกลง Sheet: Dime_Closed_Orders
                                    try:
                                        ws_closed = sh.worksheet("Dime_Closed_Orders")
                                    except:
                                        ws_closed = sh.add_worksheet(title="Dime_Closed_Orders", rows="100", cols="10")
                                        ws_closed.append_row(["หุ้น (Ticker)", "ตลาด (US/TH)", "จำนวนหุ้น (Qty)", "ราคาซื้อเฉลี่ย (Buy Price)", "ราคาขายจริง (Sell Price)", "วันที่ปิดไม้ (Date)"])
                                    
                                    formatted_date = trade_date.strftime("%d/%m/%Y")
                                    new_closed_row = [
                                        selected_ticker,
                                        market_code,
                                        sell_qty,
                                        avg_cost,
                                        round(actual_sell_price, 4),
                                        formatted_date
                                    ]
                                    ws_closed.append_row(new_closed_row)
                                    
                                    # 3. ตัดสต็อก/อัปเดตพอร์ตคงเหลือ
                                    remaining_qty = current_qty - sell_qty
                                    
                                    if remaining_qty <= 0.0001:
                                        # ลบแถวออกหากขายหมดพอร์ต
                                        ws_port.delete_rows(row_idx)
                                        st.success(f"✅ ปิดไม้หุ้น {selected_ticker} เรียบร้อย! ตัดออกจากพอร์ตคงเหลือแล้ว")
                                    else:
                                        # อัปเดตจำนวนหุ้นคงเหลือใหม่ (คอลัมน์ B / Column 2 คือ จำนวนหุ้น)
                                        ws_port.update_cell(row_idx, 2, remaining_qty)
                                        st.success(f"✅ บันทึกคำสั่งขายเรียบร้อย! หุ้น {selected_ticker} เหลือในพอร์ต {remaining_qty:,.2f} หุ้น")
                                    
                                    st.balloons()
                                    st.rerun()
                else:
                    st.warning("⚠️ ไม่พบรายการหุ้นที่มีจำนวนถือครองในพอร์ตนี้")
            else:
                st.warning("⚠️ ไม่พบข้อมูลในตารางพอร์ตโฟลิโอ")
                
    except Exception as e:
        st.error(f"🚨 เกิดข้อผิดพลาดในการประมวลผล Google Sheets: {str(e)}")

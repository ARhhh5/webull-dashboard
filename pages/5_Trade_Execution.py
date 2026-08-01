import streamlit as st
import pandas as pd
import json
import base64
import re
import gspread
from datetime import datetime

st.set_page_config(page_title="Trade Execution & Order Management", layout="wide")

st.title("🛒 บันทึกรายการซื้อ-ขาย & อัปเดตพอร์ตอัตโนมัติ (Trade Execution)")
st.markdown("ระบบบันทึกรายการซื้อ (Buy) และขาย (Sell) ลง Google Sheets พร้อมตัดสต็อกและคำนวณต้นทุนเฉลี่ยให้อัตโนมัติ")
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
# 2. ส่วนเลือกตลาด / โบรกเกอร์
# ==========================================
col_market, col_main = st.columns([1, 3])

with col_market:
    st.subheader("📌 เลือกตลาด / โบรกเกอร์")
    market_type = st.radio(
        "เลือกบัญชีที่ต้องการทำรายการ:",
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
        
        with col_main:
            # สร้าง 2 แท็บสำหรับ ซื้อ และ ขาย
            tab_buy, tab_sell = st.tabs(["🟢 บันทึกคำสั่งซื้อ (Buy Order)", "🔴 บันทึกคำสั่งขาย (Sell Order)"])
            
            # ----------------------------------------------------
            # TAB 1: บันทึกคำสั่งซื้อ (BUY ORDER)
            # ----------------------------------------------------
            with tab_buy:
                st.subheader("📝 บันทึกการซื้อหุ้นเข้าพอร์ต (Add / DCA Position)")
                st.caption(f"ข้อมูลจะถูกนำไปอัปเดตหรือเพิ่มใน Sheet: `{sheet_name}`")
                
                with st.form("buy_trade_form"):
                    b_c1, b_c2 = st.columns(2)
                    with b_c1:
                        buy_ticker = st.text_input("ชื่อหุ้น (Ticker Symbol):", placeholder="เช่น KKP, PTT, NVDA").strip().upper()
                        buy_qty = st.number_input("จำนวนหุ้นที่ซื้อ (Qty):", min_value=0.0001, value=100.0, step=1.0)
                    
                    with b_c2:
                        buy_price = st.number_input("ราคาซื้อต่อหุ้น (Buy Price):", min_value=0.0001, value=50.0, step=0.10)
                        buy_date = st.date_input("วันที่ทำรายการซื้อ:", datetime.now(), key="buy_date_picker")
                    
                    total_buy_cost = buy_qty * buy_price
                    st.markdown("---")
                    st.markdown(f"💰 **มูลค่าเงินลงทุนรวมในไม้นี้:** `{total_buy_cost:,.2f}`")
                    
                    submit_buy_btn = st.form_submit_button("📥 ยืนยันการเพิ่มหุ้นเข้าพอร์ต", type="primary", use_container_width=True)
                    
                    if submit_buy_btn:
                        if not buy_ticker:
                            st.error("⚠️ กรุณาระบุชื่อหุ้น (Ticker Symbol) ก่อนบันทึกครับ")
                        else:
                            with st.spinner("⏳ กำลังบันทึกข้อมูลและคำนวณต้นทุนเฉลี่ยใหม่..."):
                                cell_pattern = re.compile(rf"^{re.escape(buy_ticker)}$", re.IGNORECASE)
                                cell = ws_port.find(cell_pattern)
                                
                                if cell is not None:
                                    # มีหุ้นตัวนี้ในพอร์ตอยู่แล้ว -> คำนวณ Weighted Average Cost ใหม่
                                    row_idx = cell.row
                                    
                                    # อ่านค่าเดิมจาก Sheet
                                    old_qty_val = ws_port.cell(row_idx, 2).value
                                    old_cost_val = ws_port.cell(row_idx, 3).value
                                    
                                    old_qty = float(str(old_qty_val).replace(',', '')) if old_qty_val else 0.0
                                    old_cost = float(str(old_cost_val).replace(',', '')) if old_cost_val else 0.0
                                    
                                    new_total_qty = old_qty + buy_qty
                                    new_weighted_cost = ((old_qty * old_cost) + (buy_qty * buy_price)) / new_total_qty if new_total_qty > 0 else 0.0
                                    
                                    # อัปเดตกลับลง Sheet (Col 2 = Qty, Col 3 = Avg Cost)
                                    ws_port.update_cell(row_idx, 2, new_total_qty)
                                    ws_port.update_cell(row_idx, 3, round(new_weighted_cost, 4))
                                    
                                    st.success(f"✅ อัปเดตหุ้น {buy_ticker} เรียบร้อย! จำนวนรวม: {new_total_qty:,.2f} หุ้น | ต้นทุนเฉลี่ยใหม่: {new_weighted_cost:,.2f}")
                                else:
                                    # ยังไม่มีหุ้นตัวนี้ในพอร์ต -> เพิ่มบรรทัดใหม่ (Append Row)
                                    new_row = [buy_ticker, buy_qty, buy_price]
                                    ws_port.append_row(new_row)
                                    st.success(f"✅ เพิ่มหุ้นใหม่ {buy_ticker} เข้าพอร์ตเรียบร้อย! จำนวน: {buy_qty:,.2f} หุ้น @ {buy_price:,.2f}")
                                
                                st.balloons()
                                st.rerun()

            # ----------------------------------------------------
            # TAB 2: บันทึกคำสั่งขาย (SELL ORDER)
            # ----------------------------------------------------
            with tab_sell:
                st.subheader("📝 บันทึกการขายหุ้น & ปิดไม้ (Sell / Close Order)")
                
                if not df_current_port.empty and "หุ้น (Ticker)" in df_current_port.columns:
                    df_available = df_current_port[df_current_port["จำนวนหุ้น (Volume)"].astype(str).str.replace(',', '').astype(float) > 0]
                    ticker_list = df_available["หุ้น (Ticker)"].astype(str).str.strip().str.upper().tolist()
                    
                    if ticker_list:
                        selected_ticker = st.selectbox("เลือกหุ้นที่ต้องการขาย:", ticker_list)
                        
                        selected_row = df_available[df_available["หุ้น (Ticker)"].astype(str).str.strip().str.upper() == selected_ticker].iloc[0]
                        current_qty = float(str(selected_row.get("จำนวนหุ้น (Volume)", 0)).replace(',', ''))
                        avg_cost = float(str(selected_row.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)).replace(',', ''))
                        
                        st.info(f"💡 ข้อมูลปัจจุบันในพอร์ต: ถืออยู่ **{current_qty:,.2f}** หุ้น | ต้นทุนเฉลี่ย **{avg_cost:,.2f}**")
                        
                        with st.form("sell_trade_form"):
                            s_c1, s_c2 = st.columns(2)
                            with s_c1:
                                sell_qty = st.number_input("จำนวนหุ้นที่ขาย (Qty):", min_value=0.0001, max_value=current_qty, value=float(current_qty), step=1.0)
                                sell_price = st.number_input("ราคาขายต่อหุ้น (Sell Price):", min_value=0.0001, value=float(avg_cost), step=0.10)
                            
                            with s_c2:
                                sell_date = st.date_input("วันที่ทำรายการขาย:", datetime.now(), key="sell_date_picker")
                                net_received = st.number_input("ยอดเงินสุทธิที่ได้รับคืนหลังหักค่าธรรมเนียม (Optional):", min_value=0.0, value=float(sell_qty * sell_price))
                            
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
                            
                            submit_sell_btn = st.form_submit_button("🚀 ยืนยันการตัดสต็อกและบันทึกปิดไม้", type="primary", use_container_width=True)
                            
                            if submit_sell_btn:
                                with st.spinner("⏳ กำลังบันทึกข้อมูลและตัดสต็อกลง Google Sheets..."):
                                    cell_pattern = re.compile(rf"^{re.escape(selected_ticker)}$", re.IGNORECASE)
                                    cell = ws_port.find(cell_pattern)
                                    
                                    if cell is None:
                                        st.error(f"🚨 ไม่พบบรรทัดหุ้น '{selected_ticker}' ใน Sheet {sheet_name}")
                                    else:
                                        row_idx = cell.row
                                        
                                        # 1. บันทึกลง Sheet: Dime_Closed_Orders
                                        try:
                                            ws_closed = sh.worksheet("Dime_Closed_Orders")
                                        except:
                                            ws_closed = sh.add_worksheet(title="Dime_Closed_Orders", rows="100", cols="10")
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
                                        
                                        # 2. ตัดสต็อกพอร์ตคงเหลือ
                                        remaining_qty = current_qty - sell_qty
                                        
                                        if remaining_qty <= 0.0001:
                                            ws_port.delete_rows(row_idx)
                                            st.success(f"✅ ปิดไม้หุ้น {selected_ticker} เรียบร้อย! ตัดออกจากพอร์ตคงเหลือแล้ว")
                                        else:
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

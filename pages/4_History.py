import streamlit as st
import pandas as pd
import numpy as np
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Trade History & Realized P/L", layout="wide")

st.title("📜 ประวัติการเทรด และคำนวณกำไร/ขาดทุน (Realized P/L)")

# -----------------------------------------------------------------------------
# Helper Function: FIFO Calculation
# -----------------------------------------------------------------------------
def calculate_fifo_pnl(df_symbol):
    """
    คำนวณ Realized P/L ด้วยเกณฑ์ FIFO (ซื้อก่อน ขายก่อน)
    เรียงตามลำดับเวลาอย่างถูกต้อง
    """
    df_sorted = df_symbol.copy()
    
    # แปลงเวลาให้รองรับทั้ง Timestamp และ Date String
    if pd.api.types.is_numeric_dtype(df_sorted['Time']):
        df_sorted['DateTime'] = pd.to_datetime(df_sorted['Time'], unit='ms', errors='coerce')
    else:
        df_sorted['DateTime'] = pd.to_datetime(df_sorted['Time'], errors='coerce')
        
    df_sorted = df_sorted.sort_values(by='DateTime', ascending=True)

    buy_queue = []
    closed_qty = 0.0
    total_cost_closed = 0.0
    total_revenue_closed = 0.0

    for _, row in df_sorted.iterrows():
        side = str(row['Side']).strip().upper()
        try:
            qty = float(row['Qty'])
            price = float(row['Price'])
        except (ValueError, TypeError):
            continue

        if 'BUY' in side:
            buy_queue.append({'qty': qty, 'price': price})
        elif 'SELL' in side:
            qty_to_sell = qty
            
            while qty_to_sell > 0 and buy_queue:
                earliest_buy = buy_queue[0]
                
                if earliest_buy['qty'] <= qty_to_sell:
                    matched_qty = earliest_buy['qty']
                    qty_to_sell -= matched_qty
                    cost = matched_qty * earliest_buy['price']
                    revenue = matched_qty * price
                    
                    closed_qty += matched_qty
                    total_cost_closed += cost
                    total_revenue_closed += revenue
                    buy_queue.pop(0)
                else:
                    matched_qty = qty_to_sell
                    earliest_buy['qty'] -= matched_qty
                    qty_to_sell = 0
                    cost = matched_qty * earliest_buy['price']
                    revenue = matched_qty * price
                    
                    closed_qty += matched_qty
                    total_cost_closed += cost
                    total_revenue_closed += revenue

    remaining_qty = sum(b['qty'] for b in buy_queue)
    realized_pnl = total_revenue_closed - total_cost_closed
    
    avg_buy_price = (total_cost_closed / closed_qty) if closed_qty > 0 else 0.0
    avg_sell_price = (total_revenue_closed / closed_qty) if closed_qty > 0 else 0.0
    pnl_percent = ((realized_pnl / total_cost_closed) * 100) if total_cost_closed > 0 else 0.0

    status = "ยังไม่ได้ขาย"
    if closed_qty > 0 and remaining_qty > 0:
        status = "ขายแล้วบางส่วน"
    elif closed_qty > 0 and remaining_qty == 0:
        status = "ปิดออเดอร์ทั้งหมดแล้ว"

    return {
        'closed_qty': closed_qty,
        'remaining_qty': remaining_qty,
        'avg_buy_price': avg_buy_price,
        'avg_sell_price': avg_sell_price,
        'total_cost_closed': total_cost_closed,
        'total_revenue_closed': total_revenue_closed,
        'realized_pnl': realized_pnl,
        'pnl_percent': pnl_percent,
        'status': status
    }

# -----------------------------------------------------------------------------
# Data Loading Strategy (Session State -> Direct Load Fallback)
# -----------------------------------------------------------------------------
df = None

if 'webull_df' in st.session_state and st.session_state['webull_df'] is not None:
    df = st.session_state['webull_df']
else:
    # โหลดตรงจาก Google Sheets / Local Cache หากใน Session State ไม่มีข้อมูล
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # ลองดึงคีย์จาก Streamlit Secrets
        if "gcp_service_account" in st.secrets:
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
            client = gspread.authorize(creds)
            sheet = client.open("หุ้นของเรา").worksheet("Webull_Order_History")
            data = sheet.get_all_records()
            df = pd.DataFrame(data)
            st.session_state['webull_df'] = df
    except Exception as e:
        df = None

# -----------------------------------------------------------------------------
# Render UI
# -----------------------------------------------------------------------------
if df is not None and not df.empty:
    symbols = df['Symbol'].unique()
    results = []

    for sym in symbols:
        df_sym = df[df['Symbol'] == sym]
        res = calculate_fifo_pnl(df_sym)
        
        if res['closed_qty'] > 0:
            results.append({
                'ชื่อหุ้น': sym,
                'โบรกเกอร์': 'Webull',
                'จำนวนหุ้นที่ปิดขายแล้ว': res['closed_qty'],
                'ราคาซื้อเฉลี่ย ($)': res['avg_buy_price'],
                'ราคาขายเฉลี่ย ($)': res['avg_sell_price'],
                'กำไร/ขาดทุนสุทธิ ($)': res['realized_pnl'],
                'ผลตอบแทน (%)': res['pnl_percent'],
                'สถานะ': res['status']
            })

    report_df = pd.DataFrame(results)

    if not report_df.empty:
        def highlight_pnl(val):
            color = '#00E676' if val > 0 else ('#FF5252' if val < 0 else 'white')
            return f'color: {color}; font-weight: bold;'

        st.subheader("📊 ตารางสรุปผลกำไร/ขาดทุนจากการขายจริง (FIFO Method)")
        
        total_pnl = report_df['กำไร/ขาดทุนสุทธิ ($)'].sum()
        col1, col2, col3 = st.columns(3)
        col1.metric("กำไร/ขาดทุนรวมทั้งหมด", f"${total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")
        col2.metric("จำนวนหุ้นที่เคยขายปิดรอบ", f"{len(report_df)} ตัว")
        col3.metric("หุ้นที่ชนะ (Win Trade)", f"{len(report_df[report_df['กำไร/ขาดทุนสุทธิ ($)'] > 0])} ตัว")

        st.dataframe(
            report_df.style.format({
                'จำนวนหุ้นที่ปิดขายแล้ว': '{:,.2f}',
                'ราคาซื้อเฉลี่ย ($)': '${:,.2f}',
                'ราคาขายเฉลี่ย ($)': '${:,.2f}',
                'กำไร/ขาดทุนสุทธิ ($)': '${:,.2f}',
                'ผลตอบแทน (%)': '{:+.2f}%'
            }).map(highlight_pnl, subset=['กำไร/ขาดทุนสุทธิ ($)', 'ผลตอบแทน (%)']),
            use_container_width=True
        )
    else:
        st.warning("ไม่พบประวัติการขายหุ้นในระบบ")
else:
    st.info("💡 ไม่พบข้อมูลในระบบ กรุณาตรวจสอบการเชื่อมต่อ Google Sheets หรืออัปโหลดไฟล์ในหน้าหลัก (app.py) อีกครั้งครับ")

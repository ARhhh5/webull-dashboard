import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf
import plotly.express as px

st.title("💵 ระบบติดตามเงินปันผลรวม (Dividend Tracker)")
st.markdown("---")

# 1. ปุ่มสลับสกุลเงินหลักในการแสดงผล Dashboard
currency_mode = st.radio("💱 เลือกสกุลเงินหลักในการแสดงผลรายได้เงินปันผล:", ("แสดงเป็นเงินบาท (฿ THB)", "แสดงเป็นดอลลาร์ ($ USD)"), horizontal=True)

# ฟังก์ชันดึงอัตราแลกเปลี่ยนเรียลไทม์
@st.cache_data(ttl=3600)
def get_usd_thb_rate():
    try:
        # ดึงราคาคู่เงิน USD/THB จากตลาดโลก
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0 # ค่าดักเผื่อระบบดึงไม่ได้ชั่วคราว

fx_rate = get_usd_thb_rate()

# ฟังก์ชันโหลดข้อมูลปันผลจาก Google Sheet
def load_dividend_data():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64:
            st.warning("⚠️ ไม่พบกุญแจ Google ใน Secrets")
            return []
            
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        
        sh = gc.open("หุ้นของเรา")
        worksheet = sh.worksheet("Dividend_Tracker")
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"❌ ดึงข้อมูลเงินปันผลไม่สำเร็จ: {str(e)}")
        return []

records = load_dividend_data()

if records:
    df = pd.DataFrame(records)
    
    # เคลียร์ชื่อฟิลด์ให้ปลอดภัย
    df.columns = [c.strip() for c in df.columns]
    
    # แปลงข้อมูลตัวเลข
    df['Amount'] = df['จำนวนเงินที่ได้รับ (Amount)'].astype(float)
    df['Currency'] = df['สกุลเงิน (Currency)'].str.strip().str.upper()
    df['Ticker'] = df['หุ้น (Ticker)'].str.strip().str.upper()
    df['Broker'] = df['โบรกเกอร์ (Broker)'].str.strip()
    df['Date'] = pd.to_datetime(df['วันที่รับเงิน (Date)'])
    df['Month_Year'] = df['Date'].dt.strftime('%Y-%m')
    
    # 2. ตรรกะแปลงค่าเงิน (Normalize)
    # ถ้าเลือกแสดงเป็น THB -> แปลงตัวที่เป็น USD ให้คูณ fx_rate
    # ถ้าเลือกแสดงเป็น USD -> แปลงตัวที่เป็น THB ให้หาร fx_rate
    def normalize_currency(row):
        amt = row['Amount']
        curr = row['Currency']
        
        if "บาท" in currency_mode:
            if curr == "USD":
                return amt * fx_rate
            return amt  # เป็น THB อยู่แล้ว
        else:
            if curr == "THB":
                return amt / fx_rate
            return amt  # เป็น USD อยู่แล้ว

    df['Normalized_Amount'] = df.apply(normalize_currency, axis=1)
    
    # คำนวณยอดรวมสุทธิ
    total_dividend_all = df['Normalized_Amount'].sum()
    
    # แยกยอดตามโบรกเกอร์
    df_broker = df.groupby('Broker')['Normalized_Amount'].sum().reset_index()
    
    # --- กล่องสรุปผลด้านบน ---
    st.markdown(f"📊 *อ้างอิงอัตราแลกเปลี่ยนปัจจุบัน: 1 USD = {fx_rate:,.2f} THB*")
    
    if "บาท" in currency_mode:
        st.success(f"💰 **รวมรายได้ปันผลเข้ากระเป๋าทั้งสิ้น:** ฿{total_dividend_all:,.2f} บาท")
    else:
        st.success(f"💰 **รวมรายได้ปันผลเข้ากระเป๋าทั้งสิ้น:** ${total_dividend_all:,.2f} USD")
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # --- ส่วนการสร้างกราฟวิเคราะห์ ---
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📅 กระแสเงินสดเงินปันผลรายเดือน (Monthly Passive Income)")
        df_monthly = df.groupby('Month_Year')['Normalized_Amount'].sum().reset_index()
        fig_bar = px.bar(df_monthly, x='Month_Year', y='Normalized_Amount', 
                         labels={'Normalized_Amount': 'เงินปันผลรวม', 'Month_Year': 'เดือน'},
                         color_discrete_sequence=['#00c853'])
        fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col2:
        st.subheader("🏆 สัดส่วนเงินปันผลแยกตามรายหุ้น (Dividend Share)")
        df_ticker = df.groupby('Ticker')['Normalized_Amount'].sum().reset_index()
        fig_pie = px.pie(df_ticker, values='Normalized_Amount', names='Ticker', hole=0.4,
                         color_discrete_sequence=px.colors.sequential.Agsunset)
        fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="white"))
        st.plotly_chart(fig_pie, use_container_width=True)
        
    # --- แสดงตารางประวัติปันผลย้อนหลัง ---
    st.markdown("---")
    st.subheader("📋 บันทึกประวัติรับเงินปันผลทั้งหมด")
    
    display_df = pd.DataFrame({
        "วันที่": df['Date'].dt.strftime('%Y-%m-%d'),
        "ชื่อหุ้น": df['Ticker'],
        "เงินปันผลที่คีย์": df['Amount'].map(lambda x: f"{x:,.2f}"),
        "สกุลเงินเดิม": df['Currency'],
        "คำนวณเป็นเงินแสดงผล": df['Normalized_Amount'].map(lambda x: f"฿{x:,.2f}" if "บาท" in currency_mode else f"${x:,.2f}"),
        "รับผ่านโบรกเกอร์": df['Broker']
    })
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
else:
    st.info("💡 เปิดใช้งานระบบสำเร็จแล้ว! ให้นายลองเข้าไปกรอกข้อมูลรับเงินปันผลในแท็บ 'Dividend_Tracker' บน Google Sheet ได้เลยเพื่อน")

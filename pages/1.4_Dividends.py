import base64
import json
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="Dividend Income Analytics", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Minimal Modern Header */
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

    /* Metric Cards */
    .metric-card {
        background-color: #0f1115;
        padding: 16px 20px;
        border-radius: 12px;
        border: 1px solid #1a1d24;
        text-align: center;
    }
    .metric-label {
        color: #9ca3af;
        font-size: 12px;
        font-weight: 600;
        margin-bottom: 4px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 800;
        color: #ffffff;
        font-family: 'JetBrains Mono', monospace;
    }
    .text-cyan { color: #38bdf8 !important; }
    .text-green { color: #4ade80 !important; }
    .text-purple { color: #c084fc !important; }

    /* Chart Container Card */
    .chart-card {
        background-color: #0f1115;
        border: 1px solid #1a1d24;
        border-radius: 14px;
        padding: 18px;
        margin-top: 10px;
    }
    .chart-card-title {
        font-size: 0.9rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Custom Input Controls */
    div[data-baseweb="select"] > div {
        background-color: #0f1115 !important;
        border-color: #1a1d24 !important;
        color: #ffffff !important;
        border-radius: 8px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Minimal Header
st.markdown('<div class="page-title-minimal">Dividend Income Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">วิเคราะห์กระแสเงินสดจากเงินปันผลสะสม รายเดือน และสัดส่วนรายหุ้น</div>', unsafe_allow_html=True)

# ==========================================
# 2. HELPER FUNCTIONS & DATA LOADING
# ==========================================
@st.cache_data(ttl=300)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except Exception:
        return 35.0

fx_rate = get_usd_thb_rate()

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

def load_dividend_data():
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()
    
    try:
        sh = gc.open("หุ้นของเรา")
        try:
            ws = sh.worksheet("Dividend_Tracker")
        except Exception:
            return pd.DataFrame()
            
        records = ws.get_all_records()
        if not records:
            return pd.DataFrame()
            
        df = pd.DataFrame(records)
        
        # 1. Clean Column Names & Remove Duplicate Columns
        df.columns = [str(col).strip() for col in df.columns]
        df = df.loc[:, ~df.columns.duplicated()]
        
        # 2. Flexible Column Name Mapping
        col_map = {}
        for col in df.columns:
            c_str = str(col).lower()
            if "วัน" in c_str or "date" in c_str:
                col_map[col] = "Date"
            elif "หุ้น" in c_str or "ticker" in c_str:
                col_map[col] = "Ticker"
            elif "เงิน" in c_str or "amount" in c_str:
                col_map[col] = "Amount"
            elif "สกุล" in c_str or "curr" in c_str:
                col_map[col] = "Currency"
            elif "โบรก" in c_str or "broker" in c_str:
                col_map[col] = "Broker"
            
        df = df.rename(columns=col_map)
        
        # 3. Ensure All Required Columns Exist
        required_cols = ["Date", "Ticker", "Amount", "Currency", "Broker"]
        for rc in required_cols:
            if rc not in df.columns:
                df[rc] = "" if rc in ["Ticker", "Currency", "Broker"] else 0

        # 4. Handle Case If Multiple Columns Mapped to Same Target (Force Series)
        clean_df = pd.DataFrame()
        for rc in required_cols:
            col_data = df[rc]
            if isinstance(col_data, pd.DataFrame):
                clean_df[rc] = col_data.iloc[:, 0]
            else:
                clean_df[rc] = col_data

        # 5. Safe Data Types Parsing
        clean_df["Date"] = pd.to_datetime(clean_df["Date"].astype(str), format="%d/%m/%Y", errors='coerce')
        
        null_dates = clean_df["Date"].isna()
        if null_dates.any():
            clean_df.loc[null_dates, "Date"] = pd.to_datetime(df.loc[null_dates, "Date"], dayfirst=True, errors='coerce')

        clean_df["Amount"] = pd.to_numeric(clean_df["Amount"].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        clean_df["Ticker"] = clean_df["Ticker"].astype(str).str.strip().str.upper()
        clean_df["Currency"] = clean_df["Currency"].astype(str).str.strip().str.upper()
        clean_df["Broker"] = clean_df["Broker"].astype(str).str.strip().str.upper()
        
        # 6. Correct Currency Normalization Logic
        # Amount_USD: If already USD, keep Amount. If THB, convert to USD (/ fx_rate)
        clean_df["Amount_USD"] = clean_df.apply(
            lambda r: r["Amount"] if r["Currency"] == "USD" else (r["Amount"] / fx_rate if fx_rate > 0 else r["Amount"]),
            axis=1
        )
        
        # Amount_THB: If already THB, keep Amount. If USD, convert to THB (* fx_rate)
        clean_df["Amount_THB"] = clean_df.apply(
            lambda r: r["Amount"] * fx_rate if r["Currency"] == "USD" else r["Amount"],
            axis=1
        )
        
        clean_df["YearMonth"] = clean_df["Date"].dt.strftime("%Y-%m")
        clean_df["Month_Name"] = clean_df["Date"].dt.strftime("%b %Y")
        
        return clean_df.dropna(subset=["Date"])
        
    except Exception as e:
        st.error(f"❌ เกิดข้อผิดพลาดในการโหลดข้อมูล: {str(e)}")
        return pd.DataFrame()

df_div = load_dividend_data()

# ==========================================
# 3. CONTROL & CURRENCY SWITCHER
# ==========================================
c_curr, c_space = st.columns([1.5, 2.5])
with c_curr:
    currency_mode = st.radio(
        "แสดงผลตามสกุลเงิน:",
        ("USD ($)", "THB (฿)"),
        horizontal=True,
        index=0
    )

is_thb = "THB" in currency_mode
curr_sym = "฿" if is_thb else "$"
amt_col = "Amount_THB" if is_thb else "Amount_USD"

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. MAIN ANALYTICS DASHBOARD
# ==========================================
if not df_div.empty:
    total_dividend = df_div[amt_col].sum()
    unique_months = df_div["YearMonth"].nunique() or 1
    avg_monthly = total_dividend / unique_months
    
    top_ticker_row = df_div.groupby("Ticker")[amt_col].sum().reset_index().sort_values(by=amt_col, ascending=False)
    top_ticker_name = top_ticker_row.iloc[0]["Ticker"] if not top_ticker_row.empty else "-"
    top_ticker_val = top_ticker_row.iloc[0][amt_col] if not top_ticker_row.empty else 0

    # Summary Metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">รวมรายได้ปันผลทั้งหมด</div><div class="metric-value text-green">{curr_sym}{total_dividend:,.2f}</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-label">เฉลี่ยต่อเดือน</div><div class="metric-value text-cyan">{curr_sym}{avg_monthly:,.2f}</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="metric-label">หุ้นปันผลอันดับ 1 ({top_ticker_name})</div><div class="metric-value text-purple">{curr_sym}{top_ticker_val:,.2f}</div></div>', unsafe_allow_html=True)

    st.caption(f"ℹ️ อัตราแลกเปลี่ยนอ้างอิง: 1 USD = {fx_rate:.2f} THB")
    st.markdown("---")

    # ----------------------------------------------------
    # CHARTS SECTION (MONTHLY BAR + TICKER DONUT)
    # ----------------------------------------------------
    cg1, cg2 = st.columns([1.2, 1])

    with cg1:
        st.markdown('<div class="chart-card"><div class="chart-card-title">📅 กระแสเงินสดปันผลรายเดือน (Monthly Passive Income)</div>', unsafe_allow_html=True)
        
        df_monthly = df_div.groupby(["YearMonth", "Month_Name"])[amt_col].sum().reset_index().sort_values(by="YearMonth")
        
        fig_bar = go.Figure(data=[
            go.Bar(
                x=df_monthly["Month_Name"],
                y=df_monthly[amt_col],
                marker=dict(
                    color=df_monthly[amt_col],
                    colorscale='Blues',
                    line=dict(color='#38bdf8', width=1.5)
                ),
                text=[f"{curr_sym}{v:,.2f}" for v in df_monthly[amt_col]],
                textposition='auto',
                hovertemplate="<b>%{x}</b><br>ปันผลที่ได้รับ: " + curr_sym + "%{y:,.2f}<extra></extra>"
            )
        ])
        fig_bar.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#9ca3af', family='Plus Jakarta Sans'),
            xaxis=dict(showgrid=False, color='#6b7280'),
            yaxis=dict(showgrid=True, gridcolor='#1f232d', color='#6b7280'),
            margin=dict(t=10, b=10, l=10, r=10),
            height=290
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    with cg2:
        st.markdown('<div class="chart-card"><div class="chart-card-title">🏆 สัดส่วนปันผลแยกตามรายหุ้น (Dividend Share)</div>', unsafe_allow_html=True)
        
        df_ticker = df_div.groupby("Ticker")[amt_col].sum().reset_index().sort_values(by=amt_col, ascending=False)
        
        fig_pie = go.Figure(data=[go.Pie(
            labels=df_ticker["Ticker"],
            values=df_ticker[amt_col],
            hole=0.6,
            textinfo='label+percent',
            hovertemplate="<b>%{label}</b><br>ปันผลสะสม: " + curr_sym + "%{value:,.2f}<br>สัดส่วน: %{percent}<extra></extra>",
            marker=dict(colors=['#38bdf8', '#818cf8', '#c084fc', '#34d399', '#f472b6', '#fbbf24', '#a3e635'])
        )])
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#9ca3af', family='Plus Jakarta Sans'),
            margin=dict(t=10, b=10, l=10, r=10),
            height=290,
            showlegend=False
        )
        st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ----------------------------------------------------
    # INTERACTIVE DRILL-DOWN SECTION
    # ----------------------------------------------------
    st.markdown("### 🔍 เจาะลึกข้อมูลปันผล (Interactive Drill-down)")
    
    view_tab1, view_tab2 = st.tabs(["📅 แยกดูรายเดือน (Monthly Breakdowns)", "📌 แยกดูรายหุ้น (By Ticker)"])
    
    with view_tab1:
        month_list = ["ทั้งหมด (All Months)"] + sorted(df_div["Month_Name"].unique().tolist(), reverse=True)
        selected_month = st.selectbox("เลือกเดือนที่ต้องการดูรายละเอียด:", month_list, key="select_month_drill")
        
        if selected_month != "ทั้งหมด (All Months)":
            df_filtered_m = df_div[df_div["Month_Name"] == selected_month]
        else:
            df_filtered_m = df_div.copy()
            
        if not df_filtered_m.empty:
            df_m_disp = df_filtered_m[["Date", "Ticker", "Broker", "Currency", "Amount", amt_col]].copy()
            df_m_disp["Date"] = df_m_disp["Date"].dt.strftime("%d/%m/%Y")
            df_m_disp.columns = ["วันที่รับเงิน", "หุ้น (Ticker)", "โบรกเกอร์", "สกุลเงินเดิม", "ปันผลที่ได้รับ (Original)", f"มูลค่าในระบบ ({curr_sym})"]
            
            st.dataframe(
                df_m_disp.style.format({
                    "ปันผลที่ได้รับ (Original)": "{:,.2f}",
                    f"มูลค่าในระบบ ({curr_sym})": f"{curr_sym}{{:,.2f}}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ไม่พบข้อมูลปันผลในเดือนที่เลือก")

    with view_tab2:
        ticker_list = ["ทั้งหมด (All Tickers)"] + sorted(df_div["Ticker"].unique().tolist())
        selected_ticker = st.selectbox("เลือกหุ้นที่ต้องการดูประวัติปันผล:", ticker_list, key="select_ticker_drill")
        
        if selected_ticker != "ทั้งหมด (All Tickers)":
            df_filtered_t = df_div[df_div["Ticker"] == selected_ticker]
        else:
            df_filtered_t = df_div.copy()
            
        if not df_filtered_t.empty:
            ticker_sum = df_filtered_t[amt_col].sum()
            st.caption(f"💰 ปันผลสะสมจากหุ้นกลุ่มนี้: **{curr_sym}{ticker_sum:,.2f}**")
            
            df_t_disp = df_filtered_t[["Date", "Ticker", "Broker", "Currency", "Amount", amt_col]].copy()
            df_t_disp["Date"] = df_t_disp["Date"].dt.strftime("%d/%m/%Y")
            df_t_disp.columns = ["วันที่รับเงิน", "หุ้น (Ticker)", "โบรกเกอร์", "สกุลเงินเดิม", "ปันผลที่ได้รับ (Original)", f"มูลค่าในระบบ ({curr_sym})"]
            
            st.dataframe(
                df_t_disp.style.format({
                    "ปันผลที่ได้รับ (Original)": "{:,.2f}",
                    f"มูลค่าในระบบ ({curr_sym})": f"{curr_sym}{{:,.2f}}"
                }),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ไม่พบข้อมูลปันผลสำหรับหุ้นที่เลือก")

else:
    st.info("💡 เปิดใช้งานระบบสำเร็จ! หากพบค่านี่แสดงว่ายังไม่มีข้อมูลปันผลใน Google Sheets หรือรูปแบบวันที่ไม่ถูกต้อง สามารถไปบันทึกปันผลใหม่ได้ที่เมนู Trade Execution Desk ครับ")

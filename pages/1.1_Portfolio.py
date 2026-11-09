import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import yfinance as yf

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ==========================================
# 1. PAGE STYLE & COMPACT PILL NAVIGATION CSS
# ==========================================
st.markdown("""
    <style>
    /* Minimal Header Style */
    .page-title-minimal {
        font-size: 1.5rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin-bottom: 2px;
    }
    .page-subtitle-minimal {
        color: #6b7280;
        font-size: 0.85rem;
        margin-bottom: 15px;
    }

    /* Metric Cards */
    .metric-card {
        background-color: #0f1115;
        padding: 18px;
        border-radius: 12px;
        border: 1px solid #1a1d24;
        text-align: center;
        margin-bottom: 15px;
    }
    .metric-label {
        color: #9ca3af;
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 22px;
        font-weight: 800;
        color: #ffffff;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .text-green { color: #4ade80 !important; }
    .text-red { color: #f87171 !important; }

    /* Chart Container Card */
    .chart-card {
        background-color: #0f1115;
        border: 1px solid #1a1d24;
        border-radius: 14px;
        padding: 20px;
        margin-top: 10px;
    }
    .chart-card-title {
        font-size: 0.9rem;
        font-weight: 700;
        color: #e2e8f0;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* COMPACT PILL BUTTONS OVERRIDE */
    .pill-nav-container div[data-testid="stColumn"] div.stButton > button {
        background-color: #0f1115 !important;
        border: 1px solid #1a1d24 !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        height: 42px !important;
        min-height: 42px !important;
        font-size: 0.88rem !important;
        font-weight: 600 !important;
        color: #9ca3af !important;
        transition: all 0.2s ease !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
    }

    .pill-nav-container div[data-testid="stColumn"] div.stButton > button:hover {
        border-color: #38bdf8 !important;
        color: #38bdf8 !important;
        background-color: #161822 !important;
    }

    /* Active Pill Button Highlight */
    .pill-nav-container div[data-testid="stColumn"] div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #0284c7 0%, #0369a1 100%) !important;
        color: #ffffff !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25) !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATA (shared loader: Webull via API, Dime via Google Sheets)
# ==========================================
from core import market, ui
from core import portfolio as pf

# Header Section
hdr_title, hdr_curr = st.columns([3, 1], vertical_alignment="center")
with hdr_title:
    ui.page_header("Portfolio Overview",
                   "สัดส่วนการถือครองและผลตอบแทนรายโบรกเกอร์ · Webull จาก API · Dime จาก Google Sheets + yfinance")
with hdr_curr:
    currency_mode = st.segmented_control("Display Currency", ["USD ($)", "THB (฿)"], default="USD ($)",
                                         key="portfolio_currency", label_visibility="collapsed") or "USD ($)"

# Load / Refresh Shared Data
df_port, load_status, is_demo = pf.load_holdings()
st.session_state["all_holdings_df"] = df_port
fx_rate = market.get_usd_thb()
st.session_state["usd_thb_rate"] = fx_rate
if is_demo:
    st.markdown('<div class="demo-banner">🧪 DEMO MODE — ยังไม่มี secrets จึงใช้พอร์ตตัวอย่าง</div>', unsafe_allow_html=True)


def sync_portfolio_snapshot_to_gsheet(invested_val, market_val, pnl_val, pnl_pct):
    return pf.sync_snapshot(df_port)


def highlight_pnl(val):
    if val is None or pd.isna(val):
        return ''
    s = str(val).strip()
    if s.startswith("+") or (not s.startswith("-") and not s.startswith("0") and any(char.isdigit() for char in s)):
        try:
            val_num = float(s.replace('$', '').replace('฿', '').replace(',', '').replace('%', '').replace('+', ''))
            if val_num > 0:
                return 'background-color: rgba(34, 197, 94, 0.15); color: #4ade80; font-weight: bold;'
            elif val_num < 0:
                return 'background-color: rgba(239, 68, 68, 0.15); color: #f87171; font-weight: bold;'
        except:
            if s.startswith("+"):
                return 'background-color: rgba(34, 197, 94, 0.15); color: #4ade80; font-weight: bold;'
    elif s.startswith("-"):
        return 'background-color: rgba(239, 68, 68, 0.15); color: #f87171; font-weight: bold;'
    return 'color: #9ca3af;'

# Helper สำหรับแสดงการ์ดสรุปยอดในแต่ละแท็บ
def render_tab_summary_metrics(df_sub, broker_name):
    is_thb = "THB" in currency_mode
    multiplier = fx_rate if is_thb else 1.0
    symbol = "฿" if is_thb else "$"
    s = pf.summarize(df_sub)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"มูลค่าตลาด ({broker_name})", ui.fmt_money(s["market"] * multiplier, symbol),
              f"{ui.fmt_money(s['day_pnl'] * multiplier, symbol, True)} ({s['day_pct']:+.2f}%) วันนี้")
    c2.metric(f"เงินลงทุน ({broker_name})", ui.fmt_money(s["invested"] * multiplier, symbol))
    c3.metric(f"กำไร/ขาดทุน ({broker_name})", ui.fmt_money(s["pnl"] * multiplier, symbol, True), f"{s['pnl_pct']:+.2f}%")
    sources = sorted({load_status[b]["source"] for b in pf.BROKERS if b in set(df_sub.get("Broker", []))})
    c4.metric("Positions", s["count"], " + ".join(sources) or "-", delta_color="off", delta_arrow="off")

# ==========================================
# 3. COMPACT PILL TAB NAVIGATION
# ==========================================
if "active_portfolio_tab" not in st.session_state:
    st.session_state["active_portfolio_tab"] = "all"

active_tab = st.session_state["active_portfolio_tab"]

st.markdown('<div class="pill-nav-container">', unsafe_allow_html=True)
c_tab1, c_tab2, c_tab3, c_tab4, c_tab5 = st.columns(5)

with c_tab1:
    btn_type = "primary" if active_tab == "all" else "secondary"
    if st.button("📊 ภาพรวมทั้งหมด", key="btn_tab_all", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "all"
        st.rerun()

with c_tab2:
    btn_type = "primary" if active_tab == "webull" else "secondary"
    if st.button("🦅 Webull US", key="btn_tab_webull", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "webull"
        st.rerun()

with c_tab3:
    btn_type = "primary" if active_tab == "dime_us" else "secondary"
    if st.button("💵 Dime US", key="btn_tab_dime_us", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "dime_us"
        st.rerun()

with c_tab4:
    btn_type = "primary" if active_tab == "dime_th" else "secondary"
    if st.button("🇹🇭 Dime TH", key="btn_tab_dime_th", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "dime_th"
        st.rerun()

with c_tab5:
    btn_type = "primary" if active_tab == "consolidated" else "secondary"
    if st.button("🧩 US Consolidated", key="btn_tab_consolidated", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "consolidated"
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 4. TAB CONTENT RENDERER
# ==========================================
is_thb = "THB" in currency_mode
multiplier = fx_rate if is_thb else 1.0
curr_symbol = "฿" if is_thb else "$"
curr_text = "THB" if is_thb else "USD"

if active_tab == "all":
    col_hdr_title, col_hdr_sync = st.columns([3, 1.2])
    with col_hdr_title:
        st.subheader(f"🌐 สถิติรวมพอร์ตทุกโบรกเกอร์ ({curr_text})")
    with col_hdr_sync:
        if st.button("🔄 Sync Snapshot to Dashboard", key="btn_sync_portfolio", use_container_width=True, type="primary"):
            if not df_port.empty:
                g_inv = df_port['Invested_USD'].sum()
                g_mkt = df_port['Market_Value_USD'].sum()
                g_pnl = g_mkt - g_inv
                g_pct = (g_pnl / g_inv * 100) if g_inv > 0 else 0.0
                
                with st.spinner("⏳ กำลังบันทึกประวัติลง Portfolio_History..."):
                    success, msg = sync_portfolio_snapshot_to_gsheet(g_inv, g_mkt, g_pnl, g_pct)
                    if success:
                        st.toast(f"✅ {msg}", icon="🎉")
                    else:
                        st.error(f"❌ {msg}")
            else:
                st.warning("⚠️ ไม่มีข้อมูลพอร์ตที่จะซิงค์")

    if not df_port.empty:
        render_tab_summary_metrics(df_port, "ทุกโบรกเกอร์")

        st.caption(f"ℹ️ อัตราแลกเปลี่ยนอ้างอิง: 1 USD = {fx_rate:.2f} THB · Webull: ราคาจาก Webull API · Dime: ราคาสดจาก yfinance")
        st.markdown("---")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1, ui.card("pf-broker", "🏦 สัดส่วนพอร์ตแยกตามโบรกเกอร์"):
            df_broker = df_port.groupby("Broker")["Market_Value_USD"].sum().reset_index()
            df_broker["Value"] = df_broker["Market_Value_USD"] * multiplier
            
            fig1 = go.Figure(data=[go.Pie(
                labels=df_broker["Broker"],
                values=df_broker["Value"],
                hole=0.6,
                textinfo='percent',
                hovertemplate="<b>%{label}</b><br>มูลค่า: " + curr_symbol + "%{value:,.2f}<br>สัดส่วน: %{percent}<extra></extra>",
                marker=dict(colors=[pf.BROKER_META.get(b, {}).get("color", "#64748b") for b in df_broker["Broker"]])
            )])
            fig1.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#9ca3af', family='Plus Jakarta Sans'),
                margin=dict(t=10, b=10, l=10, r=10),
                height=280,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
            )
            st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar': False})

        with col_g2, ui.card("pf-symbols", "📈 สัดส่วนการถือครองหุ้น (Top Holdings)"):
            df_sym = df_port.groupby("Symbol")["Market_Value_USD"].sum().reset_index()
            df_sym["Value"] = df_sym["Market_Value_USD"] * multiplier
            df_sym = df_sym.sort_values(by="Value", ascending=False)
            
            if len(df_sym) > 5:
                top_5 = df_sym.iloc[:5].copy()
                others_val = df_sym.iloc[5:]["Value"].sum()
                others_row = pd.DataFrame([{"Symbol": "Others", "Market_Value_USD": 0, "Value": others_val}])
                df_chart_sym = pd.concat([top_5, others_row], ignore_index=True)
            else:
                df_chart_sym = df_sym.copy()

            fig2 = go.Figure(data=[go.Pie(
                labels=df_chart_sym["Symbol"],
                values=df_chart_sym["Value"],
                hole=0.6,
                textinfo='label+percent',
                hovertemplate="<b>%{label}</b><br>มูลค่า: " + curr_symbol + "%{value:,.2f}<br>สัดส่วน: %{percent}<extra></extra>",
                marker=dict(colors=['#0284c7', '#38bdf8', '#818cf8', '#c084fc', '#f472b6', '#64748b'])
            )])
            fig2.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color='#9ca3af', family='Plus Jakarta Sans'),
                margin=dict(t=10, b=10, l=10, r=10),
                height=280,
                showlegend=False
            )
            st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar': False})
            
    else:
        st.info("ยังไม่มีข้อมูลหุ้นในพอร์ตโฟลิโอ")

elif active_tab == "webull":
    st.subheader(f"🦅 พอร์ตการลงทุน Webull ({curr_text})")
    df_w = df_port[df_port["Broker"] == "Webull"] if not df_port.empty else pd.DataFrame()
    
    render_tab_summary_metrics(df_w, "Webull US")
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_w.empty:
        df_w_disp = df_w.copy()
        if is_thb:
            df_w_disp["Cost"] = df_w_disp["Cost"] * fx_rate
            df_w_disp["Price"] = df_w_disp["Price"] * fx_rate
            df_w_disp["Invested_USD"] = df_w_disp["Invested_USD"] * fx_rate
            df_w_disp["Market_Value_USD"] = df_w_disp["Market_Value_USD"] * fx_rate
            df_w_disp["PnL_USD"] = df_w_disp["PnL_USD"] * fx_rate

        df_w_disp = df_w_disp[["Symbol", "Qty", "Cost", "Price", "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct"]].copy()
        df_w_disp.columns = ["Symbol", "Qty", f"Avg Cost ({curr_symbol})", f"Market Price ({curr_symbol})", f"Total Cost ({curr_symbol})", f"Market Value ({curr_symbol})", f"Unrealized P/L ({curr_symbol})", "P/L (%)"]
        
        fmt_symbol = f"฿{{:,.2f}}" if is_thb else f"${{:,.2f}}"
        fmt_pnl_symbol = f"฿{{:+,.2f}}" if is_thb else f"${{:+,.2f}}"

        formatted_df = df_w_disp.style.format({
            "Qty": "{:,.4f}", f"Avg Cost ({curr_symbol})": fmt_symbol, f"Market Price ({curr_symbol})": fmt_symbol,
            f"Total Cost ({curr_symbol})": fmt_symbol, f"Market Value ({curr_symbol})": fmt_symbol,
            f"Unrealized P/L ({curr_symbol})": fmt_pnl_symbol, "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=[f"Unrealized P/L ({curr_symbol})", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Webull")

elif active_tab == "dime_us":
    st.subheader(f"💵 พอร์ตการลงทุน Dime US ({curr_text})")
    df_dus = df_port[df_port["Broker"] == "Dime US"] if not df_port.empty else pd.DataFrame()
    
    render_tab_summary_metrics(df_dus, "Dime US")
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_dus.empty:
        df_dus_disp = df_dus.copy()
        if is_thb:
            df_dus_disp["Cost"] = df_dus_disp["Cost"] * fx_rate
            df_dus_disp["Price"] = df_dus_disp["Price"] * fx_rate
            df_dus_disp["Invested_USD"] = df_dus_disp["Invested_USD"] * fx_rate
            df_dus_disp["Market_Value_USD"] = df_dus_disp["Market_Value_USD"] * fx_rate
            df_dus_disp["PnL_USD"] = df_dus_disp["PnL_USD"] * fx_rate

        df_dus_disp = df_dus_disp[["Symbol", "Qty", "Cost", "Price", "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct"]].copy()
        df_dus_disp.columns = ["Symbol", "Qty", f"Avg Cost ({curr_symbol})", f"Market Price ({curr_symbol})", f"Total Cost ({curr_symbol})", f"Market Value ({curr_symbol})", f"Unrealized P/L ({curr_symbol})", "P/L (%)"]
        
        fmt_symbol = f"฿{{:,.2f}}" if is_thb else f"${{:,.2f}}"
        fmt_pnl_symbol = f"฿{{:+,.2f}}" if is_thb else f"${{:+,.2f}}"

        formatted_df = df_dus_disp.style.format({
            "Qty": "{:,.4f}", f"Avg Cost ({curr_symbol})": fmt_symbol, f"Market Price ({curr_symbol})": fmt_symbol,
            f"Total Cost ({curr_symbol})": fmt_symbol, f"Market Value ({curr_symbol})": fmt_symbol,
            f"Unrealized P/L ({curr_symbol})": fmt_pnl_symbol, "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=[f"Unrealized P/L ({curr_symbol})", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime US")

elif active_tab == "dime_th":
    st.subheader(f"🇹🇭 พอร์ตการลงทุน Dime TH (หุ้นไทย - {curr_text})")
    df_dth = df_port[df_port["Broker"] == "Dime TH"] if not df_port.empty else pd.DataFrame()
    
    render_tab_summary_metrics(df_dth, "Dime TH")
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_dth.empty:
        df_dth_disp = df_dth.copy()
        if is_thb:
            df_dth_disp["Cost_Disp"] = df_dth_disp["Cost"]
            df_dth_disp["Price_Disp"] = df_dth_disp["Price"]
            df_dth_disp["Total_Cost_Disp"] = df_dth_disp["Qty"] * df_dth_disp["Cost"]
            df_dth_disp["Market_Value_Disp"] = df_dth_disp["Qty"] * df_dth_disp["Price"]
            df_dth_disp["PnL_Disp"] = df_dth_disp["Market_Value_Disp"] - df_dth_disp["Total_Cost_Disp"]
        else:
            df_dth_disp["Cost_Disp"] = df_dth_disp["Cost"] / fx_rate
            df_dth_disp["Price_Disp"] = df_dth_disp["Price"] / fx_rate
            df_dth_disp["Total_Cost_Disp"] = df_dth_disp["Invested_USD"]
            df_dth_disp["Market_Value_Disp"] = df_dth_disp["Market_Value_USD"]
            df_dth_disp["PnL_Disp"] = df_dth_disp["PnL_USD"]

        df_dth_disp = df_dth_disp[["Symbol", "Qty", "Cost_Disp", "Price_Disp", "Total_Cost_Disp", "Market_Value_Disp", "PnL_Disp", "PnL_Pct"]]
        df_dth_disp.columns = ["Symbol", "Qty", f"Avg Cost ({curr_symbol})", f"Market Price ({curr_symbol})", f"Total Cost ({curr_symbol})", f"Market Value ({curr_symbol})", f"Unrealized P/L ({curr_symbol})", "P/L (%)"]
        
        fmt_symbol = f"฿{{:,.2f}}" if is_thb else f"${{:,.2f}}"
        fmt_pnl_symbol = f"฿{{:+,.2f}}" if is_thb else f"${{:+,.2f}}"

        formatted_df = df_dth_disp.style.format({
            "Qty": "{:,.0f}", f"Avg Cost ({curr_symbol})": fmt_symbol, f"Market Price ({curr_symbol})": fmt_symbol,
            f"Total Cost ({curr_symbol})": fmt_symbol, f"Market Value ({curr_symbol})": fmt_symbol,
            f"Unrealized P/L ({curr_symbol})": fmt_pnl_symbol, "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=[f"Unrealized P/L ({curr_symbol})", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime TH")

elif active_tab == "consolidated":
    st.subheader(f"🧩 รวมหุ้นทุกตัวเฉพาะหุ้นสหรัฐฯ (US Consolidated Holdings - {curr_text})")
    df_us_only = df_port[df_port["Broker"].isin(["Webull", "Dime US"])] if not df_port.empty else pd.DataFrame()
    
    render_tab_summary_metrics(df_us_only, "US Consolidated")
    st.markdown("<br>", unsafe_allow_html=True)

    if not df_us_only.empty:
        grouped_rows = []
        for sym, group in df_us_only.groupby("Symbol"):
            tot_qty = group["Qty"].sum()
            tot_cost = group["Invested_USD"].sum() * multiplier
            tot_market = group["Market_Value_USD"].sum() * multiplier
            tot_pnl = tot_market - tot_cost
            pnl_pct = (tot_pnl / tot_cost * 100) if tot_cost > 0 else 0.0
            avg_cost = tot_cost / tot_qty if tot_qty > 0 else 0.0
            market_price = (group["Price"].iloc[0]) * multiplier
            sources = ", ".join(group["Broker"].unique())
            
            grouped_rows.append({
                "Symbol": sym,
                "Total_Qty": tot_qty,
                "Avg_Cost": avg_cost,
                "Market_Price": market_price,
                "Total_Cost": tot_cost,
                "Market_Value": tot_market,
                "Unrealized_PL": tot_pnl,
                "Unrealized_PL_Pct": pnl_pct,
                "Sources": sources
            })
            
        df_grouped = pd.DataFrame(grouped_rows)
        st.session_state["us_consolidated_df"] = df_grouped
        
        df_grouped_disp = df_grouped.copy()
        df_grouped_disp.columns = ["Symbol", "Total Qty", f"Avg Cost ({curr_symbol})", f"Market Price ({curr_symbol})", f"Total Cost ({curr_symbol})", f"Market Value ({curr_symbol})", f"Unrealized P/L ({curr_symbol})", "P/L (%)", "Sources"]
        
        fmt_symbol = f"฿{{:,.2f}}" if is_thb else f"${{:,.2f}}"
        fmt_pnl_symbol = f"฿{{:+,.2f}}" if is_thb else f"${{:+,.2f}}"

        formatted_df = df_grouped_disp.style.format({
            "Total Qty": "{:,.4f}", f"Avg Cost ({curr_symbol})": fmt_symbol, f"Market Price ({curr_symbol})": fmt_symbol,
            f"Total Cost ({curr_symbol})": fmt_symbol, f"Market Value ({curr_symbol})": fmt_symbol,
            f"Unrealized P/L ({curr_symbol})": fmt_pnl_symbol, "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=[f"Unrealized P/L ({curr_symbol})", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบรายการถือครองหุ้นสหรัฐฯ ในระบบ")

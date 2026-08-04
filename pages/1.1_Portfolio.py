import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ==========================================
# 1. PAGE STYLE & MINIMAL CARD CSS
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
        margin-bottom: 20px;
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

    /* Modern Large Navigation Cards Override */
    div[data-testid="stColumn"] div.stButton > button {
        background-color: #0f1115 !important;
        border: 1px solid #1a1d24 !important;
        border-radius: 14px !important;
        padding: 16px 20px !important;
        height: auto !important;
        min-height: 100px !important;
        text-align: left !important;
        transition: all 0.25s ease !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
    }

    div[data-testid="stColumn"] div.stButton > button:hover {
        border-color: #38bdf8 !important;
        background-color: #141822 !important;
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(56, 189, 248, 0.15);
    }

    /* Active Big Card Highlight */
    div[data-testid="stColumn"] div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #111e2e 0%, #0d1724 100%) !important;
        border: 1px solid #38bdf8 !important;
        box-shadow: 0 8px 20px rgba(56, 189, 248, 0.2) !important;
    }
    </style>
""", unsafe_allow_html=True)

# Minimal Header
st.markdown('<div class="page-title-minimal">Portfolio Overview</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">วิเคราะห์สัดส่วนการถือครองและผลตอบแทนรายโบรกเกอร์</div>', unsafe_allow_html=True)

# Currency Switcher
c_curr, c_space = st.columns([1.5, 2.5])
with c_curr:
    currency_mode = st.radio(
        "Display Currency",
        ("USD ($)", "THB (฿)"),
        horizontal=True,
        index=0
    )

# Get Shared Master Data
df_port = st.session_state.get("all_holdings_df", pd.DataFrame())
fx_rate = st.session_state.get("usd_thb_rate", 35.0)

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

# ==========================================
# 2. LARGE MODERN NAVIGATION CARDS (GRID UI)
# ==========================================
if "active_portfolio_tab" not in st.session_state:
    st.session_state["active_portfolio_tab"] = "all"

active_tab = st.session_state["active_portfolio_tab"]

col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)

with col_c1:
    btn_type = "primary" if active_tab == "all" else "secondary"
    if st.button("📊 All In One\n\nสรุปภาพรวมพอร์ตรวมทุกโบรกเกอร์", key="btn_tab_all", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "all"
        st.rerun()

with col_c2:
    btn_type = "primary" if active_tab == "webull" else "secondary"
    if st.button("🦅 Webull US\n\nข้อมูลตำแหน่งหุ้นสดจาก Webull API", key="btn_tab_webull", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "webull"
        st.rerun()

with col_c3:
    btn_type = "primary" if active_tab == "dime_us" else "secondary"
    if st.button("💵 Dime US\n\nรายการหุ้นสหรัฐฯ ใน Dime", key="btn_tab_dime_us", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "dime_us"
        st.rerun()

with col_c4:
    btn_type = "primary" if active_tab == "dime_th" else "secondary"
    if st.button("🇹🇭 Dime TH\n\nรายการหุ้นไทยใน Dime", key="btn_tab_dime_th", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "dime_th"
        st.rerun()

with col_c5:
    btn_type = "primary" if active_tab == "consolidated" else "secondary"
    if st.button("🧩 US Consolidated\n\nรวมหุ้น US จากทุกโบรกถัวเฉลี่ยต้นทุน", key="btn_tab_consolidated", use_container_width=True, type=btn_type):
        st.session_state["active_portfolio_tab"] = "consolidated"
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ==========================================
# 3. TAB CONTENT RENDERER
# ==========================================
is_thb = "THB" in currency_mode
multiplier = fx_rate if is_thb else 1.0
curr_symbol = "฿" if is_thb else "$"
curr_text = "THB" if is_thb else "USD"

if active_tab == "all":
    st.subheader(f"🌐 สถิติรวมพอร์ตทุกโบรกเกอร์ ({curr_text})")
    
    if not df_port.empty:
        grand_invested = df_port['Invested_USD'].sum() * multiplier
        grand_market = df_port['Market_Value_USD'].sum() * multiplier
        grand_pnl = grand_market - grand_invested
        grand_pnl_pct = (grand_pnl / grand_invested * 100) if grand_invested > 0 else 0
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">เงินลงทุนรวมทั้งสิ้น</div><div class="metric-value">{curr_symbol}{grand_invested:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">มูลค่าตลาดรวมพอร์ตทั้งหมด</div><div class="metric-value">{curr_symbol}{grand_market:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            pnl_class = "text-green" if grand_pnl >= 0 else "text-red"
            pnl_prefix = "+" if grand_pnl >= 0 else ""
            st.markdown(f'<div class="metric-card"><div class="metric-label">กำไร / ขาดทุนสุทธิรวม</div><div class="metric-value {pnl_class}">{pnl_prefix}{curr_symbol}{grand_pnl:,.2f} ({grand_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

        st.caption(f"ℹ️ อัตราแลกเปลี่ยนอ้างอิง: 1 USD = {fx_rate:.2f} THB")
        st.markdown("---")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown('<div class="chart-card"><div class="chart-card-title">🏦 สัดส่วนพอร์ตแยกตามโบรกเกอร์</div>', unsafe_allow_html=True)
            df_broker = df_port.groupby("Broker")["Market_Value_USD"].sum().reset_index()
            df_broker["Value"] = df_broker["Market_Value_USD"] * multiplier
            
            fig1 = go.Figure(data=[go.Pie(
                labels=df_broker["Broker"],
                values=df_broker["Value"],
                hole=0.6,
                textinfo='percent',
                hovertemplate="<b>%{label}</b><br>มูลค่า: " + curr_symbol + "%{value:,.2f}<br>สัดส่วน: %{percent}<extra></extra>",
                marker=dict(colors=['#38bdf8', '#a855f7', '#34d399', '#f59e0b'])
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
            st.markdown('</div>', unsafe_allow_html=True)

        with col_g2:
            st.markdown('<div class="chart-card"><div class="chart-card-title">📈 สัดส่วนการถือครองหุ้น (Top Holdings)</div>', unsafe_allow_html=True)
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
            st.markdown('</div>', unsafe_allow_html=True)
            
    else:
        st.info("ยังไม่มีข้อมูลหุ้นในพอร์ตโฟลิโอ")

elif active_tab == "webull":
    st.subheader("🦅 พอร์ตการลงทุน Webull (Live API Data)")
    df_w = df_port[df_port["Broker"] == "Webull"] if not df_port.empty else pd.DataFrame()
    if not df_w.empty:
        df_w_disp = df_w[["Symbol", "Qty", "Cost", "Price", "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct"]].copy()
        df_w_disp.columns = ["Symbol", "Qty", "Avg Cost ($)", "Market Price ($)", "Total Cost ($)", "Market Value ($)", "Unrealized P/L ($)", "P/L (%)"]
        
        formatted_df = df_w_disp.style.format({
            "Qty": "{:,.4f}", "Avg Cost ($)": "${:,.2f}", "Market Price ($)": "${:,.2f}",
            "Total Cost ($)": "${:,.2f}", "Market Value ($)": "${:,.2f}",
            "Unrealized P/L ($)": "${:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=["Unrealized P/L ($)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Webull")

elif active_tab == "dime_us":
    st.subheader("💵 พอร์ตการลงทุน Dime US")
    df_dus = df_port[df_port["Broker"] == "Dime US"] if not df_port.empty else pd.DataFrame()
    if not df_dus.empty:
        df_dus_disp = df_dus[["Symbol", "Qty", "Cost", "Price", "Invested_USD", "Market_Value_USD", "PnL_USD", "PnL_Pct"]].copy()
        df_dus_disp.columns = ["Symbol", "Qty", "Avg Cost ($)", "Market Price ($)", "Total Cost ($)", "Market Value ($)", "Unrealized P/L ($)", "P/L (%)"]
        
        formatted_df = df_dus_disp.style.format({
            "Qty": "{:,.4f}", "Avg Cost ($)": "${:,.2f}", "Market Price ($)": "${:,.2f}",
            "Total Cost ($)": "${:,.2f}", "Market Value ($)": "${:,.2f}",
            "Unrealized P/L ($)": "${:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=["Unrealized P/L ($)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime US")

elif active_tab == "dime_th":
    st.subheader("🇹🇭 พอร์ตการลงทุน Dime TH (หุ้นไทย)")
    df_dth = df_port[df_port["Broker"] == "Dime TH"] if not df_port.empty else pd.DataFrame()
    if not df_dth.empty:
        df_dth_disp = df_dth.copy()
        df_dth_disp["Total_Cost_THB"] = df_dth_disp["Qty"] * df_dth_disp["Cost"]
        df_dth_disp["Market_Value_THB"] = df_dth_disp["Qty"] * df_dth_disp["Price"]
        df_dth_disp["PnL_THB"] = df_dth_disp["Market_Value_THB"] - df_dth_disp["Total_Cost_THB"]
        
        df_dth_disp = df_dth_disp[["Symbol", "Qty", "Cost", "Price", "Total_Cost_THB", "Market_Value_THB", "PnL_THB", "PnL_Pct"]]
        df_dth_disp.columns = ["Symbol", "Qty", "Avg Cost (฿)", "Market Price (฿)", "Total Cost (฿)", "Market Value (฿)", "Unrealized P/L (฿)", "P/L (%)"]
        
        formatted_df = df_dth_disp.style.format({
            "Qty": "{:,.0f}", "Avg Cost (฿)": "฿{:,.2f}", "Market Price (฿)": "฿{:,.2f}",
            "Total Cost (฿)": "฿{:,.2f}", "Market Value (฿)": "฿{:,.2f}",
            "Unrealized P/L (฿)": "฿{:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=["Unrealized P/L (฿)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime TH")

elif active_tab == "consolidated":
    st.subheader("🧩 รวมหุ้นทุกตัวเฉพาะหุ้นสหรัฐฯ (US Consolidated Holdings)")
    df_us_only = df_port[df_port["Broker"].isin(["Webull", "Dime US"])] if not df_port.empty else pd.DataFrame()
    
    if not df_us_only.empty:
        grouped_rows = []
        for sym, group in df_us_only.groupby("Symbol"):
            tot_qty = group["Qty"].sum()
            tot_cost = group["Invested_USD"].sum()
            tot_market = group["Market_Value_USD"].sum()
            tot_pnl = tot_market - tot_cost
            pnl_pct = (tot_pnl / tot_cost * 100) if tot_cost > 0 else 0.0
            avg_cost = tot_cost / tot_qty if tot_qty > 0 else 0.0
            market_price = group["Price"].iloc[0]
            sources = ", ".join(group["Broker"].unique())
            
            grouped_rows.append({
                "Symbol": sym,
                "Total_Qty": tot_qty,
                "Avg_Cost_USD": avg_cost,
                "Market_Price": market_price,
                "Total_Cost_USD": tot_cost,
                "Market_Value_USD": tot_market,
                "Unrealized_PL_USD": tot_pnl,
                "Unrealized_PL_Pct": pnl_pct,
                "Sources": sources
            })
            
        df_grouped = pd.DataFrame(grouped_rows)
        st.session_state["us_consolidated_df"] = df_grouped
        
        df_grouped_disp = df_grouped.copy()
        df_grouped_disp.columns = ["Symbol", "Total Qty", "Avg Cost ($)", "Market Price ($)", "Total Cost ($)", "Market Value ($)", "Unrealized P/L ($)", "P/L (%)", "Sources"]
        
        formatted_df = df_grouped_disp.style.format({
            "Total Qty": "{:,.4f}", "Avg Cost ($)": "${:,.2f}", "Market Price ($)": "${:,.2f}",
            "Total Cost ($)": "${:,.2f}", "Market Value ($)": "${:,.2f}",
            "Unrealized P/L ($)": "${:+,.2f}", "P/L (%)": "{:+.2f}%"
        }).map(highlight_pnl, subset=["Unrealized P/L ($)", "P/L (%)"])
        
        st.dataframe(formatted_df, use_container_width=True)
    else:
        st.info("ไม่พบรายการถือครองหุ้นสหรัฐฯ ในระบบ")

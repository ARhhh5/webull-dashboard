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
        background-color: #141822 !important;
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
# 2. GOOGLE SHEETS & REAL-TIME PRICE PIPELINE
# ==========================================
def get_gspread_client():
    if not HAS_GSPREAD:
        return None
    try:
        import json, base64
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if cred_base64:
            cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
            return gspread.service_account_from_dict(cred_dict)
        elif "gcp_service_account" in st.secrets:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
            return gspread.authorize(creds)
    except Exception:
        pass
    return None

def fetch_live_prices(symbols):
    """ดึงราคาตลาดสด Real-time จาก yfinance โดยประมวลผลรายตัวแบบปลอดภัย"""
    price_map = {}
    if not symbols:
        return price_map
    
    clean_symbols = [str(s).strip().upper() for s in symbols if str(s).strip()]
    for sym in clean_symbols:
        try:
            ticker = yf.Ticker(sym)
            fast_info = ticker.fast_info
            price = fast_info.last_price
            if price is None or pd.isna(price):
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
            price_map[sym] = float(price) if price and not pd.isna(price) else None
        except Exception:
            price_map[sym] = None
    return price_map

def sync_portfolio_snapshot_to_gsheet(invested_val, market_val, pnl_val, pnl_pct):
    gc = get_gspread_client()
    if not gc:
        return False, "ไม่พบการเชื่อมต่อ Google Sheets Credentials"
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)

        try:
            sh = gc.open(sheet_title)
        except Exception:
            sh = gc.open_by_key(sheet_title) if len(sheet_title) > 20 else gc.open_by_url(sheet_title)

        try:
            worksheet = sh.worksheet("Portfolio_History")
        except Exception:
            worksheet = sh.add_worksheet(title="Portfolio_History", rows="1000", cols="5")
            worksheet.append_row(["วันที่", "มูลค่าตั้งต้น", "มูลค่าปัจจุบัน", "กำไรขาดทุน", "กำไรขาดทุน%"])
            
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_row = [now_str, round(invested_val, 2), round(market_val, 2), round(pnl_val, 2), f"{pnl_pct:.2f}%"]
        worksheet.append_row(new_row)
        return True, "บันทึกประวัติลง Portfolio_History สำเร็จ!"
    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการเขียน Google Sheets: {str(e)}"

def clean_val(val):
    if pd.isna(val) or val == "":
        return 0.0
    val_str = str(val).replace(",", "").replace("%", "").replace("$", "").replace("฿", "").strip()
    try:
        return float(val_str)
    except:
        return 0.0

def load_master_holdings_from_sheets():
    """คำนวณยอดพอร์ตสะสม Net Position และกรองเอาเฉพาะหุ้นที่มีอยู่จริงใน Snapshot สดล่าสุด"""
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try:
            sh = gc.open(sheet_title)
        except Exception:
            sh = gc.open_by_key(sheet_title) if len(sheet_title) > 20 else gc.open_by_url(sheet_title)

        raw_records = []

        # 1. คำนวณพอร์ต Webull จาก Webull_Order_History
        try:
            ws_w = sh.worksheet("Webull_Order_History")
            data_w = ws_w.get_all_values()
            if len(data_w) > 1:
                df_w = pd.DataFrame(data_w[1:], columns=data_w[0])
                cols = list(df_w.columns)
                
                sym_col = next((c for c in cols if "Sym" in c or "Ticker" in c or "หุ้น" in c), cols[2] if len(cols) > 2 else cols[0])
                side_col = next((c for c in cols if "Side" in c or "ประเภท" in c), cols[3] if len(cols) > 3 else None)
                qty_col = next((c for c in cols if "Qty" in c or "Volume" in c or "จำนวน" in c), cols[4] if len(cols) > 4 else cols[1])
                cost_col = next((c for c in cols if "Pr" in c or "Cost" in c or "ต้นทุน" in c or "Avg" in c), cols[5] if len(cols) > 5 else cols[2])
                time_col = next((c for c in cols if "Time" in c or "Date" in c or "วันที่" in c), cols[1] if len(cols) > 1 else None)

                # ดึงวันทีล่าสุดเพื่อเช็ก Snapshot ปัจจุบัน
                latest_date_str = ""
                if time_col and time_col in df_w.columns:
                    latest_date_str = str(df_w[time_col].iloc[-1]).strip()

                # หาลำดับสัญลักษณ์หุ้นที่มีอยู่ใน Snapshot ล่าสุด (บรรทัดที่ Side เป็นค่าว่างของวันล่าสุด)
                active_snapshot_symbols = set()
                if latest_date_str:
                    snap_rows = df_w[(df_w[time_col].astype(str).str.strip() == latest_date_str) & 
                                     (df_w[side_col].astype(str).str.strip() == "")] if side_col else df_w
                    for _, s_row in snap_rows.iterrows():
                        s_sym = str(s_row.get(sym_col, "")).strip().upper()
                        s_qty = clean_val(s_row.get(qty_col, 0))
                        if s_sym and s_qty > 0:
                            active_snapshot_symbols.add(s_sym)

                for sym, grp in df_w.groupby(sym_col):
                    clean_sym = str(sym).strip().upper()
                    if not clean_sym:
                        continue

                    # กรองทิ้งทันทีถ้าหุ้นตัวนั้นไม่อยู่ใน Snapshot ล่าสุด (กรณีขายหมดแล้วเช่น ULTY)
                    if active_snapshot_symbols and clean_sym not in active_snapshot_symbols:
                        continue

                    total_qty = 0.0
                    total_cost_val = 0.0
                    has_explicit_trades = False

                    for _, row in grp.iterrows():
                        q = clean_val(row.get(qty_col, 0))
                        p = clean_val(row.get(cost_col, 0))
                        side = str(row.get(side_col, "")).strip().upper() if side_col else ""

                        if "SELL" in side or "ขาย" in side:
                            has_explicit_trades = True
                            if total_qty > 0:
                                avg_c = total_cost_val / total_qty
                                total_qty -= q
                                total_cost_val = total_qty * avg_c
                        elif "BUY" in side or "ซื้อ" in side:
                            has_explicit_trades = True
                            total_qty += q
                            total_cost_val += (q * p)

                    # ถ้าไม่มีออเดอร์ BUY/SELL ตรงๆ ให้ใช้ค่าแถวล่าสุดจาก Snapshot
                    if not has_explicit_trades or total_qty <= 0.0001:
                        latest_r = grp.iloc[-1]
                        total_qty = clean_val(latest_r.get(qty_col, 0))
                        avg_cost = clean_val(latest_r.get(cost_col, 0))
                    else:
                        avg_cost = total_cost_val / total_qty

                    if total_qty > 0.0001:
                        raw_records.append({
                            "Broker": "Webull",
                            "Symbol": clean_sym,
                            "Qty": total_qty,
                            "Cost": avg_cost
                        })
        except Exception:
            pass

        # 2. คำนวณ Dime US จาก Dime_Portfolio
        try:
            ws_dus = sh.worksheet("Dime_Portfolio")
            data_dus = ws_dus.get_all_values()
            if len(data_dus) > 1:
                df_dus = pd.DataFrame(data_dus[1:], columns=data_dus[0])
                sym_col = next((c for c in df_dus.columns if "หุ้น" in c or "Ticker" in c or "Sym" in c), df_dus.columns[0])
                qty_col = next((c for c in df_dus.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), df_dus.columns[1])
                cost_col = next((c for c in df_dus.columns if "ต้นทุน" in c or "Avg" in c or "Cost" in c), df_dus.columns[2])

                for sym, grp in df_dus.groupby(sym_col):
                    clean_sym = str(sym).strip().upper()
                    if not clean_sym:
                        continue
                    
                    tot_q = 0.0
                    tot_c = 0.0
                    for _, row in grp.iterrows():
                        q = clean_val(row.get(qty_col, 0))
                        c = clean_val(row.get(cost_col, 0))
                        tot_q += q
                        tot_c += (q * c)

                    if tot_q > 0.0001:
                        raw_records.append({
                            "Broker": "Dime US",
                            "Symbol": clean_sym,
                            "Qty": tot_q,
                            "Cost": tot_c / tot_q
                        })
        except Exception:
            pass

        # 3. คำนวณ Dime TH จาก Dime_TH_Portfolio
        try:
            ws_dth = sh.worksheet("Dime_TH_Portfolio")
            data_dth = ws_dth.get_all_values()
            if len(data_dth) > 1:
                df_dth = pd.DataFrame(data_dth[1:], columns=data_dth[0])
                sym_col = next((c for c in df_dth.columns if "หุ้น" in c or "Ticker" in c or "Sym" in c), df_dth.columns[0])
                qty_col = next((c for c in df_dth.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), df_dth.columns[1])
                cost_col = next((c for c in df_dth.columns if "ต้นทุน" in c or "Avg" in c or "Cost" in c), df_dth.columns[2])

                for sym, grp in df_dth.groupby(sym_col):
                    clean_sym = str(sym).strip().upper()
                    if not clean_sym:
                        continue
                    
                    tot_q = 0.0
                    tot_c = 0.0
                    for _, row in grp.iterrows():
                        q = clean_val(row.get(qty_col, 0))
                        c = clean_val(row.get(cost_col, 0))
                        tot_q += q
                        tot_c += (q * c)

                    if tot_q > 0.0001:
                        raw_records.append({
                            "Broker": "Dime TH",
                            "Symbol": clean_sym,
                            "Qty": tot_q,
                            "Cost": tot_c / tot_q
                        })
        except Exception:
            pass

        if not raw_records:
            return pd.DataFrame()

        df_holdings = pd.DataFrame(raw_records)

        # 4. รวมรายการหุ้นเพื่อยิงดึงราคาตลาดสด yfinance
        us_symbols = df_holdings[df_holdings["Broker"].isin(["Webull", "Dime US"])]["Symbol"].unique().tolist()
        th_symbols = [f"{s}.BK" for s in df_holdings[df_holdings["Broker"] == "Dime TH"]["Symbol"].unique().tolist()]
        
        all_symbols = us_symbols + th_symbols
        live_prices = fetch_live_prices(all_symbols)

        fx_rate = st.session_state.get("usd_thb_rate", 35.0)

        # 5. คำนวณ Market Value / Unrealized PnL สด
        holdings_calculated = []
        for _, row in df_holdings.iterrows():
            broker = row["Broker"]
            sym = row["Symbol"]
            qty = row["Qty"]
            cost = row["Cost"]

            if broker in ["Webull", "Dime US"]:
                price = live_prices.get(sym)
                if price is None or price <= 0:
                    price = cost
                inv_usd = qty * cost
                mkt_usd = qty * price
                pnl_usd = mkt_usd - inv_usd
                pct = (pnl_usd / inv_usd * 100) if inv_usd > 0 else 0.0

                holdings_calculated.append({
                    "Broker": broker, "Symbol": sym, "Qty": qty, "Cost": cost,
                    "Price": price, "Invested_USD": inv_usd, "Market_Value_USD": mkt_usd,
                    "PnL_USD": pnl_usd, "PnL_Pct": pct
                })
            else: # Dime TH
                th_sym = f"{sym}.BK"
                price = live_prices.get(th_sym)
                if price is None or price <= 0:
                    price = cost
                
                inv_thb = qty * cost
                mkt_thb = qty * price
                pnl_thb = mkt_thb - inv_thb
                pct = (pnl_thb / inv_thb * 100) if inv_thb > 0 else 0.0

                holdings_calculated.append({
                    "Broker": broker, "Symbol": sym, "Qty": qty, "Cost": cost,
                    "Price": price, "Invested_USD": inv_thb / fx_rate, "Market_Value_USD": mkt_thb / fx_rate,
                    "PnL_USD": pnl_thb / fx_rate, "PnL_Pct": pct
                })

        return pd.DataFrame(holdings_calculated)
    except Exception:
        return pd.DataFrame()

# Header Section
st.markdown('<div class="page-title-minimal">Portfolio Overview</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">วิเคราะห์สัดส่วนการถือครองและผลตอบแทนรายโบรกเกอร์ (Live Price via yfinance)</div>', unsafe_allow_html=True)

# Currency Control
currency_mode = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

# Load / Refresh Shared Data
df_port = load_master_holdings_from_sheets()
st.session_state["all_holdings_df"] = df_port

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
        grand_invested = df_port['Invested_USD'].sum() * multiplier
        grand_market = df_port['Market_Value_USD'].sum() * multiplier
        grand_pnl = grand_market - grand_invested
        grand_pnl_pct = (grand_pnl / grand_invested * 100) if grand_invested > 0 else 0.0
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">เงินลงทุนรวมทั้งสิ้น</div><div class="metric-value">{curr_symbol}{grand_invested:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">มูลค่าตลาดรวมพอร์ตทั้งหมด</div><div class="metric-value">{curr_symbol}{grand_market:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            pnl_class = "text-green" if grand_pnl >= 0 else "text-red"
            pnl_prefix = "+" if grand_pnl >= 0 else ""
            st.markdown(f'<div class="metric-card"><div class="metric-label">กำไร / ขาดทุนสุทธิรวม</div><div class="metric-value {pnl_class}">{pnl_prefix}{curr_symbol}{grand_pnl:,.2f} ({grand_pnl_pct:+.2f}%)</div></div>', unsafe_allow_html=True)

        st.caption(f"ℹ️ อัตราแลกเปลี่ยนอ้างอิง: 1 USD = {fx_rate:.2f} THB (อัปเดตราคาหุ้นสดผ่าน yfinance)")
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
    st.subheader("🦅 พอร์ตการลงทุน Webull (Live Price via yfinance)")
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
    st.subheader("💵 พอร์ตการลงทุน Dime US (Live Price via yfinance)")
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
    st.subheader("🇹🇭 พอร์ตการลงทุน Dime TH (หุ้นไทย - Live Price via yfinance)")
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

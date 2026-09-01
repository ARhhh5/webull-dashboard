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
    """ดึงราคาตลาดสด Real-time จาก yfinance"""
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

def extract_dime_portfolio(sh, ws_name, broker_name):
    """ตัวแยกวิเคราะห์ข้อมูลบัญชี Dime ที่ยืดหยุ่นต่อโครงสร้างคอลัมน์แบบสากล"""
    records = []
    try:
        ws = sh.worksheet(ws_name)
        data = ws.get_all_values()
        if len(data) > 1:
            # ค้นหาแถวที่เป็น Header จริงๆ (เผื่อผู้ใช้เว้นบรรทัดว่าง)
            header_idx = 0
            for i, row in enumerate(data[:5]):
                if any("หุ้น" in str(cell) or "Ticker" in str(cell) or "Sym" in str(cell) for cell in row):
                    header_idx = i
                    break

            headers = [str(h).strip() for h in data[header_idx]]
            df = pd.DataFrame(data[header_idx+1:], columns=headers)

            # สแกนหาคอลัมน์ที่ต้องการด้วย Keyword ที่ฉลาดขึ้น
            sym_col = next((c for c in df.columns if "หุ้น" in c or "Ticker" in c or "Sym" in c), None)
            qty_col = next((c for c in df.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), None)
            cost_col = next((c for c in df.columns if "ต้นทุน" in c or "Avg" in c or "Cost" in c), None)

            if sym_col and qty_col and cost_col:
                for sym, grp in df.groupby(sym_col):
                    clean_sym = str(sym).strip().upper()
                    if not clean_sym or clean_sym == 'NAN' or clean_sym == 'NONE':
                        continue

                    tot_qty = 0.0
                    tot_cost_cash = 0.0

                    for _, row in grp.iterrows():
                        q = clean_val(row.get(qty_col, 0))
                        c = clean_val(row.get(cost_col, 0))
                        if q > 0:
                            tot_qty += q
                            tot_cost_cash += (q * c)

                    if tot_qty > 0.0001:
                        avg_cost = tot_cost_cash / tot_qty
                        records.append({
                            "Broker": broker_name,
                            "Symbol": clean_sym,
                            "Qty": tot_qty,
                            "Cost": avg_cost
                        })
    except Exception:
        pass
    return records

def load_master_holdings_from_sheets():
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

        # ==========================================================
        # 1. ดึงพอร์ต Webull  ***โหมด TRANSACTION LEDGER***
        #    - อ่านทุกแถว (ไม่กรองเฉพาะวันล่าสุดอีกต่อไป)
        #    - BUY = บวกจำนวน / SELL = หักจำนวน
        #    - ต้นทุนเฉลี่ยแบบถ่วงน้ำหนัก (Weighted Average Cost)
        # ==========================================================
        try:
            ws_w = sh.worksheet("Webull_Order_History")
            data_w = ws_w.get_all_values()
            if len(data_w) > 1:
                df_w = pd.DataFrame(data_w[1:], columns=data_w[0])
                cols = list(df_w.columns)

                time_col = next((c for c in cols if "Time" in c or "Date" in c or "วันที่" in c), cols[1] if len(cols) > 1 else None)
                sym_col = next((c for c in cols if "Sym" in c or "Ticker" in c or "หุ้น" in c), cols[2] if len(cols) > 2 else cols[0])
                qty_col = next((c for c in cols if "Qty" in c or "Volume" in c or "จำนวน" in c), cols[4] if len(cols) > 4 else cols[1])
                cost_col = next((c for c in cols if "Pr" in c or "Cost" in c or "ต้นทุน" in c or "Avg" in c), cols[5] if len(cols) > 5 else cols[2])
                status_col = next((c for c in cols if "สถานะ" in c or "Status" in c), cols[6] if len(cols) > 6 else None)

                # หาคอลัมน์ฝั่งซื้อ/ขาย (ถ้าไม่มี จะถือว่าเป็น BUY ทั้งหมด หรือดูจากจำนวนติดลบ)
                used_cols = {time_col, sym_col, qty_col, cost_col, status_col}
                side_col = next(
                    (c for c in cols if c not in used_cols and (
                        "Side" in c or "Action" in c or "ประเภท" in c
                        or "คำสั่ง" in c or "B/S" in c or "Buy" in c or "Type" in c
                    )),
                    None
                )

                # เรียงตามเวลาก่อน เพื่อให้คำนวณต้นทุนเฉลี่ยตามลำดับการซื้อขายจริง
                if time_col and time_col in df_w.columns:
                    df_w["_parsed_date"] = pd.to_datetime(df_w[time_col], errors="coerce")
                else:
                    df_w["_parsed_date"] = pd.NaT
                df_w["_row_order"] = range(len(df_w))
                df_w = df_w.sort_values(by=["_parsed_date", "_row_order"], na_position="last", kind="stable")

                ledger = {}
                for _, r in df_w.iterrows():
                    clean_sym = str(r.get(sym_col, "")).strip().upper()
                    if not clean_sym or clean_sym in ("NAN", "NONE"):
                        continue

                    status_val = str(r.get(status_col, "")).strip().upper() if status_col else ""
                    if status_val in ("C", "CANCEL", "CANCELED", "CANCELLED", "ยกเลิก"):
                        continue

                    qty_raw = clean_val(r.get(qty_col, 0))
                    price = clean_val(r.get(cost_col, 0))
                    if qty_raw == 0:
                        continue

                    side_raw = str(r.get(side_col, "")).strip().upper() if side_col else ""
                    is_sell = ("SELL" in side_raw) or (side_raw == "S") or ("ขาย" in side_raw) or (qty_raw < 0)

                    qty = abs(qty_raw)

                    if clean_sym not in ledger:
                        ledger[clean_sym] = {"qty": 0.0, "cost_cash": 0.0}
                    pos = ledger[clean_sym]

                    if is_sell:
                        avg_now = (pos["cost_cash"] / pos["qty"]) if pos["qty"] > 0 else 0.0
                        sell_qty = min(qty, pos["qty"])
                        pos["qty"] -= sell_qty
                        pos["cost_cash"] -= sell_qty * avg_now
                        if pos["qty"] <= 0.0000001:
                            pos["qty"] = 0.0
                            pos["cost_cash"] = 0.0
                    else:
                        pos["qty"] += qty
                        pos["cost_cash"] += qty * price

                for clean_sym, pos in ledger.items():
                    if pos["qty"] > 0.0001:
                        raw_records.append({
                            "Broker": "Webull",
                            "Symbol": clean_sym,
                            "Qty": pos["qty"],
                            "Cost": pos["cost_cash"] / pos["qty"]
                        })
        except Exception:
            pass

        # 2. ดึงพอร์ต Dime US & TH ผ่านฟังก์ชันแยกที่มีความยืดหยุ่นสูง
        dime_us_records = extract_dime_portfolio(sh, "Dime_Portfolio", "Dime US")
        raw_records.extend(dime_us_records)

        dime_th_records = extract_dime_portfolio(sh, "Dime_TH_Portfolio", "Dime TH")
        raw_records.extend(dime_th_records)

        if not raw_records:
            return pd.DataFrame()

        df_holdings = pd.DataFrame(raw_records)

        # 3. รวมรายการหุ้นเพื่อยิงดึงราคาตลาดสด yfinance
        us_symbols = df_holdings[df_holdings["Broker"].isin(["Webull", "Dime US"])]["Symbol"].unique().tolist()
        th_symbols = [f"{s}.BK" for s in df_holdings[df_holdings["Broker"] == "Dime TH"]["Symbol"].unique().tolist()]

        all_symbols = us_symbols + th_symbols
        live_prices = fetch_live_prices(all_symbols)

        fx_rate = st.session_state.get("usd_thb_rate", 35.0)

        # 4. คำนวณ Market Value / Unrealized PnL สด
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
            else:  # Dime TH
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
            val_num = float(s.replace('

---

### วิธีทดสอบ (ทำตามลำดับ)
1. เซฟไฟล์ทับ → รัน `streamlit run app.py`
2. เข้าหน้า Portfolio → แท็บ **🦅 Webull US**
3. ต้องเห็นครบ **12 ตัว** (RR, SOFI, SVCO, TLRY, TMDX, TRX, TSYY, UUUU, VIVO, WINT + NEE + VST)
4. เช็ค "เงินลงทุนรวม" ว่าตรงกับผลรวม Qty × Pr ทุกแถวในชีท

### ⚠️ 1 จุดที่ยังต้องยืนยัน
ถ้าแถว 27–36 (วันที่ 2026-08-01) เป็น **"ยอดคงเหลือ ณ วันนั้น"** ไม่ใช่รายการซื้อขายทีละครั้ง → ยอดอาจเบิ้ลได้ ให้ดูง่าย ๆ ว่ามีหุ้นตัวเดียวกันขึ้นซ้ำ 2 แถวไหม ถ้าไม่ซ้ำเลยและตัวเลขตรงกับ Webull app → ใช้ได้เลยครับ

รันแล้วเป็นยังไงบ้างครับ ตัวเลขตรงกับใน Webull ไหม? ถ้าเพี้ยนตรงไหน ส่งภาพหน้าจอ + ภาพชีทมาได้เลย 👍, '').replace('฿', '').replace(',', '').replace('%', '').replace('+', ''))
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

    if not df_sub.empty:
        inv = df_sub["Invested_USD"].sum() * multiplier
        mkt = df_sub["Market_Value_USD"].sum() * multiplier
        pnl = mkt - inv
        pct = (pnl / inv * 100) if inv > 0 else 0.0

        pnl_class = "text-green" if pnl >= 0 else "text-red"
        pnl_prefix = "+" if pnl >= 0 else ""

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">เงินลงทุนรวม ({broker_name})</div><div class="metric-value">{symbol}{inv:,.2f}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">มูลค่าตลาดรวม ({broker_name})</div><div class="metric-value">{symbol}{mkt:,.2f}</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">กำไร / ขาดทุนสุทธิ ({broker_name})</div><div class="metric-value {pnl_class}">{pnl_prefix}{symbol}{pnl:,.2f} ({pct:+.2f}%)</div></div>', unsafe_allow_html=True)
    else:
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="metric-card"><div class="metric-label">เงินลงทุนรวม ({broker_name})</div><div class="metric-value">{symbol}0.00</div></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card"><div class="metric-label">มูลค่าตลาดรวม ({broker_name})</div><div class="metric-value">{symbol}0.00</div></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card"><div class="metric-label">กำไร / ขาดทุนสุทธิ ({broker_name})</div><div class="metric-value">{symbol}0.00 (0.00%)</div></div>', unsafe_allow_html=True)

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

import streamlit as st
import pandas as pd
from datetime import datetime
import yfinance as yf

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ==========================================
# 1. PAGE CONFIG & MODERN DARK CSS
# ==========================================
st.set_page_config(page_title="US Daily Price Comparison", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

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

    .metric-card {
        background-color: #0f1115;
        padding: 16px 20px;
        border-radius: 12px;
        border: 1px solid #1a1d24;
        text-align: center;
        margin-bottom: 15px;
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
    .text-green { color: #4ade80 !important; }
    .text-red { color: #f87171 !important; }
    .text-cyan { color: #38bdf8 !important; }
    </style>
""", unsafe_allow_html=True)

# Header Section
st.markdown('<div class="page-title-minimal">US Daily Price Tracker (เปรียบเทียบราคาหุ้นสหรัฐฯ กับเมื่อวาน)</div>', unsafe_allow_html=True)
st.markdown('<div class="page-subtitle-minimal">วิเคราะห์การเคลื่อนไหวของราคารายวัน เฉพาะหุ้นที่มีอยู่ใน US Consolidated (Webull + Dime US)</div>', unsafe_allow_html=True)

# ==========================================
# 2. GOOGLE SHEETS & DATA PIPELINE
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

def clean_val(val):
    if pd.isna(val) or val == "": return 0.0
    val_str = str(val).replace(",", "").replace("%", "").replace("$", "").replace("฿", "").strip()
    try: return float(val_str)
    except: return 0.0

@st.cache_data(ttl=60)
def load_us_consolidated_holdings():
    """ดึงข้อมูลเฉพาะหุ้นสหรัฐฯ จาก Webull และ Dime US มารวมกัน"""
    gc = get_gspread_client()
    if not gc:
        return pd.DataFrame()
    
    us_holdings = {}
    try:
        sheet_title = st.secrets.get("SPREADSHEET_NAME", "หุ้นของเรา")
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            sheet_title = st.secrets["connections"]["gsheets"].get("spreadsheet", sheet_title)
            
        try: sh = gc.open(sheet_title)
        except Exception: sh = gc.open_by_key(sheet_title) if len(sheet_title) > 20 else gc.open_by_url(sheet_title)

        # 1. ดึง Webull_Order_History
        try:
            ws_w = sh.worksheet("Webull_Order_History")
            data_w = ws_w.get_all_values()
            if len(data_w) > 1:
                df_w = pd.DataFrame(data_w[1:], columns=data_w[0])
                cols = list(df_w.columns)
                sym_col = next((c for c in cols if "Sym" in c or "Ticker" in c or "หุ้น" in c), cols[2] if len(cols) > 2 else cols[0])
                side_col = next((c for c in cols if "Side" in c or "ประเภท" in c or "Action" in c), cols[3] if len(cols) > 3 else None)
                qty_col = next((c for c in cols if "Qty" in c or "Volume" in c or "จำนวน" in c), cols[4] if len(cols) > 4 else cols[1])
                status_col = next((c for c in cols if "สถานะ" in c or "Status" in c), cols[6] if len(cols) > 6 else None)

                for _, r in df_w.iterrows():
                    status_val = str(r.get(status_col, "")).strip().upper() if status_col else ""
                    if status_val == "C": continue
                    sym = str(r.get(sym_col, "")).strip().upper()
                    if not sym or sym in ['NAN', 'NONE']: continue
                    
                    q = clean_val(r.get(qty_col, 0))
                    side_val = str(r.get(side_col, "BUY")).strip().upper() if side_col else "BUY"
                    
                    if "BUY" in side_val or "ซื้อ" in side_val:
                        us_holdings[sym] = us_holdings.get(sym, 0.0) + q
                    elif "SELL" in side_val or "ขาย" in side_val:
                        us_holdings[sym] = us_holdings.get(sym, 0.0) - q
        except Exception:
            pass

        # 2. ดึง Dime_Portfolio (US)
        try:
            ws_d = sh.worksheet("Dime_Portfolio")
            data_d = ws_d.get_all_values()
            if len(data_d) > 1:
                header_idx = 0
                for i, row in enumerate(data_d[:5]):
                    if any("หุ้น" in str(c) or "Ticker" in str(c) for c in row):
                        header_idx = i
                        break
                headers = [str(h).strip() for h in data_d[header_idx]]
                df_d = pd.DataFrame(data_d[header_idx+1:], columns=headers)
                sym_col = next((c for c in df_d.columns if "หุ้น" in c or "Ticker" in c or "Sym" in c), None)
                qty_col = next((c for c in df_d.columns if "จำนวน" in c or "Volume" in c or "Qty" in c), None)

                if sym_col and qty_col:
                    for _, r in df_d.iterrows():
                        sym = str(r.get(sym_col, "")).strip().upper()
                        if not sym or sym in ['NAN', 'NONE']: continue
                        q = clean_val(r.get(qty_col, 0))
                        if q > 0:
                            us_holdings[sym] = us_holdings.get(sym, 0.0) + q
        except Exception:
            pass

    except Exception:
        pass

    clean_records = [{"Symbol": sym, "Qty": qty} for sym, qty in us_holdings.items() if qty > 0.0001]
    return pd.DataFrame(clean_records)

def fetch_daily_comparison_prices(symbols):
    """ดึงราคาปิดเมื่อวาน (Prev Close) และราคาล่าสุด (Live Price) ผ่าน yfinance"""
    data = {}
    if not symbols:
        return data
    for sym in symbols:
        try:
            t = yf.Ticker(sym)
            fast = t.fast_info
            prev_close = fast.previous_close
            curr_price = fast.last_price

            if curr_price is None or prev_close is None:
                h = t.history(period="5d")
                if len(h) >= 2:
                    prev_close = float(h['Close'].iloc[-2])
                    curr_price = float(h['Close'].iloc[-1])
                elif len(h) == 1:
                    prev_close = float(h['Close'].iloc[-1])
                    curr_price = float(h['Close'].iloc[-1])

            if prev_close and curr_price:
                data[sym] = {
                    "prev_close": float(prev_close),
                    "curr_price": float(curr_price)
                }
        except Exception:
            pass
    return data

# ==========================================
# 3. DATA PROCESSING & RENDER
# ==========================================
col_top_sync, _ = st.columns([1.5, 3.5])
with col_top_sync:
    if st.button("🔄 รีเฟรชราคาตลาดสด", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.toast("✅ ดึงข้อมูลราคาตลาดล่าสุดเรียบร้อย!", icon="🚀")
        st.rerun()

df_us = load_us_consolidated_holdings()

if not df_us.empty:
    symbols = df_us["Symbol"].tolist()
    price_info = fetch_daily_comparison_prices(symbols)

    rows = []
    for _, r in df_us.iterrows():
        sym = r["Symbol"]
        qty = r["Qty"]
        p_data = price_info.get(sym)

        if p_data:
            prev_close = p_data["prev_close"]
            curr_price = p_data["curr_price"]
            diff = curr_price - prev_close
            pct = (diff / prev_close * 100) if prev_close > 0 else 0.0
            today_pnl = diff * qty

            rows.append({
                "Symbol": sym,
                "Qty": qty,
                "Prev_Close": prev_close,
                "Current_Price": curr_price,
                "Price_Diff": diff,
                "Pct_Change": pct,
                "Today_PnL": today_pnl
            })
        else:
            rows.append({
                "Symbol": sym,
                "Qty": qty,
                "Prev_Close": 0.0,
                "Current_Price": 0.0,
                "Price_Diff": 0.0,
                "Pct_Change": 0.0,
                "Today_PnL": 0.0
            })

    df_comp = pd.DataFrame(rows).sort_values(by="Pct_Change", ascending=False).reset_index(drop=True)

    # Metric Cards บนสุด
    tot_today_pnl = df_comp["Today_PnL"].sum()
    pnl_class = "text-green" if tot_today_pnl >= 0 else "text-red"
    pnl_prefix = "+" if tot_today_pnl >= 0 else ""

    top_gainer = df_comp.iloc[0] if not df_comp.empty else None
    top_loser = df_comp.iloc[-1] if not df_comp.empty else None

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-label">ผลกระทบต่อพอร์ต US วันนี้ (Today Impact)</div><div class="metric-value {pnl_class}">{pnl_prefix}${tot_today_pnl:,.2f}</div></div>', unsafe_allow_html=True)
    with c2:
        if top_gainer is not None:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🚀 ขึ้นแรงสุดวันนี้ (Top Gainer)</div><div class="metric-value text-green">{top_gainer["Symbol"]} ({top_gainer["Pct_Change"]:+.2f}%)</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card"><div class="metric-label">Top Gainer</div><div class="metric-value">-</div></div>', unsafe_allow_html=True)
    with c3:
        if top_loser is not None:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🔻 ลงหนักสุดวันนี้ (Top Loser)</div><div class="metric-value text-red">{top_loser["Symbol"]} ({top_loser["Pct_Change"]:+.2f}%)</div></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="metric-card"><div class="metric-label">Top Loser</div><div class="metric-value">-</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    # ฟังก์ชันตรวจจับและไฮไลต์สีเขียว/แดงอย่างแม่นยำ
    def highlight_change(val):
        if val is None or pd.isna(val):
            return ''
        s = str(val).strip()
        # ตรวจสอบจากเครื่องหมาย String นำหน้าโดยตรง
        if s.startswith("+"):
            return 'background-color: rgba(34, 197, 94, 0.20); color: #4ade80; font-weight: 700;'
        elif s.startswith("-"):
            return 'background-color: rgba(239, 68, 68, 0.20); color: #f87171; font-weight: 700;'
        
        # กรณีแปลงเป็นตัวเลขเพื่อความชัวร์
        try:
            num = float(s.replace('$', '').replace('%', '').replace(',', '').replace('+', '').strip())
            if num > 0.0001:
                return 'background-color: rgba(34, 197, 94, 0.20); color: #4ade80; font-weight: 700;'
            elif num < -0.0001:
                return 'background-color: rgba(239, 68, 68, 0.20); color: #f87171; font-weight: 700;'
        except:
            pass
        return 'color: #9ca3af;'

    df_disp = df_comp.copy()
    df_disp.columns = [
        "ชื่อหุ้น (Symbol)", 
        "จำนวนหุ้นที่ถือ (Qty)", 
        "ราคาปิดเมื่อวาน ($)", 
        "ราคาปัจจุบัน ($)", 
        "ส่วนต่างราคา ($)", 
        "เปลี่ยนแปลงวันนี้ (%)", 
        "กำไร/ขาดทุนวันนี้ ($)"
    ]

    formatted_df = df_disp.style.format({
        "จำนวนหุ้นที่ถือ (Qty)": "{:,.4f}",
        "ราคาปิดเมื่อวาน ($)": "${:,.2f}",
        "ราคาปัจจุบัน ($)": "${:,.2f}",
        "ส่วนต่างราคา ($)": "${:+,.2f}",
        "เปลี่ยนแปลงวันนี้ (%)": "{:+.2f}%",
        "กำไร/ขาดทุนวันนี้ ($)": "${:+,.2f}"
    }).map(highlight_change, subset=["ส่วนต่างราคา ($)", "เปลี่ยนแปลงวันนี้ (%)", "กำไร/ขาดทุนวันนี้ ($)"])

    st.dataframe(formatted_df, use_container_width=True, hide_index=True)

else:
    st.info("💡 ไม่พบรายการหุ้นสหรัฐฯ ในพอร์ต US Consolidated")

import os
import json
import base64
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

try:
    import gspread
    from google.oauth2.service_account import Credentials
    HAS_GSPREAD = True
except ImportError:
    HAS_GSPREAD = False

# ==========================================
# 1. SHARED DATA PIPELINE & HELPERS
# ==========================================
@st.cache_data(ttl=60)
def get_usd_thb_rate():
    try:
        ticker = yf.Ticker("USDTHB=X")
        rate = ticker.fast_info.get('last_price') or ticker.info.get('regularMarketPrice') or 35.0
        return float(rate)
    except:
        return 35.0

def get_gspread_client():
    if not HAS_GSPREAD:
        return None
    try:
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

def load_webull_from_gsheet():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Webull_Order_History")
            records = worksheet.get_all_records()
            if records:
                df_raw = pd.DataFrame(records)
                
                # Dynamic Column Identification
                c_sym = next((c for c in df_raw.columns if "Sym" in c or "Ticker" in c or "หุ้น" in c), df_raw.columns[2])
                c_qty = next((c for c in df_raw.columns if "Qty" in c or "จำนวน" in c or "Volume" in c), df_raw.columns[4])
                c_pr = next((c for c in df_raw.columns if "Pr" in c or "Price" in c or "ต้นทุน" in c), df_raw.columns[5])
                c_side = next((c for c in df_raw.columns if "Side" in c or "ประเภท" in c), None)
                c_time = next((c for c in df_raw.columns if "Time" in c or "Date" in c or "เวลา" in c), df_raw.columns[1])

                # Clean strings & handle empty Side (Snapshot records)
                df_raw["Clean_Sym"] = df_raw[c_sym].astype(str).str.strip().str.upper()
                if c_side:
                    df_raw["Clean_Side"] = df_raw[c_side].astype(str).str.strip().str.upper()
                else:
                    df_raw["Clean_Side"] = ""

                # Filter ONLY Snapshot rows where Side is empty (or blank)
                df_snapshots = df_raw[df_raw["Clean_Side"].isin(["", "NAN", "NONE"])].copy()

                if not df_snapshots.empty:
                    # Get the latest Snapshot row per Symbol by sorting Time/Index
                    df_snapshots = df_snapshots.drop_duplicates(subset=["Clean_Sym"], keep="first")
                    
                    for _, r in df_snapshots.iterrows():
                        sym = r["Clean_Sym"]
                        if not sym: continue
                        
                        try: qty = float(str(r.get(c_qty, 0)).replace(",", ""))
                        except: qty = 0.0
                        
                        try: pr = float(str(r.get(c_pr, 0)).replace(",", ""))
                        except: pr = 0.0

                        if qty > 0:
                            holdings.append({
                                "Symbol": sym,
                                "Qty": qty,
                                "Cost": pr,
                                "Broker": "Webull"
                            })
                else:
                    # Fallback: If no Snapshot rows found, aggregate BUY/SELL transactions
                    grouped = {}
                    for _, r in df_raw.iterrows():
                        sym = r["Clean_Sym"]
                        if not sym: continue
                        
                        try: qty = float(str(r.get(c_qty, 0)).replace(",", ""))
                        except: qty = 0.0
                        
                        try: pr = float(str(r.get(c_pr, 0)).replace(",", ""))
                        except: pr = 0.0

                        side = r["Clean_Side"]
                        if "SELL" in side or side == "S":
                            qty = -abs(qty)

                        if sym not in grouped:
                            grouped[sym] = {"tot_qty": 0.0, "tot_cost_val": 0.0}
                        
                        if qty > 0:
                            grouped[sym]["tot_qty"] += qty
                            grouped[sym]["tot_cost_val"] += (qty * pr)
                        elif qty < 0:
                            grouped[sym]["tot_qty"] += qty

                    for sym, data in grouped.items():
                        if data["tot_qty"] > 0:
                            avg_cost = data["tot_cost_val"] / data["tot_qty"] if data["tot_qty"] > 0 else 0.0
                            holdings.append({
                                "Symbol": sym,
                                "Qty": data["tot_qty"],
                                "Cost": avg_cost,
                                "Broker": "Webull"
                            })
        except Exception as e:
            pass
    return holdings

def load_dime_us_from_gsheet():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                        "Broker": "Dime US",
                        "Manual_Price": r.get("ราคาปัจจุบันล็อก (Manual Price)", "")
                    })
        except:
            pass
    return holdings

def load_dime_th_from_gsheet():
    holdings = []
    gc = get_gspread_client()
    if gc:
        try:
            sh = gc.open("หุ้นของเรา")
            worksheet = sh.worksheet("Dime_TH_Portfolio")
            records = worksheet.get_all_records()
            for r in records:
                sym = str(r.get("หุ้น (Ticker)", "")).strip().upper()
                if sym:
                    holdings.append({
                        "Symbol": sym,
                        "Qty": float(r.get("จำนวนหุ้น (Volume)", 0)),
                        "Cost": float(r.get("ต้นทุนเฉลี่ย (Avg Cost)", 0)),
                        "Broker": "Dime TH"
                    })
        except:
            pass
    return holdings

def fetch_full_portfolio_df():
    fx_rate = get_usd_thb_rate()
    w_holdings = load_webull_from_gsheet()
    d_us_holdings = load_dime_us_from_gsheet()
    d_th_holdings = load_dime_th_from_gsheet()
    
    all_holdings = w_holdings + d_us_holdings + d_th_holdings
    if not all_holdings:
        return pd.DataFrame(), fx_rate

    df_raw = pd.DataFrame(all_holdings)
    live_prices = {}

    for index, row in df_raw.iterrows():
        sym = row['Symbol']
        broker = row['Broker']
        
        if broker == "Dime US" and row.get("Manual_Price") != "" and row.get("Manual_Price") is not None:
            try: live_prices[sym] = float(row["Manual_Price"])
            except: live_prices[sym] = 0.0

        if sym not in live_prices or live_prices[sym] == 0.0:
            yf_sym = f"{sym}.BK" if broker == "Dime TH" and not sym.endswith(".BK") else sym
            try:
                t_data = yf.Ticker(yf_sym)
                p = t_data.info.get('currentPrice') or t_data.info.get('regularMarketPrice') or t_data.fast_info.get('last_price')
                if not p:
                    h = t_data.history(period="1d")
                    if not h.empty: p = h['Close'].iloc[-1]
                live_prices[sym] = float(p) if p else 0.0
            except:
                live_prices[sym] = 0.0

    portfolio_rows = []
    for index, row in df_raw.iterrows():
        sym = row['Symbol']
        qty = row['Qty']
        cost_in = row['Cost']
        broker = row['Broker']
        
        price_raw = live_prices.get(sym, 0)
        if price_raw == 0: price_raw = cost_in

        if broker == "Dime TH":
            invested_usd = (qty * cost_in) / fx_rate
            market_val_usd = (qty * price_raw) / fx_rate
        else:
            invested_usd = qty * cost_in
            market_val_usd = qty * price_raw

        pnl_usd = market_val_usd - invested_usd
        pnl_pct = (pnl_usd / invested_usd * 100) if invested_usd > 0 else 0.0

        portfolio_rows.append({
            "Symbol": sym,
            "Broker": broker,
            "Qty": qty,
            "Cost": cost_in,
            "Price": price_raw,
            "Invested_USD": invested_usd,
            "Market_Value_USD": market_val_usd,
            "PnL_USD": pnl_usd,
            "PnL_Pct": pnl_pct
        })

    df_port = pd.DataFrame(portfolio_rows)
    st.session_state["all_holdings_df"] = df_port
    st.session_state["usd_thb_rate"] = fx_rate
    return df_port, fx_rate

# ==========================================
# 2. MAIN PAGE RENDER
# ==========================================
st.title("Portfolio Overview")
st.caption("วิเคราะห์สัดส่วนการถือครองและผลตอบแทนรายโบรกเกอร์")

df_port, fx_rate = fetch_full_portfolio_df()

c_curr, _ = st.columns([1, 3])
with c_curr:
    currency_selected = st.radio("Display Currency", ("USD ($)", "THB (฿)"), horizontal=True, index=0)

is_usd = "USD" in currency_selected
multiplier = 1.0 if is_usd else fx_rate
symbol = "$" if is_usd else "฿"

if "port_tab" not in st.session_state:
    st.session_state["port_tab"] = "All In One"

tabs_list = ["All In One", "Webull US", "Dime US", "Dime TH", "US Consolidated"]
t_cols = st.columns(len(tabs_list))

for idx, t_name in enumerate(tabs_list):
    with t_cols[idx]:
        btn_kind = "primary" if st.session_state["port_tab"] == t_name else "secondary"
        if st.button(t_name, key=f"port_tab_btn_{t_name}", type=btn_kind, use_container_width=True):
            st.session_state["port_tab"] = t_name
            st.rerun()

current_tab = st.session_state["port_tab"]
st.markdown("<br>", unsafe_allow_html=True)

if df_port.empty:
    st.info("💡 ไม่พบข้อมูลพอร์ตโฟลิโอ กรุณาตรวจสอบ Google Sheets หรือบันทึกรายการใน Trade Execution")
else:
    # Filter DF based on tab selection
    if current_tab == "Webull US":
        sub_df = df_port[df_port["Broker"] == "Webull"].copy()
    elif current_tab == "Dime US":
        sub_df = df_port[df_port["Broker"] == "Dime US"].copy()
    elif current_tab == "Dime TH":
        sub_df = df_port[df_port["Broker"] == "Dime TH"].copy()
    elif current_tab == "US Consolidated":
        sub_df = df_port[df_port["Broker"].isin(["Webull", "Dime US"])].copy()
        if not sub_df.empty:
            # Consolidate US stocks across Webull & Dime
            sub_df = sub_df.groupby("Symbol").apply(lambda x: pd.Series({
                "Broker": "US Consolidated",
                "Qty": x["Qty"].sum(),
                "Cost": (x["Invested_USD"].sum() / x["Qty"].sum()) if x["Qty"].sum() > 0 else 0,
                "Price": x["Price"].iloc[0],
                "Invested_USD": x["Invested_USD"].sum(),
                "Market_Value_USD": x["Market_Value_USD"].sum(),
                "PnL_USD": x["Market_Value_USD"].sum() - x["Invested_USD"].sum(),
                "PnL_Pct": ((x["Market_Value_USD"].sum() - x["Invested_USD"].sum()) / x["Invested_USD"].sum() * 100) if x["Invested_USD"].sum() > 0 else 0
            })).reset_index()
    else:
        sub_df = df_port.copy()

    if sub_df.empty:
        st.warning(f"ไม่พบรายการถือครองในหมวด {current_tab}")
    else:
        tot_inv = sub_df["Invested_USD"].sum() * multiplier
        tot_mkt = sub_df["Market_Value_USD"].sum() * multiplier
        tot_pnl = tot_mkt - tot_inv
        tot_pnl_pct = (tot_pnl / tot_inv * 100) if tot_inv > 0 else 0.0

        # High Level Metrics Row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Invested Capital", f"{symbol}{tot_inv:,.2f}")
        m2.metric("Market Value", f"{symbol}{tot_mkt:,.2f}")
        m3.metric("Total Return ($)", f"{symbol}{tot_pnl:,.2f}", delta=f"{tot_pnl:,.2f}")
        m4.metric("Total Return (%)", f"{tot_pnl_pct:.2f}%", delta=f"{tot_pnl_pct:.2f}%")

        st.markdown("<hr style='border-color: #1f232d;'>", unsafe_allow_html=True)

        # Prepare Table View
        disp_df = sub_df.copy()
        disp_df["Qty"] = disp_df["Qty"].map("{:,.4f}".format)
        disp_df["Cost"] = disp_df["Cost"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["Price"] = disp_df["Price"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["Invested"] = disp_df["Invested_USD"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["Market Value"] = disp_df["Market_Value_USD"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["PnL ($)"] = disp_df["PnL_USD"].map(lambda x: f"{symbol}{x * multiplier:,.2f}")
        disp_df["PnL (%)"] = disp_df["PnL_Pct"].map("{:,.2f}%".format)

        show_cols = ["Symbol", "Broker", "Qty", "Cost", "Price", "Invested", "Market Value", "PnL ($)", "PnL (%)"]
        st.dataframe(disp_df[show_cols], use_container_width=True, hide_index=True)

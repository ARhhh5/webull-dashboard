import json
import base64
import streamlit as st
import pandas as pd
import gspread
import yfinance as yf
import plotly.express as px

st.set_page_config(page_title="Portfolio Overview", layout="wide")

st.markdown("""
    <style>
    .metric-card {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2a2e39;
        text-align: center;
        margin-bottom: 15px;
    }
    .metric-label {
        color: #848e9c;
        font-size: 14px;
        margin-bottom: 8px;
    }
    .metric-value {
        font-size: 26px;
        font-weight: bold;
        color: #ffffff;
    }
    .text-green { color: #00c853; }
    .text-red { color: #ff3d00; }
    </style>
""", unsafe_allow_html=True)

st.title("💼 สรุปภาพรวมพอร์ตการลงทุน (Total Portfolio Overview)")
st.markdown("---")

# ==========================================
# 1. เชื่อมต่อ Google Sheets
# ==========================================
@st.cache_resource
def init_gsheet():
    try:
        google_secrets = st.secrets.get("Google", {})
        cred_base64 = google_secrets.get("credentials_base64", "")
        if not cred_base64: return None
        cred_dict = json.loads(base64.b64decode(cred_base64).decode("utf-8"))
        gc = gspread.service_account_from_dict(cred_dict)
        return gc
    except Exception:
        return None

@st.cache_data(ttl=300)
def get_fx_usd_thb():
    try:
        ticker = yf.Ticker("USDTHB=X")
        price = ticker.info.get("regularMarketPrice", ticker.info.get("currentPrice", 35.0))
        return float(price)
    except Exception:
        return 35.0

# ==========================================
# 2. โหลดและประมวลผลข้อมูลพอร์ตทั้ง 3 โบรก
# ==========================================
def load_all_portfolios():
    gc = init_gsheet()
    usd_thb_rate = get_fx_usd_thb()
    
    webull_data = []
    dime_us_data = []
    dime_th_data = []
    
    if not gc:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), usd_thb_rate

    try:
        sh = gc.open("หุ้นของเรา")
        
        # --- 2.1 Webull Data ---
        try:
            ws1 = sh.worksheet("Webull_Order_History")
            df_w = pd.DataFrame(ws1.get_all_records())
            if not df_w.empty:
                sym_col = next((c for c in df_w.columns if 'sym' in str(c).lower() or 'symbol' in str(c).lower()), 'Symbol')
                side_col = next((c for c in df_w.columns if 'side' in str(c).lower() or 'buy/sell' in str(c).lower()), 'Side')
                qty_col = next((c for c in df_w.columns if 'qty' in str(c).lower() or 'quantity' in str(c).lower()), 'Qty')
                price_col = next((c for c in df_w.columns if 'price' in str(c).lower()), 'Price')
                
                for symbol, group in df_w.groupby(sym_col):
                    sym_clean = str(symbol).strip().upper()
                    if not sym_clean or sym_clean == 'NAN': continue
                    
                    buy_qty, sell_qty = 0.0, 0.0
                    total_buy_cost = 0.0
                    for _, row in group.iterrows():
                        side = str(row[side_col]).upper()
                        try:
                            q = float(str(row[qty_col]).replace(",", "").replace("$", ""))
                            p = float(str(row[price_col]).replace(",", "").replace("$", ""))
                        except: continue
                        
                        if "BUY" in side or "ซื้อ" in side:
                            buy_qty += q
                            total_buy_cost += (q * p)
                        elif "SELL" in side or "ขาย" in side:
                            sell_qty += q
                    
                    rem_qty = buy_qty - sell_qty
                    if rem_qty > 0.001:
                        avg_cost = total_buy_cost / buy_qty if buy_qty > 0 else 0.0
                        webull_data.append({
                            "Symbol": sym_clean,
                            "Source": "Webull",
                            "Qty": rem_qty,
                            "Avg_Cost": avg_cost,
                            "Total_Cost_USD": rem_qty * avg_cost
                        })
        except Exception: pass

        # --- 2.2 Dime US Data ---
        try:
            ws2 = sh.worksheet("Dime_Portfolio")
            df_d = pd.DataFrame(ws2.get_all_records())
            if not df_d.empty:
                sym_col = next((c for c in df_d.columns if 'sym' in str(c).lower() or 'ticker' in str(c).lower() or 'หุ้น' in str(c)), 'Symbol')
                qty_col = next((c for c in df_d.columns if 'qty' in str(c).lower() or 'จำนวน' in str(c)), 'Qty')
                cost_col = next((c for c in df_d.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c)), 'Avg_Cost')
                
                for _, row in df_d.iterrows():
                    sym = str(row.get(sym_col, "")).strip().upper()
                    if not sym or sym == 'NAN': continue
                    try:
                        q = float(str(row.get(qty_col, 0)).replace(",", ""))
                        c = float(str(row.get(cost_col, 0)).replace(",", "").replace("$", ""))
                        if q > 0:
                            dime_us_data.append({
                                "Symbol": sym,
                                "Source": "Dime US",
                                "Qty": q,
                                "Avg_Cost": c,
                                "Total_Cost_USD": q * c
                            })
                    except: continue
        except Exception: pass

        # --- 2.3 Dime TH Data ---
        try:
            ws3 = sh.worksheet("Dime_TH_Portfolio")
            df_th = pd.DataFrame(ws3.get_all_records())
            if not df_th.empty:
                sym_col = next((c for c in df_th.columns if 'sym' in str(c).lower() or 'ticker' in str(c).lower() or 'หุ้น' in str(c)), 'Symbol')
                qty_col = next((c for c in df_th.columns if 'qty' in str(c).lower() or 'จำนวน' in str(c)), 'Qty')
                cost_col = next((c for c in df_th.columns if 'cost' in str(c).lower() or 'ต้นทุน' in str(c)), 'Avg_Cost')
                
                for _, row in df_th.iterrows():
                    sym = str(row.get(sym_col, "")).strip().upper()
                    if not sym or sym == 'NAN': continue
                    try:
                        q = float(str(row.get(qty_col, 0)).replace(",", ""))
                        c_thb = float(str(row.get(cost_col, 0)).replace(",", "").replace("฿", ""))
                        if q > 0:
                            total_thb = q * c_thb
                            dime_th_data.append({
                                "Symbol": sym,
                                "Source": "Dime TH",
                                "Qty": q,
                                "Avg_Cost_THB": c_thb,
                                "Total_Cost_THB": total_thb,
                                "Total_Cost_USD": total_thb / usd_thb_rate
                            })
                    except: continue
        except Exception: pass

    except Exception: pass

    return pd.DataFrame(webull_data), pd.DataFrame(dime_us_data), pd.DataFrame(dime_th_data), usd_thb_rate

# ==========================================
# 3. ฟังก์ชันดึงราคาเรียลไทม์
# ==========================================
def fetch_realtime_prices(df_portfolio, is_th=False):
    if df_portfolio.empty:
        return df_portfolio
    
    df = df_portfolio.copy()
    prices = []
    
    for idx, row in df.iterrows():
        sym = row["Symbol"]
        ticker_search = f"{sym}.BK" if is_th and not sym.endswith(".BK") else sym
        try:
            t = yf.Ticker(ticker_search)
            p = t.info.get("currentPrice", t.info.get("regularMarketPrice", 0.0))
            prices.append(p if p else 0.0)
        except:
            prices.append(0.0)
            
    df["Market_Price"] = prices
    
    if not is_th:
        df["Market_Value_USD"] = df["Qty"] * df["Market_Price"]
        df["Unrealized_PL_USD"] = df["Market_Value_USD"] - df["Total_Cost_USD"]
        df["Unrealized_PL_Pct"] = (df["Unrealized_PL_USD"] / df["Total_Cost_USD"]) * 100
    else:
        df["Market_Value_THB"] = df["Qty"] * df["Market_Price"]
        df["Unrealized_PL_THB"] = df["Market_Value_THB"] - df["Total_Cost_THB"]
        df["Unrealized_PL_Pct"] = (df["Unrealized_PL_THB"] / df["Total_Cost_THB"]) * 100
        
    return df

# โหลดข้อมูล
df_webull, df_dime_us, df_dime_th, fx_rate = load_all_portfolios()

# ==========================================
# 4. โครงสร้าง 4 แท็บ (4-Tab Layout)
# ==========================================
tab_all, tab_webull, tab_dime_us, tab_dime_th = st.tabs([
    "📊 1. ภาพรวมทั้งหมด (All In One)", 
    "🦅 2. Webull", 
    "💵 3. Dime US", 
    "🇹🇭 4. Dime TH"
])

# ------------------------------------------
# TAB 1: ALL IN ONE OVERVIEW
# ------------------------------------------
with tab_all:
    st.subheader("🌐 รวมสถิติพอร์ตการลงทุนทุกโบรกเกอร์ (Converted to USD)")
    
    with st.spinner("กำลังประมวลผลและดึงราคาตลาดเรียลไทม์..."):
        df_webull_rt = fetch_realtime_prices(df_webull, is_th=False)
        df_dime_us_rt = fetch_realtime_prices(df_dime_us, is_th=False)
        df_dime_th_rt = fetch_realtime_prices(df_dime_th, is_th=True)
        
        # คำนวณมูลค่ารวมทุกพอร์ตเป็น USD
        total_cost_webull = df_webull_rt["Total_Cost_USD"].sum() if not df_webull_rt.empty else 0.0
        total_val_webull = df_webull_rt["Market_Value_USD"].sum() if not df_webull_rt.empty else 0.0
        
        total_cost_dime_us = df_dime_us_rt["Total_Cost_USD"].sum() if not df_dime_us_rt.empty else 0.0
        total_val_dime_us = df_dime_us_rt["Market_Value_USD"].sum() if not df_dime_us_rt.empty else 0.0
        
        total_cost_dime_th = df_dime_th_rt["Total_Cost_USD"].sum() if not df_dime_th_rt.empty else 0.0
        total_val_dime_th = (df_dime_th_rt["Market_Value_THB"].sum() / fx_rate) if not df_dime_th_rt.empty else 0.0
        
        grand_total_cost = total_cost_webull + total_cost_dime_us + total_cost_dime_th
        grand_total_val = total_val_webull + total_val_dime_us + total_val_dime_th
        grand_pl = grand_total_val - grand_total_cost
        grand_pl_pct = (grand_pl / grand_total_cost * 100) if grand_total_cost > 0 else 0.0
        
        # แสดง KPI Cards
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">💵 เงินลงทุนรวมทั้งหมด (Total Cost)</div>
                    <div class="metric-value">${grand_total_cost:,.2f}</div>
                </div>
            """, unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">📈 มูลค่าตลาดปัจจุบัน (Market Value)</div>
                    <div class="metric-value">${grand_total_val:,.2f}</div>
                </div>
            """, unsafe_allow_html=True)
            
        with c3:
            color_class = "text-green" if grand_pl >= 0 else "text-red"
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">📊 กำไร/ขาดทุน สุทธิ (Total P/L)</div>
                    <div class="metric-value {color_class}">${grand_pl:+,.2f} ({grand_pl_pct:+.2f}%)</div>
                </div>
            """, unsafe_allow_html=True)

        st.caption(f"ℹ️ อัตราแลกเปลี่ยนปัจจุบัน: 1 USD = {fx_rate:.2f} THB")
        st.markdown("---")
        
        # กราฟ Pie Chart สัดส่วนการลงทุน
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            df_pie_source = pd.DataFrame([
                {"Source": "Webull", "Value": total_val_webull},
                {"Source": "Dime US", "Value": total_val_dime_us},
                {"Source": "Dime TH (USD)", "Value": total_val_dime_th}
            ])
            df_pie_source = df_pie_source[df_pie_source["Value"] > 0]
            if not df_pie_source.empty:
                fig1 = px.pie(df_pie_source, names="Source", values="Value", title="สัดส่วนมูลค่าพอร์ตแยกตามโบรกเกอร์ (Broker Allocation)", hole=0.4, template="plotly_dark")
                st.plotly_chart(fig1, use_container_width=True)

        with col_g2:
            # รวมสินทรัพย์ทั้งหมดมาพล็อต
            all_assets = []
            if not df_webull_rt.empty:
                for _, r in df_webull_rt.iterrows(): all_assets.append({"Symbol": r["Symbol"], "Value": r["Market_Value_USD"]})
            if not df_dime_us_rt.empty:
                for _, r in df_dime_us_rt.iterrows(): all_assets.append({"Symbol": r["Symbol"], "Value": r["Market_Value_USD"]})
            if not df_dime_th_rt.empty:
                for _, r in df_dime_th_rt.iterrows(): all_assets.append({"Symbol": r["Symbol"], "Value": r["Market_Value_THB"] / fx_rate})
                
            df_all_assets = pd.DataFrame(all_assets)
            if not df_all_assets.empty:
                fig2 = px.pie(df_all_assets, names="Symbol", values="Value", title="สัดส่วนการถือครองหุ้นทุกตัว (Holdings Allocation)", template="plotly_dark")
                st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------
# TAB 2: WEBULL PORTFOLIO
# ------------------------------------------
with tab_webull:
    st.subheader("🦅 พอร์ตการลงทุน Webull")
    if not df_webull.empty:
        df_w_display = fetch_realtime_prices(df_webull, is_th=False)
        st.dataframe(df_w_display[[
            "Symbol", "Qty", "Avg_Cost", "Market_Price", "Total_Cost_USD", "Market_Value_USD", "Unrealized_PL_USD", "Unrealized_PL_Pct"
        ]].style.format({
            "Qty": "{:,.2f}", "Avg_Cost": "${:,.2f}", "Market_Price": "${:,.2f}",
            "Total_Cost_USD": "${:,.2f}", "Market_Value_USD": "${:,.2f}",
            "Unrealized_PL_USD": "${:+,.2f}", "Unrealized_PL_Pct": "{:+.2f}%"
        }), use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Webull")

# ------------------------------------------
# TAB 3: DIME US PORTFOLIO
# ------------------------------------------
with tab_dime_us:
    st.subheader("💵 พอร์ตการลงทุน Dime US")
    if not df_dime_us.empty:
        df_dus_display = fetch_realtime_prices(df_dime_us, is_th=False)
        st.dataframe(df_dus_display[[
            "Symbol", "Qty", "Avg_Cost", "Market_Price", "Total_Cost_USD", "Market_Value_USD", "Unrealized_PL_USD", "Unrealized_PL_Pct"
        ]].style.format({
            "Qty": "{:,.4f}", "Avg_Cost": "${:,.2f}", "Market_Price": "${:,.2f}",
            "Total_Cost_USD": "${:,.2f}", "Market_Value_USD": "${:,.2f}",
            "Unrealized_PL_USD": "${:+,.2f}", "Unrealized_PL_Pct": "{:+.2f}%"
        }), use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime US")

# ------------------------------------------
# TAB 4: DIME TH PORTFOLIO
# ------------------------------------------
with tab_dime_th:
    st.subheader("🇹🇭 พอร์ตการลงทุน Dime TH (หุ้นไทย)")
    if not df_dime_th.empty:
        df_dth_display = fetch_realtime_prices(df_dime_th, is_th=True)
        st.dataframe(df_dth_display[[
            "Symbol", "Qty", "Avg_Cost_THB", "Market_Price", "Total_Cost_THB", "Market_Value_THB", "Unrealized_PL_THB", "Unrealized_PL_Pct"
        ]].style.format({
            "Qty": "{:,.0f}", "Avg_Cost_THB": "฿{:,.2f}", "Market_Price": "฿{:,.2f}",
            "Total_Cost_THB": "฿{:,.2f}", "Market_Value_THB": "฿{:,.2f}",
            "Unrealized_PL_THB": "฿{:+,.2f}", "Unrealized_PL_Pct": "{:+.2f}%"
        }), use_container_width=True)
    else:
        st.info("ไม่พบข้อมูลรายการถือครองในพอร์ต Dime TH")

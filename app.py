import os
import importlib.util
from datetime import timedelta

import pandas as pd
import streamlit as st

from core import market, ui
from core import portfolio as pf
from core.webull_api import to_float

# ==========================================
# 1. PAGE CONFIGURATION & GLOBAL STYLE
# ==========================================
st.set_page_config(
    page_title="Executive Dashboard - Webull & Dime Desk",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
ui.inject_theme()

TIMEFRAMES = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "YTD": None, "1Y": 365, "MAX": None}
CHART_PERIODS = {"1M": ("1mo", "1d"), "3M": ("3mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d"),
                 "5Y": ("5y", "1wk")}


def _money(value_usd, is_usd, fx, signed=False):
    return ui.fmt_money(value_usd if is_usd else value_usd * fx, "$" if is_usd else "฿", signed)


# ==========================================
# 2. DASHBOARD
# ==========================================
def render_dashboard():
    with st.spinner("กำลังโหลดข้อมูลพอร์ต..."):
        df, status, is_demo = pf.load_holdings()
    fx = market.get_usd_thb()
    st.session_state["usd_thb_rate"] = fx
    st.session_state["all_holdings_df"] = df

    # ---- Header ----
    c_title, c_curr, c_sync = st.columns([2.4, 1.1, 0.7], vertical_alignment="center")
    with c_title:
        ui.page_header("Executive Dashboard", "ภาพรวมพอร์ต Webull + Dime แบบเรียลไทม์")
        chips = "".join(
            ui.status_chip(f"{pf.BROKER_META[b]['icon']} {b} · {status[b]['source']}",
                           ok=not status[b]["error"], detail=status[b]["error"] or "")
            for b in pf.BROKERS
        )
        st.markdown(f"<div style='margin-top:8px'>{chips}</div>", unsafe_allow_html=True)
    with c_curr:
        currency = st.segmented_control("Currency", ["USD", "THB"], default="USD", key="dash_currency",
                                        label_visibility="collapsed")
    with c_sync:
        if st.button("🔄 Sync Snapshot", type="primary", width="stretch", disabled=is_demo):
            ok, msg = pf.sync_snapshot(df)
            (st.toast if ok else st.error)(("✅ " if ok else "⚠️ ") + msg)
    is_usd = (currency or "USD") == "USD"
    cur = "$" if is_usd else "฿"

    if is_demo:
        st.markdown('<div class="demo-banner">🧪 <b>DEMO MODE</b> — ยังไม่พบ secrets ของ Webull API / Google Sheets '
                    'จึงแสดงพอร์ตตัวอย่าง (ราคาจริงจาก yfinance)</div>', unsafe_allow_html=True)

    ui.ticker_tape(df.sort_values("Market_Value_USD", ascending=False).drop_duplicates("Symbol"))

    total = pf.summarize(df)
    balance, _ = pf.get_webull_balance()

    # ---- Key metrics ----
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("มูลค่าพอร์ตรวม", _money(total["market"], is_usd, fx),
              f"{_money(total['day_pnl'], is_usd, fx, True)} ({total['day_pct']:+.2f}%) วันนี้")
    k2.metric("เงินลงทุน (ต้นทุน)", _money(total["invested"], is_usd, fx), f"{total['count']} positions",
              delta_color="off", delta_arrow="off")
    k3.metric("กำไร/ขาดทุนสุทธิ", _money(total["pnl"], is_usd, fx, True), f"{total['pnl_pct']:+.2f}%")
    if balance:
        cash = to_float(balance.get("total_cash_balance"))
        k4.metric("Webull Cash", _money(cash, is_usd, fx), "via Webull API", delta_color="off", delta_arrow="off")
    else:
        k4.metric("USD / THB", f"฿{fx:,.2f}", "yfinance · THB=X", delta_color="off", delta_arrow="off")

    st.write("")
    # ---- Portfolio value + allocation ----
    col_left, col_right = st.columns([1.9, 1.1])
    with col_left:
        with ui.card("value", "Portfolio value"):
            tf = st.segmented_control("Timeframe", list(TIMEFRAMES), default="MAX", key="dash_tf",
                                      label_visibility="collapsed") or "MAX"
            history = pf.load_history()
            if not history.empty:
                max_dt = history["Parsed_Date"].max()
                if tf == "YTD":
                    start = pd.Timestamp(year=max_dt.year, month=1, day=1)
                elif TIMEFRAMES[tf]:
                    start = max_dt - timedelta(days=TIMEFRAMES[tf])
                else:
                    start = history["Parsed_Date"].min()
                view = history[history["Parsed_Date"] >= start]
                view = view if not view.empty else history
                x = view["Parsed_Date"].tolist()
                y = (view["MarketValue"] * (1 if is_usd else fx)).tolist()
                y.append(total["market"] * (1 if is_usd else fx))
                x.append(pd.Timestamp.now())
                ui.show_chart(ui.area_chart(x, y, height=300, prefix=cur))
            else:
                st.caption("ยังไม่มีประวัติใน Portfolio_History — กด **Sync Snapshot** เพื่อเริ่มเก็บข้อมูล · "
                           "แสดงมูลค่าตามหุ้นแทน")
                top = df.groupby("Symbol")["Market_Value_USD"].sum().sort_values().tail(10)
                ui.show_chart(ui.bar_chart(list(top.index), [v * (1 if is_usd else fx) for v in top.values],
                                           height=300, prefix=cur))

    with col_right:
        with ui.card("alloc", "Broker allocation"):
            by_broker = df.groupby("Broker")["Market_Value_USD"].sum().reindex(pf.BROKERS).fillna(0)
            ui.show_chart(ui.donut_chart(
                list(by_broker.index), [v * (1 if is_usd else fx) for v in by_broker.values],
                [pf.BROKER_META[b]["color"] for b in by_broker.index], height=190, prefix=cur))
            rows = ""
            for b, v in by_broker.items():
                share = (v / total["market"] * 100) if total["market"] else 0
                meta = pf.BROKER_META[b]
                rows += (f'<div class="row"><div class="lbl"><span class="dot" style="width:9px;height:9px;'
                         f'border-radius:50%;background:{meta["color"]}"></span>{meta["icon"]} {b}</div>'
                         f'<div class="val">{_money(v, is_usd, fx)}<div class="sub">{share:.1f}%</div></div></div>')
            st.markdown(rows, unsafe_allow_html=True)

    # ---- TradingView-style chart + movers ----
    col_chart, col_movers = st.columns([1.9, 1.1])
    with col_chart:
        with ui.card("chart", "Chart"):
            options = df.sort_values("Market_Value_USD", ascending=False)[["Symbol", "Broker"]].drop_duplicates("Symbol")
            if options.empty:
                st.info("ยังไม่มีหุ้นในพอร์ต")
            else:
                labels = [f"{r.Symbol}  ·  {r.Broker}" for r in options.itertuples()]
                c_sym, c_per = st.columns([1.3, 1.7], vertical_alignment="center")
                pick = c_sym.selectbox("Symbol", labels, label_visibility="collapsed", key="dash_symbol")
                period = c_per.segmented_control("Period", list(CHART_PERIODS), default="6M", key="dash_period",
                                                 label_visibility="collapsed") or "6M"
                row = options.iloc[labels.index(pick)]
                yf_sym = market.yf_symbol(row["Symbol"], row["Broker"])
                ohlc = market.get_ohlc(yf_sym, *CHART_PERIODS[period])
                if ohlc.empty:
                    st.warning(f"ดึงกราฟ {yf_sym} ไม่สำเร็จ")
                else:
                    last, prev = ohlc["Close"].iloc[-1], ohlc["Close"].iloc[-2] if len(ohlc) > 1 else ohlc["Close"].iloc[-1]
                    sym_cur = "฿" if row["Broker"] == pf.DIME_TH else "$"
                    st.markdown(f'<div style="display:flex;gap:12px;align-items:baseline">'
                                f'<span class="big-value">{sym_cur}{last:,.2f}</span>{ui.pct_badge((last / prev - 1) * 100)}'
                                f'<span class="page-sub">{yf_sym} · O/H/L/C · SMA20/50 · ลาก/scroll เพื่อซูม</span></div>',
                                unsafe_allow_html=True)
                    ui.show_chart(ui.candlestick_chart(ohlc, height=440, currency=sym_cur))

    with col_movers:
        with ui.card("movers", "Today's movers"):
            movers = df.sort_values("DayChange_Pct", key=abs, ascending=False).head(8)
            rows = ""
            for r in movers.itertuples():
                sym_cur = "฿" if r.Currency == "THB" else "$"
                meta = pf.BROKER_META[r.Broker]
                rows += (f'<div class="row"><div class="lbl"><b style="color:#fff">{r.Symbol}</b>'
                         f'<span class="sub" style="color:{meta["color"]}">{r.Broker}</span></div>'
                         f'<div class="val">{sym_cur}{r.Price:,.2f} {ui.pct_badge(r.DayChange_Pct)}</div></div>')
            st.markdown(rows or "<div class='page-sub'>—</div>", unsafe_allow_html=True)

    # ---- Per-broker cards (Webull vs Dime) ----
    cols = st.columns(3)
    for col, broker in zip(cols, pf.BROKERS):
        sub = pf.summarize(df[df["Broker"] == broker])
        meta = pf.BROKER_META[broker]
        with col, ui.card(f"broker-{meta['market']}-{meta['group']}"):
            st.markdown(
                f'<div class="card-title">{ui.broker_badge(broker, meta)}{ui.pct_badge(sub["pnl_pct"])}</div>'
                f'<div class="big-value">{_money(sub["market"], is_usd, fx)}</div>'
                f'<div class="row"><div class="lbl">P/L</div><div class="val {"pos" if sub["pnl"] >= 0 else "neg"}">'
                f'{_money(sub["pnl"], is_usd, fx, True)}</div></div>'
                f'<div class="row"><div class="lbl">Positions</div><div class="val">{sub["count"]}</div></div>'
                f'<div class="row"><div class="lbl">Data source</div><div class="val sub">{status[broker]["source"]}</div></div>',
                unsafe_allow_html=True)


# ==========================================
# 3. PAGE LOADER
# ==========================================
def load_page_module(file_name):
    possible_paths = [f"pages/{file_name}.py", f"pages/{file_name}"]
    target_path = next((p for p in possible_paths if os.path.exists(p)), None)
    if not target_path and os.path.exists("pages"):
        for f in os.listdir("pages"):
            if f.lower() == f"{file_name}.py".lower():
                target_path = os.path.join("pages", f)
                break

    if target_path:
        spec = importlib.util.spec_from_file_location("subpage_module", target_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        st.warning(f"⚠️ ไม่พบไฟล์ระบบย่อยที่ตำแหน่ง: `pages/{file_name}.py`")


# ==========================================
# 4. SIDEBAR NAVIGATION
# ==========================================
if "current_page" not in st.session_state:
    st.session_state["current_page"] = "Dashboard"


def nav_button(label, page):
    active = st.session_state["current_page"] == page
    if st.button(label, width="stretch", type="primary" if active else "secondary", key=f"nav_{page}"):
        st.session_state["current_page"] = page
        st.rerun()


NAV_SECTIONS = [
    ("🏦 Brokers", [
        ("⚡ Webull (API)", "0.1_Webull"),
        ("💵 Dime US / TH", "0.2_Dime"),
    ]),
    ("📁 Portfolio", [
        ("📊 Portfolio Holdings", "1.1_Portfolio"),
        ("⚡ Trade Execution", "1.2_Trade_Execution"),
        ("📜 Trade History", "1.3_History"),
        ("💰 Dividends", "1.4_Dividends"),
        ("📈 Daily US Comparison", "1.5_Daily_Price_Comparison"),
    ]),
    ("🛠️ Portfolio Management Tools", [
        ("🎯 Winner Tilt", "2.1_Winner_Tilt"),
        ("🛡️ Portfolio Risk Desk", "2.2_Portfolio_Risk_Desk"),
        ("📐 MM Calculator", "2.3_MM_Calculator"),
        ("📰 Market News", "2.4_News"),
    ]),
    ("🧠 AI Stock Selection", [
        ("🎯 AI Fundamental (GOD MODE)", "3.1_AI_Fundamental"),
        ("💎 Diamond Hunter OS (v3.0)", "3.2_Diamond_Hunter"),
        ("🔍 Peer Comparison", "3.3_Peer_Comparison"),
        ("🧠 Multi-Brain Guru AI", "3.4_Multi_Brain_AI"),
    ]),
]

with st.sidebar:
    st.markdown('<div class="sidebar-brand">♾️ WEBULL · DIME DESK<small>Portfolio command center</small></div>',
                unsafe_allow_html=True)
    nav_button("🏠 Executive Dashboard", "Dashboard")
    for section, items in NAV_SECTIONS:
        with st.expander(section, expanded=True):
            for label, page in items:
                nav_button(label, page)

# ==========================================
# 5. PAGE SWITCHER ROUTER
# ==========================================
selected_page = st.session_state["current_page"]

if selected_page == "Dashboard":
    render_dashboard()
else:
    load_page_module(selected_page)

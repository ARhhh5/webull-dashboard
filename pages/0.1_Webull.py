import pandas as pd
import streamlit as st

from core import market, ui
from core import portfolio as pf
from core.webull_api import WebullAPIError, to_float

ui.page_header("⚡ Webull Account", "ข้อมูลสดจาก Webull Thailand OpenAPI · api.webull.co.th")

cfg = pf.webull_config()
df_all, status, is_demo = pf.load_holdings()
df = df_all[df_all["Broker"] == pf.WEBULL]
st_wb = status[pf.WEBULL]

st.markdown(
    ui.status_chip("API credentials", cfg.is_configured, "" if cfg.is_configured else "ใส่ [Webull] ใน secrets")
    + ui.status_chip(f"Source · {st_wb['source']}", not st_wb["error"], st_wb["error"] or "")
    + ui.status_chip("Access token (2FA)", bool(cfg.access_token)),
    unsafe_allow_html=True,
)
if st_wb["error"] and not is_demo:
    st.warning(f"Webull API: {st_wb['error']}")
if is_demo:
    st.markdown('<div class="demo-banner">🧪 DEMO MODE — ยังไม่มี secrets จึงใช้พอร์ตตัวอย่าง</div>', unsafe_allow_html=True)

# ---- Balance (API only) ----
balance, bal_err = pf.get_webull_balance()
summary = pf.summarize(df)
k1, k2, k3, k4 = st.columns(4)
if balance:
    k1.metric("Total market value", ui.fmt_money(to_float(balance.get("total_market_value"))))
    k2.metric("Cash balance", ui.fmt_money(to_float(balance.get("total_cash_balance"))))
    upl = to_float(balance.get("total_unrealized_profit_loss"))
    k3.metric("Unrealized P/L", ui.fmt_money(upl, signed=True), f"{summary['pnl_pct']:+.2f}%")
    bp = sum(to_float(a.get("buying_power")) for a in balance.get("account_currency_assets", []))
    k4.metric("Buying power", ui.fmt_money(bp), balance.get("total_asset_currency", "USD"), delta_color="off", delta_arrow="off")
else:
    k1.metric("Market value", ui.fmt_money(summary["market"]),
              f"{ui.fmt_money(summary['day_pnl'], signed=True)} วันนี้")
    k2.metric("Invested", ui.fmt_money(summary["invested"]))
    k3.metric("Unrealized P/L", ui.fmt_money(summary["pnl"], signed=True), f"{summary['pnl_pct']:+.2f}%")
    k4.metric("Positions", summary["count"], "balance API ไม่พร้อม" if cfg.is_configured else "ไม่มี API",
              delta_color="off", delta_arrow="off")

st.write("")
col_chart, col_tbl = st.container(), st.container()  # chart on top, full-width table below
with col_tbl:
    with ui.card("wb-pos", "Positions"):
        if df.empty:
            st.info("ไม่พบสินทรัพย์ในบัญชี Webull")
        else:
            view = df[["Symbol", "Qty", "Cost", "Price", "Market_Value_USD", "PnL_USD", "PnL_Pct", "DayChange_Pct"]]
            view = view.sort_values("Market_Value_USD", ascending=False).rename(columns={
                "Market_Value_USD": "Value", "PnL_USD": "P/L", "PnL_Pct": "P/L %", "DayChange_Pct": "Day %"})
            st.dataframe(
                view.style.format({"Qty": "{:,.4f}", "Cost": "${:,.2f}", "Price": "${:,.2f}", "Value": "${:,.2f}",
                                   "P/L": "${:+,.2f}", "P/L %": "{:+.2f}%", "Day %": "{:+.2f}%"})
                .map(ui.pnl_style, subset=["P/L", "P/L %", "Day %"]),
                hide_index=True, width="stretch", height=min(460, 38 + 35 * len(view)),
            )

with col_chart:
    with ui.card("wb-chart", "Chart"):
        symbols = df.sort_values("Market_Value_USD", ascending=False)["Symbol"].tolist()
        if symbols:
            c1, c2 = st.columns([1, 2], vertical_alignment="center")
            sym = c1.selectbox("Symbol", symbols, label_visibility="collapsed", key="wb_sym")
            period = c2.segmented_control("Period", ["1mo", "3mo", "6mo", "1y", "2y"], default="6mo",
                                          key="wb_period", label_visibility="collapsed") or "6mo"
            ohlc = market.get_ohlc(sym, period)
            if ohlc.empty:
                st.warning(f"ดึงกราฟ {sym} ไม่สำเร็จ")
            else:
                ui.show_chart(ui.candlestick_chart(ohlc, height=420))

# ---- Live snapshot from Webull market data (needs market-data permission) ----
if cfg.is_configured and not df.empty:
    with st.expander("📡 Webull real-time snapshot (Market Data API)"):
        try:
            snaps = pf.webull_client().get_snapshots(df["Symbol"].tolist())
            if snaps:
                snap_df = pd.DataFrame(snaps)
                keep = [c for c in ["symbol", "price", "change", "change_ratio", "open", "high", "low", "volume",
                                    "bid", "ask"] if c in snap_df.columns]
                st.dataframe(snap_df[keep], hide_index=True, width="stretch")
            else:
                st.caption("API ไม่คืนข้อมูล snapshot")
        except WebullAPIError as exc:
            st.caption(f"Snapshot ใช้ไม่ได้ (อาจยังไม่ได้สิทธิ์ Market Data): {exc}")

with st.expander("⚙️ วิธีตั้งค่า Webull API (.streamlit/secrets.toml)"):
    st.code('''[Webull]
AppKey = "..."
AppSecret = "..."
AccessToken = "..."   # token หลังยืนยัน 2FA ในแอป Webull
AccountId = "..."     # เว้นว่างได้ ระบบจะเลือกบัญชีแรกจาก /trading/accounts/list
# Host = "th-api.uat.webullbroker.com"   # ใช้ UAT ตอนทดสอบ''', language="toml")

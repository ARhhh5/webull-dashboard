import streamlit as st

from core import market, ui
from core import portfolio as pf

ui.page_header("💵 Dime Accounts", "Dime US และ Dime TH · ข้อมูลจาก Google Sheets + ราคาสดจาก yfinance")

df_all, status, is_demo = pf.load_holdings()
fx = market.get_usd_thb()

st.markdown("".join(ui.status_chip(f"{b} · {status[b]['source']}", not status[b]["error"], status[b]["error"] or "")
                    for b in (pf.DIME_US, pf.DIME_TH)), unsafe_allow_html=True)
if is_demo:
    st.markdown('<div class="demo-banner">🧪 DEMO MODE — ยังไม่มี secrets จึงใช้พอร์ตตัวอย่าง</div>', unsafe_allow_html=True)

tab_us, tab_th = st.tabs(["💵 Dime US (USD)", "🇹🇭 Dime TH (THB)"])

for tab, broker in ((tab_us, pf.DIME_US), (tab_th, pf.DIME_TH)):
    with tab:
        df = df_all[df_all["Broker"] == broker]
        is_th = broker == pf.DIME_TH
        cur = "฿" if is_th else "$"
        rate = fx if is_th else 1.0  # summaries are USD; show Dime TH in its own currency
        s = pf.summarize(df)

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("มูลค่าตลาด", ui.fmt_money(s["market"] * rate, cur),
                  f"{ui.fmt_money(s['day_pnl'] * rate, cur, True)} ({s['day_pct']:+.2f}%) วันนี้")
        k2.metric("เงินลงทุน", ui.fmt_money(s["invested"] * rate, cur))
        k3.metric("กำไร/ขาดทุน", ui.fmt_money(s["pnl"] * rate, cur, True), f"{s['pnl_pct']:+.2f}%")
        k4.metric("จำนวนหุ้น", s["count"], status[broker]["source"], delta_color="off", delta_arrow="off")

        if df.empty:
            st.info(f"ไม่พบข้อมูลในชีท {broker}")
            continue

        st.write("")
        col_chart, col_tbl = st.container(), st.container()
        with col_tbl, ui.card(f"dime-pos-{'th' if is_th else 'us'}", "Holdings"):
            view = df.assign(Value=df["Qty"] * df["Price"], PL=(df["Price"] - df["Cost"]) * df["Qty"])
            view = view[["Symbol", "Qty", "Cost", "Price", "Value", "PL", "PnL_Pct", "DayChange_Pct"]]
            view = view.sort_values("Value", ascending=False).rename(
                columns={"PL": "P/L", "PnL_Pct": "P/L %", "DayChange_Pct": "Day %"})
            money = cur + "{:,.2f}"
            st.dataframe(
                view.style.format({"Qty": "{:,.2f}", "Cost": money, "Price": money, "Value": money,
                                   "P/L": cur + "{:+,.2f}", "P/L %": "{:+.2f}%", "Day %": "{:+.2f}%"})
                .map(ui.pnl_style, subset=["P/L", "P/L %", "Day %"]),
                hide_index=True, width="stretch", height=min(460, 38 + 35 * len(view)),
            )
        with col_chart, ui.card(f"dime-chart-{'th' if is_th else 'us'}", "Chart"):
            symbols = df.sort_values("Market_Value_USD", ascending=False)["Symbol"].tolist()
            c1, c2 = st.columns([1, 2], vertical_alignment="center")
            sym = c1.selectbox("Symbol", symbols, label_visibility="collapsed", key=f"dime_sym_{broker}")
            period = c2.segmented_control("Period", ["1mo", "3mo", "6mo", "1y", "2y"], default="6mo",
                                          key=f"dime_period_{broker}", label_visibility="collapsed") or "6mo"
            yf_sym = market.yf_symbol(sym, broker)
            ohlc = market.get_ohlc(yf_sym, period)
            if ohlc.empty:
                st.warning(f"ดึงกราฟ {yf_sym} ไม่สำเร็จ")
            else:
                ui.show_chart(ui.candlestick_chart(ohlc, height=420, currency=cur))

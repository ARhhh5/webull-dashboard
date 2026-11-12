from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from core import dime_data, fx, theme
from core.theme import money, pct
from core.webull_data import get_portfolio

ACCOUNT_COLORS = {"Webull": "#38bdf8", "Webull Cash": "#0e7490", "Dime US": "#facc15", "Dime TH": "#f97316"}
BANGKOK = ZoneInfo("Asia/Bangkok")

wb = get_portfolio()
dime = dime_data.get_dime_portfolio()
fx_rate = dime_data.get_usd_thb()  # FxRate (source + timestamp); estimated when no live quote

wm = wb["metrics"]
d_us = dime_data.summarize(dime, "Dime US")
d_th = dime_data.summarize(dime, "Dime TH")

# Calculation layer: every amount is USD (Webull is converted once at sync, Dime TH in get_dime_portfolio).
# Unverified Webull cash is None and already excluded from wm["total_value"].
net_worth_usd = wm["total_value"] + d_us["market_value_usd"] + d_th["market_value_usd"]
open_pnl_usd = wm["open_pnl"] + d_us["unrealized_pnl_usd"] + d_th["unrealized_pnl_usd"]

# ---- Header ----
c_title, c_ccy = st.columns([4, 1], vertical_alignment="center")
with c_title:
    synced = wb.get("last_synced")
    pills = (theme.status_pill("Webull · DEMO (not synced)", "#facc15") if wb["is_mock"] else
             theme.status_pill(f"Webull · synced {synced.astimezone(BANGKOK):%d %b %H:%M}"
                               if synced else "Webull · cached", "#22c55e"))
    pills += " " + theme.status_pill(f"Dime · {int(len(dime))} holdings (SQLite)",
                                     "#22c55e" if len(dime) else "#64748b")
    pills += " " + theme.status_pill(f"USD/THB {fx_rate.rate:,.2f}" + (" (estimated)" if fx_rate.estimated else ""),
                                     "#64748b" if fx_rate.estimated else "#22c55e")
    theme.page_header("Executive Dashboard", pills)
with c_ccy:
    ccy = st.segmented_control("Currency", ["USD", "THB"], required=True, default="USD", key="exec_ccy",
                               label_visibility="collapsed") or "USD"

sym = fx.SYMBOLS[ccy]


def show(amount_usd, signed=False):
    """Presentation layer only: USD -> display currency."""
    return money(fx.from_usd(amount_usd, ccy, fx_rate), sym, signed)


st.write("")

# ---- KPI cards ----
k1, k2, k3, k4 = st.columns([1.3, 1, 1, 1])
k1.metric("Total Net Worth", show(net_worth_usd), f"{show(open_pnl_usd, True)} open PnL")
k2.metric("⚡ Webull", show(wm["total_value"]),
          f"{show(wm['day_pnl'], True)} today" if wm["day_pnl"] is not None else None)
k3.metric("💵 Dime US", show(d_us["market_value_usd"]), pct(d_us["unrealized_pct"]))
k4.metric("🇹🇭 Dime TH", show(d_th["market_value_usd"]),
          f"฿{d_th['market_value']:,.0f} · {pct(d_th['unrealized_pct'])}", delta_color="off", delta_arrow="off")

if wb["is_mock"]:
    st.caption("🧪 Webull figures are sample data until the first sync on the Webull Portfolio page.")
else:
    st.caption("Webull figures are from the last sync (SQLite cache). Sync on the Webull Portfolio page to refresh.")
if wm.get("warnings"):
    st.warning(f"Webull currency check: {len(wm['warnings'])} warning(s). "
               + ("Cash is unverified and excluded from net worth. " if wm["cash"] is None else "")
               + "See the Webull Portfolio page for details.", icon="⚠️")
st.caption(f"Calculated in USD · {fx_rate.label(BANGKOK)}"
           + (" · THB figures use this rate for display only" if ccy == "THB" else ""))

st.write("")

# ---- Consolidated allocation ----
rows = [{"Account": "Webull", "Symbol": r["Symbol"], "Value": r["Market Value"]}
        for _, r in wb["positions"].iterrows()]
if wm["cash"]:
    rows.append({"Account": "Webull Cash", "Symbol": "CASH (Webull)", "Value": wm["cash"]})
rows += [{"Account": r["account_type"], "Symbol": r["symbol"], "Value": r["market_value_usd"]}
         for _, r in dime.iterrows()]
alloc = pd.DataFrame(rows, columns=["Account", "Symbol", "Value"])
alloc["Value"] = [fx.from_usd(v, ccy, fx_rate) for v in alloc["Value"]]

col_pie, col_side = st.columns([1.6, 1])
with col_pie, theme.card("alloc", "Asset Allocation · All Accounts",
                         f"Webull + Dime US + Dime TH, in {ccy}"):
    view = st.segmented_control("Group by", ["Account", "Symbol"], required=True, default="Account", key="alloc_by",
                                label_visibility="collapsed") or "Account"
    if alloc.empty:
        st.info("No assets yet.")
    else:
        if view == "Account":
            chart = alloc.groupby("Account", as_index=False)["Value"].sum()
            fig = px.pie(chart, names="Account", values="Value", hole=0.62, color="Account",
                         color_discrete_map=ACCOUNT_COLORS)
        else:
            # Same ticker held in several accounts is combined.
            chart = alloc.groupby("Symbol", as_index=False)["Value"].sum().sort_values("Value", ascending=False)
            if len(chart) > 12:
                chart = pd.concat([chart.iloc[:12], pd.DataFrame([{"Symbol": "Others",
                                                                    "Value": chart.iloc[12:]["Value"].sum()}])])
            fig = px.pie(chart, names="Symbol", values="Value", hole=0.62,
                         color_discrete_sequence=theme.PALETTE)
        fig.update_traces(textposition="inside", textinfo="percent+label", sort=False,
                          marker=dict(line=dict(color="#131722", width=2)),
                          hovertemplate=f"<b>%{{label}}</b><br>{sym}%{{value:,.2f}}<br>%{{percent}}<extra></extra>")
        theme.style_fig(fig, 420).update_layout(
            showlegend=True, legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=12)),
            annotations=[dict(text=f"<b>{show(net_worth_usd)}</b><br>"
                                   "<span style='font-size:11px'>net worth</span>",
                              x=0.5, y=0.5, showarrow=False, font=dict(size=17, color="#f8fafc"))])
        st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

with col_side, theme.card("breakdown", "Account Breakdown", "Share of net worth"):
    breakdown = [
        ("⚡ Webull", wm["total_value"], wm["open_pnl_pct"], "Auto · Webull API"),
        ("💵 Dime US", d_us["market_value_usd"], d_us["unrealized_pct"], f"Manual · {d_us['positions']} holdings"),
        ("🇹🇭 Dime TH", d_th["market_value_usd"], d_th["unrealized_pct"], f"Manual · {d_th['positions']} holdings"),
    ]
    for name, value_usd, pnl_pct, source in breakdown:
        share = value_usd / net_worth_usd * 100 if net_worth_usd else 0
        color = theme.UP if pnl_pct >= 0 else theme.DOWN
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-top:14px">'
            f'<div><div style="color:#e2e8f0;font-weight:700">{name}</div>'
            f'<div class="card-sub">{source}</div></div>'
            f'<div style="text-align:right"><div style="font-family:JetBrains Mono,monospace;color:#f8fafc;'
            f'font-weight:700">{show(value_usd)}</div>'
            f'<div style="font-size:.78rem;color:{color};font-weight:700">{pct(pnl_pct)} open</div></div></div>',
            unsafe_allow_html=True)
        st.progress(min(max(share / 100, 0.0), 1.0), text=f"{share:.1f}% of net worth")
    if dime.empty:
        st.caption("No Dime holdings yet: record trades in **Dime Desk**.")
        st.page_link("pages/3_Dime.py", label="Open Dime Desk", icon="🧠")

import pandas as pd
import plotly.express as px
import streamlit as st

from core import theme
from core.webull_data import get_portfolio


def money(value, signed=False):
    if value is None:
        return "—"
    sign = ("+" if value >= 0 else "-") if signed else ("-" if value < 0 else "")
    return f"{sign}${abs(value):,.2f}"


def pct(value):
    return "—" if value is None else f"{value:+.2f}%"


data = get_portfolio()
df, m = data["positions"], data["metrics"]

# ---- Header ----
c_title, c_refresh = st.columns([5, 1], vertical_alignment="center")
with c_title:
    status = ('<span class="pill"><span class="dot" style="background:#facc15"></span>DEMO DATA</span>'
              if data["is_mock"] else
              '<span class="pill"><span class="dot" style="background:#22c55e"></span>LIVE · Webull OpenAPI</span>')
    st.markdown(
        f'<div class="hero-title">Webull Portfolio</div>'
        f'<div class="hero-sub">{status}&nbsp; Account {data["account_id"]} · '
        f'updated {data["fetched_at"]:%Y-%m-%d %H:%M:%S} · cached 15 min</div>',
        unsafe_allow_html=True)
with c_refresh:
    if st.button("↻ Refresh", width="stretch"):
        get_portfolio.clear()
        st.rerun()

if data["is_mock"]:
    st.info("Showing mock portfolio data: Webull credentials were not found or the API call failed. "
            "Add `[Webull]` AppKey / AppSecret / AccessToken / AccountId to `.streamlit/secrets.toml`.",
            icon="🧪")
    with st.expander("Error details"):
        st.code(data["error"] or "-", language=None)

st.write("")

# ---- KPI cards ----
k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Account Value", money(m["total_value"]), f"Cash {money(m['cash'])}", delta_color="off",
          delta_arrow="off")
k2.metric("Day PnL", money(m["day_pnl"], signed=True), pct(m["day_pnl_pct"]) if m["day_pnl"] is not None else None)
k3.metric("Open PnL", money(m["open_pnl"], signed=True), pct(m["open_pnl_pct"]))
k4.metric("Positions", m["positions"], f"Invested {money(m['market_value'])}", delta_color="off", delta_arrow="off")

st.write("")

if df.empty:
    st.info("No open positions in this Webull account.")
    st.stop()

# ---- Charts ----
col_alloc, col_pnl = st.columns([1, 1.35])

with col_alloc, theme.card("alloc", "Portfolio Allocation", "Market value by symbol"):
    alloc = df[["Symbol", "Market Value"]].copy()
    if len(alloc) > 10:  # fold the long tail so the donut stays readable
        tail = alloc.iloc[10:]["Market Value"].sum()
        alloc = pd.concat([alloc.iloc[:10], pd.DataFrame([{"Symbol": "Others", "Market Value": tail}])])
    fig = px.pie(alloc, names="Symbol", values="Market Value", hole=0.62,
                 color_discrete_sequence=theme.PALETTE)
    fig.update_traces(textposition="inside", textinfo="percent+label", sort=False,
                      marker=dict(line=dict(color="#131722", width=2)),
                      hovertemplate="<b>%{label}</b><br>$%{value:,.2f}<br>%{percent}<extra></extra>")
    theme.style_fig(fig, 380).update_layout(
        showlegend=False,
        annotations=[dict(text=f"<b>{money(m['market_value'])}</b><br><span style='font-size:11px'>market value</span>",
                          x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#f8fafc"))])
    st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

with col_pnl, theme.card("pnl", "Open PnL by Position", "Unrealized gain / loss per symbol"):
    pnl = df.sort_values("Open PnL")
    pnl = pnl.assign(Result=["Gain" if v >= 0 else "Loss" for v in pnl["Open PnL"]])
    fig = px.bar(pnl, x="Open PnL", y="Symbol", orientation="h", color="Result",
                 color_discrete_map={"Gain": theme.UP, "Loss": theme.DOWN},
                 custom_data=["Open PnL %", "Market Value"])
    fig.update_traces(hovertemplate="<b>%{y}</b><br>Open PnL $%{x:,.2f} (%{customdata[0]:+.2f}%)"
                                    "<br>Value $%{customdata[1]:,.2f}<extra></extra>")
    theme.style_fig(fig, 380).update_layout(showlegend=False, bargap=0.25)
    fig.update_xaxes(tickformat="$,.0f", title=None)
    fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(pnl["Symbol"]))
    st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

# ---- Positions table ----
with theme.card("table", "Positions", "Raw position data from Webull"):
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "Quantity": st.column_config.NumberColumn(format="%.4f"),
            "Avg Cost": st.column_config.NumberColumn(format="$%.2f"),
            "Last Price": st.column_config.NumberColumn(format="$%.2f"),
            "Market Value": st.column_config.NumberColumn(format="dollar"),
            "Cost Basis": st.column_config.NumberColumn(format="dollar"),
            "Open PnL": st.column_config.NumberColumn(format="dollar"),
            "Open PnL %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Day Change %": st.column_config.NumberColumn(format="%+.2f%%"),
            "Day PnL": st.column_config.NumberColumn(format="dollar"),
            "Weight %": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
        },
    )

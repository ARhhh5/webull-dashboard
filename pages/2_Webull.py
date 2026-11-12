from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import streamlit as st

from core import theme
from core.theme import money, pct
from core.webull_data import get_dividend_history, get_order_history, get_portfolio, sync_from_webull

BANGKOK = ZoneInfo("Asia/Bangkok")


def _age(ts):
    minutes = int((datetime.now(timezone.utc) - ts).total_seconds() // 60)
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 48 * 60:
        return f"{minutes // 60} h ago"
    return f"{minutes // 1440} days ago"


def _sync_error(exc):
    # Missing secrets surface as KeyError or Streamlit's secrets-not-found error.
    if isinstance(exc, KeyError) or "Secret" in type(exc).__name__:
        return "Webull credentials not found. Add `[Webull]` AppKey / AppSecret / AccessToken / AccountId to secrets."
    return f"{type(exc).__name__}: {str(exc)[:300]}"


# Page load reads the SQLite cache only; the Webull SDK runs solely from the Sync button below.
data = get_portfolio()
df, m = data["positions"], data["metrics"]
last_synced = data.get("last_synced")

# ---- Header ----
c_title, c_sync = st.columns([3.2, 1.4], vertical_alignment="center")
with c_title:
    if last_synced:
        stale = datetime.now(timezone.utc) - last_synced > pd.Timedelta(days=1)
        status = theme.status_pill("CACHED · SQLite", "#facc15" if stale else "#22c55e")
        sub = (f"{status}&nbsp; Account {data['account_id']} · Last synced "
               f"{last_synced.astimezone(BANGKOK):%Y-%m-%d %H:%M} (Bangkok) · {_age(last_synced)}")
    else:
        sub = f"{theme.status_pill('DEMO DATA', '#facc15')}&nbsp; Never synced · showing sample data"
    theme.page_header("📈 Webull Portfolio", sub)
with c_sync:
    sync_clicked = st.button("🔄 Sync Live Data from Webull", type="primary", width="stretch", key="webull_sync",
                             help="Fetch the latest data from Webull. You may need to approve on the Webull app.")

if sync_clicked:
    result, error = None, None
    with st.spinner("Connecting to Webull and waiting for approval..."):
        try:
            result = sync_from_webull()
        except Exception as exc:  # credentials, 2FA timeout, network or API errors
            error = _sync_error(exc)
    if result:
        st.session_state["webull_sync_result"] = result
        st.rerun()
    st.error(f"Sync failed: {error}" + (" · Previously synced data is kept." if last_synced else ""), icon="⚠️")

sync_result = st.session_state.pop("webull_sync_result", None)
if sync_result:
    orders_note = "" if sync_result["orders"] is None else f", {sync_result['orders']} orders"
    st.success(f"Synced {sync_result['positions']} positions{orders_note} from Webull.", icon="✅")
    for warning in sync_result["warnings"]:
        st.warning(warning)

if data["is_mock"]:
    st.info("No Webull data saved yet: the figures below are sample data. Press **🔄 Sync Live Data from Webull** "
            "to fetch your account, then approve the request in the Webull app.", icon="🧪")

st.write("")

tab_overview, tab_positions, tab_history, tab_div = st.tabs([
    "📊 Dashboard Overview", "📈 Position Performance", "📝 Trade History", "💰 Dividends",
])

with tab_overview:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Account Value", money(m["total_value"]), f"{m['positions']} positions", delta_color="off",
              delta_arrow="off")
    k2.metric("Day PnL", money(m["day_pnl"], signed=True), pct(m["day_pnl_pct"]) if m["day_pnl"] is not None else None)
    k3.metric("Open PnL", money(m["open_pnl"], signed=True), pct(m["open_pnl_pct"]))
    cash_share = m["cash"] / m["total_value"] * 100 if m["total_value"] else 0.0
    k4.metric("Cash Balance", money(m["cash"]), f"{cash_share:.1f}% of account", delta_color="off", delta_arrow="off")

    st.write("")
    if df.empty:
        st.info("No open positions in this Webull account.")
    else:
        with theme.card("alloc", "Portfolio Allocation", "Market value by symbol"):
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
                annotations=[dict(text=f"<b>{money(m['market_value'])}</b><br>"
                                       "<span style='font-size:11px'>market value</span>",
                                  x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#f8fafc"))])
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)


with tab_positions:
    if df.empty:
        st.info("No open positions in this Webull account.")
    else:
        with theme.card("table", "Current Holdings", "Daily price comparison versus previous trading close (not calendar yesterday); USD per share"):
            table = df[["Symbol", "Quantity", "Avg Cost", "Last Price", "Day PnL", "Day Change %",
                        "Open PnL", "Open PnL %"]].rename(columns={
                            "Avg Cost": "Average Cost", "Last Price": "Current Price", "Day Change %": "Day PnL %"})
            # Day PnL is for the holding; divide by shares for the per-share price move.
            table["Price Change (USD)"] = df["Day PnL"] / df["Quantity"].where(df["Quantity"] > 0)
            table["Previous Close"] = table["Current Price"] - table["Price Change (USD)"]
            table["Price Change (%)"] = df["Day Change %"]
            table = table[[*table.columns[:8], "Previous Close", "Price Change (USD)", "Price Change (%)"]]
            st.dataframe(
                table.style.map(theme.pnl_color, subset=["Day PnL", "Day PnL %", "Open PnL", "Open PnL %",
                                                         "Price Change (USD)", "Price Change (%)"]),
                hide_index=True, width="stretch", column_config={
                    "Quantity": st.column_config.NumberColumn(format="%.4f"),
                    "Average Cost": st.column_config.NumberColumn(format="$%.2f"),
                    "Current Price": st.column_config.NumberColumn(format="$%.2f"),
                    "Day PnL": st.column_config.NumberColumn(format="dollar"),
                    "Day PnL %": st.column_config.NumberColumn(format="%+.2f%%"),
                    "Open PnL": st.column_config.NumberColumn(format="dollar"),
                    "Open PnL %": st.column_config.NumberColumn(format="%+.2f%%"),
                    "Previous Close": st.column_config.NumberColumn(format="$%.2f"),
                    "Price Change (USD)": st.column_config.NumberColumn(
                        format="$%+.2f", help="Current price minus previous trading close, per share (USD)."),
                    "Price Change (%)": st.column_config.NumberColumn(
                        format="%+.2f%%", help="Price change versus previous trading close."),
                })

        with theme.card("pnl", "Open PnL by Position", "Unrealized gain / loss per symbol"):
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


        best, worst = df.loc[df["Open PnL %"].idxmax()], df.loc[df["Open PnL %"].idxmin()]
        winners = int((df["Open PnL"] > 0).sum())
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("🏆 Best Position", best["Symbol"], pct(best["Open PnL %"]))
        p2.metric("📉 Worst Position", worst["Symbol"], pct(worst["Open PnL %"]))
        p3.metric("Win Rate (open)", f"{winners / len(df) * 100:.0f}%", f"{winners} of {len(df)} in profit",
                  delta_color="off", delta_arrow="off")
        top = df.loc[df["Weight %"].idxmax()]
        p4.metric("Largest Weight", top["Symbol"], f"{top['Weight %']:.1f}% of portfolio",
                  delta_color="off", delta_arrow="off")
        st.write("")

        col_ret, col_day = st.columns(2)
        with col_ret, theme.card("ret", "Return % by Position", "Open PnL relative to cost basis"):
            ret = df.sort_values("Open PnL %")
            fig = px.bar(ret, x="Symbol", y="Open PnL %",
                         color=ret["Open PnL %"] >= 0, color_discrete_map={True: theme.UP, False: theme.DOWN})
            fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y:+.2f}%<extra></extra>")
            theme.style_fig(fig, 320).update_layout(showlegend=False, bargap=0.3)
            fig.update_yaxes(ticksuffix="%", title=None)
            fig.update_xaxes(title=None)
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
        with col_day, theme.card("day", "Today's Movers", "Day change % from Webull market data"):
            if df["Day Change %"].notna().any():
                day = df.dropna(subset=["Day Change %"]).sort_values("Day Change %")
                fig = px.bar(day, x="Day Change %", y="Symbol", orientation="h",
                             color=day["Day Change %"] >= 0,
                             color_discrete_map={True: theme.UP, False: theme.DOWN}, custom_data=["Day PnL"])
                fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:+.2f}% · $%{customdata[0]:+,.2f}<extra></extra>")
                theme.style_fig(fig, 320).update_layout(showlegend=False, bargap=0.3)
                fig.update_xaxes(ticksuffix="%", title=None)
                fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(day["Symbol"]))
                st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
            else:
                st.caption("Day change requires Webull market-data permission.")


with tab_history:
    hist = get_order_history()
    orders = hist["orders"]
    if hist["is_mock"]:
        st.info("🧪 DEMO Trade History: never synced, so the orders below are sample data.")
    with theme.card("orders", "Trade History · last 6 months",
                    "Saved at the last Webull sync · dates in Asia/Bangkok"):
        st.caption("Quantity is the requested order size. Price is the executed price; unfilled orders show —.")
        if orders.empty:
            st.info("No orders in the last 6 months.")
        else:
            history = orders[["Symbol", "Side", "Quantity", "Filled Price", "Time"]].copy()
            history["Side"] = history["Side"].str.title()
            history["Filled Price"] = history["Filled Price"].where(orders["Filled Qty"] > 0)
            history["Time"] = history["Time"].dt.tz_convert("Asia/Bangkok").dt.strftime("%Y-%m-%d %H:%M")
            history = history.rename(columns={"Filled Price": "Price", "Time": "Date"})
            st.dataframe(history, hide_index=True, width="stretch", column_config={
                "Quantity": st.column_config.NumberColumn(format="%.4f"),
                "Price": st.column_config.NumberColumn(format="$%.2f"),
            })

# ============ Dividends ============
with tab_div:
    st.caption("Webull TH OpenAPI has no dividend/cash-activity endpoint (US region only), so income is "
               "**estimated** from Yahoo Finance dividend history × your current shares.")
    if df.empty:
        st.info("No positions to estimate dividends for.")
    else:
        divs = get_dividend_history(tuple(df["Symbol"]))
        shares = df.set_index("Symbol")["Quantity"]
        price = df.set_index("Symbol")["Last Price"]
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=365)
        last12 = divs[divs["Date"] >= cutoff].groupby("Symbol")["Dividend"].sum() if not divs.empty else pd.Series()
        income = pd.DataFrame({
            "Symbol": df["Symbol"], "Shares": df["Quantity"].values,
            "Dividend / Share (TTM)": df["Symbol"].map(last12).fillna(0.0).values,
        })
        income["Est. Annual Income"] = income["Shares"] * income["Dividend / Share (TTM)"]
        income["Yield %"] = income["Dividend / Share (TTM)"] / income["Symbol"].map(price) * 100
        income["Yield on Cost %"] = income["Dividend / Share (TTM)"] / income["Symbol"].map(
            df.set_index("Symbol")["Avg Cost"]) * 100
        payers = income[income["Est. Annual Income"] > 0].sort_values("Est. Annual Income", ascending=False)

        annual = payers["Est. Annual Income"].sum()
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Est. Annual Income", money(annual), f"{money(annual / 12)} / month", delta_color="off",
                  delta_arrow="off")
        d2.metric("Portfolio Yield", f"{annual / m['market_value'] * 100:.2f}%" if m["market_value"] else "—")
        d3.metric("Dividend Payers", f"{len(payers)} / {len(df)}")
        d4.metric("Top Payer", payers.iloc[0]["Symbol"] if not payers.empty else "—",
                  money(payers.iloc[0]["Est. Annual Income"]) if not payers.empty else None,
                  delta_color="off", delta_arrow="off")
        st.write("")

        if payers.empty:
            st.info("None of the current holdings paid a dividend in the last 12 months.")
        else:
            col_bar, col_cal = st.columns([1, 1.3])
            with col_bar, theme.card("div-income", "Income by Holding", "Estimated annual, USD"):
                fig = px.bar(payers.sort_values("Est. Annual Income"), x="Est. Annual Income", y="Symbol",
                             orientation="h", color_discrete_sequence=["#facc15"], custom_data=["Yield %"])
                fig.update_traces(hovertemplate="<b>%{y}</b><br>$%{x:,.2f} / yr · yield %{customdata[0]:.2f}%"
                                                "<extra></extra>")
                theme.style_fig(fig, 320).update_layout(bargap=0.3)
                fig.update_xaxes(tickformat="$,.0f", title=None)
                fig.update_yaxes(title=None)
                st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
            with col_cal, theme.card("div-cal", "Dividend Payments · last 12 months",
                                     "Ex-dividend events × current shares"):
                events = divs[(divs["Date"] >= cutoff) & divs["Symbol"].isin(payers["Symbol"])].copy()
                events["Amount"] = events["Dividend"] * events["Symbol"].map(shares)
                events["Month"] = events["Date"].dt.tz_convert(None).dt.to_period("M").dt.to_timestamp()
                cal = events.groupby(["Month", "Symbol"], as_index=False)["Amount"].sum()
                fig = px.bar(cal, x="Month", y="Amount", color="Symbol", color_discrete_sequence=theme.PALETTE)
                fig.update_traces(hovertemplate="%{x|%b %Y}<br>$%{y:,.2f}<extra></extra>")
                theme.style_fig(fig, 320).update_layout(legend=dict(orientation="h", y=1.12, x=0, title=None))
                fig.update_yaxes(tickformat="$,.0f", title=None)
                fig.update_xaxes(title=None, dtick="M1", tickformat="%b")
                st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

            with theme.card("div-table", "Dividend Details", "Per holding, trailing 12 months"):
                st.dataframe(payers, hide_index=True, width="stretch", column_config={
                    "Shares": st.column_config.NumberColumn(format="%.4f"),
                    "Dividend / Share (TTM)": st.column_config.NumberColumn(format="$%.4f"),
                    "Est. Annual Income": st.column_config.NumberColumn(format="dollar"),
                    "Yield %": st.column_config.NumberColumn(format="%.2f%%"),
                    "Yield on Cost %": st.column_config.NumberColumn(format="%.2f%%"),
                })

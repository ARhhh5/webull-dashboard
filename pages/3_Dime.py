import plotly.express as px
import streamlit as st

from core import db_manager, dime_data, theme
from core.theme import money, pct

CCY_SYMBOL = {"Dime US": "$", "Dime TH": "฿"}
TRADE_COLUMNS = {
    "id": "ID", "timestamp": "Time", "account_type": "Account", "symbol": "Symbol", "trade_type": "Action",
    "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
    "price": st.column_config.NumberColumn("Price", format="%.4f"),
}

theme.page_header("🧠 Dime Desk",
                  theme.status_pill("Local SQLite · portfolio.db", "#22c55e")
                  + "&nbsp; Manual Dime TH / Dime US trades · prices via Yahoo Finance (cached 15 min)")
st.write("")

holdings = dime_data.get_dime_portfolio()
fx, _ = dime_data.get_usd_thb()
s_us = dime_data.summarize(holdings, "Dime US")
s_th = dime_data.summarize(holdings, "Dime TH")
realized_usd = 0.0
if not holdings.empty:
    realized_usd = float((holdings["realized_pnl"] * holdings["currency"].map({"USD": 1.0, "THB": 1 / fx})).sum())

# ---- KPI cards ----
k1, k2, k3, k4 = st.columns(4)
k1.metric("💵 Dime US", money(s_us["market_value"], "$"),
          f"{money(s_us['unrealized_pnl'], '$', True)} ({pct(s_us['unrealized_pct'])})")
k2.metric("🇹🇭 Dime TH", money(s_th["market_value"], "฿"),
          f"{money(s_th['unrealized_pnl'], '฿', True)} ({pct(s_th['unrealized_pct'])})")
k3.metric("Dime Total (USD)", money(s_us["market_value_usd"] + s_th["market_value_usd"]),
          f"USD/THB {fx:,.2f}", delta_color="off", delta_arrow="off")
k4.metric("Realized PnL (USD)", money(realized_usd, signed=True), "From recorded sells",
          delta_color="off", delta_arrow="off")

st.write("")
tab_trade, tab_hold = st.tabs(["✍️ Trade Execution", "📚 Holdings & History"])

# ============ Trade Execution ============
with tab_trade:
    col_form, col_recent = st.columns([1.3, 1])
    with col_form, theme.card("form", "New Transaction", "Saved instantly to the local SQLite database"):
        with st.form("dime_trade_form", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            account = c1.segmented_control("Account", db_manager.ACCOUNTS, required=True, default="Dime US",
                                           key="f_account")
            action = c2.segmented_control("Action", db_manager.TRADE_TYPES, required=True, default="Buy",
                                          key="f_action")
            symbol = st.text_input("Symbol", placeholder="e.g. AAPL (Dime US) or PTT (Dime TH)", key="f_symbol")
            c3, c4 = st.columns(2)
            shares = c3.number_input("Shares", min_value=0.0, step=1.0, format="%.4f", key="f_shares")
            price = c4.number_input("Price per share (USD for Dime US · THB for Dime TH)", min_value=0.0,
                                    step=0.01, format="%.4f", key="f_price")
            submitted = st.form_submit_button("💾 Record transaction", type="primary", width="stretch")

        if submitted:
            try:
                db_manager.insert_trade(account, action, symbol, shares, price)
            except ValueError as exc:
                st.error(f"⚠️ {exc}")
            else:
                st.toast(f"✅ {action} {shares:g} {symbol.strip().upper()} @ "
                         f"{CCY_SYMBOL[account]}{price:,.2f} → {account}")
                st.rerun()

    with col_recent, theme.card("recent", "Recent Transactions", "Last 8 entries"):
        recent = db_manager.fetch_trades()
        if recent.empty:
            st.caption("No transactions yet. Your first entry will appear here.")
        else:
            recent = recent.sort_values(["timestamp", "id"], ascending=False).head(8)
            for r in recent.itertuples():
                color = theme.UP if r.trade_type == "Buy" else "#f472b6"
                cur = CCY_SYMBOL[r.account_type]
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:8px 0;'
                    f'border-bottom:1px solid #1c2130;font-size:.86rem">'
                    f'<div><b style="color:{color}">{r.trade_type.upper()}</b> '
                    f'<b style="color:#f8fafc">{r.symbol}</b> '
                    f'<span class="card-sub">{r.account_type} · {r.timestamp[:16]}</span></div>'
                    f'<div style="font-family:JetBrains Mono,monospace;color:#e2e8f0">{r.shares:g} @ '
                    f'{cur}{r.price:,.2f}</div></div>', unsafe_allow_html=True)

# ============ Holdings & History ============
with tab_hold:
    with theme.card("holdings", "Current Holdings", "Calculated from all recorded trades (average-cost method)"):
        if holdings.empty:
            st.info("No holdings yet. Record your first trade in **Trade Execution**.")
        else:
            acct_view = st.segmented_control("Account filter", ["All", "Dime US", "Dime TH"], required=True,
                                             default="All", key="hold_filter", label_visibility="collapsed")
            view = holdings if acct_view == "All" else holdings[holdings["account_type"] == acct_view]
            if view.empty:
                st.caption(f"No holdings in {acct_view}.")
            else:
                cols = ["account_type", "symbol", "shares", "avg_cost", "last_price", "cost_basis", "market_value",
                        "unrealized_pnl", "unrealized_pct", "realized_pnl", "currency", "price_source"]
                st.dataframe(view[cols], hide_index=True, width="stretch", column_config={
                    "account_type": "Account", "symbol": "Symbol",
                    "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                    "avg_cost": st.column_config.NumberColumn("Avg Cost", format="%.2f"),
                    "last_price": st.column_config.NumberColumn("Last Price", format="%.2f"),
                    "cost_basis": st.column_config.NumberColumn("Cost Basis", format="%.2f"),
                    "market_value": st.column_config.NumberColumn("Market Value", format="%.2f"),
                    "unrealized_pnl": st.column_config.NumberColumn("Unrealized PnL", format="%+.2f"),
                    "unrealized_pct": st.column_config.NumberColumn("PnL %", format="%+.2f%%"),
                    "realized_pnl": st.column_config.NumberColumn("Realized PnL", format="%+.2f"),
                    "currency": "Ccy", "price_source": "Price Source",
                })

                col_alloc, col_pnl = st.columns([1, 1.3])
                with col_alloc:
                    fig = px.pie(view, names="symbol", values="market_value_usd", hole=0.62,
                                 color_discrete_sequence=theme.PALETTE)
                    fig.update_traces(textposition="inside", textinfo="percent+label",
                                      marker=dict(line=dict(color="#131722", width=2)),
                                      hovertemplate="<b>%{label}</b><br>$%{value:,.2f} (USD)<extra></extra>")
                    theme.style_fig(fig, 320).update_layout(showlegend=False)
                    st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)
                with col_pnl:
                    ordered = view.sort_values("unrealized_pct")
                    fig = px.bar(ordered, x="unrealized_pct", y="symbol", orientation="h",
                                 color=ordered["unrealized_pct"] >= 0,
                                 color_discrete_map={True: theme.UP, False: theme.DOWN},
                                 custom_data=["account_type", "unrealized_pnl", "currency"])
                    fig.update_traces(hovertemplate="<b>%{y}</b> · %{customdata[0]}<br>%{x:+.2f}% · "
                                                    "%{customdata[1]:+,.2f} %{customdata[2]}<extra></extra>")
                    theme.style_fig(fig, 320).update_layout(showlegend=False, bargap=0.3)
                    fig.update_xaxes(ticksuffix="%", title=None)
                    fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(ordered["symbol"]))
                    st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

    with theme.card("history", "Transaction History", "Every recorded trade · delete entries made by mistake"):
        trades = db_manager.fetch_trades()
        if trades.empty:
            st.caption("No transactions recorded.")
        else:
            trades = trades.sort_values(["timestamp", "id"], ascending=False)
            st.dataframe(trades, hide_index=True, width="stretch", height=300, column_config=TRADE_COLUMNS)
            c_del, c_btn = st.columns([3, 1], vertical_alignment="bottom")
            labels = {int(r.id): f"#{r.id} · {r.timestamp} · {r.trade_type} {r.shares:g} {r.symbol} "
                                 f"({r.account_type})" for r in trades.itertuples()}
            to_delete = c_del.selectbox("Delete a transaction", list(labels), format_func=labels.get, key="del_id")
            if c_btn.button("🗑️ Delete", width="stretch"):
                # Deleting a buy that later sells depend on leaves those sells capped at zero shares.
                db_manager.delete_trade(to_delete)
                st.toast(f"Deleted transaction #{to_delete}")
                st.rerun()

import plotly.express as px
import streamlit as st

from core import db_manager, dime_data, theme
from core.theme import money, pct

CCY_SYMBOL = {"Dime US": "$", "Dime TH": "฿"}

theme.page_header("✍️ Dime Manual Desk",
                  theme.status_pill("Local SQLite · portfolio.db", "#22c55e")
                  + "&nbsp; Record Dime TH / Dime US trades manually · prices via Yahoo Finance (cached 15 min)")
st.write("")

# ---- Entry form ----
col_form, col_summary = st.columns([1.25, 1])

with col_form, theme.card("form", "New Transaction", "Saved instantly to the local database"):
    with st.form("dime_trade_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns(2)
        account = c1.segmented_control("Account", db_manager.ACCOUNTS, required=True, default="Dime US", key="f_account")
        action = c2.segmented_control("Action", db_manager.TRADE_TYPES, required=True, default="Buy", key="f_action")
        symbol = st.text_input("Symbol", placeholder="e.g. AAPL (Dime US) or PTT (Dime TH)", key="f_symbol")
        c3, c4 = st.columns(2)
        shares = c3.number_input("Shares", min_value=0.0, step=1.0, format="%.4f", key="f_shares")
        price = c4.number_input("Price per share (USD for Dime US · THB for Dime TH)", min_value=0.0,
                                step=0.01, format="%.4f", key="f_price")
        submitted = st.form_submit_button("💾 Record transaction", type="primary", width="stretch")

    if submitted:
        try:
            if not account or not action:
                raise ValueError("Please choose an account and an action")
            db_manager.insert_trade(account, action, symbol, shares, price)
        except ValueError as exc:
            st.error(f"⚠️ {exc}")
        else:
            cur = CCY_SYMBOL[account]
            st.toast(f"✅ {action} {shares:g} {symbol.strip().upper()} @ {cur}{price:,.2f} → {account}")
            st.rerun()

holdings = dime_data.get_dime_portfolio()
fx, _ = dime_data.get_usd_thb()

with col_summary:
    for acct in db_manager.ACCOUNTS:
        s = dime_data.summarize(holdings, acct)
        cur = CCY_SYMBOL[acct]
        icon = "🇹🇭" if acct == "Dime TH" else "💵"
        st.metric(f"{icon} {acct} · Market Value", money(s["market_value"], cur),
                  f"{money(s['unrealized_pnl'], cur, True)} ({pct(s['unrealized_pct'])})")
    total_usd = holdings["market_value_usd"].sum() if not holdings.empty else 0.0
    st.metric("Dime Total (USD)", money(total_usd), f"USD/THB {fx:,.2f}", delta_color="off", delta_arrow="off")

st.write("")

# ---- Current holdings ----
with theme.card("holdings", "Current Holdings", "Calculated from all recorded trades (average-cost method)"):
    if holdings.empty:
        st.info("No holdings yet. Record your first Dime trade above.")
    else:
        tab_all, tab_us, tab_th = st.tabs(["All", "💵 Dime US", "🇹🇭 Dime TH"])
        cols = ["account_type", "symbol", "shares", "avg_cost", "last_price", "cost_basis", "market_value",
                "unrealized_pnl", "unrealized_pct", "realized_pnl", "currency", "price_source"]
        config = {
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
        }
        for tab, acct in ((tab_all, None), (tab_us, "Dime US"), (tab_th, "Dime TH")):
            with tab:
                view = holdings if acct is None else holdings[holdings["account_type"] == acct]
                if view.empty:
                    st.caption(f"No holdings in {acct}.")
                    continue
                st.dataframe(view[cols], hide_index=True, width="stretch", column_config=config)
                if acct:
                    fig = px.bar(view.sort_values("unrealized_pnl"), x="unrealized_pnl", y="symbol",
                                 orientation="h", color=view.sort_values("unrealized_pnl")["unrealized_pnl"] >= 0,
                                 color_discrete_map={True: theme.UP, False: theme.DOWN})
                    theme.style_fig(fig, 60 + 34 * len(view)).update_layout(showlegend=False, bargap=0.3)
                    fig.update_xaxes(title=None, tickprefix=CCY_SYMBOL[acct])
                    fig.update_yaxes(title=None)
                    st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

# ---- Trade log ----
with st.expander("📜 Transaction log (edit mistakes here)"):
    trades = db_manager.fetch_trades()
    if trades.empty:
        st.caption("No transactions recorded.")
    else:
        trades = trades.sort_values(["timestamp", "id"], ascending=False)
        st.dataframe(trades, hide_index=True, width="stretch", column_config={
            "id": "ID", "timestamp": "Time", "account_type": "Account", "symbol": "Symbol",
            "trade_type": "Action", "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
            "price": st.column_config.NumberColumn("Price", format="%.4f")})
        c_del, c_btn = st.columns([3, 1], vertical_alignment="bottom")
        labels = {int(r.id): f"#{r.id} · {r.timestamp} · {r.trade_type} {r.shares:g} {r.symbol} ({r.account_type})"
                  for r in trades.itertuples()}
        to_delete = c_del.selectbox("Delete a transaction", list(labels), format_func=labels.get, key="del_id")
        if c_btn.button("🗑️ Delete", width="stretch"):
            # Deleting a buy that later sells depend on leaves those sells capped at zero shares.
            db_manager.delete_trade(to_delete)
            st.toast(f"Deleted transaction #{to_delete}")
            st.rerun()

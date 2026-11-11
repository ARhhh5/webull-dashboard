from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from core import db_manager, dime_data, theme
from core.theme import money, pct

CCY_SYMBOL = {"Dime US": "$", "Dime TH": "฿"}
SHORT = {"Dime US": "US", "Dime TH": "TH"}
VIEWS = ["All Dime", "Dime US", "Dime TH"]

# ---- Header + account filter ----
c_title, c_filter = st.columns([3, 2], vertical_alignment="center")
with c_title:
    theme.page_header("🧠 Dime Desk",
                      theme.status_pill("Local SQLite · portfolio.db", "#22c55e")
                      + "&nbsp; Manual entries · live prices via Yahoo Finance (cached 15 min)")
with c_filter:
    view = st.pills("Account view", VIEWS, required=True, default="All Dime", key="dime_view",
                    label_visibility="collapsed")
account = None if view == "All Dime" else view

fx, fx_live = dime_data.get_usd_thb()


def _prepare(df, usd_thb):
    """Guarantee every column this page reads, derived from the base holding fields.

    The page must not depend on optional columns from core.dime_data: Streamlit Cloud can keep an
    older imported module in memory after a deploy, and empty frames may carry no columns at all.
    """
    df = df.copy() if df is not None else pd.DataFrame()
    for col in ("account_type", "symbol", "currency", "price_source"):
        if col not in df.columns:
            df[col] = pd.Series(dtype="object")
    for col in ("shares", "avg_cost", "cost_basis", "realized_pnl", "last_price", "market_value"):
        if col not in df.columns:
            df[col] = pd.Series(dtype="float64")
    df["currency"] = df["currency"].fillna(df["account_type"].map(db_manager.ACCOUNT_CURRENCY))
    df["last_price"] = df["last_price"].fillna(df["avg_cost"])
    df["market_value"] = df["market_value"].fillna(df["shares"] * df["last_price"])
    df["price_source"] = df["price_source"].fillna("Avg cost")
    df["unrealized_pnl"] = df["market_value"] - df["cost_basis"]
    df["unrealized_pct"] = (df["unrealized_pnl"] / df["cost_basis"] * 100).where(df["cost_basis"] > 0, 0.0)
    to_usd = df["currency"].map({"USD": 1.0, "THB": 1 / usd_thb}).fillna(1.0)
    df["market_value_usd"] = df["market_value"] * to_usd
    df["cost_basis_usd"] = df["cost_basis"] * to_usd
    df["unrealized_pnl_usd"] = df["unrealized_pnl"] * to_usd
    return df


holdings_all = _prepare(dime_data.get_dime_portfolio(), fx)
holdings = holdings_all if account is None else holdings_all[holdings_all["account_type"] == account]

# Mixed accounts are consolidated in USD; a single account stays in its own currency.
if account is None:
    cur, value_col, cost_col, pnl_col = "$", "market_value_usd", "cost_basis_usd", "unrealized_pnl_usd"
    ccy_note = f"All amounts in USD · Dime TH converted at USD/THB {fx:,.2f}" + ("" if fx_live else " (fallback)")
else:
    cur, value_col, cost_col, pnl_col = CCY_SYMBOL[account], "market_value", "cost_basis", "unrealized_pnl"
    ccy_note = f"Amounts in {db_manager.ACCOUNT_CURRENCY[account]}"

st.write("")
tab_entry, tab_dash, tab_perf, tab_hist, tab_div = st.tabs(
    ["✍️ Trade Entry", "📊 Dashboard", "📈 Performance", "📝 History", "💰 Dividends"])

# ============ Trade Entry ============
with tab_entry:
    col_form, col_recent = st.columns([1.3, 1])
    with col_form, theme.card("form", "New Trade", "Saved instantly to the local SQLite database"):
        with st.form("dime_trade_form", clear_on_submit=True, border=False):
            c1, c2 = st.columns(2)
            f_account = c1.selectbox("Account", db_manager.ACCOUNTS,
                                     index=db_manager.ACCOUNTS.index(account or "Dime US"), key="f_account")
            f_action = c2.radio("Action", db_manager.TRADE_TYPES, horizontal=True, key="f_action")
            f_symbol = st.text_input("Symbol", placeholder="AAPL for Dime US · PTT for Dime TH (no .BK needed)",
                                     key="f_symbol")
            c3, c4 = st.columns(2)
            f_qty = c3.number_input("Quantity", min_value=0.0, step=1.0, format="%.4f", key="f_qty")
            f_price = c4.number_input("Price per share (USD for Dime US · THB for Dime TH)", min_value=0.0,
                                      step=0.01, format="%.4f", key="f_price")
            submitted = st.form_submit_button("💾 Save trade", type="primary", width="stretch")
        if submitted:
            try:
                db_manager.insert_trade(f_account, f_action, f_symbol, f_qty, f_price)
            except ValueError as exc:
                st.error(f"⚠️ {exc}")
            else:
                st.toast(f"✅ {f_action} {f_qty:g} {f_symbol.strip().upper()} @ "
                         f"{CCY_SYMBOL[f_account]}{f_price:,.2f} → {f_account}")
                st.rerun()

    with col_recent, theme.card("recent", "Recent Trades", f"{view} · last 8 entries"):
        recent = db_manager.fetch_trades(account)
        if recent.empty:
            st.caption("No trades yet. Your first entry will appear here.")
        else:
            for r in recent.sort_values(["timestamp", "id"], ascending=False).head(8).itertuples():
                color = theme.UP if r.trade_type == "Buy" else "#f472b6"
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:8px 0;'
                    f'border-bottom:1px solid #1c2130;font-size:.86rem">'
                    f'<div><b style="color:{color}">{r.trade_type.upper()}</b> '
                    f'<b style="color:#f8fafc">{r.symbol}</b> '
                    f'<span class="card-sub">{r.account_type} · {r.timestamp[:16]}</span></div>'
                    f'<div style="font-family:JetBrains Mono,monospace;color:#e2e8f0">{r.shares:g} @ '
                    f'{CCY_SYMBOL[r.account_type]}{r.price:,.2f}</div></div>', unsafe_allow_html=True)

# ============ Dashboard ============
with tab_dash:
    total_value = float(holdings[value_col].sum())
    total_cost = float(holdings[cost_col].sum())
    total_pnl = total_value - total_cost
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Value", money(total_value, cur), f"{len(holdings)} positions", delta_color="off",
              delta_arrow="off")
    k2.metric("Total PnL (Unrealized)", money(total_pnl, cur, signed=True),
              pct(total_pnl / total_cost * 100 if total_cost else 0.0))
    k3.metric("Cost Basis", money(total_cost, cur), ccy_note.split(" · ")[0], delta_color="off", delta_arrow="off")
    stale = int((holdings["price_source"] != "Market").sum())
    k4.metric("Live Prices", f"{len(holdings) - stale} / {len(holdings)}",
              "Yahoo Finance" if not stale else f"{stale} using avg cost", delta_color="off", delta_arrow="off")
    st.caption(ccy_note)

    if holdings.empty:
        st.info(f"No open positions in {view}. Record a Buy in **✍️ Trade Entry**.")
    else:
        with theme.card("dime-alloc", "Portfolio Allocation", f"Market value by symbol · {view}"):
            alloc = holdings.assign(
                Label=holdings["symbol"] + (" (" + holdings["account_type"].map(SHORT) + ")" if account is None
                                            else ""),
                Value=holdings[value_col])
            fig = px.pie(alloc, names="Label", values="Value", hole=0.62, color_discrete_sequence=theme.PALETTE)
            fig.update_traces(textposition="inside", textinfo="percent+label",
                              marker=dict(line=dict(color="#131722", width=2)),
                              hovertemplate=f"<b>%{{label}}</b><br>{cur}%{{value:,.2f}}<br>%{{percent}}<extra></extra>")
            theme.style_fig(fig, 400).update_layout(
                showlegend=True, legend=dict(orientation="v", x=1.02, y=0.5),
                annotations=[dict(text=f"<b>{money(total_value, cur)}</b><br>"
                                       "<span style='font-size:11px'>total value</span>",
                                  x=0.5, y=0.5, showarrow=False, font=dict(size=16, color="#f8fafc"))])
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

# ============ Performance ============
with tab_perf:
    if holdings.empty:
        st.info(f"No open positions in {view}.")
    else:
        with theme.card("dime-perf", "Position Performance",
                        "Prices and PnL in each account's own currency (USD for Dime US · THB for Dime TH)"):
            perf = holdings.rename(columns={
                "symbol": "Symbol", "account_type": "Account", "shares": "Quantity", "avg_cost": "Average Cost",
                "last_price": "Current Price", "market_value": "Market Value", "unrealized_pnl": "Unrealized PnL",
                "unrealized_pct": "Unrealized PnL %", "currency": "Ccy", "price_source": "Price Source"})
            perf = perf[["Symbol", "Account", "Quantity", "Average Cost", "Current Price", "Market Value",
                         "Unrealized PnL", "Unrealized PnL %", "Ccy", "Price Source"]]
            st.dataframe(
                perf.style.map(theme.pnl_color, subset=["Unrealized PnL", "Unrealized PnL %"]),
                hide_index=True, width="stretch", column_config={
                    "Quantity": st.column_config.NumberColumn(format="%.4f"),
                    "Average Cost": st.column_config.NumberColumn(format="%.2f"),
                    "Current Price": st.column_config.NumberColumn(format="%.2f"),
                    "Market Value": st.column_config.NumberColumn(format="%.2f"),
                    "Unrealized PnL": st.column_config.NumberColumn(format="%+.2f"),
                    "Unrealized PnL %": st.column_config.NumberColumn(format="%+.2f%%"),
                })
            if (perf["Price Source"] != "Market").any():
                st.caption("⚠️ Rows with Price Source = Avg cost had no Yahoo Finance price, so PnL shows 0.")

        with theme.card("dime-pnl", "Unrealized PnL % by Position", "Green = profit · Red = loss"):
            ordered = perf.assign(Label=perf["Symbol"] + " (" + perf["Account"].map(SHORT) + ")").sort_values(
                "Unrealized PnL %")
            fig = px.bar(ordered, x="Unrealized PnL %", y="Label", orientation="h",
                         color=ordered["Unrealized PnL %"] >= 0,
                         color_discrete_map={True: theme.UP, False: theme.DOWN})
            fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x:+.2f}%<extra></extra>")
            theme.style_fig(fig, 80 + 36 * len(ordered)).update_layout(showlegend=False, bargap=0.3)
            fig.update_xaxes(ticksuffix="%", title=None)
            fig.update_yaxes(title=None, categoryorder="array", categoryarray=list(ordered["Label"]))
            st.plotly_chart(fig, width="stretch", theme=None, config=theme.PLOTLY_CONFIG)

# ============ History ============
with tab_hist:
    with theme.card("history", "Trade History", f"Raw entries from SQLite · {view}"):
        trades = db_manager.fetch_trades(account)
        if trades.empty:
            st.caption("No trades recorded.")
        else:
            trades = trades.sort_values(["timestamp", "id"], ascending=False)
            st.dataframe(trades, hide_index=True, width="stretch", height=320, column_config={
                "id": "ID", "timestamp": "Date", "account_type": "Account", "symbol": "Symbol",
                "trade_type": "Type", "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
                "price": st.column_config.NumberColumn("Price", format="%.4f")})
            labels = {int(r.id): f"#{r.id} · {r.timestamp} · {r.trade_type} {r.shares:g} {r.symbol} "
                                 f"({r.account_type})" for r in trades.itertuples()}
            c_sel, c_ok, c_btn = st.columns([3, 1.2, 1], vertical_alignment="bottom")
            to_delete = c_sel.selectbox("Delete a mistaken trade", list(labels), format_func=labels.get,
                                        key="del_trade")
            confirm = c_ok.checkbox("Confirm delete", key="del_trade_ok")
            if c_btn.button("🗑️ Delete", width="stretch", disabled=not confirm, key="del_trade_btn"):
                # Deleting a buy that later sells depend on leaves those sells capped at zero shares.
                db_manager.delete_trade(to_delete)
                st.toast(f"Deleted trade #{to_delete}")
                st.rerun()

# ============ Dividends ============
with tab_div:
    divs = db_manager.fetch_dividends(account)
    if account is None:
        div_total = float((divs["amount"] / divs["account_type"].map({"Dime US": 1.0, "Dime TH": fx})).sum())
    else:
        div_total = float(divs["amount"].sum())
    d1, d2, d3 = st.columns(3)
    d1.metric("Dividends Received", money(div_total, cur), ccy_note.split(" · ")[0], delta_color="off",
              delta_arrow="off")
    d2.metric("Payments Logged", len(divs))
    d3.metric("Paying Symbols", int(divs["symbol"].nunique()) if not divs.empty else 0)
    st.write("")

    col_dform, col_dtable = st.columns([1, 1.6])
    with col_dform, theme.card("div-form", "Log Received Dividend", "Amount after tax, in the account's currency"):
        with st.form("dime_dividend_form", clear_on_submit=True, border=False):
            dv_account = st.selectbox("Account", db_manager.ACCOUNTS,
                                      index=db_manager.ACCOUNTS.index(account or "Dime US"), key="dv_account")
            dv_symbol = st.text_input("Symbol", key="dv_symbol")
            c1, c2 = st.columns(2)
            dv_amount = c1.number_input("Amount (USD for Dime US · THB for Dime TH)", min_value=0.0, step=0.01,
                                        format="%.2f", key="dv_amount")
            dv_date = c2.date_input("Date received", value=date.today(), key="dv_date")
            dv_submit = st.form_submit_button("💰 Save dividend", type="primary", width="stretch")
        if dv_submit:
            try:
                db_manager.insert_dividend(dv_account, dv_symbol, dv_amount, date=dv_date)
            except ValueError as exc:
                st.error(f"⚠️ {exc}")
            else:
                st.toast(f"✅ Dividend {CCY_SYMBOL[dv_account]}{dv_amount:,.2f} from "
                         f"{dv_symbol.strip().upper()} → {dv_account}")
                st.rerun()

    with col_dtable, theme.card("div-table", "Dividend History", f"{view} · newest first"):
        if divs.empty:
            st.caption("No dividends logged yet.")
        else:
            st.dataframe(divs, hide_index=True, width="stretch", height=280, column_config={
                "id": "ID", "date": "Date", "account_type": "Account", "symbol": "Symbol",
                "amount": st.column_config.NumberColumn("Amount", format="%.2f"), "currency": "Ccy"})
            labels = {int(r.id): f"#{r.id} · {r.date} · {r.symbol} {CCY_SYMBOL[r.account_type]}{r.amount:,.2f}"
                      for r in divs.itertuples()}
            c_sel, c_btn = st.columns([3, 1], vertical_alignment="bottom")
            dv_delete = c_sel.selectbox("Delete a dividend entry", list(labels), format_func=labels.get,
                                        key="del_div")
            if c_btn.button("🗑️ Delete", width="stretch", key="del_div_btn"):
                db_manager.delete_dividend(dv_delete)
                st.toast(f"Deleted dividend #{dv_delete}")
                st.rerun()

"""SQLite storage for manually recorded Dime trades (built-in sqlite3, no external services)."""
import os
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

DB_PATH = Path(os.environ.get("PORTFOLIO_DB_PATH", Path(__file__).resolve().parent.parent / "portfolio.db"))

ACCOUNTS = ("Dime TH", "Dime US")
TRADE_TYPES = ("Buy", "Sell")
ACCOUNT_CURRENCY = {"Dime TH": "THB", "Dime US": "USD"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dime_trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp    TEXT    NOT NULL,
    account_type TEXT    NOT NULL CHECK (account_type IN ('Dime TH', 'Dime US')),
    symbol       TEXT    NOT NULL,
    trade_type   TEXT    NOT NULL CHECK (trade_type IN ('Buy', 'Sell')),
    shares       REAL    NOT NULL CHECK (shares > 0),
    price        REAL    NOT NULL CHECK (price >= 0)
);
CREATE INDEX IF NOT EXISTS idx_dime_trades_account_symbol ON dime_trades (account_type, symbol);
CREATE TABLE IF NOT EXISTS dime_dividends (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    date         TEXT    NOT NULL,
    account_type TEXT    NOT NULL CHECK (account_type IN ('Dime TH', 'Dime US')),
    symbol       TEXT    NOT NULL,
    amount       REAL    NOT NULL CHECK (amount > 0)
);
-- Webull cache: written only by an explicit Sync, read on every page load (no SDK on load).
CREATE TABLE IF NOT EXISTS webull_summary (
    id           INTEGER PRIMARY KEY CHECK (id = 1),
    account_id   TEXT,
    total_value  REAL    NOT NULL,
    market_value REAL    NOT NULL,
    cash         REAL    NOT NULL,
    cost_basis   REAL    NOT NULL,
    day_pnl      REAL,
    day_pnl_pct  REAL,
    open_pnl     REAL    NOT NULL,
    open_pnl_pct REAL    NOT NULL,
    positions    INTEGER NOT NULL,
    last_synced  TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS webull_positions (
    symbol         TEXT NOT NULL,
    quantity       REAL,
    avg_cost       REAL,
    last_price     REAL,
    market_value   REAL,
    cost_basis     REAL,
    open_pnl       REAL,
    open_pnl_pct   REAL,
    day_change_pct REAL,
    day_pnl        REAL,
    weight_pct     REAL,
    currency       TEXT
);
CREATE TABLE IF NOT EXISTS webull_orders (
    order_id     TEXT,
    time         TEXT,
    symbol       TEXT,
    side         TEXT,
    status       TEXT,
    order_type   TEXT,
    quantity     REAL,
    filled_qty   REAL,
    filled_price REAL,
    amount       REAL
);
"""

WEBULL_SUMMARY_FIELDS = ["account_id", "total_value", "market_value", "cash", "cost_basis", "day_pnl",
                         "day_pnl_pct", "open_pnl", "open_pnl_pct", "positions"]
WEBULL_POSITION_FIELDS = ["symbol", "quantity", "avg_cost", "last_price", "market_value", "cost_basis", "open_pnl",
                          "open_pnl_pct", "day_change_pct", "day_pnl", "weight_pct", "currency"]
WEBULL_ORDER_FIELDS = ["order_id", "time", "symbol", "side", "status", "order_type", "quantity", "filled_qty",
                       "filled_price", "amount"]

HOLDING_COLUMNS = ["account_type", "symbol", "shares", "avg_cost", "cost_basis", "realized_pnl", "currency"]
# Tolerance for float leftovers from fractional shares.
_EPS = 1e-9


def _connect(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Create portfolio.db and the dime_trades table if they don't exist."""
    with closing(_connect(db_path)) as conn, conn:
        conn.executescript(_SCHEMA)


def _normalize_symbol(symbol, account_type):
    symbol = str(symbol or "").strip().upper()
    if account_type == "Dime TH" and symbol.endswith(".BK"):
        symbol = symbol[:-3]
    return symbol


def insert_trade(account_type, trade_type, symbol, shares, price, timestamp=None, db_path=None):
    """Validate and insert one trade. Returns the new row id. Raises ValueError on bad input."""
    if account_type not in ACCOUNTS:
        raise ValueError(f"account_type must be one of {ACCOUNTS}")
    if trade_type not in TRADE_TYPES:
        raise ValueError(f"trade_type must be one of {TRADE_TYPES}")
    symbol = _normalize_symbol(symbol, account_type)
    if not symbol:
        raise ValueError("Symbol is required")
    shares, price = float(shares), float(price)
    if shares <= 0:
        raise ValueError("Shares must be greater than 0")
    if price < 0:
        raise ValueError("Price cannot be negative")

    init_db(db_path)
    if trade_type == "Sell":
        held = get_position_shares(account_type, symbol, db_path)
        if shares > held + _EPS:
            raise ValueError(f"Cannot sell {shares:g} {symbol}: only {held:g} shares held in {account_type}")

    ts = (timestamp or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    with closing(_connect(db_path)) as conn, conn:
        cur = conn.execute(
            "INSERT INTO dime_trades (timestamp, account_type, symbol, trade_type, shares, price) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, account_type, symbol, trade_type, shares, price),
        )
        return cur.lastrowid


def delete_trade(trade_id, db_path=None):
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        return conn.execute("DELETE FROM dime_trades WHERE id = ?", (int(trade_id),)).rowcount


def fetch_trades(account_type=None, db_path=None):
    init_db(db_path)
    query = "SELECT * FROM dime_trades"
    params = ()
    if account_type:
        query += " WHERE account_type = ?"
        params = (account_type,)
    with closing(_connect(db_path)) as conn:
        df = pd.read_sql_query(query + " ORDER BY timestamp, id", conn, params=params)
    return df


def get_position_shares(account_type, symbol, db_path=None):
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(CASE trade_type WHEN 'Buy' THEN shares ELSE -shares END), 0) "
            "FROM dime_trades WHERE account_type = ? AND symbol = ?",
            (account_type, _normalize_symbol(symbol, account_type)),
        ).fetchone()
    return float(row[0])


def get_holdings(db_path=None):
    """Current holdings per (account, symbol) using the average-cost method.

    Sells reduce shares at the running average cost and book the difference as realized PnL.
    """
    trades = fetch_trades(db_path=db_path)
    positions = {}
    for t in trades.itertuples(index=False):
        key = (t.account_type, t.symbol)
        pos = positions.setdefault(key, {"shares": 0.0, "cost_basis": 0.0, "realized_pnl": 0.0})
        if t.trade_type == "Buy":
            pos["shares"] += t.shares
            pos["cost_basis"] += t.shares * t.price
        else:
            sold = min(t.shares, pos["shares"])
            avg = pos["cost_basis"] / pos["shares"] if pos["shares"] > _EPS else 0.0
            pos["realized_pnl"] += sold * (t.price - avg)
            pos["shares"] -= sold
            pos["cost_basis"] -= sold * avg

    rows = []
    for (account, symbol), pos in positions.items():
        if pos["shares"] <= _EPS:
            continue
        rows.append({
            "account_type": account, "symbol": symbol, "shares": pos["shares"],
            "avg_cost": pos["cost_basis"] / pos["shares"], "cost_basis": pos["cost_basis"],
            "realized_pnl": pos["realized_pnl"], "currency": ACCOUNT_CURRENCY[account],
        })
    return pd.DataFrame(rows, columns=HOLDING_COLUMNS).sort_values(
        ["account_type", "cost_basis"], ascending=[True, False]).reset_index(drop=True)


def insert_dividend(account_type, symbol, amount, date=None, db_path=None):
    """Record a received dividend (amount in the account's currency). Returns the new row id."""
    if account_type not in ACCOUNTS:
        raise ValueError(f"account_type must be one of {ACCOUNTS}")
    symbol = _normalize_symbol(symbol, account_type)
    if not symbol:
        raise ValueError("Symbol is required")
    amount = float(amount)
    if amount <= 0:
        raise ValueError("Amount must be greater than 0")
    day = (date or datetime.now()).strftime("%Y-%m-%d")
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        return conn.execute(
            "INSERT INTO dime_dividends (date, account_type, symbol, amount) VALUES (?, ?, ?, ?)",
            (day, account_type, symbol, amount),
        ).lastrowid


def delete_dividend(dividend_id, db_path=None):
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        return conn.execute("DELETE FROM dime_dividends WHERE id = ?", (int(dividend_id),)).rowcount


def fetch_dividends(account_type=None, db_path=None):
    init_db(db_path)
    query, params = "SELECT * FROM dime_dividends", ()
    if account_type:
        query, params = query + " WHERE account_type = ?", (account_type,)
    with closing(_connect(db_path)) as conn:
        df = pd.read_sql_query(query + " ORDER BY date DESC, id DESC", conn, params=params)
    df["currency"] = df["account_type"].map(ACCOUNT_CURRENCY)
    return df


def _records(df, fields):
    """DataFrame -> list of tuples in `fields` order, with NaN/NaT stored as NULL."""
    if df is None or df.empty:
        return []
    df = df.reindex(columns=fields).astype(object)
    return [tuple(row) for row in df.where(df.notna(), None).itertuples(index=False, name=None)]


def _insert_sql(table, fields):
    return f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({', '.join('?' * len(fields))})"


def save_webull_data(summary, positions, orders=None, synced_at=None, db_path=None):
    """Replace the cached Webull snapshot in one transaction.

    summary: dict with WEBULL_SUMMARY_FIELDS; positions / orders: DataFrames with the snake_case fields.
    orders=None keeps the previously cached orders (e.g. when only the order-history call failed).
    """
    synced = synced_at or datetime.now(timezone.utc)
    init_db(db_path)
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM webull_summary")
        conn.execute(_insert_sql("webull_summary", ["id", *WEBULL_SUMMARY_FIELDS, "last_synced"]),
                     [1, *[summary.get(f) for f in WEBULL_SUMMARY_FIELDS], synced.isoformat(timespec="seconds")])
        conn.execute("DELETE FROM webull_positions")
        conn.executemany(_insert_sql("webull_positions", WEBULL_POSITION_FIELDS),
                         _records(positions, WEBULL_POSITION_FIELDS))
        if orders is not None:
            conn.execute("DELETE FROM webull_orders")
            conn.executemany(_insert_sql("webull_orders", WEBULL_ORDER_FIELDS), _records(orders, WEBULL_ORDER_FIELDS))


def get_webull_data(db_path=None):
    """Cached Webull snapshot: dict(summary=dict|None, positions=DataFrame, orders=DataFrame, last_synced=str|None)."""
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT * FROM webull_summary WHERE id = 1").fetchone()
        positions = pd.read_sql_query(
            f"SELECT {', '.join(WEBULL_POSITION_FIELDS)} FROM webull_positions ORDER BY market_value DESC", conn)
        orders = pd.read_sql_query(
            f"SELECT {', '.join(WEBULL_ORDER_FIELDS)} FROM webull_orders ORDER BY time DESC", conn)
    summary = dict(row) if row else None
    return {"summary": summary, "positions": positions, "orders": orders,
            "last_synced": summary["last_synced"] if summary else None}

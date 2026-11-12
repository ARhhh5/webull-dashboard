"""SQLite storage: manual Dime trades/dividends and the Webull sync cache (built-in sqlite3).

Schema changes are versioned migrations (PRAGMA user_version). Pending migrations run automatically
inside init_db(), after a backup of the existing database is written to backups/. See
scripts/db_tool.py for status / backup / migrate / rollback / restore.
"""
import json
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

# Baseline (schema version 0). Never edit: later changes must be added as MIGRATIONS.
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

# Columns added by migration 1. A NULL base_currency marks a snapshot synced before the USD fix.
WEBULL_CURRENCY_FIELDS = ["base_currency", "account_currency", "cash_status", "cash_detail", "fx_rate", "fx_source",
                          "fx_as_of", "fx_estimated", "reported_market_value", "reported_open_pnl", "reported_cash",
                          "reconciliation_diff_pct", "warnings", "raw_balance"]
_SUMMARY_CURRENCY_DDL = [
    ("base_currency", "TEXT"), ("account_currency", "TEXT"), ("cash_status", "TEXT"), ("cash_detail", "TEXT"),
    ("fx_rate", "REAL"), ("fx_source", "TEXT"), ("fx_as_of", "TEXT"), ("fx_estimated", "INTEGER"),
    ("reported_market_value", "REAL"), ("reported_open_pnl", "REAL"), ("reported_cash", "REAL"),
    ("reconciliation_diff_pct", "REAL"), ("warnings", "TEXT"), ("raw_balance", "TEXT"),
]
_SYNC_LOG_FIELDS = ["synced_at", "account_id", "total_value", "market_value", "cash", "open_pnl", "open_pnl_pct",
                    "day_pnl", "positions", *WEBULL_CURRENCY_FIELDS]

def _rebuild_without_new_columns(table, keep_columns):
    """Down-migration that drops columns by rebuilding the table, since ALTER TABLE DROP COLUMN needs
    SQLite >= 3.35 and Streamlit Community Cloud has shipped 3.34.1. Rows in kept columns are copied as is."""
    ddl = _SCHEMA.split(f"CREATE TABLE IF NOT EXISTS {table} (", 1)[1].split("\n);", 1)[0]
    cols = ", ".join(keep_columns)
    return [f"CREATE TABLE {table}__rollback ({ddl}\n)",
            f"INSERT INTO {table}__rollback ({cols}) SELECT {cols} FROM {table}",
            f"DROP TABLE {table}",
            f"ALTER TABLE {table}__rollback RENAME TO {table}"]


# (version, name, up statements, down statements). Downs only drop what the matching up added.
# Only SQL supported by SQLite 3.34 (Streamlit Community Cloud) may be used here.
MIGRATIONS = [
    (1, "usd_base_currency",
     [f"ALTER TABLE webull_summary ADD COLUMN {name} {kind}" for name, kind in _SUMMARY_CURRENCY_DDL]
     + ["ALTER TABLE webull_positions ADD COLUMN fx_to_usd REAL",
        """CREATE TABLE IF NOT EXISTS webull_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, synced_at TEXT NOT NULL, account_id TEXT,
            total_value REAL, market_value REAL, cash REAL, open_pnl REAL, open_pnl_pct REAL, day_pnl REAL,
            positions INTEGER, base_currency TEXT, account_currency TEXT, cash_status TEXT, cash_detail TEXT,
            fx_rate REAL, fx_source TEXT, fx_as_of TEXT, fx_estimated INTEGER, reported_market_value REAL,
            reported_open_pnl REAL, reported_cash REAL, reconciliation_diff_pct REAL, warnings TEXT,
            raw_balance TEXT)"""],
     ["DROP TABLE IF EXISTS webull_sync_log"]
     + _rebuild_without_new_columns("webull_positions", WEBULL_POSITION_FIELDS)
     + _rebuild_without_new_columns("webull_summary", ["id", *WEBULL_SUMMARY_FIELDS, "last_synced"])),
]
SCHEMA_VERSION = MIGRATIONS[-1][0]
_USER_TABLES = ("dime_trades", "dime_dividends", "webull_summary", "webull_positions", "webull_orders")
_migrated = set()  # db paths already verified at SCHEMA_VERSION in this process

HOLDING_COLUMNS = ["account_type", "symbol", "shares", "avg_cost", "cost_basis", "realized_pnl", "currency"]
# Tolerance for float leftovers from fractional shares.
_EPS = 1e-9


def _connect(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _path(db_path=None):
    return Path(db_path or DB_PATH)


def schema_version(db_path=None):
    with closing(sqlite3.connect(_path(db_path))) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def _row_counts(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in _USER_TABLES if t in tables}


def row_counts(db_path=None):
    with closing(sqlite3.connect(_path(db_path))) as conn:
        return _row_counts(conn)


def backup_dir(db_path=None):
    return _path(db_path).parent / "backups"


def backup_db(label="manual", db_path=None):
    """Consistent online copy (sqlite backup API) into backups/. Returns the backup path."""
    src_path = _path(db_path)
    dest = backup_dir(db_path) / f"{src_path.stem}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{label}.db"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(src_path)) as src, closing(sqlite3.connect(dest)) as dst:
        src.backup(dst)
    return dest


def backup_bytes(db_path=None):
    """Consistent snapshot of the database as bytes (for the in-app download button)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "portfolio.db"
        with closing(sqlite3.connect(_path(db_path))) as src, closing(sqlite3.connect(dest)) as dst:
            src.backup(dst)
        return dest.read_bytes()


def _apply(db_path, steps, target, expected_current):
    """Run (version, statements) steps in one IMMEDIATE transaction, then set user_version = target.

    The version is re-read under the write lock; if another session already moved it, nothing runs.
    """
    conn = sqlite3.connect(_path(db_path), isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        if conn.execute("PRAGMA user_version").fetchone()[0] != expected_current:
            conn.execute("ROLLBACK")
            return False
        for _, statements in steps:
            for sql in statements:
                conn.execute(sql)
        conn.execute(f"PRAGMA user_version = {int(target)}")
        conn.execute("COMMIT")
        return True
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def migrate(db_path=None, target=SCHEMA_VERSION):
    """Apply pending migrations up to `target`. Backs up first when the DB holds data.

    Returns dict(from_version, to_version, backup) — backup is None when nothing ran or the DB was empty.
    """
    current = schema_version(db_path)
    if current >= target:
        return {"from_version": current, "to_version": current, "backup": None}
    backup = backup_db(f"pre-migrate-v{current}-to-v{target}", db_path) if sum(row_counts(db_path).values()) else None
    with closing(sqlite3.connect(_path(db_path))) as conn, conn:
        conn.executescript(_SCHEMA)  # migrations alter baseline tables, so make sure they exist (non-destructive)
    pending = [(v, up) for v, _, up, _ in MIGRATIONS if current < v <= target]
    _apply(db_path, pending, target, current)
    return {"from_version": current, "to_version": schema_version(db_path), "backup": backup}


def rollback(target, db_path=None):
    """Revert migrations above `target` (down statements). Always backs up first. Data in earlier
    columns/tables is preserved; columns added by the reverted migrations are dropped."""
    current = schema_version(db_path)
    if target >= current:
        return {"from_version": current, "to_version": current, "backup": None}
    backup = backup_db(f"pre-rollback-v{current}-to-v{target}", db_path)
    steps = [(v, down) for v, _, _, down in sorted(MIGRATIONS, reverse=True) if target < v <= current]
    _apply(db_path, steps, target, current)
    _migrated.discard(str(_path(db_path)))
    return {"from_version": current, "to_version": schema_version(db_path), "backup": backup}


def restore(backup_path, db_path=None):
    """Replace the database with a backup. The current database is backed up first."""
    backup_path = Path(backup_path)
    if not backup_path.exists():
        raise FileNotFoundError(backup_path)
    safety = backup_db("pre-restore", db_path) if _path(db_path).exists() else None
    with closing(sqlite3.connect(backup_path)) as src, closing(sqlite3.connect(_path(db_path))) as dst:
        src.backup(dst)
    _migrated.discard(str(_path(db_path)))
    return {"restored_from": backup_path, "backup": safety}


def init_db(db_path=None):
    """Create the baseline tables if missing, then apply pending migrations (with backup)."""
    key = str(_path(db_path))
    with closing(_connect(db_path)) as conn, conn:
        conn.executescript(_SCHEMA)
    if key in _migrated:
        return
    migrate(db_path)
    _migrated.add(key)


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


def _summary_value(summary, field):
    value = summary.get(field)
    if field in ("warnings", "raw_balance") and value is not None and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, default=str)
    if field == "fx_as_of" and isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if field == "fx_estimated" and value is not None:
        return int(bool(value))
    if field == "cash" and value is None:
        return 0.0  # NOT NULL in the v0 schema; cash_status = 'unverified' marks it as unknown on read
    return value


def save_webull_data(summary, positions, orders=None, synced_at=None, db_path=None):
    """Replace the cached Webull snapshot in one transaction and append it to webull_sync_log.

    summary: dict with WEBULL_SUMMARY_FIELDS (+ optional WEBULL_CURRENCY_FIELDS); positions / orders:
    DataFrames with the snake_case fields. orders=None keeps the previously cached orders.
    """
    synced = (synced_at or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    init_db(db_path)
    summary_fields = [*WEBULL_SUMMARY_FIELDS, *WEBULL_CURRENCY_FIELDS]
    with closing(_connect(db_path)) as conn, conn:
        conn.execute("DELETE FROM webull_summary")
        conn.execute(_insert_sql("webull_summary", ["id", *summary_fields, "last_synced"]),
                     [1, *[_summary_value(summary, f) for f in summary_fields], synced])
        conn.execute("DELETE FROM webull_positions")
        position_fields = [*WEBULL_POSITION_FIELDS, "fx_to_usd"]
        conn.executemany(_insert_sql("webull_positions", position_fields), _records(positions, position_fields))
        if orders is not None:
            conn.execute("DELETE FROM webull_orders")
            conn.executemany(_insert_sql("webull_orders", WEBULL_ORDER_FIELDS), _records(orders, WEBULL_ORDER_FIELDS))
        log_fields = _SYNC_LOG_FIELDS[2:]
        conn.execute(_insert_sql("webull_sync_log", _SYNC_LOG_FIELDS),
                     [synced, summary.get("account_id"), *[_summary_value(summary, f) for f in log_fields]])


def get_webull_data(db_path=None):
    """Cached Webull snapshot: dict(summary=dict|None, positions=DataFrame, orders=DataFrame, last_synced=str|None)."""
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT * FROM webull_summary WHERE id = 1").fetchone()
        positions = pd.read_sql_query(
            f"SELECT {', '.join(WEBULL_POSITION_FIELDS)}, fx_to_usd FROM webull_positions "
            "ORDER BY market_value DESC", conn)
        orders = pd.read_sql_query(
            f"SELECT {', '.join(WEBULL_ORDER_FIELDS)} FROM webull_orders ORDER BY time DESC", conn)
    summary = dict(row) if row else None
    if summary:
        try:
            summary["warnings"] = json.loads(summary.get("warnings") or "[]")
        except ValueError:
            summary["warnings"] = [str(summary.get("warnings"))]
    return {"summary": summary, "positions": positions, "orders": orders,
            "last_synced": summary["last_synced"] if summary else None}


def get_sync_log(limit=50, db_path=None):
    init_db(db_path)
    with closing(_connect(db_path)) as conn:
        return pd.read_sql_query("SELECT * FROM webull_sync_log ORDER BY id DESC LIMIT ?", conn, params=(limit,))

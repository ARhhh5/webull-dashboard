"""Dry-run the schema migration against a COPY of a real portfolio.db and print an evidence report.

    python scripts/verify_migration.py path/to/portfolio.db [--report report.json]

The given file is only ever opened read-only (its SHA-256 is checked before and after). All work happens on
copies in a temporary directory: migrate, backup, rollback, restore, then a simulated Webull sync (the Webull
API is mocked, no network, no credentials) including a failed sync. Dime holdings and dividends are compared
with the pre-migration code from origin/main when git is available. Exit code 1 if any check fails.
"""
import argparse
import hashlib
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from core import db_manager, dime_data, fx, webull_data  # noqa: E402

TEST_FX = fx.FxRate(rate=33.65, source="verify_migration fixed quote", as_of=datetime(2026, 11, 12, tzinfo=timezone.utc))
BASELINE_COLUMNS = {"webull_summary": ["id", *db_manager.WEBULL_SUMMARY_FIELDS, "last_synced"],
                    "webull_positions": db_manager.WEBULL_POSITION_FIELDS,
                    "webull_orders": db_manager.WEBULL_ORDER_FIELDS}


class Report:
    def __init__(self):
        self.checks, self.facts = [], {}

    def check(self, name, ok, detail=None):
        self.checks.append({"check": name, "ok": bool(ok), **({"detail": detail} if detail is not None else {})})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail is not None else ""))
        return ok

    @property
    def ok(self):
        return all(c["ok"] for c in self.checks)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tables(db):
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        return sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"))


def all_row_counts(db):
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        return {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables(db)}


def fingerprint(db, table, columns=None):
    """Order-independent hash of a table's rows (optionally restricted to the v0 columns)."""
    with closing(sqlite3.connect(f"file:{db}?mode=ro", uri=True)) as conn:
        cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
        rows = sorted(repr(tuple(r)) for r in conn.execute(f'SELECT {cols} FROM "{table}"'))
    return hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16]


def fingerprints(db, v0_only=True):
    present = set(tables(db))
    return {t: fingerprint(db, t, BASELINE_COLUMNS.get(t) if v0_only else None)
            for t in ("dime_trades", "dime_dividends", *BASELINE_COLUMNS) if t in present}


def copy(src, dest):
    with closing(sqlite3.connect(f"file:{src}?mode=ro", uri=True)) as s, closing(sqlite3.connect(dest)) as d:
        s.backup(d)
    return dest


def load_main_db_manager(tmp):
    try:
        source = subprocess.run(["git", "-C", str(ROOT), "show", "origin/main:core/db_manager.py"],
                                capture_output=True, text=True, check=True).stdout
    except Exception:
        return None
    path = Path(tmp) / "db_manager_main.py"
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("db_manager_main", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dime_snapshot(module, db):
    holdings = module.get_holdings(db_path=db).round(8).reset_index(drop=True)
    divs = module.fetch_dividends(db_path=db)
    return holdings, divs


def check_dime(report, before, after, db):
    (h0, d0), (h1, d1) = before, after
    report.check("Dime holdings identical to pre-migration code", h0.equals(h1), f"{len(h1)} holdings")
    report.check("Dime dividends identical", d0.reset_index(drop=True).equals(d1.reset_index(drop=True)),
                 f"{len(d1)} rows")
    for account, ccy in db_manager.ACCOUNT_CURRENCY.items():
        sub = d1[d1["account_type"] == account]
        report.facts[f"dividends_{account}"] = f"{ccy} {sub['amount'].sum():,.2f} ({len(sub)} rows)"
    # Valuation at avg cost and a fixed FX so the result does not depend on the network.
    with patch.object(db_manager, "DB_PATH", db), patch.object(dime_data, "get_prices", lambda syms: {}), \
            patch.object(dime_data, "get_usd_thb", lambda: TEST_FX):
        port = dime_data.get_dime_portfolio()
    factor = port["currency"].map({"USD": 1.0, "THB": 1 / TEST_FX.rate})
    report.check("Dime USD conversion = native × (1 or 1/USDTHB), no unknown currency",
                 factor.notna().all() and ((port["market_value_usd"] - port["market_value"] * factor).abs() < 1e-9).all())
    for account in db_manager.ACCOUNT_CURRENCY:
        s = dime_data.summarize(port, account)
        report.facts[f"summary_{account}"] = {k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}


def mocked_sync(rows, balance, orders=None, orders_error=None, connect_error=None):
    connect = MagicMock(side_effect=connect_error, return_value=(object(), object(), "VERIFY-ACC"))
    with patch.object(webull_data, "_connect", connect), \
            patch.object(webull_data, "_fetch_account", lambda *a: (rows, {}, balance)), \
            patch.object(webull_data, "_fetch_orders", MagicMock(side_effect=orders_error, return_value=orders or [])), \
            patch.object(fx, "fetch_usd_thb", lambda: TEST_FX):
        return webull_data.sync_from_webull()


def check_sync(report, db):
    rows = [{"Symbol": "AAPL", "Quantity": 2.0, "Avg Cost": 150.0, "Last Price": 200.0, "Currency": "USD"},
            {"Symbol": "VOO", "Quantity": 1.0, "Avg Cost": 500.0, "Last Price": 550.0, "Currency": "USD"}]
    balance = {"total_asset_currency": "THB", "total_market_value": str(950 * TEST_FX.rate),
               "total_cash_balance": str(20.47 * TEST_FX.rate),
               "account_currency_assets": [{"currency": "USD", "cash_balance": "20.47"}]}
    with patch.object(db_manager, "DB_PATH", db):
        before = db_manager.get_webull_data()
        log_before = len(db_manager.get_sync_log())
        try:
            mocked_sync(rows, balance, connect_error=RuntimeError("401 UNAUTHORIZED"))
            raised = False
        except RuntimeError:
            raised = True
        after = db_manager.get_webull_data()
        report.check("Failed sync (auth error) raises and keeps the previous snapshot",
                     raised and after["summary"] == before["summary"] and after["positions"].equals(before["positions"])
                     and after["orders"].equals(before["orders"]) and len(db_manager.get_sync_log()) == log_before)

        orders_before = len(before["orders"])
        result = mocked_sync(rows, balance, orders_error=RuntimeError("history down"))
        cache = db_manager.get_webull_data()
        report.check("Sync with order-history failure keeps previous orders",
                     result["orders"] is None and len(cache["orders"]) == orders_before, f"{orders_before} orders")

        s, log = cache["summary"], db_manager.get_sync_log()
        report.check("Sync stores currency metadata",
                     (s["base_currency"], s["account_currency"], s["fx_source"], s["fx_rate"])
                     == ("USD", "THB", TEST_FX.source, TEST_FX.rate) and s["fx_as_of"] is not None,
                     {k: s[k] for k in ("base_currency", "account_currency", "fx_rate", "fx_source", "fx_as_of")})
        report.check("Sync cash verified in USD", s["cash_status"] == "USD" and abs(s["cash"] - 20.47) < 1e-9,
                     s["cash_detail"])
        report.check("Sync positions/total in USD",
                     len(cache["positions"]) == 2 and abs(s["total_value"] - 970.47) < 1e-9
                     and set(cache["positions"]["fx_to_usd"]) == {1.0}, f"total_value {s['total_value']:.2f}")
        report.check("Sync log row appended with raw balance",
                     len(log) == log_before + 1 and "total_asset_currency" in log.loc[0, "raw_balance"])
        portfolio = webull_data.get_portfolio()
        report.check("Page data reads the synced snapshot without re-converting",
                     not portfolio["legacy"] and abs(portfolio["metrics"]["total_value"] - 970.47) < 1e-9)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("db")
    parser.add_argument("--report", help="write the JSON report here")
    args = parser.parse_args(argv)
    original = Path(args.db).resolve()
    report = Report()
    original_hash = sha256(original)
    report.facts.update(sqlite_runtime=sqlite3.sqlite_version, python=sys.version.split()[0],
                        file=original.name, size_bytes=original.stat().st_size, sha256=original_hash)
    print(f"SQLite {sqlite3.sqlite_version} · {original.name} · sha256 {original_hash[:16]}…")

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        work, pristine = tmp / "portfolio.db", tmp / "pristine.db"
        copy(original, work)
        copy(original, pristine)
        version0 = db_manager.schema_version(work)
        counts0, prints0 = all_row_counts(work), fingerprints(work)
        report.facts.update(schema_version_before=version0, row_counts_before=counts0)
        print(f"Before: schema v{version0}, rows {counts0}")
        main_dbm = load_main_db_manager(tmp)
        dime0 = dime_snapshot(main_dbm or db_manager, copy(original, tmp / "baseline.db"))
        report.facts["dime_baseline_code"] = "origin/main" if main_dbm else "current (git unavailable)"

        # 0. a migration that fails half-way must leave the copy exactly as it was
        broken = tmp / "broken.db"
        copy(original, broken)
        cols_before = {t: [r[1] for r in sqlite3.connect(broken).execute(f'PRAGMA table_info("{t}")')]
                       for t in tables(broken)}
        version, name, up, down = db_manager.MIGRATIONS[-1]
        failing = [*db_manager.MIGRATIONS[:-1], (version, name, up[:len(up) // 2] + ["SELECT * FROM no_such_table"], down)]
        with patch.object(db_manager, "MIGRATIONS", failing):
            try:
                db_manager.migrate(broken)
                failed = False
            except sqlite3.OperationalError:
                failed = True
        cols_after = {t: [r[1] for r in sqlite3.connect(broken).execute(f'PRAGMA table_info("{t}")')]
                      for t in tables(broken)}
        report.check("Migration failing half-way rolls back completely",
                     failed and db_manager.schema_version(broken) == version0 and cols_after == cols_before
                     and all_row_counts(broken) == counts0 and fingerprints(broken, False) == fingerprints(pristine, False),
                     f"{len(up) // 2} of {len(up)} statements ran before the error")

        # 1. migrate
        result = db_manager.migrate(work)
        report.facts["migrate"] = {**result, "backup": result["backup"] and result["backup"].name}
        report.check("Migrated to latest schema", db_manager.schema_version(work) == db_manager.SCHEMA_VERSION,
                     f"v{version0} → v{db_manager.schema_version(work)}")
        counts1 = all_row_counts(work)
        report.check("Row counts unchanged after migration (existing tables)",
                     all(counts1.get(t) == n for t, n in counts0.items()), counts1)
        report.check("Existing data unchanged after migration (row fingerprints)", fingerprints(work) == prints0)
        if version0 < db_manager.SCHEMA_VERSION:
            backup = result["backup"]
            report.check("Pre-migration backup written and equal to the original",
                         backup is not None and db_manager.schema_version(backup) == version0
                         and all_row_counts(backup) == counts0 and fingerprints(backup, False) == fingerprints(pristine, False),
                         backup and backup.name)
        check_dime(report, dime0, dime_snapshot(db_manager, work), work)

        # 2. rollback
        rb = db_manager.rollback(version0, work)
        report.check("Rollback restores the previous schema version", db_manager.schema_version(work) == version0,
                     f"backup {rb['backup'] and rb['backup'].name}")
        report.check("Rollback keeps all rows and data", all_row_counts(work) == counts0 and fingerprints(work) == prints0)
        if main_dbm:
            report.check("Pre-migration code still reads the rolled-back DB", dime_snapshot(main_dbm, work)[0].equals(dime0[0]))

        # 3. restore from the pre-migration backup (after migrating again)
        db_manager.migrate(work)
        source = result["backup"] or pristine
        rs = db_manager.restore(source, work)
        report.check("Restore returns an exact copy of the backup",
                     fingerprints(work, False) == fingerprints(pristine, False) and all_row_counts(work) == counts0
                     and db_manager.schema_version(work) == version0, f"safety backup {rs['backup'].name}")

        # 4. sync on the migrated copy
        db_manager._migrated.discard(str(work))
        db_manager.migrate(work)
        check_sync(report, work)
        prints_after_sync = fingerprints(work)
        report.check("Dime trades and dividends untouched by sync",
                     all(prints_after_sync[t] == prints0[t] for t in ("dime_trades", "dime_dividends") if t in prints0))

    report.check("Original file was not modified", sha256(original) == original_hash)
    print(f"\n{sum(c['ok'] for c in report.checks)}/{len(report.checks)} checks passed")
    if args.report:
        Path(args.report).write_text(json.dumps({"ok": report.ok, "facts": report.facts, "checks": report.checks},
                                                indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

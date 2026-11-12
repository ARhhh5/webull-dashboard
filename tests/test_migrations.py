import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from core import db_manager, webull_data
from scripts import db_tool


def columns(db, table):
    with closing(sqlite3.connect(db)) as conn:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / "portfolio.db")
        db_manager._migrated.clear()
        # A version-0 database exactly as the previous release left it, with user data.
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript(db_manager._SCHEMA)
            conn.executemany("INSERT INTO dime_trades (timestamp, account_type, symbol, trade_type, shares, price) "
                             "VALUES (?, ?, ?, ?, ?, ?)",
                             [("2026-01-02 10:00:00", "Dime US", "AAPL", "Buy", 2, 150),
                              ("2026-01-03 10:00:00", "Dime TH", "PTT", "Buy", 100, 33)])
            conn.execute("INSERT INTO dime_dividends (date, account_type, symbol, amount) "
                         "VALUES ('2026-02-01', 'Dime US', 'AAPL', 0.5)")
            conn.execute("INSERT INTO webull_summary (id, total_value, market_value, cash, cost_basis, open_pnl, "
                         "open_pnl_pct, positions, last_synced) VALUES (1, 1, 1, 0, 1, 0, 0, 1, "
                         "'2026-11-12T01:27:00+00:00')")
            conn.execute("INSERT INTO webull_positions (symbol, quantity, avg_cost, last_price, currency) "
                         "VALUES ('AAPL', 1, 1, 1, 'USD')")
            conn.execute("INSERT INTO webull_orders (order_id, symbol) VALUES ('O-1', 'AAPL')")
        self.before = db_manager.row_counts(self.db)

    def tearDown(self):
        db_manager._migrated.clear()
        self.tmp.cleanup()

    def backups(self):
        return sorted(db_manager.backup_dir(self.db).glob("*.db"))

    def test_init_db_backs_up_then_migrates_without_losing_rows(self):
        self.assertEqual(db_manager.schema_version(self.db), 0)
        db_manager.init_db(self.db)
        self.assertEqual(db_manager.schema_version(self.db), db_manager.SCHEMA_VERSION)
        self.assertEqual({k: v for k, v in db_manager.row_counts(self.db).items()}, self.before)
        self.assertTrue(set(db_manager.WEBULL_CURRENCY_FIELDS) <= columns(self.db, "webull_summary"))
        self.assertIn("fx_to_usd", columns(self.db, "webull_positions"))
        [backup] = self.backups()
        self.assertIn("pre-migrate-v0-to-v1", backup.name)
        self.assertEqual(db_manager.schema_version(backup), 0)
        self.assertEqual(db_manager.row_counts(backup), self.before)
        # Re-running is a no-op: no second backup.
        db_manager._migrated.clear()
        self.assertIsNone(db_manager.migrate(self.db)["backup"])
        self.assertEqual(len(self.backups()), 1)

    def test_migrated_legacy_data_is_still_readable(self):
        with patch.object(db_manager, "DB_PATH", self.db):
            data = webull_data.get_portfolio()
            self.assertTrue(data["legacy"])
            self.assertEqual(len(db_manager.fetch_trades()), 2)
            self.assertEqual(len(db_manager.fetch_dividends()), 1)
            self.assertEqual(len(webull_data.get_order_history()["orders"]), 1)

    def test_rollback_keeps_data_and_restore_returns_exact_copy(self):
        def dump(table):
            with closing(sqlite3.connect(self.db)) as conn:
                return sorted(conn.execute(f"SELECT * FROM {table}").fetchall())

        before = {t: dump(t) for t in self.before}
        v0_columns = {t: columns(self.db, t) for t in self.before}
        db_manager.init_db(self.db)
        result = db_manager.rollback(0, self.db)
        self.assertEqual((result["from_version"], result["to_version"]), (1, 0))
        self.assertTrue(result["backup"].exists())
        self.assertEqual({t: columns(self.db, t) for t in self.before}, v0_columns)
        self.assertNotIn("webull_sync_log", db_manager.row_counts(self.db))
        self.assertEqual(db_manager.row_counts(self.db), self.before)
        self.assertEqual({t: dump(t) for t in self.before}, before)

        db_manager.migrate(self.db)
        pre_migrate = next(b for b in self.backups() if "pre-migrate" in b.name)
        restored = db_manager.restore(pre_migrate, self.db)
        self.assertTrue(restored["backup"].exists())  # current DB saved before being replaced
        self.assertEqual(db_manager.schema_version(self.db), 0)
        self.assertEqual(db_manager.row_counts(self.db), self.before)

    def test_failed_migration_is_atomic(self):
        bad = [(1, "broken", ["ALTER TABLE webull_summary ADD COLUMN fx_rate REAL", "THIS IS NOT SQL"], [])]
        with patch.object(db_manager, "MIGRATIONS", bad):
            with self.assertRaises(sqlite3.OperationalError):
                db_manager.migrate(self.db, target=1)
        self.assertEqual(db_manager.schema_version(self.db), 0)
        self.assertNotIn("fx_rate", columns(self.db, "webull_summary"))
        self.assertEqual(db_manager.row_counts(self.db), self.before)

    def test_concurrent_migration_runs_once(self):
        db_manager.migrate(self.db)
        # A second process that read version 0 before the first one committed must not re-apply.
        steps = [(v, up) for v, _, up, _ in db_manager.MIGRATIONS]
        self.assertIsNone(db_manager._apply(self.db, steps, db_manager.SCHEMA_VERSION, 0))
        self.assertEqual(db_manager.schema_version(self.db), db_manager.SCHEMA_VERSION)

    def dump_all(self, db):
        with closing(sqlite3.connect(db)) as conn:
            return {t: sorted(conn.execute(f"SELECT * FROM {t}").fetchall()) for t in self.before}

    def test_backup_bytes_is_complete_verified_and_read_only(self):
        db_manager.init_db(self.db)
        source_bytes = Path(self.db).read_bytes()
        expected = self.dump_all(self.db)
        # A writer holds an open transaction while the backup runs: only committed data is copied.
        writer = sqlite3.connect(self.db, isolation_level=None)
        writer.execute("BEGIN IMMEDIATE")
        writer.execute("INSERT INTO dime_dividends (date, account_type, symbol, amount) "
                       "VALUES ('2026-03-01', 'Dime US', 'AAPL', 9.9)")
        try:
            data = db_manager.backup_bytes(self.db)
        finally:
            writer.execute("ROLLBACK")
            writer.close()
        self.assertEqual(Path(self.db).read_bytes(), source_bytes)  # source untouched
        self.assertTrue(data.startswith(b"SQLite format 3\x00"))
        copy = Path(self.tmp.name) / "downloaded.db"
        copy.write_bytes(data)
        info = db_manager.inspect_db(copy)
        self.assertEqual(info["integrity"], "ok")
        self.assertEqual(info["schema_version"], db_manager.SCHEMA_VERSION)
        self.assertEqual(set(info["tables"]), set(db_manager.inspect_db(self.db)["tables"]))
        self.assertEqual(self.dump_all(copy), expected)

        # Restore the downloaded file into a separate temporary database.
        target = str(Path(self.tmp.name) / "restored" / "portfolio.db")
        Path(target).parent.mkdir()
        result = db_manager.restore(copy, target)
        self.assertIsNone(result["backup"])  # nothing existed there to protect
        self.assertEqual(result["restored"]["integrity"], "ok")
        self.assertEqual(self.dump_all(target), expected)
        self.assertEqual(Path(self.db).read_bytes(), source_bytes)

    def test_backup_of_missing_db_does_not_create_it(self):
        missing = Path(self.tmp.name) / "nope.db"
        with self.assertRaises(sqlite3.OperationalError):
            db_manager.backup_bytes(missing)
        self.assertFalse(missing.exists())

    def test_restore_rejects_corrupt_backup(self):
        bad = Path(self.tmp.name) / "bad.db"
        bad.write_bytes(b"not a database" * 100)
        before = Path(self.db).read_bytes()
        with self.assertRaises(sqlite3.DatabaseError):
            db_manager.restore(bad, self.db)
        self.assertEqual(Path(self.db).read_bytes(), before)

    def test_pre_migration_backup_is_listed_and_downloadable(self):
        db_manager.init_db(self.db)
        [backup] = db_manager.pre_migration_backups(self.db)
        copy = Path(self.tmp.name) / "pre.db"
        copy.write_bytes(db_manager.backup_bytes(source=backup))
        self.assertEqual(db_manager.inspect_db(copy)["schema_version"], 0)
        self.assertEqual(db_manager.row_counts(copy), self.before)

    def test_migration_reports_and_enforces_unchanged_data(self):
        result = db_manager.migrate(self.db)
        self.assertEqual(result["data_check"]["dime_trades"], {"rows_before": 2, "rows_after": 2})
        self.assertEqual(set(result["data_check"]), set(self.before))
        rb = db_manager.rollback(0, self.db)
        self.assertEqual(rb["data_check"]["webull_positions"], {"rows_before": 1, "rows_after": 1})

    def test_migration_that_changes_data_is_rolled_back(self):
        expected = self.dump_all(self.db)
        for bad_sql in ("DELETE FROM dime_dividends", "UPDATE dime_trades SET price = price + 1"):
            bad = [(1, "bad", ["ALTER TABLE webull_summary ADD COLUMN fx_rate REAL", bad_sql], [])]
            with patch.object(db_manager, "MIGRATIONS", bad), self.assertRaises(db_manager.DataCheckError):
                db_manager.migrate(self.db, target=1)
            self.assertEqual(db_manager.schema_version(self.db), 0)
            self.assertNotIn("fx_rate", columns(self.db, "webull_summary"))
            self.assertEqual(self.dump_all(self.db), expected)

    def test_sidebar_backup_panel_renders(self):
        from streamlit.testing.v1 import AppTest

        with patch.object(db_manager, "DB_PATH", self.db):
            app = AppTest.from_file("../app.py").run(timeout=30)
        self.assertEqual(len(app.exception), 0, [e.value for e in app.exception])
        panel = " ".join(c.value for c in app.sidebar.caption)
        self.assertIn(f"Schema v{db_manager.SCHEMA_VERSION}", panel)
        self.assertIn("integrity ok", panel)
        self.assertIn("dime_trades 2", panel)

    def test_migrations_use_only_sqlite_334_compatible_sql(self):
        # Streamlit Community Cloud has shipped SQLite 3.34.1; DROP COLUMN / RENAME COLUMN need newer versions.
        for version, name, up, down in db_manager.MIGRATIONS:
            for sql in up + down:
                self.assertNotRegex(sql.upper(), r"DROP\s+COLUMN|RENAME\s+COLUMN", f"v{version} {name}: {sql}")

    def test_db_tool_cli(self):
        with patch("builtins.print") as out:
            db_tool.main(["--db", self.db, "status"])
            self.assertIn('"schema_version": 0', out.call_args[0][0])
            db_tool.main(["--db", self.db, "backup"])
            db_tool.main(["--db", self.db, "migrate"])
        self.assertEqual(db_manager.schema_version(self.db), db_manager.SCHEMA_VERSION)
        self.assertEqual(len(self.backups()), 2)


if __name__ == "__main__":
    unittest.main()

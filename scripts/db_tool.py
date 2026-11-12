"""portfolio.db maintenance: status / backup / migrate / rollback / restore.

Every command that changes the schema or replaces the file writes a backup to backups/ first.
Usage (from the repo root):
    python scripts/db_tool.py status
    python scripts/db_tool.py backup
    python scripts/db_tool.py migrate
    python scripts/db_tool.py rollback 0
    python scripts/db_tool.py restore backups/portfolio-....db
Set PORTFOLIO_DB_PATH or pass --db to work on another file.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import db_manager  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", help="database path (default: PORTFOLIO_DB_PATH or ./portfolio.db)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("backup")
    sub.add_parser("migrate")
    rb = sub.add_parser("rollback")
    rb.add_argument("target", type=int)
    rs = sub.add_parser("restore")
    rs.add_argument("backup")
    args = parser.parse_args(argv)
    db = args.db

    if args.cmd != "restore" and not db_manager._path(db).exists():
        parser.error(f"database not found: {db_manager._path(db)}")
    if args.cmd == "status":
        result = {"db": str(db_manager._path(db)), "sqlite_runtime": db_manager.sqlite3.sqlite_version,
                  "schema_version": db_manager.schema_version(db),
                  "latest_version": db_manager.SCHEMA_VERSION, "row_counts": db_manager.row_counts(db)}
    elif args.cmd == "backup":
        result = {"backup": db_manager.backup_db("manual", db)}
    elif args.cmd == "migrate":
        result = db_manager.migrate(db)
    elif args.cmd == "rollback":
        result = db_manager.rollback(args.target, db)
    else:
        result = db_manager.restore(args.backup, db)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

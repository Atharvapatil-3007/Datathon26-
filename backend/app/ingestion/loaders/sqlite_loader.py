"""SQLite loader.

* Lists all user tables from `sqlite_master`
* Loads one selected table (default: first user table by row count)
* Delegates identifier quoting to SQLAlchemy's SQLite dialect so we get
  dialect-correct escape rules instead of hand-rolled string surgery.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy.dialects.sqlite import dialect as _sqlite_dialect

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import CorruptedFileError, FileParsingError, InvalidDatasetError


# One preparer instance is enough \u2014 it is stateless.
_SQLITE_PREPARER = _sqlite_dialect().identifier_preparer


def _quote_ident(name: str) -> str:
    """Return a fully-quoted SQLite identifier ready to splice into a statement."""
    return _SQLITE_PREPARER.quote(name)


class SQLiteLoader(DataLoader):
    name = "SQLiteLoader"
    supported_formats = frozenset({FileFormat.SQLITE})

    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        options = options or {}
        p = Path(source)

        try:
            conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise CorruptedFileError(f"Could not open SQLite database: {exc}") from exc

        try:
            tables = _list_tables(conn)
            if not tables:
                raise InvalidDatasetError("SQLite database has no user tables")

            requested = options.get("table_name")
            if requested is not None:
                if requested not in tables:
                    raise InvalidDatasetError(
                        f"Table '{requested}' not found",
                        details={"available_tables": tables},
                    )
                target = requested
            else:
                target = _pick_largest_table(conn, tables)

            df = _read_table(conn, target)
            df.columns = [str(c) for c in df.columns]
        finally:
            conn.close()

        dataset.data = df
        dataset.metadata.update(
            {
                "engine": "sqlite3",
                "tables": tables,
                "selected_table": target,
                "table_count": len(tables),
            }
        )
        if len(tables) > 1 and requested is None:
            dataset.add_warning(
                f"Database has {len(tables)} user tables; loaded '{target}'. "
                "Re-upload with `table_name` to select another."
            )
        return dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _list_tables(conn: sqlite3.Connection) -> List[str]:
    cur = conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "ORDER BY name"
    )
    return [row[0] for row in cur.fetchall()]


def _pick_largest_table(conn: sqlite3.Connection, tables: List[str]) -> str:
    best_table = tables[0]
    best_count = -1
    for t in tables:
        try:
            # SQLite doesn't support parameter binding for identifiers; use
            # the dialect preparer for correct dialect-aware quoting.
            cur = conn.execute(f"SELECT COUNT(*) FROM {_quote_ident(t)}")
            count = int(cur.fetchone()[0])
        except sqlite3.Error:
            count = 0
        if count > best_count:
            best_count = count
            best_table = t
    return best_table


def _read_table(conn: sqlite3.Connection, table: str) -> pd.DataFrame:
    try:
        return pd.read_sql_query(f"SELECT * FROM {_quote_ident(table)}", conn)
    except Exception as exc:  # noqa: BLE001
        raise FileParsingError(f"Failed to read table '{table}': {exc}") from exc

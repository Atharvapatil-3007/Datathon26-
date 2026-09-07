"""External SQL database loader (PostgreSQL, MySQL, SQL Server, Oracle, SQLite).

Uses SQLAlchemy as the common abstraction so any dialect installed alongside
this backend can be targeted without changing loader code. Callers pass a
`connection_string` (or a preconfigured SQLAlchemy `Engine`) via `options`.

This loader is deliberately NOT used through the file-upload pipeline —
the manager exposes a dedicated `ingest_sql()` entry point in Phase 1. The
class is registered for `FileFormat.SQL` so future .sql-connector files can
plug in without changing the detector contract.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat, SourceType
from app.ingestion.exceptions import (
    DatabaseConnectionError,
    FileParsingError,
    InvalidDatasetError,
)


class SQLLoader(DataLoader):
    """SQLAlchemy-backed loader for external SQL databases."""

    name = "SQLLoader"
    supported_formats = frozenset({FileFormat.SQL})

    def load(
        self,
        source: LoadSource,  # unused for SQL — kept for interface parity
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        options = options or {}
        conn_str: Optional[str] = options.get("connection_string")
        query: Optional[str] = options.get("query")
        table_name: Optional[str] = options.get("table_name")
        row_limit: Optional[int] = options.get("row_limit")

        if not conn_str:
            raise InvalidDatasetError("SQL ingestion requires a `connection_string`")
        if not query and not table_name:
            raise InvalidDatasetError("Provide either `query` or `table_name`")

        try:
            from sqlalchemy import create_engine, inspect, text
        except ImportError as exc:  # pragma: no cover
            raise DatabaseConnectionError(
                "SQLAlchemy is not installed"
            ) from exc

        try:
            engine = create_engine(conn_str, pool_pre_ping=True)
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(
                f"Failed to build SQL engine: {_sanitize(exc)}"
            ) from exc

        try:
            with engine.connect() as conn:
                if query:
                    stmt = text(query if row_limit is None else _wrap_limit(query, row_limit))
                    df = pd.read_sql_query(stmt, conn)
                    tables = _safe_inspect_tables(engine)
                    selected = None
                else:
                    tables = _safe_inspect_tables(engine)
                    if table_name not in tables:
                        raise InvalidDatasetError(
                            f"Table '{table_name}' not found on server",
                            details={"available_tables": tables[:50]},
                        )
                    limit_clause = f" LIMIT {int(row_limit)}" if row_limit else ""
                    stmt = text(f'SELECT * FROM "{_escape(table_name)}"{limit_clause}')
                    df = pd.read_sql_query(stmt, conn)
                    selected = table_name
        except InvalidDatasetError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(
                f"SQL query failed: {_sanitize(exc)}"
            ) from exc
        finally:
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001
                pass

        df.columns = [str(c) for c in df.columns]
        dataset.data = df
        dataset.source_type = SourceType.SQL_DATABASE
        dataset.format = FileFormat.SQL
        dataset.metadata.update(
            {
                "engine": "sqlalchemy",
                "dialect": engine.dialect.name if hasattr(engine, "dialect") else "unknown",
                "tables_visible": tables[:50],
                "selected_table": selected,
                "query_supplied": bool(query),
                "row_limit": row_limit,
            }
        )
        return dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_inspect_tables(engine) -> List[str]:
    try:
        from sqlalchemy import inspect
        return sorted(inspect(engine).get_table_names())
    except Exception:  # noqa: BLE001
        return []


def _wrap_limit(query: str, limit: int) -> str:
    q = query.strip().rstrip(";")
    return f"SELECT * FROM ({q}) AS _sub LIMIT {int(limit)}"


def _escape(name: str) -> str:
    return name.replace('"', '""')


def _sanitize(exc: Exception) -> str:
    """Remove connection strings / credentials that some drivers leak into errors."""
    msg = str(exc)
    for token in ("password=", "pwd=", "@"):
        if token in msg:
            msg = msg.split(token, 1)[0] + "***"
            break
    return msg[:500]

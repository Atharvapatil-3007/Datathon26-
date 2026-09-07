"""JSONL / NDJSON loader.

One JSON object per line. Uses pandas' native reader for speed and falls
back to a per-line parse only if that fails, so we can report the exact
offending line number.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError

try:
    import orjson as _json_lib  # noqa: WPS433

    def _loads(s: str) -> Any:
        return _json_lib.loads(s)

except ImportError:  # pragma: no cover
    import json as _json_lib  # type: ignore

    def _loads(s: str) -> Any:
        return _json_lib.loads(s)


class JSONLLoader(DataLoader):
    name = "JSONLLoader"
    supported_formats = frozenset({FileFormat.JSONL})

    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        p = Path(source)
        try:
            df = pd.read_json(p, lines=True, dtype=False)
        except ValueError:
            # Slow-path per-line parse to surface a precise line number.
            df, bad_lines = _parse_line_by_line(p)
            if bad_lines:
                dataset.add_warning(
                    f"Skipped {len(bad_lines)} invalid JSONL line(s); first bad line: {bad_lines[0]}"
                )
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(f"Failed to read JSONL: {exc}") from exc

        # If nested keys survived, flatten (pandas.read_json keeps dicts as-is)
        if any(df.dtypes == "object") and _contains_dict(df):
            try:
                df = pd.json_normalize(df.to_dict(orient="records"), sep=".")
            except Exception:  # noqa: BLE001
                pass

        df.columns = [str(c) for c in df.columns]

        dataset.data = df
        dataset.metadata.update(
            {
                "parser": "pandas.read_json(lines=True)",
                "flattened": any("." in c for c in df.columns),
            }
        )
        return dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_line_by_line(p: Path) -> tuple[pd.DataFrame, list[int]]:
    records: list[dict] = []
    bad: list[int] = []
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = _loads(line)
            except Exception:  # noqa: BLE001
                bad.append(lineno)
                continue
            if isinstance(obj, dict):
                records.append(obj)
            else:
                records.append({"value": obj})
    if not records and bad:
        raise FileParsingError(
            "JSONL file contains no parseable objects",
            details={"bad_line_count": len(bad)},
        )
    return pd.DataFrame(records), bad


def _contains_dict(df: pd.DataFrame) -> bool:
    for col in df.columns:
        if df[col].dtype == "object":
            sample = df[col].dropna().head(10)
            if any(isinstance(v, dict) for v in sample):
                return True
    return False

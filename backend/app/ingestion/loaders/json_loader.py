"""JSON loader.

Handles three shapes:

1. Array of objects           -> straight DataFrame
2. Single object              -> single-row DataFrame  (or unwrapped array-under-a-key)
3. Nested JSON                -> flattened via pandas.json_normalize(sep='.')

For streaming line-delimited JSON, see `JSONLLoader`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError

try:
    import orjson as _json_lib  # noqa: WPS433
    _ORJSON = True

    def _loads(data: bytes) -> Any:
        return _json_lib.loads(data)

except ImportError:  # pragma: no cover
    import json as _json_lib  # type: ignore
    _ORJSON = False

    def _loads(data: bytes) -> Any:
        return _json_lib.loads(data.decode("utf-8"))


_MAX_ARRAY_UNWRAP_KEYS = 20


class JSONLoader(DataLoader):
    name = "JSONLoader"
    supported_formats = frozenset({FileFormat.JSON})

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
            with open(p, "rb") as f:
                raw = f.read()
        except OSError as exc:
            raise FileParsingError(f"Could not read JSON file: {exc}") from exc

        try:
            payload = _loads(raw)
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(f"Invalid JSON document: {exc}") from exc

        records, shape, unwrap_key = _extract_records(payload)

        try:
            df = pd.json_normalize(records, sep=".") if records else pd.DataFrame()
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(f"Failed to normalize JSON: {exc}") from exc

        df.columns = [str(c) for c in df.columns]

        dataset.data = df
        dataset.metadata.update(
            {
                "parser": "orjson" if _ORJSON else "json",
                "json_shape": shape,
                "unwrap_key": unwrap_key,
                "flattened": any("." in c for c in df.columns),
            }
        )
        return dataset


# ---------------------------------------------------------------------------
# Payload -> list-of-records extraction
# ---------------------------------------------------------------------------
def _extract_records(payload: Any) -> tuple[List[dict], str, Optional[str]]:
    """Return (records, shape_label, unwrap_key)."""
    if isinstance(payload, list):
        if not payload:
            return [], "empty_array", None
        if all(isinstance(x, dict) for x in payload):
            return payload, "array_of_objects", None
        # Array of scalars — represent as a single "value" column
        return [{"value": x} for x in payload], "array_of_scalars", None

    if isinstance(payload, dict):
        # Look for a single obvious "list of records" value
        list_keys = [
            k for k, v in payload.items()
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v)
        ]
        if len(list_keys) == 1 and len(payload) <= _MAX_ARRAY_UNWRAP_KEYS:
            key = list_keys[0]
            return payload[key], "object_wrapping_array", key
        # Otherwise treat as a single record
        return [payload], "single_object", None

    # Scalar top-level JSON — one row, one column
    return [{"value": payload}], "scalar", None

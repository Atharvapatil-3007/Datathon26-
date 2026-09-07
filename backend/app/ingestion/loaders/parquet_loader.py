"""Parquet loader.

Uses PyArrow for schema + efficient columnar reads. Converts to pandas at
the loader boundary so the rest of the pipeline stays uniform.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import pyarrow.parquet as pq

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import CorruptedFileError, FileParsingError


class ParquetLoader(DataLoader):
    name = "ParquetLoader"
    supported_formats = frozenset({FileFormat.PARQUET})

    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        options = options or {}
        p = Path(source)
        columns = options.get("columns")

        try:
            pf = pq.ParquetFile(p)
        except Exception as exc:  # noqa: BLE001
            raise CorruptedFileError(f"Not a valid Parquet file: {exc}") from exc

        try:
            table = pf.read(columns=columns) if columns else pf.read()
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(f"Failed to read Parquet data: {exc}") from exc

        df = table.to_pandas(types_mapper=pd.ArrowDtype)

        # ArrowDtype produces nicer null handling but is still relatively new;
        # fall back to object/numeric for downstream stability.
        try:
            df = df.convert_dtypes(dtype_backend="numpy_nullable")
        except Exception:  # noqa: BLE001
            pass

        df.columns = [str(c) for c in df.columns]

        dataset.data = df

        try:
            schema = pf.schema_arrow
            arrow_schema = [
                {"name": f.name, "arrow_type": str(f.type), "nullable": f.nullable}
                for f in schema
            ]
        except Exception:  # noqa: BLE001
            arrow_schema = []

        dataset.metadata.update(
            {
                "engine": "pyarrow",
                "num_row_groups": pf.num_row_groups,
                "arrow_schema": arrow_schema,
            }
        )
        return dataset

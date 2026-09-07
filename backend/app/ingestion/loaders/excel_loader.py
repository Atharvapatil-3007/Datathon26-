"""Excel loader (.xlsx / .xls).

* Lists all sheets in metadata
* Loads the requested sheet (default: first non-empty)
* Uses openpyxl for xlsx and xlrd for legacy xls
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError


class ExcelLoader(DataLoader):
    """Loader for XLSX and XLS workbooks."""

    name = "ExcelLoader"
    supported_formats = frozenset({FileFormat.EXCEL_XLSX, FileFormat.EXCEL_XLS})

    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        options = options or {}
        p = Path(source)
        engine = "openpyxl" if dataset.format == FileFormat.EXCEL_XLSX else "xlrd"

        try:
            book = pd.ExcelFile(p, engine=engine)
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(
                f"Could not open Excel workbook: {exc}",
                details={"engine": engine},
            ) from exc

        sheet_names = list(book.sheet_names)
        if not sheet_names:
            raise FileParsingError("Excel workbook contains no sheets")

        # Choose sheet: explicit -> first sheet
        requested_sheet = options.get("sheet_name")
        if requested_sheet is not None and requested_sheet not in sheet_names:
            raise FileParsingError(
                f"Sheet '{requested_sheet}' not found in workbook",
                details={"available_sheets": sheet_names},
            )
        target_sheet = requested_sheet if requested_sheet is not None else sheet_names[0]

        try:
            df = book.parse(sheet_name=target_sheet)
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(f"Failed to parse sheet '{target_sheet}': {exc}") from exc
        finally:
            book.close()

        df.columns = [str(c).strip() for c in df.columns]

        dataset.data = df
        dataset.metadata.update(
            {
                "engine": engine,
                "sheet_names": sheet_names,
                "selected_sheet": target_sheet,
                "sheet_count": len(sheet_names),
            }
        )
        if len(sheet_names) > 1 and requested_sheet is None:
            dataset.add_warning(
                f"Workbook has {len(sheet_names)} sheets; loaded the first one ('{target_sheet}')"
            )
        return dataset

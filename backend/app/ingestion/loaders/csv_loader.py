"""CSV / TSV loader.

Handles:

* `,` / `;` / `\t` / `|` delimiters (via csv.Sniffer + explicit override)
* Common encodings (utf-8, utf-8-sig, latin-1) with chardet fallback
* Optional header detection
* Large files — reads with pandas' C engine and low_memory=False
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError

try:
    import chardet  # noqa: WPS433
    _CHARDET_AVAILABLE = True
except ImportError:  # pragma: no cover
    _CHARDET_AVAILABLE = False


_DELIMITER_CANDIDATES = [",", "\t", ";", "|"]
_ENCODING_CANDIDATES = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
_HEADER_SNIFF_ROWS = 20


class CSVLoader(DataLoader):
    """Loader for CSV / TSV files."""

    name = "CSVLoader"
    supported_formats = frozenset({FileFormat.CSV, FileFormat.TSV})

    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        options = options or {}
        p = Path(source)

        # Encoding + delimiter detection (cheap peek)
        encoding = options.get("encoding") or _detect_encoding(p)
        delimiter = options.get("delimiter") or _detect_delimiter(p, encoding, dataset.format)
        has_header = options.get("has_header")
        if has_header is None:
            has_header = _detect_header(p, encoding, delimiter)

        try:
            df = pd.read_csv(
                p,
                sep=delimiter,
                encoding=encoding,
                header=0 if has_header else None,
                low_memory=False,
                on_bad_lines="warn",
                skip_blank_lines=True,
                engine="c",
            )
        except UnicodeDecodeError as exc:
            raise FileParsingError(
                "CSV file has an unrecognized encoding",
                details={"encoding_tried": encoding, "reason": str(exc)},
            ) from exc
        except pd.errors.EmptyDataError as exc:
            raise FileParsingError("CSV file has no data") from exc
        except pd.errors.ParserError as exc:
            raise FileParsingError(f"Failed to parse CSV: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise FileParsingError(f"Unexpected CSV parse failure: {exc}") from exc

        if not has_header:
            df.columns = [f"col_{i}" for i in range(len(df.columns))]

        # Normalize obviously-noisy column names
        df.columns = [str(c).strip() for c in df.columns]

        dataset.data = df
        dataset.metadata.update(
            {
                "encoding": encoding,
                "delimiter": _describe_delimiter(delimiter),
                "has_header": bool(has_header),
                "engine": "pandas.read_csv (c)",
            }
        )
        return dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _detect_encoding(p: Path) -> str:
    if not _CHARDET_AVAILABLE:
        return "utf-8"
    with open(p, "rb") as f:
        sample = f.read(64 * 1024)
    if not sample:
        return "utf-8"
    guess = chardet.detect(sample) or {}
    enc = (guess.get("encoding") or "utf-8").lower()
    # Normalize some chardet quirks
    if enc in ("ascii",):
        return "utf-8"
    return enc


def _detect_delimiter(p: Path, encoding: str, fmt: FileFormat) -> str:
    if fmt == FileFormat.TSV:
        return "\t"
    try:
        with open(p, "r", encoding=encoding, errors="replace") as f:
            sample = f.read(64 * 1024)
    except OSError as exc:
        raise FileParsingError(f"Could not read CSV sample: {exc}") from exc

    if not sample:
        return ","

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters="".join(_DELIMITER_CANDIDATES))
        return dialect.delimiter
    except csv.Error:
        # Fall back to a frequency count on the first non-empty line
        first_line = next((ln for ln in sample.splitlines() if ln.strip()), "")
        counts = {d: first_line.count(d) for d in _DELIMITER_CANDIDATES}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ","


def _detect_header(p: Path, encoding: str, delimiter: str) -> bool:
    try:
        with open(p, "r", encoding=encoding, errors="replace") as f:
            sample = "".join([next(f, "") for _ in range(_HEADER_SNIFF_ROWS)])
    except OSError:
        return True
    if not sample.strip():
        return True
    try:
        return csv.Sniffer().has_header(sample)
    except csv.Error:
        return True  # assume header — safer for downstream schema inference


def _describe_delimiter(d: str) -> str:
    return {",": "comma", "\t": "tab", ";": "semicolon", "|": "pipe"}.get(d, d)

"""Format detection.

The detector never trusts the filename alone. It combines:

1. File extension  (fast, but spoofable)
2. MIME type       (from `mimetypes` stdlib, best-effort)
3. Magic bytes     (authoritative for binary formats)
4. Content sniff   (peek into ZIP/JSON/CSV to disambiguate)

Result is a `DetectionResult` naming the concrete `FileFormat` and the
loader class that should handle it.
"""

from __future__ import annotations

import io
import json
import mimetypes
import os
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Type

from app.ingestion.base import DataLoader
from app.ingestion.dataset import FileFormat
from app.ingestion.exceptions import UnsupportedFileTypeError


# ---------------------------------------------------------------------------
# Extension → format lookup
# ---------------------------------------------------------------------------
_EXT_TO_FORMAT: dict[str, FileFormat] = {
    ".csv": FileFormat.CSV,
    ".tsv": FileFormat.TSV,
    ".txt": FileFormat.CSV,          # treat plain .txt as CSV candidate; sniffed
    ".xlsx": FileFormat.EXCEL_XLSX,
    ".xlsm": FileFormat.EXCEL_XLSX,
    ".xls": FileFormat.EXCEL_XLS,
    ".json": FileFormat.JSON,
    ".jsonl": FileFormat.JSONL,
    ".ndjson": FileFormat.JSONL,
    ".parquet": FileFormat.PARQUET,
    ".pq": FileFormat.PARQUET,
    ".db": FileFormat.SQLITE,
    ".sqlite": FileFormat.SQLITE,
    ".sqlite3": FileFormat.SQLITE,
    ".zip": FileFormat.ZIP,
}

# ---------------------------------------------------------------------------
# Magic byte signatures
# ---------------------------------------------------------------------------
_ZIP_MAGIC = b"PK\x03\x04"
_XLS_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # OLE compound file
_PARQUET_MAGIC = b"PAR1"
_SQLITE_MAGIC = b"SQLite format 3\x00"


@dataclass
class DetectionResult:
    format: FileFormat
    mime_type: str
    size_bytes: int
    loader_name: str
    loader_cls: Type[DataLoader]
    extension: str
    reason: str  # human-readable why we chose this format

    def to_dict(self) -> dict:
        return {
            "format": self.format.value,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "loader": self.loader_name,
            "extension": self.extension,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_format(path: str | Path, *, filename_hint: Optional[str] = None) -> DetectionResult:
    """Detect the concrete format of the file at `path`.

    `filename_hint` is used to recover the original extension when `path`
    points to a temp file with a randomized name.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise UnsupportedFileTypeError(f"File does not exist or is not a regular file: {p}")

    size = p.stat().st_size
    ext = _pick_extension(p, filename_hint)
    mime = _guess_mime(filename_hint or p.name)

    # Read a small header for magic-byte sniff.
    header = _read_header(p, 4096)

    fmt, reason = _decide_format(p, header, ext)
    loader_cls = _resolve_loader(fmt)

    return DetectionResult(
        format=fmt,
        mime_type=mime,
        size_bytes=size,
        loader_name=loader_cls.__name__,
        loader_cls=loader_cls,
        extension=ext,
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Format decision
# ---------------------------------------------------------------------------
def _decide_format(p: Path, header: bytes, ext: str) -> Tuple[FileFormat, str]:
    # 1. SQLite (very specific magic)
    if header.startswith(_SQLITE_MAGIC):
        return FileFormat.SQLITE, "magic bytes match SQLite header"

    # 2. Parquet (magic at start; also present at end)
    if header.startswith(_PARQUET_MAGIC) or _has_parquet_footer(p):
        return FileFormat.PARQUET, "PAR1 magic footer detected"

    # 3. OLE-based XLS
    if header.startswith(_XLS_MAGIC):
        return FileFormat.EXCEL_XLS, "OLE compound-file signature (XLS)"

    # 4. ZIP / XLSX / possibly other zipped datasets
    if header.startswith(_ZIP_MAGIC):
        if _is_xlsx_zip(p):
            return FileFormat.EXCEL_XLSX, "ZIP container with XLSX signature"
        if ext == ".xlsx":
            # Heuristic fallback if the archive is unusual.
            return FileFormat.EXCEL_XLSX, "ZIP + .xlsx extension"
        return FileFormat.ZIP, "ZIP container"

    # 5. Content-based sniff for text formats
    text_sniff = _sniff_text_format(header, ext)
    if text_sniff is not None:
        return text_sniff

    # 6. Fallback to extension mapping
    if ext in _EXT_TO_FORMAT:
        return _EXT_TO_FORMAT[ext], f"extension mapping ({ext})"

    raise UnsupportedFileTypeError(
        f"Could not determine a supported format for '{p.name}'",
        details={"extension": ext, "size_bytes": p.stat().st_size},
    )


# ---------------------------------------------------------------------------
# Sniffs
# ---------------------------------------------------------------------------
def _sniff_text_format(header: bytes, ext: str) -> Optional[Tuple[FileFormat, str]]:
    try:
        text = header.decode("utf-8", errors="ignore").lstrip("\ufeff").strip()
    except Exception:
        return None
    if not text:
        return None

    first_char = text[0]

    # JSON / JSONL
    if first_char in "{[":
        # Try to detect JSONL: multiple JSON objects separated by newlines
        if ext in (".jsonl", ".ndjson"):
            return FileFormat.JSONL, f"extension {ext}"
        if _looks_like_jsonl(text):
            return FileFormat.JSONL, "multiple line-delimited JSON objects detected"
        if _looks_like_json(text):
            return FileFormat.JSON, "text starts with JSON structure"

    # CSV / TSV — accept if the first line has delimiters
    if "\t" in text.splitlines()[0] and ext != ".csv":
        return FileFormat.TSV, "tab-delimited first line"
    if ext in (".csv", ".tsv", ".txt") and ("," in text or ";" in text or "\t" in text):
        return (FileFormat.TSV if "\t" in text and "," not in text else FileFormat.CSV), (
            f"delimited text, extension {ext}"
        )
    return None


def _looks_like_json(text: str) -> bool:
    try:
        json.loads(text if text.endswith(("}", "]")) else text + ("}" if text[0] == "{" else "]"))
        return True
    except Exception:
        # Full-text parse may fail on a truncated header; a starting brace/bracket is still a strong hint.
        return text[0] in "{["


def _looks_like_jsonl(text: str) -> bool:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return False
    parsed = 0
    for ln in lines[:5]:
        try:
            json.loads(ln)
            parsed += 1
        except Exception:
            return False
    return parsed >= 2


def _is_xlsx_zip(p: Path) -> bool:
    """Peek inside a ZIP to see if it looks like an OOXML workbook."""
    try:
        with zipfile.ZipFile(p) as zf:
            names = set(zf.namelist())
        return "[Content_Types].xml" in names and any(n.startswith("xl/") for n in names)
    except (zipfile.BadZipFile, OSError):
        return False


def _has_parquet_footer(p: Path) -> bool:
    try:
        if p.stat().st_size < 8:
            return False
        with open(p, "rb") as f:
            f.seek(-4, os.SEEK_END)
            return f.read(4) == _PARQUET_MAGIC
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_header(p: Path, n: int) -> bytes:
    try:
        with open(p, "rb") as f:
            return f.read(n)
    except OSError:
        return b""


def _pick_extension(p: Path, filename_hint: Optional[str]) -> str:
    if filename_hint:
        ext = Path(filename_hint).suffix.lower()
        if ext:
            return ext
    return p.suffix.lower()


def _guess_mime(name: str) -> str:
    mime, _ = mimetypes.guess_type(name)
    return mime or "application/octet-stream"


def _resolve_loader(fmt: FileFormat) -> Type[DataLoader]:
    """Late-imported loader registry (avoids circular imports at module load)."""
    from app.ingestion.loaders import (
        CSVLoader,
        ExcelLoader,
        JSONLoader,
        JSONLLoader,
        ParquetLoader,
        SQLiteLoader,
        SQLLoader,
        ZIPLoader,
    )

    registry: dict[FileFormat, Type[DataLoader]] = {
        FileFormat.CSV: CSVLoader,
        FileFormat.TSV: CSVLoader,
        FileFormat.EXCEL_XLSX: ExcelLoader,
        FileFormat.EXCEL_XLS: ExcelLoader,
        FileFormat.JSON: JSONLoader,
        FileFormat.JSONL: JSONLLoader,
        FileFormat.PARQUET: ParquetLoader,
        FileFormat.SQLITE: SQLiteLoader,
        FileFormat.SQL: SQLLoader,
        FileFormat.ZIP: ZIPLoader,
    }
    if fmt not in registry:
        raise UnsupportedFileTypeError(f"No loader registered for format '{fmt.value}'")
    return registry[fmt]


# Make .parquet a known mimetype (Python stdlib doesn't ship it)
mimetypes.add_type("application/vnd.apache.parquet", ".parquet")
mimetypes.add_type("application/x-sqlite3", ".sqlite")
mimetypes.add_type("application/x-sqlite3", ".sqlite3")
mimetypes.add_type("application/x-ndjson", ".jsonl")
mimetypes.add_type("application/x-ndjson", ".ndjson")


__all__ = ["DetectionResult", "detect_format"]

# `io` imported to keep future streaming hooks handy without breaking imports
_ = io

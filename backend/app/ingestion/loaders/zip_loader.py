"""Safe ZIP loader.

Security-critical loader. Protections in place:

* Path traversal blocked (rejects absolute paths and `..` components).
* Symlinks are rejected outright.
* File-count and uncompressed-size caps prevent zip bombs.
* Executable file extensions inside the archive are skipped, not extracted.
* Extraction happens inside a temp directory that is cleaned up after use.
* Only ONE dataset is materialized per load call (chosen or first supported).

Nested ZIPs are extracted but not recursively unpacked to avoid ambiguity;
users can re-upload the inner archive if needed.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional

from app.config.settings import get_settings
from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat, SourceType
from app.ingestion.exceptions import (
    InvalidDatasetError,
    UnsafeArchiveError,
    UnsupportedFileTypeError,
)


_SUPPORTED_INNER_EXTENSIONS = {
    ".csv", ".tsv", ".txt",
    ".xlsx", ".xlsm", ".xls",
    ".json", ".jsonl", ".ndjson",
    ".parquet", ".pq",
    ".db", ".sqlite", ".sqlite3",
}

_EXECUTABLE_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".com", ".sh", ".ps1", ".msi",
    ".scr", ".vbs", ".js", ".jar", ".pl", ".py", ".rb",
    ".app", ".dll", ".so", ".dylib",
}


class ZIPLoader(DataLoader):
    name = "ZIPLoader"
    supported_formats = frozenset({FileFormat.ZIP})

    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        options = options or {}
        settings = get_settings()

        p = Path(source)
        try:
            zf = zipfile.ZipFile(p)
        except zipfile.BadZipFile as exc:
            raise UnsafeArchiveError(f"Not a valid ZIP archive: {exc}") from exc

        try:
            entries = zf.infolist()
            _enforce_archive_limits(
                entries,
                max_file_count=settings.max_zip_file_count,
                max_uncompressed_bytes=settings.max_zip_uncompressed_size_bytes,
            )

            candidates = _list_supported(entries)
            all_names = [e.filename for e in entries if not e.is_dir()]
            if not candidates:
                raise InvalidDatasetError(
                    "ZIP archive contains no supported datasets",
                    details={"files_in_archive": all_names[:50]},
                )

            selected = _choose_member(candidates, options.get("member"))
            temp_dir = Path(tempfile.mkdtemp(prefix="ingest_zip_"))
            try:
                extracted_path = _safe_extract_one(zf, selected, temp_dir)

                # Delegate to the appropriate inner loader
                inner_dataset = _load_inner(extracted_path, selected.filename, dataset)
                # Propagate metadata but keep ZIP as the outer source_type
                inner_meta = inner_dataset.metadata
                dataset.data = inner_dataset.data
                dataset.metadata.update(
                    {
                        "archive_member": selected.filename,
                        "archive_member_count": len(all_names),
                        "archive_supported_members": [c.filename for c in candidates][:50],
                        "inner_loader": inner_meta.get("loader"),
                        "inner_metadata": inner_meta,
                    }
                )
                for w in inner_dataset.warnings:
                    dataset.add_warning(w)
                dataset.source_type = SourceType.ZIP_ARCHIVE
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
        finally:
            zf.close()

        return dataset


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
def _enforce_archive_limits(
    entries: List[zipfile.ZipInfo],
    *,
    max_file_count: int,
    max_uncompressed_bytes: int,
) -> None:
    file_entries = [e for e in entries if not e.is_dir()]
    if len(file_entries) > max_file_count:
        raise UnsafeArchiveError(
            f"Archive contains {len(file_entries)} files (limit {max_file_count})",
            details={"file_count": len(file_entries), "limit": max_file_count},
        )
    total = sum(int(e.file_size) for e in file_entries)
    if total > max_uncompressed_bytes:
        raise UnsafeArchiveError(
            "Archive exceeds the maximum uncompressed size",
            details={
                "uncompressed_bytes": total,
                "limit_bytes": max_uncompressed_bytes,
            },
        )
    # Zip-bomb ratio check
    total_compressed = sum(int(e.compress_size) for e in file_entries) or 1
    if total / total_compressed > 200:
        raise UnsafeArchiveError(
            "Suspicious compression ratio (possible zip bomb)",
            details={"ratio": round(total / total_compressed, 2)},
        )


def _is_unsafe_name(name: str) -> bool:
    if not name or name.endswith("/"):
        return False
    # Reject absolute paths and traversal segments
    if name.startswith(("/", "\\")):
        return True
    # ZIPs store forward-slash paths; use PurePosixPath so traversal detection
    # is identical on Windows and POSIX.
    normalized = name.replace("\\", "/")
    if ".." in PurePosixPath(normalized).parts:
        return True
    # Reject drive-letter or UNC paths on Windows
    if len(name) >= 2 and name[1] == ":":
        return True
    if name.startswith(("\\\\", "//")):
        return True
    return False


def _list_supported(entries: List[zipfile.ZipInfo]) -> List[zipfile.ZipInfo]:
    supported: List[zipfile.ZipInfo] = []
    for e in entries:
        if e.is_dir():
            continue
        if _is_unsafe_name(e.filename):
            # Just skip — don't fail entire archive.
            continue
        ext = Path(e.filename).suffix.lower()
        if ext in _EXECUTABLE_EXTENSIONS:
            continue
        if ext in _SUPPORTED_INNER_EXTENSIONS:
            supported.append(e)
    return supported


def _choose_member(
    candidates: List[zipfile.ZipInfo], requested: Optional[str]
) -> zipfile.ZipInfo:
    if requested:
        for c in candidates:
            if c.filename == requested:
                return c
        raise InvalidDatasetError(
            f"Requested member '{requested}' not found in archive",
            details={"available_members": [c.filename for c in candidates][:50]},
        )
    # Prefer the largest file — usually the "main" dataset
    return max(candidates, key=lambda e: e.file_size)


def _safe_extract_one(
    zf: zipfile.ZipFile, member: zipfile.ZipInfo, dest_dir: Path
) -> Path:
    """Extract a single validated member into `dest_dir`."""
    if _is_unsafe_name(member.filename):
        raise UnsafeArchiveError(f"Unsafe archive path rejected: {member.filename}")

    # Reject symlinks (unix external attributes)
    if _is_symlink(member):
        raise UnsafeArchiveError(f"Symlinks are not allowed in archives: {member.filename}")

    target = (dest_dir / member.filename).resolve()
    # Belt-and-braces: ensure resolved path is still inside dest_dir
    try:
        target.relative_to(dest_dir.resolve())
    except ValueError as exc:
        raise UnsafeArchiveError(
            f"Path traversal attempt detected: {member.filename}"
        ) from exc

    target.parent.mkdir(parents=True, exist_ok=True)
    with zf.open(member, "r") as src, open(target, "wb") as dst:
        shutil.copyfileobj(src, dst)
    return target


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    # Unix mode is stored in the top 16 bits of external_attr.
    # S_IFLNK == 0o120000
    mode = (info.external_attr >> 16) & 0xFFFF
    return (mode & 0o170000) == 0o120000


# ---------------------------------------------------------------------------
# Inner-loader dispatch
# ---------------------------------------------------------------------------
def _load_inner(path: Path, original_name: str, outer: DatasetObject) -> DatasetObject:
    """Route the extracted file through detector + appropriate loader."""
    from app.ingestion.detector import detect_format  # local to avoid cycle

    detection = detect_format(path, filename_hint=original_name)
    loader_cls = detection.loader_cls
    if loader_cls is ZIPLoader:
        raise InvalidDatasetError(
            "Nested ZIP archives are not supported in a single ingest call",
            details={"member": original_name},
        )

    inner_ds = DatasetObject(
        dataset_id=outer.dataset_id,
        source_type=SourceType.ZIP_ARCHIVE,
        source_name=original_name,
        format=detection.format,
    )
    loader = loader_cls()
    loader.load(path, dataset=inner_ds, options=None)
    loader.get_metadata(inner_ds)
    return inner_ds

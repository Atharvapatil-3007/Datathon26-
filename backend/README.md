# Predictive Insight Dashboard — Phase 1: Data Ingestion

FastAPI + Supabase backend that takes any supported dataset (CSV, Excel, JSON,
JSONL, Parquet, SQLite, external SQL, ZIP), detects the format, validates
it, extracts a schema, and hands a standardized `DatasetObject` to Phase 2.

- **Framework**: FastAPI 0.115 + Uvicorn
- **Data**: pandas, polars, pyarrow, openpyxl, xlrd, orjson
- **DB / storage**: Supabase (PostgreSQL + Storage), SQLAlchemy for external DBs
- **Fallback**: local filesystem + JSON side-table when Supabase isn't configured

---

## 1. Project structure

```
backend/
├── app/
│   ├── main.py                     FastAPI entrypoint
│   ├── api/
│   │   └── ingestion.py            HTTP routes
│   ├── ingestion/
│   │   ├── base.py                 DataLoader abstract class
│   │   ├── dataset.py              DatasetObject + ColumnSchema
│   │   ├── detector.py             Magic-byte format detection
│   │   ├── validator.py            File- and dataset-level validation
│   │   ├── schema.py               Column-type inference
│   │   ├── manager.py              IngestionManager (orchestrator)
│   │   ├── exceptions.py           Custom exception hierarchy
│   │   └── loaders/
│   │       ├── csv_loader.py
│   │       ├── excel_loader.py
│   │       ├── json_loader.py
│   │       ├── jsonl_loader.py
│   │       ├── parquet_loader.py
│   │       ├── sqlite_loader.py
│   │       ├── sql_loader.py
│   │       └── zip_loader.py
│   ├── database/
│   │   └── supabase.py             Storage + metadata facade
│   ├── config/
│   │   └── settings.py             Pydantic-Settings, .env driven
│   └── utils/
│       └── logging.py              Structured stdout logger
├── tests/                          Pytest suite (detector, validator, loaders, API)
├── requirements.txt
├── supabase_schema.sql             Idempotent DB migration
├── .env.example
└── pytest.ini
```

---

## 2. Local setup (five minutes)

Requires Python 3.10+.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure environment (start with the local fallback — no Supabase needed)
copy .env.example .env

# Boot the API
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the
auto-generated Swagger UI. `GET /health` should return
`{"status": "ok", "supabase_configured": false, "local_fallback": true}`.

macOS/Linux: replace the `Activate.ps1` line with `source .venv/bin/activate`
and `copy` with `cp`.

---

## 3. Supabase setup

### 3.1 Create the project

1. Create a project at [supabase.com](https://supabase.com).
2. Copy the values from **Project Settings → API**:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (server-side only)
   - `anon` key → `SUPABASE_ANON_KEY` (kept for future frontend/auth work)

### 3.2 Apply the schema

Open **SQL Editor** in the Supabase dashboard, paste the contents of
[`supabase_schema.sql`](./supabase_schema.sql), and run it. It creates:

- `dataset_status` enum
- `public.datasets` table (with JSONB columns and an `updated_at` trigger)
- Indexes on status / user_id / created_at / source_type / file_format
- GIN indexes on `metadata` and `schema`
- RLS policies (auth-ready — bypassed by service_role from the backend)

### 3.3 Create the storage bucket

**Storage → New bucket**, name it `datasets`, keep it **private**. That name
matches the default `SUPABASE_STORAGE_BUCKET` in `.env.example`.

### 3.4 Wire the backend

Update `.env` with your real values:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...
SUPABASE_STORAGE_BUCKET=datasets
```

Restart Uvicorn. `GET /health` should now report
`"supabase_configured": true, "local_fallback": false`.

---

## 4. Environment variables

| Variable                        | Default              | Notes                                              |
| ------------------------------- | -------------------- | -------------------------------------------------- |
| `APP_HOST`                      | `0.0.0.0`            | Bind address for Uvicorn                           |
| `APP_PORT`                      | `8000`               |                                                    |
| `APP_LOG_LEVEL`                 | `INFO`               |                                                    |
| `APP_CORS_ORIGINS`              | `http://localhost:3000` | Comma-separated                                |
| `SUPABASE_URL`                  | *unset*              | Empty → local fallback engages                     |
| `SUPABASE_SERVICE_ROLE_KEY`     | *unset*              | Server-side only. Never expose to browser.         |
| `SUPABASE_ANON_KEY`             | *unset*              | Reserved for Phase 3 frontend auth                 |
| `SUPABASE_STORAGE_BUCKET`       | `datasets`           |                                                    |
| `MAX_UPLOAD_SIZE_MB`            | `200`                |                                                    |
| `MAX_ZIP_UNCOMPRESSED_SIZE_MB`  | `1024`               | Zip-bomb guard                                     |
| `MAX_ZIP_FILE_COUNT`            | `200`                |                                                    |
| `LOCAL_STORAGE_DIR`             | `./.local_storage`   | Used only when Supabase isn't configured           |

---

## 5. Running the API

Development:

```powershell
uvicorn app.main:app --reload --port 8000
```

Production-ish (single worker):

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
```

---

## 6. Endpoints

All routes are versioned under `/api/v1`.

### 6.1 Upload a dataset

`POST /api/v1/ingestion/upload` — multipart file upload with optional loader
hints.

```bash
curl -X POST http://localhost:8000/api/v1/ingestion/upload \
  -F "file=@./people.csv"
```

Optional form fields:

| Field         | Purpose                                                  |
| ------------- | -------------------------------------------------------- |
| `sheet_name`  | Excel — choose a specific sheet                          |
| `table_name`  | SQLite — choose a specific table                         |
| `delimiter`   | CSV — override the auto-detected delimiter               |
| `encoding`    | CSV — override the auto-detected encoding                |
| `member`      | ZIP — pick a specific archive member                     |
| `user_id`     | Phase-3 auth placeholder                                 |

Example response:

```json
{
  "success": true,
  "dataset_id": "8f6b0f1c-5a45-4f0e-9c0f-9d5cf3d0e2ab",
  "filename": "people.csv",
  "format": "csv",
  "source_type": "file",
  "rows": 5,
  "columns": 5,
  "column_names": ["id", "name", "age", "city", "signup_date"],
  "schema": {
    "columns": [
      {
        "name": "id",
        "dtype": "int64",
        "inferred_type": "identifier",
        "nullable": false,
        "unique_count": 5,
        "missing_count": 0,
        "missing_ratio": 0.0,
        "sample_values": [1, 2, 3, 4, 5],
        "is_identifier": true,
        "is_categorical": false,
        "is_numerical": false,
        "is_datetime": false,
        "is_text": false
      },
      {
        "name": "age",
        "dtype": "int64",
        "inferred_type": "integer",
        "nullable": false,
        "unique_count": 5,
        "missing_count": 0,
        "missing_ratio": 0.0,
        "sample_values": [36, 41, 54, 68, 29],
        "is_identifier": false,
        "is_categorical": false,
        "is_numerical": true,
        "is_datetime": false,
        "is_text": false
      }
    ],
    "column_names": ["id", "name", "age", "city", "signup_date"]
  },
  "metadata": {
    "loader": "CSVLoader",
    "encoding": "utf-8",
    "delimiter": "comma",
    "has_header": true,
    "engine": "pandas.read_csv (c)"
  },
  "warnings": [],
  "errors": [],
  "status": "validated",
  "storage_path": "datasets/8f6b0f1c.../original/people.csv",
  "duration_ms": 47,
  "detection": {
    "format": "csv",
    "mime_type": "text/csv",
    "size_bytes": 195,
    "loader": "CSVLoader",
    "extension": ".csv",
    "reason": "delimited text, extension .csv"
  }
}
```

### 6.2 Ingest from external SQL

`POST /api/v1/ingestion/sql`

```bash
curl -X POST http://localhost:8000/api/v1/ingestion/sql \
  -H "Content-Type: application/json" \
  -d '{
        "connection_string": "postgresql+psycopg2://user:pass@host:5432/db",
        "table_name": "sales",
        "row_limit": 100000
      }'
```

Provide **either** `query` or `table_name`. `row_limit` is optional and
applied server-side so accidental table scans stay bounded.

### 6.3 List / fetch / delete

```
GET    /api/v1/datasets?limit=50&offset=0
GET    /api/v1/datasets/{dataset_id}
DELETE /api/v1/datasets/{dataset_id}
```

`DELETE` removes both the storage object and the metadata row.

### 6.4 Error responses

Every error is a JSON object with a machine-readable `code`:

```json
{
  "success": false,
  "error": {
    "code": "UNSUPPORTED_FILE_TYPE",
    "message": "Could not determine a supported format for 'weird.xyz'",
    "details": { "extension": ".xyz", "size_bytes": 42 }
  }
}
```

Codes surfaced by Phase 1: `UNSUPPORTED_FILE_TYPE`, `INVALID_DATASET`,
`FILE_PARSING_ERROR`, `EMPTY_DATASET`, `CORRUPTED_FILE`, `FILE_TOO_LARGE`,
`UNSAFE_ARCHIVE`, `DATABASE_CONNECTION_ERROR`, `STORAGE_UPLOAD_ERROR`,
`DATASET_NOT_FOUND`, `REQUEST_VALIDATION_ERROR`, `INTERNAL_SERVER_ERROR`.

---

## 7. Supported formats

| Format          | Extension(s)                       | Loader          |
| --------------- | ---------------------------------- | --------------- |
| CSV             | `.csv`, `.txt`                     | `CSVLoader`     |
| TSV             | `.tsv`                             | `CSVLoader`     |
| Excel (OOXML)   | `.xlsx`, `.xlsm`                   | `ExcelLoader`   |
| Excel (legacy)  | `.xls`                             | `ExcelLoader`   |
| JSON            | `.json`                            | `JSONLoader`    |
| JSON Lines      | `.jsonl`, `.ndjson`                | `JSONLLoader`   |
| Parquet         | `.parquet`, `.pq`                  | `ParquetLoader` |
| SQLite          | `.db`, `.sqlite`, `.sqlite3`       | `SQLiteLoader`  |
| ZIP             | `.zip`                             | `ZIPLoader`     |
| External SQL DB | (`/ingestion/sql` endpoint)        | `SQLLoader`     |

SQLAlchemy dialects supported out of the box: PostgreSQL, MySQL/MariaDB,
SQLite. SQL Server and Oracle work when you install the matching driver
(`pyodbc`, `oracledb`) — the architecture is dialect-agnostic.

---

## 8. Extending with new loaders

Add a subclass of `DataLoader` and register a `FileFormat` in `detector.py`.
Minimal template:

```python
from app.ingestion.base import DataLoader, LoadSource
from app.ingestion.dataset import DatasetObject, FileFormat

class XmlLoader(DataLoader):
    name = "XmlLoader"
    supported_formats = frozenset({FileFormat.XML})   # add to the enum first

    def load(self, source: LoadSource, *, dataset: DatasetObject, options=None):
        # produce a pandas.DataFrame
        dataset.data = ...
        dataset.metadata["loader"] = self.name
        return dataset
```

Then register it in `detector._resolve_loader` and its file signature. No
change is needed to the API, the manager, or the tests scaffolding.

---

## 9. Tests

```powershell
pytest
```

The suite runs entirely against the local storage fallback — you do NOT
need a live Supabase project to run tests. Highlights:

- Detector: magic-byte tests for every format.
- Validator: file-level (empty, oversized, missing) and dataset-level
  (duplicates, all-null columns, high-missing warnings).
- Each loader: happy path + at least one failure mode.
- ZIP: path-traversal member is skipped; corrupt archives raise
  `UnsafeArchiveError`.
- Manager: end-to-end round trip persisted to the local fallback.
- API: `TestClient` smoke tests for upload, list, get, delete.

---

## 10. Security notes

- Uploads are streamed with a hard byte cap (`MAX_UPLOAD_SIZE_MB`); the
  temp file never exceeds that.
- ZIPs are validated (path traversal, symlinks, executable extensions,
  file count, uncompressed-size, compression-ratio) before extraction.
- Filenames are sanitized before they hit storage (`Path(name).name`,
  forbidden chars removed, 200-char cap).
- All Supabase credentials come from environment variables. No secrets
  ever appear in logs (the structured logger auto-redacts keys containing
  `password`, `secret`, `token`, `api_key`, `service_role`, etc).
- SQL loader sanitizes error strings to remove connection URLs.
- FastAPI exception handler prevents Python tracebacks from leaking to
  the frontend.

---

## 11. Phase 2 handoff — how Phase 2 consumes `DatasetObject`

Phase 2 (Data Understanding) receives a single artefact:

```python
from app.ingestion.dataset import DatasetObject
```

Attributes it can rely on:

| Attribute          | Type              | Notes                                          |
| ------------------ | ----------------- | ---------------------------------------------- |
| `dataset_id`       | `str` (UUID)      | Primary key in Supabase                        |
| `data`             | `pandas.DataFrame`| Canonical in-memory representation             |
| `source_type`      | `SourceType` enum | `file` / `sql_database` / `zip_archive`        |
| `source_name`      | `str`             | Original filename / SQL table                  |
| `format`           | `FileFormat` enum |                                                |
| `rows`, `columns`  | `int`             | Guaranteed to match `data.shape`               |
| `column_names`     | `List[str]`       |                                                |
| `schema`           | `List[ColumnSchema]` | Per-column inference + is_identifier/categorical/numerical/datetime/text flags |
| `metadata`         | `Dict[str, Any]`  | Loader-specific — e.g. sheet list, table list, encoding |
| `warnings`         | `List[str]`       | Non-fatal issues (e.g. duplicate column names) |
| `errors`           | `List[str]`       | Populated only when the dataset failed to load |
| `created_at`       | `datetime`        | UTC                                            |

**Contract**: Phase 2 must NOT read `source_type` / `format` /
loader-specific `metadata` keys to make business logic decisions. Anything
it needs about the data lives in `data`, `schema`, `warnings`, `errors`.
The loader-specific metadata is provenance, not signal.

If Phase 2 needs to re-hydrate a dataset after a restart, it can:

```python
from app.database.supabase import get_supabase_service
row = get_supabase_service().get_dataset(dataset_id)
# row["storage_path"] points at the original file in the datasets/ bucket
```

Downloading + reloading through the same detector/loader stack keeps
Phase 1 the single source of truth for how a dataset is turned into a
`DatasetObject`.

---

## 12. What Phase 1 explicitly does NOT do

- No ML, AutoML, or predictions.
- No feature engineering (that's Phase 3).
- No exhaustive EDA — just enough schema to decide what Phase 2 should
  look at.
- No frontend / dashboard code — the API is consumed by whatever the UI
  team builds in Phase 4.
- No authentication yet. RLS + `SUPABASE_ANON_KEY` are in place so Phase 3
  can drop in Supabase Auth without a schema migration.

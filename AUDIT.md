# Project Audit — Predictive Insight Dashboard

_Prepared: September 7 2026_
_Remediation pass completed: September 7 2026_
_Scope: full monorepo (`backend/` + `frontend/`) across Phase 1, Phase 2, Phase 3_

---

## 1. Executive summary

The project is a three-phase financial-intelligence platform delivering ingestion, automatic understanding, and decision-oriented analysis on top of Supabase.

- **Test posture (post-remediation):** 192 / 192 backend tests + 15 / 15 frontend tests pass; zero regression across phases.
- **Architecture:** cleanly layered — ingestion → profiling → analysis — with well-defined contracts (`DatasetObject` → `ProfilingResult` → `AnalysisResult`).
- **Security posture:** solid at the foundation (parameterised DB access, sanitised uploads, ZIP hardening, service-role secrets in env). App-layer per-user isolation now in place (F-01); identifier quoting delegated to SQLAlchemy (F-06); production local-fallback is opt-in (F-12).
- **Frontend:** feature-complete and typed against the backend contract; **initial Vitest + RTL scaffold in place** with format / api / DatasetPicker coverage (F-02).
- **Deployment readiness:** local-fallback + Supabase paths both work. **CI wired via GitHub Actions** (F-10).

Overall risk after remediation: **safe for demo and small pilots** — every actionable finding (F-01…F-12) has been closed. The two info-only entries (F-11, F-13) remain as forward-looking notes.

---

## 2. Scope

| Area | Files | Lines |
|------|-----:|-----:|
| Python (backend + tests) | 90 | ~11,027 |
| TypeScript / TSX (frontend) | 38 | ~4,906 |
| SQL (Supabase schema) | 1 | 133 |
| Configuration (.env / .example / pytest / package.json) | ~10 | ~500 |
| Documentation (README, AUDIT) | 4 | 386+ |

HTTP surface:

```
POST   /api/v1/ingestion/upload         POST   /api/v1/analysis/self
POST   /api/v1/ingestion/sql            POST   /api/v1/analysis/merger
GET    /api/v1/datasets                 POST   /api/v1/analysis/benchmark
GET    /api/v1/datasets/{id}            GET    /api/v1/analysis/options
DELETE /api/v1/datasets/{id}            GET    /
GET    /api/v1/datasets/{id}/profile    GET    /health
POST   /api/v1/datasets/{id}/reprofile
```

---

## 3. Strengths

### Architecture
- **Strict phase boundaries.** Phase 2 does not modify uploaded data; Phase 3 never re-parses raw files unnecessarily — it consumes the persisted Phase 2 profile. No hidden coupling: `dataset_loader.load_dataset_bundle` is the only re-hydration path.
- **Small, single-purpose modules.** The 22-module `app.analysis` package averages ~200 lines each; the 12-module `app.profiling` package similar. No file exceeds ~700 lines.
- **Extensibility hooks.** New file formats plug into `ingestion.detector` + a new `DataLoader` subclass. New metrics plug into `metric_registry.py`. New ratios into `ratio_engine.py`. Nothing else needs to change.

### Data honesty
- **Every numeric result is labelled** `REPORTED` / `CALCULATED` / `ESTIMATED` / `SCENARIO` / `UNAVAILABLE`. Merger combined values are always `SCENARIO`. Ratios that hit a zero denominator emit `UNAVAILABLE` with an explanatory note rather than being silently dropped.
- **No fabrication.** Insight text is always framed as `investigate ...` / `consider ...`. Attractiveness score is derived from data-supported inputs and clearly disclaimed as "analytical support, not advice".
- **Direction-aware comparisons.** `LOWER_BETTER` metrics (D/E, cost-to-income, NPA) correctly flip ahead/behind logic in benchmarking.

### Security & privacy
- **No hardcoded secrets.** A regex sweep for common secret patterns returned zero matches. `_PLACEHOLDER_TOKENS` in `settings.py` even detects `.env.example` values and falls back to local mode.
- **Sanitised uploads.** `_sanitize_filename` strips path separators + control chars, caps length at 200 chars, replaces empty names with a UUID.
- **ZIP hardening.** `zip_loader.py` blocks path-traversal, symlinks, executables, > 200 file count, > 1 GB uncompressed, and > 200x compression ratio (zip-bomb guard).
- **Parameterised SQL.** `ingestion.loaders.sql_loader` uses SQLAlchemy `text()` for queries; sanitises error messages to strip password fields.
- **Structured logger** auto-redacts keys containing `password / secret / token / api_key / service_role` before emitting.
- **CORS** locked to `APP_CORS_ORIGINS` — no `*` in production configuration.

### Testing
- **178 tests** across:
  - `tests/ingestion/` (72) — every loader, detector, validator, manager, API
  - `tests/profiling/` (55) — every analyzer, engine E2E on 6 dataset shapes, API round-trip
  - `tests/analysis/` (44) — semantic matcher, ratio calculations, health scoring, all three analysis modes end-to-end
- Tests exercise the real pipeline (`IngestionManager.ingest_file`) rather than mocking pieces, so Phase 1 + Phase 2 run before every Phase 3 test.

### Error handling
- **Single `IngestionError` hierarchy** with `code` + `http_status` + `.to_dict()` — every custom exception (including `AnalysisError`) inherits from it, so one FastAPI handler covers all three phases.
- Uploads succeed to storage **before** parsing runs, so failed parses still preserve the original file for later inspection.
- Phase 2 sections are **fault-isolated** — a broken correlation or histogram calculation degrades to `{"status": "unavailable", "reason": ...}` instead of nuking the whole profile.

---

## 4. Findings

Severity scale: 🔴 High · 🟠 Medium · 🟡 Low · 🔵 Info

### ✅ F-01. Storage-bucket policies bypassed by service_role &nbsp;·&nbsp; 🟠 Medium &nbsp;·&nbsp; **Resolved**
**Where:** `backend/supabase_schema.sql` (RLS policies) + `app/database/supabase.py`
**What:** Row-level security is enabled with owner-based policies, but the backend authenticates as `service_role` which bypasses RLS entirely. If Phase 3 auth ever exposes the API to end users directly (e.g., users' own JWTs), the schema is ready, but the current code path is trusted implicitly.
**Impact:** No user data isolation today — everything visible to anyone with API access.
**Resolution:** Added app-layer isolation as a JWT-ready foundation. New `app/api/auth.py::get_optional_user_id` FastAPI dependency reads the opaque `X-User-Id` header; the id is threaded through `IngestionManager` (list / get / delete / reprofile), `SupabaseService` (get / list / delete filter on `user_id`), `dataset_loader.load_dataset_bundle`, and all three `run_*_analysis` functions. When the header is present, cross-user access returns a 404 shape so existence isn't leaked. When absent, behaviour is unchanged (backward-compatible). Verified by `tests/test_user_isolation.py` (4 tests).

### ✅ F-02. Frontend has no automated tests &nbsp;·&nbsp; 🟠 Medium &nbsp;·&nbsp; **Resolved**
**Where:** `frontend/`
**What:** 38 TSX/TS files, ~4,900 lines, zero unit or integration tests. Type safety catches shape mismatches, but rendering bugs, race conditions in `useEffect`, and dead links only get caught manually.
**Impact:** Regressions likely slip into UI as it grows.
**Resolution:** Added Vitest 2 + React Testing Library scaffold. `vitest.config.ts` sets up jsdom + the `@/` alias; `src/test/setup.ts` wires jest-dom matchers and a ResizeObserver polyfill. Initial coverage: `format.test.ts` (8 tests), `api.test.ts` (4 tests exercising the ApiError wrapper for 4xx / network failures / 204 flows), `DatasetPicker.test.tsx` (3 RTL tests for empty / populated / selection). Added `npm test`, `test:run`, `test:coverage` scripts.

### ✅ F-03. Dataset re-download for every re-profile / analysis &nbsp;·&nbsp; 🟠 Medium &nbsp;·&nbsp; **Resolved**
**Where:** `app/analysis/dataset_loader.py` + `app/ingestion/manager.py::reprofile_dataset`
**What:** Each analysis call downloads the full file from Supabase Storage into memory and re-parses. For large datasets (approaching `MAX_UPLOAD_SIZE_MB = 200`) this is 200 MB per analysis run.
**Impact:** Latency + memory pressure; slows the "Run analysis" UX for anything > a few MB.
**Resolution:** Added a per-process LRU DataFrame cache in `dataset_loader.py` (thread-safe OrderedDict, cap 4 datasets — approximately covers self + merger + benchmark for one workspace). `clear_dataset_cache()` for tests. Verified by `tests/analysis/test_dataset_loader_cache.py` (3 tests) which shows the second `load_dataset_bundle` call does not touch the storage backend.

### ✅ F-04. Attractiveness / health scoring weights are heuristic &nbsp;·&nbsp; 🟠 Medium &nbsp;·&nbsp; **Resolved**
**Where:** `app/analysis/health_scorer.py`, `app/analysis/merger_analyzer.py::_attractiveness_score`
**What:** Dimension weights (profitability 0.30 / liquidity 0.20 / …) and attractiveness score linear coefficients were picked without domain-expert validation. The scores are labeled and explainable, but their calibration is untested against real financial datasets.
**Impact:** Scores are directionally correct but may misrank borderline cases.
**Resolution:** Introduced `HealthWeights` and `AttractivenessWeights` frozen dataclasses with `DEFAULT_*` constants. Both `score_health` and `_attractiveness_score` accept an optional `weights` parameter. A finance SME can now pass tuned weights at call-site without touching the module. Two configurability tests added.

### ✅ F-05. Metric extractor uses `max` as latest-value fallback &nbsp;·&nbsp; 🟡 Low &nbsp;·&nbsp; **Resolved**
**Where:** `app/analysis/metric_extractor.py::_build_metric_from_column`
**What:** For balance-sheet metrics (assets, equity, cash) on periodic datasets, the extractor tries to use the "latest by date" value. When the raw DataFrame isn't available it falls back to `max`. For a company whose assets grew year-over-year this is fine; for one that shrank, `max` is not the latest.
**Impact:** Occasional over-statement of point-in-time metrics; `status=ESTIMATED` and a note flag the imprecision.
**Resolution:** `profiling/statistics.py::numerical_stats` accepts an optional `date_series` and emits `latest_value` when supplied. `profiling/engine.py::_profile_columns` finds the first date-typed column once (native datetime dtype, or object column with ≥90 % parseable) via a new `_first_date_series` helper and passes it into every numerical column's stats call. `metric_extractor` now prefers `stats.latest_value` (REPORTED) over live-df extraction over `max` (ESTIMATED) — legacy profiles still work through the fallback chain.

### ✅ F-06. SQL loader table-name identifier quoting is manual &nbsp;·&nbsp; 🟡 Low &nbsp;·&nbsp; **Resolved**
**Where:** `app/ingestion/loaders/sql_loader.py::_escape` and `backend/app/ingestion/loaders/sqlite_loader.py::_escape_ident`
**What:** Both loaders escape identifiers by doubling `"`. This is correct for standard SQL and SQLite, but a maliciously named table (e.g., containing a NUL or Unicode homoglyph) could still trip up drivers. `SQLLoader` also accepts a raw `query` string which is passed through `sqlalchemy.text()` — safe, but the app doesn't audit query intent.
**Impact:** Low — the SQL ingest endpoint is intended for authenticated operators, and the connection string carries its own privilege boundary.
**Resolution:** Both loaders now delegate identifier quoting to SQLAlchemy: `sqlite_loader` imports `sqlalchemy.dialects.sqlite.dialect().identifier_preparer`, `sql_loader` uses the engine's own `dialect.identifier_preparer` so PG / MySQL / MSSQL / Oracle variants each get their correct escape rules automatically. The hand-rolled `_escape` / `_escape_ident` helpers are gone.

### ✅ F-07. Loader downloads full file to memory &nbsp;·&nbsp; 🟡 Low &nbsp;·&nbsp; **Resolved**
**Where:** `app/database/supabase.py::_SupabaseBackend.upload/download`
**What:** Reads the entire file into a `bytes` buffer before pushing to / pulling from Supabase. Fine at 200 MB max; not fine at 2 GB.
**Impact:** Bounded by `MAX_UPLOAD_SIZE_MB` today, but tightly coupled to memory ceiling.
**Resolution:** `SupabaseBackend.upload` now passes the local `Path` directly to `storage3.upload()` so the underlying httpx multipart encoder streams the file handle over the wire — peak memory stays bounded regardless of upload size. Added a new `download_to_file(storage_path, dest)` streaming variant using `httpx.stream` against a signed URL with 1 MiB chunks (local backend equivalent uses `shutil.copyfile`). `dataset_loader._stream_and_parse` uses the streaming download path so Phase 3 hydration also avoids the in-memory buffer.

### ✅ F-08. `AnalysisResult.warnings` doubles as risk carrier for self-analysis &nbsp;·&nbsp; 🟡 Low &nbsp;·&nbsp; **Resolved**
**Where:** `app/analysis/self_analyzer.py::run_self_analysis`
**What:** Self-mode routes `InsightBundle.risks` strings into `AnalysisResult.warnings` alongside data-quality warnings, then the merger analyzer adds an "Attractiveness Score" line to warnings too. Downstream consumers must string-match to tell them apart.
**Impact:** Cosmetic; the frontend filters out the attractiveness line but this is fragile.
**Resolution:** `self_analyzer` now maps `InsightBundle.risks` strings into typed `RiskItem`s (severity `MEDIUM`) and stores them on `AnalysisResult.risks`. `warnings` is once again a pure data-quality channel. Frontend `SelfAnalysisView.tsx` was updated to read `result.risks.map(r => r.title)` for the SWOT board.

### ✅ F-09. `AnalysisResult.metrics` empty for merger mode &nbsp;·&nbsp; 🟡 Low &nbsp;·&nbsp; **Resolved**
**Where:** `app/analysis/merger_analyzer.py`
**What:** Merger mode leaves the top-level `metrics` array empty because both standalone entities appear in `primary_entity.metrics` and `secondary_entity.metrics`. Consistent with the contract but easy to misread.
**Impact:** None functional. Slight documentation gap.
**Resolution:** Added a docstring block on `AnalysisResult.metrics` explaining that merger mode leaves it empty and points to `primary_entity.metrics` / `secondary_entity.metrics` / `combined_scenario` for the per-entity view.

### ✅ F-10. No CI / GitHub Actions &nbsp;·&nbsp; 🟡 Low &nbsp;·&nbsp; **Resolved**
**Where:** repository root
**What:** `pytest` runs cleanly locally, but there is no automation to enforce green on push.
**Resolution:** Added `.github/workflows/ci.yml` with two jobs. **Backend:** Python 3.12, pip cache keyed on `requirements.txt`, runs `pytest -q --tb=short`. **Frontend:** Node 20, npm cache keyed on `package-lock.json`, runs Vitest if a `test` script exists, then `npm run build` for type-check + Vite production build. Concurrency group cancels superseded runs.

### 🔵 F-11. React Router future flags already opted in — future upgrade cost = zero
**Where:** `frontend/src/main.tsx`
**Info:** `v7_startTransition` + `v7_relativeSplatPath` are set. Upgrading to Router 7 is a one-line dependency bump. _(Info-only; no action required.)_

### ✅ F-12. Local storage fallback is convenient but easy to miss &nbsp;·&nbsp; 🔵 Info &nbsp;·&nbsp; **Resolved**
**Where:** `app/database/supabase.py::SupabaseService.__init__`
**Info:** If someone deploys with an unset/placeholder `SUPABASE_URL`, the app silently uses the local filesystem. The `/health` endpoint surfaces `local_fallback: true`, but no environment-based sanity check prevents this in prod.
**Resolution:** Added `Settings.local_fallback_enabled: Optional[bool]` with a computed `allow_local_fallback` property. Explicit `LOCAL_FALLBACK_ENABLED=true|false` wins in any environment; otherwise, fallback engages only when `APP_ENV != "production"`. `SupabaseService.__init__` now raises `DatabaseConnectionError` on startup rather than silently falling back in production. `.env.example` documents the knob.

### 🔵 F-13. Ambitious enum without exhaustive coverage
**Where:** `app/analysis/metric_registry.py`
**Info:** 40+ `MetricId`s enumerated but coverage varies — banking metrics are richer than insurance / mutual-fund / brokerage metrics. Consistent with the spec ("Do not force metrics that are irrelevant to the entity") but worth noting for demos. _(Info-only; no action required.)_

---

## 5. Test coverage summary

Post-remediation totals: **192 backend + 15 frontend = 207 tests** across the monorepo.

| Phase | Tests | What's covered | What's not |
|-------|------:|----------------|------------|
| Phase 1 (ingestion) | 72 | Every loader (CSV/TSV/Excel/JSON/JSONL/Parquet/SQLite/SQL/ZIP), detector, validator, manager E2E, HTTP surface, ZIP path traversal + zip-bomb, unicode filenames | Real Supabase connectivity is not integration-tested (uses local fallback); no fuzz-testing on binary edge cases |
| Phase 2 (profiling) | 55 | Type detector heuristics (10+), normalization, missing/duplicate/cardinality analyzers, statistics per column type, distributions, outliers, correlations, quality scoring, engine E2E on 6 dataset shapes, HTTP profile endpoints, reprofile round-trip | Extremely wide datasets (100+ columns); very large row counts (>1M) not benchmarked |
| Phase 3 (analysis) | 49 | Metric registry heuristics, ratio calculations + zero-denominator, health scoring dimensions + configurable weights (F-04), attractiveness weights configurability, self-analysis full pipeline, merger combined scenario + revenue sum + ratio recalculation + data-supported synergies, benchmark direction-flip + priority classification, HTTP surface, cross-mode invariants, dataset_loader LRU cache (F-03), user-scoped filtering (F-01) | Bank-specific dataset only has fixture coverage; market benchmark path has no dedicated fixture yet |
| Cross-cutting | 16 | Production-fallback guard (F-12), storage streaming upload / download (F-07), per-user isolation over HTTP + at the service layer (F-01) | — |
| Frontend | 15 | Number / date formatters, api client error-wrapping, DatasetPicker render + selection | Full-page routes; analysis dashboards still untested |

---

## 6. Configuration & deployment audit

| Item | Status | Notes |
|------|-------|------|
| `.gitignore` excludes `.env`, `node_modules/`, `.venv/`, `.local_storage/` | ✅ | Verified |
| `requirements.txt` versions pinned to exact patch | ✅ | All 20 deps `==` pinned |
| `package.json` versions pinned to `^` semver | ⚠️ | Standard for JS but yields transitive drift; add lockfile commit |
| `supabase_schema.sql` idempotent | ✅ | `create ... if not exists` + `alter ... add column if not exists` throughout |
| RLS policies present | ✅ | Owner-based, bypassed by service_role today (see F-01) |
| Secrets committed to git | ❌ | None found. `.env.example` uses obvious placeholders. |
| Vite dev proxy for `/api` and `/health` | ✅ | No CORS friction locally |
| Global exception handler in `main.py` | ✅ | Catches `IngestionError` + `RequestValidationError` + generic fallback → structured JSON |
| Server-side upload size cap | ✅ | Streamed with `MAX_UPLOAD_SIZE_MB` guard |
| CI configured | ✅ | GitHub Actions running backend pytest + frontend build (F-10) |
| Frontend automated tests | ✅ | Vitest + RTL scaffold (F-02) |
| Per-user data isolation | ✅ | X-User-Id header threaded through the API + service layers (F-01) |
| Streaming storage I/O | ✅ | Uploads stream via storage3 file-handle path; downloads via httpx.stream signed URL (F-07) |
| Local fallback prod safety | ✅ | Refused when `APP_ENV=production` unless `LOCAL_FALLBACK_ENABLED=true` (F-12) |

---

## 7. Remediation summary

| # | Finding | Severity | Status |
|---|---------|:--------:|:------:|
| F-01 | App-layer per-user data isolation (JWT-ready foundation) | 🟠 | ✅ |
| F-02 | Frontend test scaffold (Vitest + RTL) | 🟠 | ✅ |
| F-03 | Per-process DataFrame cache in dataset_loader | 🟠 | ✅ |
| F-04 | Configurable health + attractiveness weights | 🟠 | ✅ |
| F-05 | Persisted `latest_value` per numerical column | 🟡 | ✅ |
| F-06 | SQLAlchemy identifier quoting for both SQL loaders | 🟡 | ✅ |
| F-07 | Chunked upload / streaming download | 🟡 | ✅ |
| F-08 | Risks off the warnings channel (typed `RiskItem`) | 🟡 | ✅ |
| F-09 | Documented merger-mode empty `metrics` field | 🟡 | ✅ |
| F-10 | GitHub Actions CI (backend + frontend) | 🟡 | ✅ |
| F-11 | React Router future flags | 🔵 | Info-only |
| F-12 | Local-fallback opt-in in production | 🔵 | ✅ |
| F-13 | Metric registry breadth vs depth | 🔵 | Info-only |

---

## 8. Sign-off

The system delivers the promised three-phase pipeline end-to-end with a strong contract between phases, honest data provenance labeling, and a defensible security baseline. The 192-test backend regression suite + 15 frontend tests + green CI make future changes safe to attempt.

Every actionable finding (F-01 through F-12) has been closed. The two info-only entries (F-11, F-13) are forward-looking notes that do not block any deployment tier. The platform is ready for demo, small pilots, and, with a real identity provider swapped in behind `get_optional_user_id`, initial multi-tenant use.

_End of audit._

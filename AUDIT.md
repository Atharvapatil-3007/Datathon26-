# Project Audit — Predictive Insight Dashboard

_Prepared: September 7 2026_
_Scope: full monorepo (`backend/` + `frontend/`) across Phase 1, Phase 2, Phase 3_

---

## 1. Executive summary

The project is a three-phase financial-intelligence platform delivering ingestion, automatic understanding, and decision-oriented analysis on top of Supabase.

- **Test posture:** 178 / 178 automated tests pass; zero regression across phases.
- **Architecture:** cleanly layered — ingestion → profiling → analysis — with well-defined contracts (`DatasetObject` → `ProfilingResult` → `AnalysisResult`).
- **Security posture:** solid at the foundation (parameterised DB access, sanitised uploads, ZIP hardening, service-role secrets in env). One low-severity SQL identifier-quoting concern and one auth-boundary policy to lock down before production.
- **Frontend:** feature-complete and typed against the backend contract but has **no automated tests**.
- **Deployment readiness:** local-fallback + Supabase paths both work. No CI/CD configured yet.

Overall risk: **acceptable for hackathon / MVP demo** — a handful of medium-severity items should be closed before real customer data hits it.

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

### 🟠 F-01. Storage-bucket policies bypassed by service_role
**Where:** `backend/supabase_schema.sql` (RLS policies) + `app/database/supabase.py`
**What:** Row-level security is enabled with owner-based policies, but the backend authenticates as `service_role` which bypasses RLS entirely. If Phase 3 auth ever exposes the API to end users directly (e.g., users' own JWTs), the schema is ready, but the current code path is trusted implicitly.
**Impact:** No user data isolation today — everything visible to anyone with API access.
**Recommendation:** Before adding user-facing auth, refactor `SupabaseService` to accept a per-request JWT (or supabase's `set_auth`) so RLS is honored. Alternatively, add app-layer authorisation until then.

### 🟠 F-02. Frontend has no automated tests
**Where:** `frontend/`
**What:** 38 TSX/TS files, ~4,900 lines, zero unit or integration tests. Type safety catches shape mismatches, but rendering bugs, race conditions in `useEffect`, and dead links only get caught manually.
**Impact:** Regressions likely slip into UI as it grows.
**Recommendation:** Add Vitest + React Testing Library. Start with the analysis views since they render the most fields.

### 🟠 F-03. Dataset re-download for every re-profile / analysis
**Where:** `app/analysis/dataset_loader.py` + `app/ingestion/manager.py::reprofile_dataset`
**What:** Each analysis call downloads the full file from Supabase Storage into memory and re-parses. For large datasets (approaching `MAX_UPLOAD_SIZE_MB = 200`) this is 200 MB per analysis run.
**Impact:** Latency + memory pressure; slows the "Run analysis" UX for anything > a few MB.
**Recommendation:** Add a request-lifetime cache (dict keyed by `dataset_id` inside `dataset_loader`). Longer-term: persist column-level aggregates alongside the profile so trend analysis doesn't need the raw frame.

### 🟠 F-04. Attractiveness / health scoring weights are heuristic
**Where:** `app/analysis/health_scorer.py`, `app/analysis/merger_analyzer.py::_attractiveness_score`
**What:** Dimension weights (profitability 0.30 / liquidity 0.20 / …) and attractiveness score linear coefficients were picked without domain-expert validation. The scores are labeled and explainable, but their calibration is untested against real financial datasets.
**Impact:** Scores are directionally correct but may misrank borderline cases.
**Recommendation:** Backtest against a small set of known good/bad public filings, expose `QualityWeights` in config so a finance SME can tune them without a redeploy.

### 🟡 F-05. Metric extractor uses `max` as latest-value fallback
**Where:** `app/analysis/metric_extractor.py::_build_metric_from_column`
**What:** For balance-sheet metrics (assets, equity, cash) on periodic datasets, the extractor tries to use the "latest by date" value. When the raw DataFrame isn't available it falls back to `max`. For a company whose assets grew year-over-year this is fine; for one that shrank, `max` is not the latest.
**Impact:** Occasional over-statement of point-in-time metrics; `status=ESTIMATED` and a note flag the imprecision.
**Recommendation:** Persist a `latest_value` field per column into the Phase 2 profile so the fallback becomes exact. Small change to `profiling/statistics.py`.

### 🟡 F-06. SQL loader table-name identifier quoting is manual
**Where:** `app/ingestion/loaders/sql_loader.py::_escape` and `backend/app/ingestion/loaders/sqlite_loader.py::_escape_ident`
**What:** Both loaders escape identifiers by doubling `"`. This is correct for standard SQL and SQLite, but a maliciously named table (e.g., containing a NUL or Unicode homoglyph) could still trip up drivers. `SQLLoader` also accepts a raw `query` string which is passed through `sqlalchemy.text()` — safe, but the app doesn't audit query intent.
**Impact:** Low — the SQL ingest endpoint is intended for authenticated operators, and the connection string carries its own privilege boundary.
**Recommendation:** Use SQLAlchemy's `Table(name, ...)` reflection instead of string-quoted identifiers when possible; document that `/ingestion/sql` should not be exposed to untrusted users.

### 🟡 F-07. Loader downloads full file to memory
**Where:** `app/database/supabase.py::_SupabaseBackend.upload/download`
**What:** Reads the entire file into a `bytes` buffer before pushing to / pulling from Supabase. Fine at 200 MB max; not fine at 2 GB.
**Impact:** Bounded by `MAX_UPLOAD_SIZE_MB` today, but tightly coupled to memory ceiling.
**Recommendation:** Stream via chunked upload once Supabase-py exposes it (or fall back to signed URLs + resumable uploads for larger files).

### 🟡 F-08. `AnalysisResult.warnings` doubles as risk carrier for self-analysis
**Where:** `app/analysis/self_analyzer.py::run_self_analysis`
**What:** Self-mode routes `InsightBundle.risks` strings into `AnalysisResult.warnings` alongside data-quality warnings, then the merger analyzer adds an "Attractiveness Score" line to warnings too. Downstream consumers must string-match to tell them apart.
**Impact:** Cosmetic; the frontend filters out the attractiveness line but this is fragile.
**Recommendation:** Move risks to `AnalysisResult.risks` (typed `RiskItem` list — already supported by the type) even for self-analysis mode.

### 🟡 F-09. `AnalysisResult.metrics` empty for merger mode
**Where:** `app/analysis/merger_analyzer.py`
**What:** Merger mode leaves the top-level `metrics` array empty because both standalone entities appear in `primary_entity.metrics` and `secondary_entity.metrics`. Consistent with the contract but easy to misread.
**Impact:** None functional. Slight documentation gap.
**Recommendation:** Document in the type: "For merger mode, `metrics` is empty; see per-entity snapshots".

### 🟡 F-10. No CI / GitHub Actions
**Where:** repository root
**What:** `pytest` runs cleanly locally, but there is no automation to enforce green on push.
**Recommendation:** Add a GitHub Action running `pytest` (backend) + `npm run build` (frontend, type-check). ~15 minutes of setup.

### 🔵 F-11. React Router future flags already opted in — future upgrade cost = zero
**Where:** `frontend/src/main.tsx`
**Info:** `v7_startTransition` + `v7_relativeSplatPath` are set. Upgrading to Router 7 is a one-line dependency bump.

### 🔵 F-12. Local storage fallback is convenient but easy to miss
**Where:** `app/database/supabase.py::SupabaseService.__init__`
**Info:** If someone deploys with an unset/placeholder `SUPABASE_URL`, the app silently uses the local filesystem. The `/health` endpoint surfaces `local_fallback: true`, but no environment-based sanity check prevents this in prod.
**Recommendation:** Consider making local fallback opt-in via `APP_ENV=development` rather than auto-engaging whenever Supabase creds look off.

### 🔵 F-13. Ambitious enum without exhaustive coverage
**Where:** `app/analysis/metric_registry.py`
**Info:** 40+ `MetricId`s enumerated but coverage varies — banking metrics are richer than insurance / mutual-fund / brokerage metrics. Consistent with the spec ("Do not force metrics that are irrelevant to the entity") but worth noting for demos.

---

## 5. Test coverage summary

| Phase | Tests | What's covered | What's not |
|-------|------:|----------------|------------|
| Phase 1 (ingestion) | 72 | Every loader (CSV/TSV/Excel/JSON/JSONL/Parquet/SQLite/SQL/ZIP), detector, validator, manager E2E, HTTP surface, ZIP path traversal + zip-bomb, unicode filenames | Real Supabase connectivity is not integration-tested (uses local fallback); no fuzz-testing on binary edge cases |
| Phase 2 (profiling) | 55 | Type detector heuristics (10+), normalization, missing/duplicate/cardinality analyzers, statistics per column type, distributions, outliers, correlations, quality scoring, engine E2E on 6 dataset shapes, HTTP profile endpoints, reprofile round-trip | Extremely wide datasets (100+ columns); very large row counts (>1M) not benchmarked |
| Phase 3 (analysis) | 44 | Metric registry heuristics (alias exclusion, banking terms, gibberish), ratio calculations + zero-denominator, health scoring dimensions, self-analysis full pipeline, merger combined scenario + revenue sum + ratio recalculation + data-supported synergies, benchmark direction-flip + priority classification + near-term targets, HTTP surface for all three modes, cross-mode invariants (same-dataset rejection, 404s) | Bank-specific dataset only has fixture coverage — no dedicated banking-mode assertion beyond metric matching; market benchmark path has no dedicated fixture yet |
| Frontend | 0 | — | Everything |

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
| CI configured | ❌ | See F-10 |

---

## 7. Priority recommendations

### Before demoing to hackathon judges
1. Verify the running Supabase project has the `datasets` table + `profile` + `profiled_at` columns (re-run `backend/supabase_schema.sql`).
2. Confirm the storage bucket named `datasets` exists and is private.
3. Smoke-test each of the three analysis modes end-to-end in the browser.

### Before onboarding a second user / real customer data
4. Close F-01 by scoping API access to authenticated users (Supabase Auth JWTs) and honoring RLS.
5. Address F-03 by caching re-hydrated DataFrames per request.
6. Address F-05 by persisting a `latest_value` column into Phase 2 profiles.

### Before any production launch
7. Add CI (F-10) and frontend tests (F-02).
8. Have a finance SME review the health / attractiveness scoring formulas (F-04).
9. Move risks off the warnings channel (F-08).
10. Streaming storage I/O for large datasets (F-07).

---

## 8. Sign-off

The system delivers the promised three-phase pipeline end-to-end with a strong contract between phases, honest data provenance labeling, and a defensible security baseline. The 178-test regression suite makes future changes safe to attempt.

The medium-severity items above are all incremental improvements — none block a demo. If the platform moves toward multi-tenant or larger-dataset production use, close F-01, F-03, and F-05 first.

_End of audit._

# Predictive Insight Dashboard

An AI/ML-powered predictive insight dashboard, built in phases.

- **Phase 1 — Data Ingestion** → [`backend/`](./backend) (this repo, current phase)
- Phase 2 — Data Understanding (upcoming)
- Phase 3 — Feature Engineering / Auth (upcoming)
- Phase 4 — Frontend Dashboard (upcoming)

Start here: [`backend/README.md`](./backend/README.md).

## Quick start

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env         # local fallback works out of the box
uvicorn app.main:app --reload
```

Then visit http://localhost:8000/docs.

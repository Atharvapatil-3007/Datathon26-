# Predictive Insight Dashboard — Frontend

React + Vite + TypeScript + Tailwind. Consumes the FastAPI backend at
`http://localhost:8000` via a Vite dev-proxy.

## Setup

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Requires the backend running on port 8000
(`uvicorn app.main:app --reload` in `../backend`).

## Scripts

- `npm run dev` — Vite dev server with HMR + backend proxy
- `npm run build` — production build (typechecked)
- `npm run preview` — serve the production build

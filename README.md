# KIYUB v4

KIYUB v4 is an AI-assisted architectural floor-plan generation platform that combines architectural requirements, spatial reasoning, Buildify-based topology generation, geometric optimization, and structured SceneDocument output.

This is a **conceptual design and planning tool**. It does not replace licensed architects. Generated designs are not claimed to be building-code compliant.

## Generation architecture

```text
User Requirements
        ↓
Architectural Specification
        ↓
Site / Lot Analysis
        ↓
Buildify
        ↓
Spatial Topology
        ↓
HouseGAN Candidate Generation
        ↓
OR-Tools Geometric Solver
        ↓
FloorPlanResult
        ↓
SceneDocument v2.0
        ↓
KIYUB Editor
```

- **Buildify** (MOE + bubble diagram) proposes spatial organization.
- **HouseGAN++** is optional inside that path. If the local checkpoint is missing, generation continues with zone-based candidates.
- **OR-Tools** is the final geometric solver (`compete()` / CP-SAT).
- **SceneDocument v2.0** is the editor-ready metric scene. Lot `site.width` / `site.depth` come from the questionnaire in meters, not from the Buildify footprint or the OR-Tools envelope (feet).

## Run locally

Workflow persistence is **Supabase Postgres + Auth**. `/api` contracts, generation (MOE / HouseGAN++ / OR-Tools), and the editors are unchanged. Pytest uses an in-memory repository (no live Supabase).

1. Create a Supabase project and enable the email Auth provider.
2. Copy `.env.example` to `.env` and set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`. Frontend needs `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` only. Never expose the service role.
3. Apply schema: `supabase db push`, or paste **`supabase/migrations/`** into the SQL editor. Do not apply `backend/migrations/legacy/` (old SQLite/`users` drafts).
4. Seed runs on backend startup (Auth Admin + demo projects) when service-role keys are set. `KIYUB_WORKFLOW_MEMORY=1` is pytest-only; uvicorn will refuse to start if it is set or if Supabase keys are missing.

Frontend (Vite, default http://localhost:5173):

```powershell
cd frontend
npm install
npm run dev
```

Backend (FastAPI, http://127.0.0.1:8002):

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8002
```

Optional one-shot import of a historical SQLite file (CLI only, never API startup; does not copy `password_hash`):

```powershell
cd backend
.\.venv\Scripts\python.exe -m workflow.import_sqlite .\kiyub_workflow.db --password "ChangeMeNow!1"
```

Ollama at `http://localhost:11434` is used for RAG embeddings and chat when those models are installed. Generation does not require Ollama if the embedding cache is already populated.

## Tests

```powershell
cd frontend
npm test

cd backend
.\.venv\Scripts\python.exe -m pytest
```

## Git

This repository’s Git history comes from the former KIYUB-Buildify / Buildify working tree. The GitHub remote may still be named Buildify; local product identity is KIYUB v4.

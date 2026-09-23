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

Optional:

```
NEXT_PUBLIC_GENERATION_ENGINE_URL   (unused by this Vite app; API is proxied to 8002)
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

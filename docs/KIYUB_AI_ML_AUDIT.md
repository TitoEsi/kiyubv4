# KIYUB AI/ML SYSTEM AUDIT

**Project:** `C:\Users\USER\Desktop\kiyub-buildify`  
**Date:** 20 September 2026  
**Scope:** Measurement and reporting only. No generation, scoring, strategy-selection, FloorPlan schema, model, or planning-logic changes.  
**Canonical result:** FloorPlan JSON from `POST /api/generate/moe`.  
**Working definition:** A component is “working” only if it is (1) executed, (2) produces valid output, and (3) that output contributes to the final FloorPlan geometry. Files, weights, imports, or successful loads are not enough.

Source of timings and A/B fingerprints: `backend/audit_last_run.json` from `python audit_generation.py` on this machine. Pytest: `111 passed in 460.88s`.

This is a conceptual design tool. `irc_compliant` on the refined FloorPlan is `false`. Quality scores are internal heuristics, not professional architectural approval.

---

## 1. Executive Summary

**What AI/ML systems are actually active on `POST /api/generate/moe`?**

- **MOE (Mixture of Experts, PyTorch, CPU)** runs once via `predict_floor_plan`. Weights load. `get_expert_weights` returns a valid 8-vector that sums to 1.0. A zone-fallback room list is built. `expert_weights` and `confidence` are copied onto the HTTP payload.
- **HouseGAN++** is imported and called three times (one per variant). Local checkpoint is missing. Remote Hugging Face Space returns **HTTP 404**. It returns **zero layouts**. Placement falls back to `_place_rooms_architectural`.
- **RAG** is initialized at FastAPI startup only. Embeddings all fail. `retrieve` is never imported or called by generate.
- **Ollama `llama3.2`** is used only by `POST /api/chat`, not by generate.
- **GNN** exists only as HouseGAN’s `GraphConvLayer` / `GraphRelationNetwork`. It does not run. **GNN is not currently part of the active generation pipeline.**

**Are they working (executed + valid + contributes to final geometry)?**

| System | Executed | Valid output | Contributes to final FloorPlan geometry (default) |
|---|---|---|---|
| MOE | Yes | Expert weights yes; geometry is zone-fallback, not HouseGAN | **No** — default `KIYUB_MULTI_STRATEGY=1` skips `hints_from_moe_plan` |
| HouseGAN++ | Try/fail | No | No |
| RAG | Startup only | No embeddings, retrieve unused | No |
| Chat LLM | Not on this endpoint | n/a | No |
| GNN | No | n/a | No |

**Which are failing?** HouseGAN local weights missing + remote 404. RAG: Ollama `localhost:11434` connection refused; cache `{}`; retrieve returns `[]`.

**Is the final floor plan using AI/ML outputs?**  
On the default path, **no**. Final boxes come from **OR-Tools CP-SAT** (`compete()`, five strategies × ~8 s) after a **deterministic** RoomProgram / spatial plan / BuildingMass. Empty-MOE vs live-MOE produced **identical** room types, counts, and boxes. MOE geometry **does** change CP-SAT output only when `KIYUB_MULTI_STRATEGY=0` (hybrid hints) — not the default.

---

## 2. AI/ML Inventory

| Component | Technology | Model | Active? | Working? | Used in final plan? | Runtime (this run) |
|---|---|---|---|---|---|---|
| MOE `BuildifyMOE` | PyTorch | ConstraintEncoder + SparseTopK (top-4 of 8 MLPs); `moe/weights/buildify_moe.pt` (17,169,805 bytes, 4,273,324 params) | Called on generate | Inference valid; **geometry unused on default path** | Weights/confidence echoed; **boxes overwritten** | Load 0.0564 s; `get_expert_weights` 0.002 s; full `predict_floor_plan` 2.7134 s |
| HouseGAN++ | PyTorch GCN + mask decoder | `housegan_pp.pt` **missing**; remote `https://buildify-housegan.hf.space/api/predict` | Called, then empty | **No** | **No** (zone fallback) | Local load 0.0001 s (skip); remote 0.9137 s → 404; 3 generate calls ~0.89–0.91 s each |
| HouseGAN GNN (`GraphConvLayer`, `GraphRelationNetwork`) | Custom GCN inside HouseGAN | Same missing checkpoint | **No** | **No** | **No** | Not loaded |
| RAG | Ollama embeddings | `nomic-embed-text:latest` at `http://localhost:11434/api/embeddings` | Startup `initialize` only | **No** (0 cached vectors) | **No** (`retrieve` not on generate) | Tags 4.2896 s refused; initialize 98.1401 s (39 failed embeds); retrieve 0.0006 s → 0 hits |
| Chat LLM | Ollama chat | `llama3.2` `POST http://localhost:11434/api/chat` | `/api/chat` only | Not tested (Ollama down); **not on generate** | **No** | n/a |
| Training pipeline | PyTorch | `moe/training/train_pipeline.py`, `generate_dataset.py` | Training-only | n/a | **No** | Not run |
| HF Space app | Duplicate HouseGAN | `backend/hf_space/app.py` | Remote Space, not local generate | Space 404 | **No** | Probe POST 404 |
| OR-Tools CP-SAT | Constraint solver | Not ML | Yes (geometry) | Yes (optimization) | **Yes** | ~8 s × 5 strategies; refine 48.4031 s |
| Planning / mass / quality | Deterministic | None | Yes | Yes (rules/scoring) | Yes (guides CP-SAT) | Plan 0.0003 s; mass 0.0001 s; quality ~0.26 s cumulative |

Not found in the repo: TensorFlow, transformers, sentence-transformers, PyTorch Geometric, DGL, OpenAI, Gemini, Claude, OpenRouter, `.pth` / `.onnx` / `.safetensors`.

---

## 3. Actual Runtime Pipeline

Verified from `backend/main.py` `generate_moe` plus one live `TestClient` `POST /api/generate/moe` (HTTP **200**, `status: valid`).

```
POST /api/generate/moe
  → constraints.model_dump()
  → validate_constraints_feasibility (hard errors → 422)
  → predict_floor_plan(constraints, num_variants=3)
       → load_model()  [cached after first load]
       → encode_constraints → get_expert_weights  (1× per request)
       → size rooms via _moe_adjusted_size(expert_weights)
       → _place_rooms_housegan  (3×; this run: all empty)
       → _place_rooms_architectural  (zone fallback)
       → IRC snap/fill/doors → moe["plans"]  (this run: 1 plan kept)
  → refine_generation(constraints, moe)
       → envelope_from_constraints + RoomProgram.from_constraints
            (questionnaire → program; NOT moe["plans"] room list)
       → spatial_planner.plan  (zones, graph, blocks, strategies)
       → plan_building_mass
       → if KIYUB_MULTI_STRATEGY != "0"  [DEFAULT]:
            compete()  5× evaluate_strategy → solve() CP-SAT 8s
            winner layout → layout_to_floorplan
            skip hints_from_moe_plan
         elif hybrid:
            solve(..., hints=hints_from_moe_plan(moe_plan, program))
       → copy expert_weights, confidence onto payload
       → irc_compliant = False
  → FloorPlan JSON to client
```

**Not on this path:** `rag.retrieve`, Ollama chat, HouseGAN GNN forward, `moe/training/*`, `/api/generate` (`generator.generate_floor_plan`).

Startup (`@app.on_event("startup")`): `rag.initialize()` then `load_model()`. Failed RAG does not abort the app. Cold TestClient this run spent ~98 s in RAG embed retries **before** generate; that is startup cost, not CP-SAT.

---

## 4. MOE Findings

1. **Name:** Mixture of Experts (`BuildifyMOE`).
2. **Architecture:** ConstraintEncoder (linear + 4-head attention) → SparseTopK gating (top-4 of 8 named MLP experts) → used at inference via `get_expert_weights`, not the full autoregressive decoder, for production placement.
3. **Weights:** `backend/moe/weights/buildify_moe.pt` (exists, 17,169,805 bytes).
4. **Load:** Yes. Log: `[MOE] Loaded weights from ...buildify_moe.pt`. `torch.load(..., map_location="cpu", weights_only=False)` then `load_state_dict` — no exception; checkpoint compatible with current `BuildifyMOE`.
5. **Input:** Encoded constraint vector shape `(1, 20)`.
6. **Output:** Expert weights shape `(1, 8)`, finite, sum `1.000001`. Names: Room Sizing, Spatial Layout, Style Adaptation, Code Compliance, Adjacency, Circulation, Outdoor & Garage, Cost Optimization. This request: Adjacency 0.194786 highest; Room Sizing 0.039934 lowest. `predict_floor_plan` also returns plans, `confidence` 86.9, `irc_compliant` true on the **MOE** dict only.
7. **Called on `/api/generate/moe`:** Yes, once per request (`predict_floor_plan`).
8. **Times per generation:** `load_model` cached after first call; `get_expert_weights` once; HouseGAN placement attempted `num_variants` times (3).
9. **Affects final geometry (default):** **No.** A/B: baseline vs empty MOE dict → identical 15-room boxes. `moe_changes_geometry_when_multi_on: false`.
10. **Discarded/overwritten:** MOE plan had **16** rooms (includes `pantry`) and different sizes (e.g. garage **38×20 at (0,0)**). Final FloorPlan has **15** rooms from RoomProgram (no pantry) and garage **18×12 at (0,0)**. Default compete path never reads MOE boxes. `expert_weights` are **echoed** on the response (`expert_weights_echoed: true`).
11. **Valid inference:** Yes for the 8-vector. Plan geometry is heuristic placement after HouseGAN miss, not a decoder sample.
12. **Device:** CPU. `cuda_available: false`.
13. **Timing:** load 0.0564 s; gating 0.002 s; full predict 2.7134 s (dominated by three HouseGAN remote 404s).
14. **Swallowed failures:** HouseGAN empty → architectural fallback (logged). Missing weights would print and use an untrained model (not this run).
15. **Checkpoint compatibility:** Load succeeded.

**When `KIYUB_MULTI_STRATEGY=0`:** `hints_from_moe_plan` maps MOE boxes onto program ids. Hybrid run produced **different** positions/sizes (garage **13×18 at (10,0)**), quality 90 vs 89, 8.0715 s (single solve, 0 strategy evals). So MOE **can** bias CP-SAT if multi-strategy is off. Default env is `"1"`.

---

## 5. HouseGAN Findings

| Question | Evidence |
|---|---|
| Imported? | Yes. `moe.inference` `from .housegan import ...`; `_HOUSEGAN_AVAILABLE` true |
| Executed? | Yes. 3× `_place_rooms_housegan` during predict; isolated `generate_layouts` |
| Checkpoint | `backend/moe/housegan/weights/housegan_pp.pt` — **file and directory missing** |
| Input | Bubble diagram: type vector, adjacency, house W/H |
| Output this run | `n_layouts: 0`; each attempt `used: false`, `n_rooms: 0` |
| Influences final plan? | **No** |
| Direct vs indirect | Direct try inside `predict_floor_plan`; then unused |
| Converted to rooms? | Would merge HG positions with MOE sizes if layouts existed |
| Overwritten by OR-Tools? | Never reached OR-Tools; MOE fallback plan itself is unused on default compete |
| Request reaches HouseGAN? | Yes, then 404 / empty |

Isolated probe: local model `None`; remote POST status **404**, HTML body (Space not serving `/api/predict`); `generate_layouts` 0.9343 s, 0 layouts, no exception (empty fallback).

Logs: `[HouseGAN] Remote inference failed: Client error '404 Not Found'`.

**Not working.** Prototype GNN inside the unloaded generator does not run.

---

## 6. RAG Findings

| Question | Evidence |
|---|---|
| Provider / model | Ollama `nomic-embed-text:latest` |
| Endpoint | `http://localhost:11434/api/embeddings` (`backend/rag.py`) |
| Why embeds fail | `ConnectError: [WinError 10061] ... actively refused` — **no process on 11434** |
| API key | None; local HTTP only |
| Local server expected | Yes, Ollama |
| Usable without embeds? | `retrieve` returns `[]` if `_embeddings` empty |
| Cached embeddings | `embed_cache.json` is `{}` (0 keys) after initialize wrote empty cache |
| Retrieve during generate? | **No.** Only `rag.initialize()` at startup. `retrieve` callers: `rag.py` + audit script |
| Affects generation? | **No** |
| Blocks generation? | Does not abort generate. Cold startup waits ~98 s on 39 failed embed attempts |
| Init-only? | **Yes** |

KB: 39 chunks in `arch_knowledge.json`. Retrieve probe: 0 hits, 0.0006 s.

**Not working for floor-plan generation.** Do not claim RAG improves layouts.

---

## 7. GNN Findings

Searched: GNN, GraphSAGE, GAT, GCN, message passing, PyTorch Geometric, DGL, graph embeddings.

**Present:** Custom `GraphConvLayer` and `GraphRelationNetwork` in `backend/moe/housegan/model.py` (and a copy in `backend/hf_space/app.py`). Used only as the encoder inside `HouseGANGenerator`. No PyG/DGL. No separate adjacency-prediction service.

**Classification: C — prototype / incomplete** (inside HouseGAN; cannot run without `housegan_pp.pt` or a live Space).

**GNN is not currently part of the active generation pipeline.**

---

## 8. LLM Findings

| Field | Chat path | Generate path |
|---|---|---|
| Provider | Ollama | None |
| Model | `llama3.2` | — |
| Endpoint | `http://localhost:11434/api/chat` | — |
| Call site | `backend/main.py` `POST /api/chat` | — |
| Input | System prompt + plan summary + messages | — |
| Output | Reply text; optional JSON plan extract | — |

No OpenAI / Gemini / Claude / OpenRouter / Hugging Face Inference API calls in Python sources.

**There is no active LLM call during `POST /api/generate/moe`.** Chat cannot affect generate geometry. Ollama was down on this host, so chat would fail if invoked; that was not required for this audit.

---

## 9. OR-Tools Findings

**OR-Tools is not an AI/ML model.** It is a CP-SAT constraint optimizer.

- **Where:** `backend/solver/solver.py` `solve()` → CP-SAT. Default generate uses `compete()` in `strategy_competition.py`.
- **Variables:** Integer room `x,y,width,height` (and related) inside the buildable envelope.
- **Hard:** Non-overlap, envelope, requested room set, selected topology (wall-share / access OR-groups), garage front-or-side when a garage exists, foyer/patio pins as encoded.
- **Soft:** Quality / cluster / mass / adjacency objectives inside `solve` (unchanged by this audit).
- **Time limit:** `time_limit_s=8` per strategy in `compete`; hybrid fallback uses 8–10 s.
- **Calls per default generation:** **5** (`patio_oriented`, `central_spine`, `linear`, `service_side`, `cluster`). A failed cluster pass can retry without cluster terms (baseline `central_spine` **16.0821 s** ≈ two 8 s solves).
- **Final FloorPlan:** Yes. Winner `patio_oriented`, `validated: true`, `status: valid`.

Measured strategy evals (baseline, live 20×30, office yes):

| Strategy | Valid | solver_s | quality | access | circulation | adjacency | zoning | usability | residual |
|---|---|---|---|---|---|---|---|---|---|
| patio_oriented | yes | 8.1256 | 89 | 100 | 68 | 75 | 89 | 82 | 967 |
| central_spine | yes | 16.0821 | 87 | 100 | 72 | 66 | 78 | 91 | 496 |
| linear | yes | 8.0705 | 88 | 100 | 65 | 73 | 78 | 82 | 867 |
| service_side | yes | 8.0567 | 87 | 100 | 66 | 50 | 100 | 91 | 549 |
| cluster | yes | 8.0652 | 88 | 100 | 66 | 66 | 89 | 91 | 806 |

Selected: **patio_oriented**, overall quality **89**. Refine wall time **48.4031 s**. HTTP TestClient **149.3207 s** (includes ~98 s RAG startup + predict + compete). Geometry-producing work is CP-SAT, not MOE/HouseGAN/RAG.

---

## 10. Architectural Planning Engine

None of the following is an ML model:

| Piece | Classification |
|---|---|
| Architectural / RoomProgram from questionnaire | Rule-based |
| Site / access (driveway, walk, street) | Rule-based |
| Philippine planning profile | Configurable rules (not legal compliance) |
| Zoning (public / private / service) | Rule-based |
| Relationship graph, avoid edges | Rule-based |
| Circulation graph | Rule-based + scoring |
| Front/middle/rear bands, room blocks | Rule-based |
| Strategy competition (5 named strategies) | Rule-based candidates + optimization + scoring |
| BuildingMass | Geometry / rules |
| Room clusters | Rule-based + scoring |
| Furniture / usability | Validation / scoring |
| Flexible geometry flag | Geometry (default off this run) |
| Quality score | Scoring (internal; not code compliance) |
| `irc_compliant` on refined result | Always `false` |

Planning 0.0003 s; mass 0.0001 s. They **do** shape CP-SAT (envelope, hard pairs, mass target) and therefore the final FloorPlan. That is deterministic architecture + optimization, not AI.

---

## 11. Performance Profile

Live questionnaire: 20×30 m rectangle, 1 floor, 3 bed, 2 bath, primary suite, 2-car, patio, **office yes**, laundry room.

| Stage | Time (s) | Notes |
|---|---|---|
| MOE load (first) | 0.0564 | Cached afterward |
| MOE `get_expert_weights` | 0.0020 | |
| HouseGAN local | 0.0001 | Missing weights |
| HouseGAN remote probe | 0.9137 | 404 |
| `predict_floor_plan` | 2.7134 | 3× HouseGAN 404 |
| RAG initialize (Ollama down) | 98.1401 | Startup only |
| RAG retrieve | 0.0006 | 0 hits; **not on generate** |
| Architectural planning | 0.0003 | |
| Building mass | 0.0001 | |
| Quality (`score_layout` sum) | 0.2599 | Inside five solves |
| `refine_generation` compete | 48.4031 | ~5×8 s CP-SAT |
| Hybrid hints (`MULTI_STRATEGY=0`) | 8.0715 | One solve |
| `POST /api/generate/moe` TestClient | 149.3207 | Startup RAG + predict + compete |

Default generate after a warm process is ~**48–51 s**, almost all CP-SAT. MOE gating is milliseconds. HouseGAN adds ~3 s of failed HTTP. RAG is not in the generate function but **punishes process start** when Ollama is absent.

`moe/tests` are **not collected** (`pytest.ini` `testpaths = solver/tests`, `python_files = test_*.py`). That is a test-discovery fact, not a pipeline change.

---

## 12. AI Contribution

### MOE

```
INPUT  20-dim constraint vector
  → MODEL  BuildifyMOE.get_expert_weights (CPU, loaded .pt)
  → OUTPUT  8 expert weights + confidence; sized rooms; zone-fallback plan
  → WHERE    moe dict → refine_generation copies weights to JSON;
             boxes only if KIYUB_MULTI_STRATEGY=0 via hints_from_moe_plan
  → FINAL GEOMETRY (default MULTI_STRATEGY=1)  NO
```

A/B: `baseline_equals_empty_moe: true`. Same 15 types and identical boxes. HTTP fingerprint **matched** baseline (`http_matches_baseline_geom: true`).

### HouseGAN++

```
INPUT  bubble diagram
  → MODEL  local missing; remote 404
  → OUTPUT  []
  → WHERE    _place_rooms_housegan → None → architectural fallback
  → FINAL GEOMETRY  NO
```

### RAG

```
INPUT  never queried on generate
  → MODEL  Ollama embeddings (down)
  → OUTPUT  empty cache
  → WHERE    startup only
  → FINAL GEOMETRY  NO
```

### Chat LLM

Not invoked. No geometry path.

---

## 13. Problems Found

**CRITICAL**

1. **Default generate ignores MOE/HouseGAN room geometry.** `compete()` does not pass `hints_from_moe_plan`. Empty MOE yields the same FloorPlan. Calling the endpoint “MOE generate” overstates what the client receives.
2. **HouseGAN cannot produce layouts.** Missing `moe/housegan/weights/` and HF Space **404**. Every request still waits ~0.9 s × 3 variants.

**HIGH**

3. **RAG embeddings fail and retrieve is unused.** Ollama refused; cache `{}`; generate never retrieves. Startup still spends ~98 s attempting 39 embeds on a cold TestClient/app.
4. **Five sequential 8 s CP-SAT solves** (~48 s) dominate latency. One extra ~8 s retry when a strategy fails cluster terms (`central_spine` 16 s). Repeated work is optimization, not ML, but it is the real cost.

**MEDIUM**

5. **MOE `irc_compliant: true` on predict is overwritten** to `false` on the refined payload (correct for KIYUB policy, easy to misread logs).
6. **MOE plan room set ≠ RoomProgram** (16 vs 15; extra pantry). Even hybrid hints cannot inject unrequested types.
7. **CPU-only PyTorch.** Fine for 2 ms gating; irrelevant vs CP-SAT.
8. **`predict_floor_plan` kept 1 of 3 variants** after envelope filtering; still paid for 3 HouseGAN attempts.

**LOW**

9. **Chat LLM / RAG depend on Ollama** which was not running; out of generate path.
10. **Training scripts and HF Space app** unused at runtime.
11. **MOE unit tests not collected** by `pytest.ini`.
12. HouseGAN 404 is logged, not silent; empty list is the fallback.

No evidence of an incompatible MOE checkpoint. No scoring/selection bugs claimed; selection was deterministic `patio_oriented` across baseline, empty-MOE, and HTTP.

---

## 14. Recommended Next Steps

Do not implement these in this audit. Order matches measured impact:

1. **Treat HouseGAN as failed until a real checkpoint or a live `/api/predict` exists.** Do not describe it as a working generator. (Do not delete the code.)
2. **Decide what MOE is for on the default path:** either document that expert weights are metadata only, or (later, separately) wire hints without changing scoring unless product intent is hybrid. Evidence: hints **do** change boxes when `MULTI_STRATEGY=0`.
3. **Avoid three HouseGAN remote round-trips that always 404** (unnecessary repeated inference). Cache “remote dead” for the process, or skip remote when local weights are missing — as a later change, not done here.
4. **Do not pay RAG at startup when Ollama is down** (unnecessary init). `retrieve` is unused on generate; init is the only cost.
5. **RAG:** without a running embed server and a non-empty cache, retrieval cannot work. Do not install services as part of claiming RAG works.
6. **Solver performance:** default latency is **5×8 s CP-SAT**, not MOE. Speed work should start there after ML contribution is explicit.
7. **Only then** architectural/planning product changes.

---

## Appendix — Evidence log

### Files inspected

- `backend/main.py` — `/api/generate/moe`, startup, `/api/chat`
- `backend/moe/inference.py`, `model.py`, `config.py`, `experts.py`, `data.py`
- `backend/moe/housegan/inference.py`, `model.py`, `bubble_diagram.py`
- `backend/moe/weights/buildify_moe.pt` (present)
- `backend/moe/housegan/weights/` (**absent**)
- `backend/moe/training/*` (training-only)
- `backend/rag.py`, `embed_cache.json`, `arch_knowledge.json`
- `backend/solver/pipeline.py`, `strategy_competition.py`, `solver.py`, `adapter.py`, `quality.py`, `spatial_planner.py`, `building_mass.py`, `room_program.py`
- `backend/hf_space/app.py`
- `backend/pytest.ini`
- `backend/audit_generation.py` (reversible timers; writes `audit_last_run.json`, gitignored)

### Tests executed

```
cd C:\Users\USER\Desktop\kiyub-buildify\backend
.\.venv\Scripts\python.exe -m pytest -v
```

**Result:** `111 passed in 460.88s` (`solver/tests` only). Tests were not edited to force pass.

### Commands executed

```
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe audit_generation.py
```

Audit script: isolated MOE / HouseGAN / RAG probes; `predict_floor_plan`; contribution A/B (`KIYUB_MULTI_STRATEGY=1` live MOE vs empty MOE vs `=0` hybrid); FastAPI `TestClient` `POST /api/generate/moe`. Env restored after each refine. No permanent config change. No new models or Ollama install.

### AI/ML components discovered

MOE, HouseGAN++ (GCN+decoder), HouseGAN GNN layers, RAG (Ollama embeddings), chat LLM (Ollama llama3.2), training scripts, HF Space duplicate. OR-Tools and the planning engine are **not** AI.

### Runtime evidence (live 20×30, office=yes)

- HTTP **200**, `status: valid`, `validated: true`, `selected_strategy: patio_oriented`, `irc_compliant: false`, quality **89**
- 15 rooms including garage **18×12 at (0,0)**, home_office **12×12 at (24,0)**, laundry_room, patio; no mudroom
- `expert_weights` present on HTTP body; geometry **identical** to empty-MOE compete
- HouseGAN: 0 layouts; RAG: 0 hits; GNN: not run; LLM: not called

### Failures

HouseGAN 404; no local `housegan_pp.pt`; Ollama refused; RAG cache empty; MOE boxes unused on default path.

### Performance measurements

See §11 and `backend/audit_last_run.json`.

### Exact recommendations

See §14. Highest leverage: stop treating unused/failed ML as the generator; then HouseGAN/RAG failure modes; then repeated CP-SAT.

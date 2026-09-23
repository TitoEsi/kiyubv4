# KIYUB AI integration (this slice)

**Date:** 20 September 2026  
**Scope:** Soft CP-SAT hints from a **validated HouseGAN candidate**, HouseGAN checkpoint/remote **availability** (Phase A), and cache-first RAG (Phase B).

This is a conceptual design tool. Quality scores are internal heuristics. `irc_compliant` on refined FloorPlans remains `false`.

## 1. Current AI architecture (after this slice)

```
Questionnaire
  → RoomProgram (canonical rooms)
  → Planning engine (site, zones, relationships, circulation, clusters, mass)
  → optional RAG retrieve (query embed only; skipped if cache empty / Ollama down)
  → optional HouseGAN candidate (only if generator == moe+housegan)
  → HintValidator (1:1 types, finite boxes, envelope mapping)
  → compete()  five strategies, SAME hints dict each
       evaluate_strategy: solve(AddHint) → cluster retry → hints=None retry
  → existing quality + select_evaluation
  → FloorPlan (OR-Tools geometry)
```

RAG hits are attached as payload metadata (`rag_available`, `rag_reason`, `rag_context`). They are **not** passed into planning, hints, `compete()`, or CP-SAT.

MOE expert weights are still copied onto the payload. Zone-fallback MOE room lists (`generator: "moe"`) are **not** hints.

## 2. HouseGAN checkpoint contract

Canonical file: `backend/moe/housegan/weights/housegan_pp.pt`.

Loader (`load_pretrained`) accepts, in order: `checkpoint["generator"]`, `checkpoint["model_state_dict"]`, or a raw `state_dict`. `load_state_dict(..., strict=False)` is the **existing** contract; it was not loosened in Phase A. An untrained `HouseGANGenerator()` is never used as a successful result.

`get_housegan_status()`:

| `source` | Meaning |
|---|---|
| `local_trained` | File loaded |
| `remote` | Opt-in remote returned layouts |
| `unavailable` | Missing checkpoint (and remote off or unused) |
| `load_failed` | File present but load raised |

`KIYUB_HOUSEGAN_REMOTE_ENABLED` defaults to **0**. The adapter `_run_remote` and `HOUSEGAN_HF_URL` remain; they are not called unless the flag is `1`. A failed remote is remembered for the process so `predict_floor_plan` variants do not 404 three times.

**Trained HouseGAN is not active** until `housegan_pp.pt` exists and loads.

## 3. HouseGAN fallback

Missing checkpoint → status `unavailable` / `checkpoint_missing` → `generate_layouts` returns `[]` with **no HTTP**. Zone fallback `generator: "moe"`. Hint validator: `ai_hints_used=False`, `not_housegan_candidate`. Five strategies still compete. OR-Tools still owns geometry.

## 4. MOE role

Implemented: expert weights + confidence on the HTTP body.  
Not used as canonical RoomProgram.  
Zone packing is **not** treated as a trained layout prior.

## 5. GNN role

Still internal to HouseGAN. Not a KIYUB relationship predictor. Inactive without a checkpoint.

## 6. RAG role (Phase B)

Cache-first. FastAPI startup calls `rag.load()` (disk only). Missing-chunk indexing is explicit: `python -m rag index`. Endpoint remains `POST /api/embeddings` with `nomic-embed-text:latest`.

Cache file `backend/embed_cache.json` (gitignored):

```json
{ "model": "nomic-embed-text:latest", "dimension": 768, "embeddings": { "<chunk_id>": [/* floats */] } }
```

Legacy `{chunk_id: vector}` files still load. Model mismatch ignores vectors; it does not delete the file.

| Cache | Startup | Generate |
|---|---|---|
| Empty / Ollama down | Immediate | `rag_available=false`, generation continues |
| Partial | Immediate (no embed) | Retrieve over cached IDs only |
| Complete | Immediate | One query embed + cosine search |

`retrieve()` never indexes the 39 knowledge chunks. Knowledge vectors come from the persistent cache. Observability on the **generation payload** (not FloorPlan rooms): `rag_available`, `rag_reason`, `rag_context`.

## 7. AI → CP-SAT hint contract

| Rule | Behavior |
|---|---|
| Soft only | `model.AddHint(x,y,w,h)` in `solver.py`. Not `Add`. |
| Same set | One validated dict passed to all five strategies |
| Invalid candidate | Entire compete uses `hints=None` |
| Per-strategy infeasible | Retry that strategy without hints (after existing cluster retry) |
| Selection | Unchanged `select_evaluation` / quality categories |
| Final geometry | Always OR-Tools layout (`generator: "ortools"`) |

Observability on the **generation payload** (not FloorPlan rooms): `ai_hints_used`, `ai_hints_reason`, plus RAG fields in §6.

## 8. Coordinate conversion

| | Source | Target |
|---|---|---|
| Units | Candidate plan feet (`totalWidth` × `totalHeight`) | Buildable envelope integer feet |
| Origin | Top-left of the candidate footprint | Top-left of envelope; `y=0` street/front |
| Scale | `scale_x = envelope.width / totalWidth`, `scale_y = envelope.depth / totalHeight` | Rounded ints, sizes ≥ 1, clamped into envelope |

If the source footprint is missing or a scaled room cannot fit in the envelope, the candidate is rejected.

## 9. Candidate validation

Reject unless:

- Plan `generator == "moe+housegan"` or `used_housegan is True`
- Type **multiset** equals RoomProgram (no extra pantry, no dropped office)
- Finite x/y; width/height ≥ 1
- 1:1 map onto `spec.id` by type order
- Boxes fit envelope after conversion

## 10. Failure / fallback

| Condition | Result |
|---|---|
| No plans / MOE fallback | `hints=None`, generate continues |
| Validation fail | `hints=None` |
| Hinted solve infeasible | Retry that strategy `hints=None` |
| All AI down | Deterministic planning + CP-SAT (existing path) |

## 11. Performance

This slice does not change CP-SAT time limits (8 s × 5). Default generate no longer calls the dead HouseGAN Space (remote flag off). When hints are `None`, extra hint-retry branches are not taken. RAG indexing is not on the generate path; a complete cache makes startup a disk read.

Live `predict_floor_plan` + `refine_generation` (20×30 m, 2 bed, office, 2-car, patio): HouseGAN `available=False` `checkpoint_missing` `remote_enabled=0`, 0 layouts, MOE `generator=['moe']`, `status=valid`, `ai_hints_used=False`, reason `not_housegan_candidate`, five strategies, winner `cluster`, FloorPlan `generator=ortools`, office/garage/living/kitchen preserved. No remote 404 calls.

Phase B timings (this host, Ollama warm): empty-cache index 39 chunks **24.8 s**; complete-cache `rag.load()` **13 ms**; partial-cache `rag.load()` **7 ms**; retrieve (one query embed) **0.59 s**; TestClient startup **0.085 s**; `POST /api/generate/moe` **42.7 s** with `rag_available=true`. Generation no longer waits on the 39-chunk job.

## 12. Implemented vs trained vs active

| Component | Implemented | Trained weights | Active on default generate |
|---|---|---|---|
| Hint validator + compete AddHint | Yes | n/a | Active only if a HouseGAN candidate validates |
| HouseGAN++ | Code yes | **No** (`housegan_pp.pt` missing) | **No** |
| GNN | Inside HouseGAN | Same missing file | **No** |
| MOE gating | Yes | Yes (`buildify_moe.pt`) | Weights echoed; geometry not hints |
| RAG | Yes | nomic-embed-text cache + Ollama query embed | Metadata only; skipped if cache empty |
| OR-Tools compete | Yes | n/a | **Yes** — final geometry |

Do not describe an untrained or missing HouseGAN as a working generator.

# KIYUB v4 GENERATION UPGRADE REPORT

Internal architectural-generation upgrade. Not professional architectural approval. Not Philippine National Building Code compliance.

## CURRENT PIPELINE

```text
Questionnaire
    → ArchitecturalSpecification
    → POST /api/generate/moe
    → MOE / optional HouseGAN
    → RoomProgram + SpatialPlan + BuildingMass
    → compete() candidates (spatial strategies + optional hint variant)
    → OR-Tools CP-SAT
    → Architectural evaluator (quality.py)
    → bounded refinement (winner only)
    → FloorPlan JSON
    → floorPlanToSceneDocument() → SceneDocument v2.0
```

Buildify still proposes. OR-Tools still produces final boxes. The evaluator ranks livability. HouseGAN remains optional.

## ARCHITECTURAL PROGRAM

[`backend/solver/architectural_program.py`](backend/solver/architectural_program.py) `ProgramSpace` now carries `preferred_area`, `max_area`, and `max_aspect_ratio` from a single [`ROOM_RULES`](backend/solver/room_rules.py) table. These are heuristics, not code values.

## SITE ANALYSIS

[`envelope.py`](backend/solver/envelope.py) still converts lot meters → buildable feet with placeholder 5 ft setbacks.

20 m × 30 m → lot ~65.6 × 98.4 ft → buildable ~55.6 × 88.4 ft.

Bubble `house_w` / `house_h` is capped to that envelope (no silent 36 ft minimum on a smaller lot). BuildingMass may grow up to 1.30× preferred program area toward a utilization band, and still cannot leave the envelope.

## ZONING

Unchanged public / private / service / arrival / circulation / outdoor planning zones. Kitchen remains dual `public` + `service`.

## RELATIONSHIP GRAPH

[`planning_graph.py`](backend/solver/planning_graph.py) now discourages bedroom ↔ foyer (soft avoid). Kitchen–dining stays required. Avoid pairs are soft CP-SAT wall-share penalties, not hard constraints.

## CANDIDATE GENERATION

`compete()` evaluates up to five spatial strategies **without** applying the same AI box to all of them, then appends **one** HouseGAN or MOE-fallback hint candidate when boxes exist.

`KIYUB_CANDIDATE_COUNT` (default 5) and `KIYUB_REFINEMENT_ITERS` (default 2) are configurable.

## OR-TOOLS

Hard constraints remain: envelope, mins, no overlap, required wall-shares, foyer/outdoor pins, vehicle access.

Soft objective no longer minimizes the indoor bounding box or hallway length. It now:

- pulls rooms toward preferred width/depth
- penalizes fat circulation short-sides only
- rewards preferred adjacencies and penalizes avoid wall-shares
- keeps mass-inside / overshoot as soft terms

Hard size cap is site-aware (`size_caps`), not `preferred + 6`.

## ARCHITECTURAL EVALUATOR

[`quality.py`](backend/solver/quality.py) `score_layout` adds:

- `room_proportion`
- `daylight_potential` (exterior-edge heuristic, not simulation)
- `service_efficiency`
- `furniture_clearance` (category weight)
- `site_utilization`
- `diagnostics`

Ranking still uses this scorer only. [`scoring.py`](backend/scoring.py) `/api/score` is unchanged and is not used for selection.

## EVALUATION METRICS

Weighted categories in `QUALITY_WEIGHTS`. Access/arrival still outrank leftover packing. Occupancy still peaks near 78% and penalizes crush above 92%.

## REFINEMENT

After the winner is chosen, up to two deterministic re-solves bump mins on cramped / poorly proportioned rooms. Best valid result is kept. No LLM in this loop.

## POST PROCESSING

Doors and furniture envelopes still run after a feasible solve. A blocking fallback bed is no longer planted when no clearance-safe placement exists — that is a usability penalty, not geometric infeasibility.

## SCENEDOCUMENT

Existing [`floorPlanToSceneDocument`](frontend/src/scene-graph/adapters/floorplan-to-scene-document.ts) is preserved (v2.0). Site remains questionnaire meters. Room metadata now records `daylightPotential` / `windowOpportunity`. Walls and openings are still not fabricated.

## HOUSEGAN STATUS

Unchanged: unavailable without `housegan_pp.pt`. Fallback spatial candidates still enter the same evaluator. `generation_debug.housegan.status` is `active` or `unavailable`.

## 20 × 30 TEST

Regression coverage:

- lot meters through envelope / bubble / mass / solve / FloorPlan
- 3 bedrooms, 2 bathrooms, living, dining, kitchen
- no overlap, inside envelope
- aspect heuristics, diagnostics present
- SceneDocument site 20 × 30 m

## BEFORE VS AFTER

The cramped-layout bottleneck was CP-SAT packing (`minimize bbox` + `preferred+6` + hallway squeeze), not missing Buildify.

| Mechanism | Before | After |
|---|---|---|
| Room size cap | preferred + 6 ft | site-aware growth (~1.6× / +12 ft, envelope-bounded) |
| Objective | minimize bbox + hall span | preferred sizes, avoid crush, soft adjacency |
| Candidates | 5 strategies, HouseGAN ignored unless every strategy got the same hint | 5 spatial + 1 optional hint variant |
| Evaluator | feasibility-heavy; `shape` only | proportion, daylight potential, service, utilization, diagnostics |
| Refinement | none | max 2 winner-only re-solves |
| Bubble footprint | `W = max(W, 36)` even on smaller lots | capped to buildable envelope |

Measurable generation time remains on the order of one `compete()` pass (~5 × 8 s) plus optional winner refinement. Exact wall-clock depends on machine and HouseGAN availability.

## TEST RESULTS

Frontend: vitest, 11 passed.

Backend: existing planning/solver tests plus new evaluator, program, lot-propagation, and 20×30 generation tests. Intentional test update: `test_compete_forwards_same_hints_to_every_strategy` → `test_compete_uses_spatial_candidates_and_one_hint_variant` because applying one HouseGAN box to every strategy was the failure mode this phase removes.

## FILES CREATED

- `backend/solver/refinement.py`
- `backend/solver/tests/test_architectural_evaluator.py`
- `backend/solver/tests/test_program_relationships.py`
- `backend/solver/tests/test_lot_propagation.py`
- `backend/solver/tests/test_generation_upgrade.py`
- `docs/KIYUB_V4_GENERATION_UPGRADE_REPORT.md`

## FILES MODIFIED

- `backend/solver/room_rules.py`, `models.py`, `room_program.py`, `architectural_program.py`
- `backend/solver/planning_graph.py`, `spatial_planner.py`, `constraints.py`, `objective.py`
- `backend/solver/quality.py`, `building_mass.py`, `solver.py`, `strategy_competition.py`, `pipeline.py`
- `backend/solver/furniture.py`, `backend/moe/housegan/bubble_diagram.py`, `backend/main.py`
- `backend/solver/tests/test_ai_hints.py`
- `frontend/src/scene-graph/adapters/floorplan-to-scene-document.ts` (+ test)

## KNOWN LIMITATIONS

- HouseGAN still optional without a checkpoint.
- Geometry is still single-storey; `stories` only scales feasibility area.
- Setbacks remain conceptual placeholders.
- Daylight is exterior-edge potential, not simulation.
- SceneDocument still has empty `walls` / `openings` arrays.
- Evaluator scores are internal heuristics, not professional certification.

## NEXT RECOMMENDED PHASE

Thin wall/opening emission into SceneDocument from solved geometry; optional second-storey massing; verified Philippine setback table behind a separate `CodeComplianceEvaluator`.

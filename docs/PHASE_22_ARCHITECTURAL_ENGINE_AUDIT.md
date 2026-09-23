# Phase 22 — Architectural Engine Audit

Internal notes. Not professional architectural approval. Not Philippine National Building Code compliance.

## Current generation pipeline

```text
POST /api/generate/moe
  → moe.predict_floor_plan
      HouseGAN++ official Generator (strict=True) or zone fallback
  → solver.pipeline.refine_generation
      RoomProgram → ArchitecturalProgram → SpatialPlan → BuildingMass
      hints_from_ai_candidate (generator == moe+housegan)
      compete()  ≤5 spatial + 1 HouseGAN/MOE hint
      OR-Tools CP-SAT
      doors / furniture / validate / quality.py
      refine_result (winner only)
  → FloorPlan JSON
  → floorPlanToSceneDocument (client)
```

## Existing relevant modules

| Need | File | Status |
|---|---|---|
| ArchitecturalProgram | `backend/solver/architectural_program.py` | Exists; no validate_program |
| RoomProgram / ROOM_RULES | `room_program.py`, `room_rules.py` | Exists |
| Soft graph | `planning_graph.py` | Hard-coded edges |
| Hard topology | `topology.py` | Duplicate hard-coded edges |
| Zoning / strategies | `spatial_planner.py` | 5 + cluster |
| PH planning profile | `planning_profile.py` | Assumptions, not code |
| Circulation | `circulation.py` | Post-solve analysis |
| Doors | `doors.py` | After solve |
| Furniture | `furniture.py` | Usability only |
| Evaluator | `quality.py` | Soft weighted score |
| compete() | `strategy_competition.py` | 5+1 candidates |
| HouseGAN official | `moe/housegan/official_generator.py` | Working, strict=True |
| SceneDocument walls | `floorplan-to-scene-document.ts` | Schema yes, emit empty |

## Existing constraints

Hard CP-SAT: envelope, mins, no overlap, foyer/outdoor pins, vehicle access, unconditional wall-share, OR-groups for access.

Soft: preferred sizes, hallway short-side fatness, zone bands, mass inside, avoid pairs.

Hallway cap `HALL_LENGTH_GROWTH_FT = 24` allows both axes to grow to ~40 ft → ~800 sf corridor.

## Existing evaluator metrics

QUALITY_WEIGHTS includes feasibility, circulation, adjacency, zoning, proportion, daylight_potential, service_efficiency, furniture_clearance, site_utilization, room_usability. Hard failures live in `validator.py` and `selection_key` prefers `valid`.

## Existing HouseGAN++ flow

`generate_layouts` → official Conv-MPN → masks_to_bboxes → room dicts → `_place_rooms_housegan` tags `moe+housegan` → `hints_from_ai_candidate` → compete extra candidate. `given_m` is unconstrained. Missing checkpoint returns `[]`.

## Existing OR-Tools flow

`solve()` uses SpatialPlan topology + hints. Final geometry is always CP-SAT, not HouseGAN boxes.

## Reuse vs add

**Reuse:** ArchitecturalProgram, SpatialPlan strategies, compete(), quality.py, doors.py, furniture.py, official HouseGAN, SceneDocument schema.

**Add:** unified RoomGraph, program validation, HouseGAN mask refine, hallway area cap + circulation_ratio, walls.py, window openings, modular ruleset, debug fields, SceneDocument mapping of engine-emitted walls/openings.

## Files to modify / add

Modify: `architectural_program.py`, `topology.py`, `planning_graph.py`, `spatial_planner.py`, `strategy_competition.py`, `pipeline.py`, `room_rules.py`, `objective.py`, `validator.py`, `quality.py`, `circulation.py`, `adapter.py`, `ai_hints.py`, `main.py`, `official_adapter.py`, `inference.py`, `floorplan.ts`, `floorplan-to-scene-document.ts`.

Add: `room_graph.py`, `walls.py`, `openings.py`, `ruleset/`, tests, `docs/PHASE_22_ARCHITECTURAL_ENGINE.md`.

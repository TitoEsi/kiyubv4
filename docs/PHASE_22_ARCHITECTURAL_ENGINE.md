# Phase 22 — Architectural Constraint and Topology Engine

Internal architecture notes. Not professional architectural approval. Not Philippine NBC or IRC certification.

## What this layer is

Phase 22 extends the existing KIYUB generation path. It does not replace HouseGAN++, OR-Tools, `compete()`, or `quality.py`.

```text
Questionnaire → ArchitecturalSpecification → RoomProgram
  → ArchitecturalProgram → unified RoomGraph
  → SpatialPlan zoning archetypes (cheap-filtered)
  → HouseGAN++ official prior (optional given_m refine)
  → compete() ≤5 spatial + 1 HouseGAN/MOE hint
  → OR-Tools geometry (hallway area/short-side caps)
  → walls / doors / windows
  → hard validator then quality.py
  → FloorPlan → SceneDocument v2.0
```

## What was added

- `validate_program()` on `ArchitecturalProgram`.
- Unified `RoomGraph` compiled once for `topology.py` and `planning_graph.py`.
- Extra SpatialPlan archetypes `rear_private` and `living_core`. `COMPETITION_STRATEGIES` order is unchanged.
- Cheap candidate filter (required rooms, no bedrooms in the service zone). `compete()` still solves at most 5 spatial + 1 hint.
- HouseGAN `given_m` iterative refine: unconstrained first pass, then freeze high-occupancy rooms. `strict=True`. Missing checkpoint still returns `[]`.
- Hallway hard caps: one axis near 4–6 ft, area ≤ 240 sf. `circulation_ratio` is a hard reject above 0.22 and a soft quality term.
- `walls.py` and `openings.py` after a valid layout. `doors.py` is unchanged. SceneDocument maps engine-emitted walls/openings and stays empty when the engine emits none.
- Modular `backend/solver/ruleset/` with PASS / FAIL / WARNING / UNKNOWN. Unverified NBC/IRC items are UNKNOWN. `irc_compliant` is never set true from heuristics.
- `compete()` and `_generation_debug` now include program, topology, hard_failures, objective_breakdown, circulation_ratio, HouseGAN counts, timings.

## What this does not guarantee

- Legal NBC, IRC, or any other code compliance.
- That HouseGAN boxes are final geometry. They remain hints.
- That every lot and program is feasible. Invalid candidates cannot win on aesthetic score.
- Daylight, ventilation, structural, or fire-rated wall correctness. Windows are a placement heuristic.
- That extra archetypes are always solved. Only the top N cheap-filtered SpatialPlans plus one hint enter CP-SAT.

## Hallway failure mode (fixed)

`HALL_LENGTH_GROWTH_FT = 24` used to raise **both** hallway axes, which allowed ~40×40 / 800 sf corridors. Length growth is still allowed on one axis. Short side and area are hard-capped.

If a live layout is still poor, inspect the layer named in `generation_debug` (topology vs hallway cap vs objective vs evaluator). Do not hide it with weight hacks.

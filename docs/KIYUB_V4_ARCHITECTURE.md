# KIYUB v4 architecture

KIYUB-Buildify is no longer the product name. **KIYUB v4** is the application. **Buildify** remains an external-style generation **component** (MOE, bubble diagrams, HouseGAN) inside this repository.

```text
                    KIYUB v4
                       │
                       ▼
          ArchitecturalSpecification
                       │
                       ▼
                 Site Analysis
                       │
                       ▼
              Architectural Program
                       │
                       ▼
                    Zoning                 (planned/future)
                       │
                       ▼
          Spatial Relationship Graph       (planned/future)
                       │
                       ▼
                 Buildify Adapter
                       │
                       ▼
                 Buildify / HouseGAN
                       │
                       ▼
              Candidate Layouts
                       │
                       ▼
                  OR-Tools
                       │
                       ▼
            Architectural Evaluator        (planned/future)
                       │
                       ▼
                   Refinement              (planned/future)
                       │
                       ▼
               Post Processing             (planned/future)
                       │
                       ▼
             SceneDocument v2.0
                       │
                       ▼
                  KIYUB Editor
```

## Responsibilities

| Component | Role |
|---|---|
| ArchitecturalSpecification | What the user wants: lot, floors, rooms, preferences |
| Buildify | Spatial/topological possibilities (MOE sizing, bubble/adjacency) |
| HouseGAN | Learned candidate organization when a checkpoint is present |
| OR-Tools | Geometric constraint solving; final boxes |
| FloorPlanResult | Generated plan in solver units (feet, buildable envelope) |
| SceneDocument v2.0 | Metric editor-ready scene; **site is the user lot in meters** |

## Implemented today

Questionnaire → specification → constraints → Buildify MOE (HouseGAN if available) → OR-Tools `compete()` → FloorPlan JSON → SceneDocument conversion on the client → 2D/3D editor.

## Planned / future

Architectural evaluator, refinement loop, advanced zoning, spatial relationship graph beyond the existing bubble matrix, post-processing for walls/windows/furniture, livability scoring, daylight/furniture/circulation upgrades.

Do not treat internal quality scores as professional certification. `irc_compliant` on refined plans remains false.

# KIYUB v3 to v4

## KIYUB v3

Location: `C:\Users\USER\Desktop\kiyub-v3`

Frozen historical/reference Next.js application and experimental generation-engine. Not the active product. This migration does not modify v3.

## KIYUB-Buildify

The Git repository at `C:\Users\USER\Desktop\kiyub-buildify` (remote still `sarvanithin/Buildify.git`) is the working FastAPI + Vite generation app. It is now the KIYUB v4 product identity.

## KIYUB v4

The same repository, renamed in product identity. Buildify remains the topology/HouseGAN/MOE component.

## Preserved

- Questionnaire (lot shape, width, depth, rooms)
- ArchitecturalSpecification converters
- Buildify MOE / bubble / HouseGAN path
- OR-Tools `compete()`
- FloorPlan JSON
- SceneDocument v2.0 types + FloorPlan → scene converter (ported types only)
- Existing solver and converter tests

## Intentionally deferred

- Maket-inspired architectural evaluator
- Candidate ranking improvements
- Refinement loop
- Advanced daylight evaluation
- Furniture-aware optimization
- Improved circulation optimization

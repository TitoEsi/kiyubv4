# KIYUB v4 HOUSEGAN++ AUDIT

Internal generation-path audit. Not professional architectural approval.

## CLASSIFICATION

**C. CALLED BUT FALLING BACK**

(At audit time the trained model itself was source-only: no usable checkpoint for the KIYUB reimplementation.)

```text
code exists                    YES
model loads                    NO  (checkpoint_missing at audit)
model runs                     NO  (never reached _run_local)
output enters pipeline         NO  (generate_layouts returned [])
output affects browser plan    NO  (winner source=spatial)
```

**HouseGAN++ WAS NOT actually functioning and being used during browser floor-plan generation at audit time.**

---

## HOUSEGAN++ SOURCE

```text
Location:      backend/moe/housegan/
Implementation: KIYUB reimplementation (Linear GCN + ConvTranspose masks)
                plus (after the follow-up task) an official Conv-MPN backend
Entry point:   moe.housegan.inference.generate_layouts
               called from moe.inference._place_rooms_housegan
```

---

## CHECKPOINT

```text
HOUSEGAN++ STATUS = UNAVAILABLE (audit time)
REASON            = CHECKPOINT MISSING

Checkpoint expected: backend/moe/housegan/weights/housegan_pp.pt
Official file:       ennauata/houseganpp checkpoints/pretrained.pth (~2.56 MB)
Checkpoint found:    NO .pt/.pth files in the repo
Exact path:          (did not exist)
Model format:        expected PyTorch state_dict
```

Do not claim HouseGAN++ is active merely because source code exists.

---

## MODEL LOADING (audit)

```text
HouseGAN++ model load: FAIL
Device:                load_pretrained defaulted to CPU; never reached
PyTorch:               requirements torch>=2.1.0
CUDA:                  unused by HouseGAN path
Error:                 _probe_local set reason=checkpoint_missing
```

---

## DIRECT INFERENCE (audit)

```text
Inference:          FAIL / empty
Runtime:            n/a
Output:             []
Candidate created:  NO
```

Unit proof: `backend/solver/tests/test_housegan_availability.py`
`test_missing_checkpoint_unavailable_no_httpx` asserts `generate_layouts(...) == []`.

---

## LIVE PIPELINE

```text
POST /api/generate/moe
  → main.generate_moe
  → moe.inference.predict_floor_plan
      → _place_rooms_housegan → housegan.inference.generate_layouts
      → if empty: _place_rooms_architectural
  → solver.pipeline.refine_generation
      → hints_from_ai_candidate (HouseGAN only if generator == moe+housegan)
      → strategy_competition.compete
      → solver.solve (OR-Tools)
      → quality.py evaluator
  → FloorPlan generator=ortools → SceneDocument
```

Live uvicorn `generation_debug` (square 20 m × 20 m, 3BR/2BA):

```text
housegan.available = false
housegan.source    = unavailable
housegan.reason    = checkpoint_missing
buildify_moe.generators = []
buildify_moe.plan_count = 0
ortools.selected_strategy = service_side
ortools.selected_source   = spatial
ortools.strategy_count    = 5
ortools.plan_generator    = ortools
timings.housegan_s        = null
```

---

## CANDIDATE FLOW (audit)

```text
HouseGAN++ output:  []
        ↓
KIYUB candidate:    none (no moe+housegan plan)
        ↓
OR-Tools:           5 spatial strategies only
        ↓
Evaluator:          scores spatial candidates
        ↓
Winner:             service_side / source=spatial
```

Fate: **not generated**. Packed browser plans were CP-SAT spatial packing, not learned HouseGAN++ geometry.

`compete()` remains: up to 5 spatial + 1 optional hint. Hint is HouseGAN only when `hints_from_ai_candidate` succeeds.

---

## FALLBACK

```text
Trigger:            checkpoint missing (KIYUB_HOUSEGAN_REMOTE_ENABLED default 0)
Fallback generator: MOE architectural zone placement, then spatial compete()
Current behavior:   HouseGAN++ UNAVAILABLE, not labeled as HouseGAN
```

---

## BROWSER TEST (audit)

```text
Input:     20 × 20 m square (live log; same path as 20 × 30 m)
           1 floor, 3BR / 2BA, living/dining/kitchen
HouseGAN++ status:     unavailable
HouseGAN++ invoked:    yes (inside predict_floor_plan)
HouseGAN++ candidate:  none
Candidate processed:   no
Candidate evaluated:   no
Candidate selected:    no
```

---

## PERFORMANCE (audit live request)

```text
Model load:   not performed
Inference:    null
OR-Tools:     40.269 s compete
Evaluator:    included in compete / refinement
Total:        48.33 s
```

Load policy in code: once per process if a checkpoint exists; a miss is cached via `_local_checked`.

---

## IMPORTANT FINDING

**HouseGAN++ IS NOT actually functioning and being used during browser floor-plan generation** (audit-time truth).

The pipeline calls it, the expected trained file is absent, the KIYUB `HouseGANGenerator` cannot load official HouseGAN++ weights (`strict=False` is not compatibility), inference returns no layouts, and the live winner is spatial OR-Tools.

See [HOUSEGANPP_IMPLEMENTATION.md](HOUSEGANPP_IMPLEMENTATION.md) for architecture mismatch and the official-backend follow-up.

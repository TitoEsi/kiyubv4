# HouseGAN++ implementation (KIYUB vs official)

Internal notes for local/research use. Not professional architectural approval.

Official House-GAN++ code and weights are **GPL-3** with a header that the original repository restricts use to **research purposes**. KIYUB vendors a minimal generator (Conv-MPN `Generator` + `CMP`) from [ennauata/houseganpp](https://github.com/ennauata/houseganpp) (Nauata et al., CVPR 2021). Do not commit checkpoints. Do not treat `strict=False` as compatibility.

---

## KIYUB reimplementation (`HouseGANGenerator`)

Files:

- [`backend/moe/housegan/model.py`](../backend/moe/housegan/model.py)
- [`backend/moe/housegan/inference.py`](../backend/moe/housegan/inference.py)
- [`backend/moe/housegan/bubble_diagram.py`](../backend/moe/housegan/bubble_diagram.py)

This network is **not** the official HouseGAN++ generator. It remains in-tree so compatibility tests can prove official weights do not load into it.

| Item | Value |
|---|---|
| Type encoding | `nn.Embedding(19, 64)`, integer `room_types (N,)` |
| Adjacency | dense `(N, N)` float |
| Latent | `z (N, 128)` |
| Graph | 3-layer Linear GCN (`GraphConvLayer` + LayerNorm + ReLU), dim 128 |
| Init decoder | `Linear → 4×4×256`, ConvTranspose `256→128→64→32→1`, **sigmoid** |
| Refine | separate GRN (`noise+64+4` mask stats) + decoder, 3 steps |
| Output | `(N, 1, 64, 64)` |
| Constants | `NUM_ROOM_TYPES=18`, `NOISE_DIM=128`, `GRAPH_DIM=128`, `MASK_SIZE=64` |
| Historical loader | `load_state_dict(..., strict=False)` — **bug, not compatibility** |

Expected KIYUB `state_dict` key prefixes: `type_embed`, `grn_init`, `decoder_init`, `grn_refine`, `decoder_refine`.

KIYUB `HG_TYPES` (not official RPLAN): living=1, master=2, kitchen=3, bath=4, dining=5, bedroom=6, office=7, guest=8, balcony=9, foyer=10, closet=11, laundry=12, hallway=13, garage=14, mudroom=15.

---

## Official HouseGAN++ (`Generator` / Conv-MPN)

Source: `ennauata/houseganpp` `models/models.py` `class Generator`.

KIYUB copy: [`backend/moe/housegan/official_generator.py`](../backend/moe/housegan/official_generator.py).

| Item | Value |
|---|---|
| Backbone | Conv-MPN (`CMP`) on edge list |
| First layer | `Linear(146, 16×8×8)` = 128 noise + 18-d one-hot |
| Condition | `given_m (N, 2, 64, 64)` mask + validity |
| Edges | `given_w (E, 3)` `[src, sign, dst]` (pos/neg pooling) |
| Types | `given_y (N, 18)` one-hot |
| Upsample | 8→16→32→64, CMP at each scale |
| Decoder | conv `16→256→128→1`, **tanh** |
| Output | `(N, 64, 64)` |
| Checkpoint | raw `state_dict`, `strict=True` |

Official RPLAN `ROOM_CLASS` (1-indexed; one-hot index = id−1): living=1, kitchen=2, bedroom=3, bathroom=4, balcony=5, entrance=6, dining=7, study=8, storage=10, front_door=15, unknown=16, interior_door=17.

---

## Can official weights load into KIYUB `HouseGANGenerator`?

**NO.**

Mismatches: Linear GCN vs Conv-MPN; embedding vs 18-d one-hot concat; `N×N` adj vs `(E,3)` edges; no condition image vs `64×64×2`; ConvTranspose+sigmoid vs conv+tanh; disjoint `state_dict` keys. Partial load with `strict=False` would silently drop every official weight.

---

## Checkpoint (local, gitignored)

```text
Source:     https://github.com/ennauata/houseganpp/blob/main/checkpoints/pretrained.pth
Download:   https://raw.githubusercontent.com/ennauata/houseganpp/main/checkpoints/pretrained.pth
Filename:   pretrained.pth  (~2,561,009 bytes)
Format:     raw generator state_dict (keys such as l1.0.weight, cmp_1.*, decoder.*)
License:    GPL-3, research-only (upstream header)
Do not:     commit the file, auto-download inside POST /api/generate/moe, download RPLAN
```

One-time local download into gitignored weights:

```text
mkdir backend\moe\housegan\weights
curl -L -o backend\moe\housegan\weights\pretrained.pth https://raw.githubusercontent.com/ennauata/houseganpp/main/checkpoints/pretrained.pth
```

Aliases probed in order: `pretrained.pth`, then `housegan_pp.pt`.

RPLAN is required to **train**, not to run this bubble-diagram adapter.

Official `requirements.txt` pins torch 1.8.1. KIYUB uses `torch>=2.1`. Do not downgrade; load on the current torch and record warnings.

---

## Production path (after official backend)

```text
BubbleDiagram
  → pack_official_inputs (type map, edges, unconstrained masks)
  → Official Generator (pretrained.pth, strict=True)
  → tanh masks → (N,1,64,64)
  → masks_to_bboxes → scale_bboxes_to_feet → US conventions
  → generate_layouts room dicts
  → _place_rooms_housegan (generator moe+housegan)
  → hints_from_ai_candidate → compete() extra hint
  → OR-Tools / evaluator unchanged
```

If the checkpoint is missing: `generate_layouts` returns `[]` (same fallback as before). Untrained networks are never used.

Device: `map_location` CPU by default; CUDA only if `torch.cuda.is_available()`. Model is loaded once per process.

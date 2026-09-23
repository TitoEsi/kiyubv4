"""
HouseGAN++ Inference — generates spatial floor plan layouts from bubble diagrams.

Pipeline:
  BubbleDiagram → HouseGAN++ generator → binary masks → bounding boxes
               → scale to real feet → US house post-processing

Two modes:
  1. Local:  loads model weights locally (backend/moe/housegan/weights/)
  2. Remote: calls HuggingFace Space API endpoint (free ZeroGPU)
"""
from __future__ import annotations

import os
import json
import uuid
import math
import time
import httpx
import numpy as np
import torch
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from .bubble_diagram import BubbleDiagram, BubbleRoom
from .model import MASK_SIZE, NUM_ROOM_TYPES
from .official_adapter import official_masks_to_nchw, pack_official_inputs
from .official_generator import Generator as OfficialGenerator

# ── Constants ─────────────────────────────────────────────────────────────────
WEIGHTS_DIR   = Path(__file__).parent / "weights"
CHECKPOINT_NAME = "pretrained.pth"
CHECKPOINT_ALIASES = ("pretrained.pth", "housegan_pp.pt")
HF_SPACE_URL  = os.getenv(
    "HOUSEGAN_HF_URL",
    "https://buildify-housegan.hf.space/api/predict"
)
WALL_BUFFER   = 0.5   # ft buffer from house edge


@dataclass
class HouseGANStatus:
    """Trained-model availability. Importing the package is not the same as trained."""

    available: bool
    source: str  # local_trained | remote | unavailable | load_failed
    checkpoint_path: str | None
    reason: str | None

    def as_dict(self) -> dict:
        return {
            "available": self.available,
            "source": self.source,
            "checkpoint_path": self.checkpoint_path,
            "reason": self.reason,
        }


def checkpoint_path() -> Path:
    """First existing alias, else the official pretrained.pth path (may be missing)."""
    for name in CHECKPOINT_ALIASES:
        candidate = WEIGHTS_DIR / name
        if candidate.exists():
            return candidate
    return WEIGHTS_DIR / CHECKPOINT_NAME


def housegan_device() -> str:
    return "cuda" if torch.cuda.is_available() else "cpu"


def remote_enabled() -> bool:
    return os.environ.get("KIYUB_HOUSEGAN_REMOTE_ENABLED", "0").strip() not in (
        "", "0", "false", "False", "no", "NO",
    )


# ── Mask → Bounding Box ──────────────────────────────────────────────────────

def masks_to_bboxes(masks: np.ndarray,
                    threshold: float = 0.5) -> List[Optional[Tuple[float,float,float,float]]]:
    """
    Convert (N, 1, 64, 64) float masks to bounding boxes.
    Returns list of (x1, y1, x2, y2) normalised 0-1, or None if empty mask.
    """
    bboxes = []
    for mask in masks:
        m = (mask[0] >= threshold).astype(np.uint8)
        ys, xs = np.where(m)
        if len(xs) == 0:
            bboxes.append(None)
        else:
            x1 = float(xs.min()) / MASK_SIZE
            y1 = float(ys.min()) / MASK_SIZE
            x2 = float(xs.max() + 1) / MASK_SIZE
            y2 = float(ys.max() + 1) / MASK_SIZE
            bboxes.append((x1, y1, x2, y2))
    return bboxes


def scale_bboxes_to_feet(bboxes: List[Optional[Tuple]],
                          rooms: List[BubbleRoom],
                          W: float, H: float) -> List[Dict]:
    """
    Scale normalised bounding boxes to real-world feet.
    Enforces minimum dimensions from IRC specs.
    Returns list of room dicts compatible with floor plan JSON.
    """
    placed = []
    for room, bbox in zip(rooms, bboxes):
        if bbox is None:
            # Fallback: place in a default position
            x, y = WALL_BUFFER, WALL_BUFFER
            w = max(room.min_w, 10.0)
            h = max(room.min_h, 10.0)
        else:
            x1, y1, x2, y2 = bbox
            x = round(x1 * W, 1)
            y = round(y1 * H, 1)
            w = round((x2 - x1) * W, 1)
            h = round((y2 - y1) * H, 1)

            # Enforce IRC minimums
            w = max(w, room.min_w)
            h = max(h, room.min_h)

            # Clamp to footprint
            x = max(WALL_BUFFER, min(x, W - w - WALL_BUFFER))
            y = max(WALL_BUFFER, min(y, H - h - WALL_BUFFER))

        placed.append({
            "id":     room.id,
            "name":   room.name,
            "type":   room.buildify_type,
            "x":      x,
            "y":      y,
            "width":  w,
            "height": h,
            "zone":   room.zone,
        })
    return placed


# ── US House Post-Processor ───────────────────────────────────────────────────

def apply_us_conventions(placed: List[Dict], W: float, H: float) -> List[Dict]:
    """
    Apply US residential floor plan conventions on top of HouseGAN output.

    HouseGAN was trained on Chinese apartments (no garages, different culture).
    This fixes the most common issues:
      1. Garage → forced to front-left (y ≈ 0)
      2. Foyer → adjacent to garage, on exterior wall
      3. Patio/Deck → forced to rear (y ≈ H)
      4. Bedrooms → pushed toward the back half of the house
    """
    id_map = {r["id"]: r for r in placed}
    idx_map = {r["id"]: i for i, r in enumerate(placed)}

    def move(rid: str, target_y: float, target_x: Optional[float] = None):
        if rid not in id_map: return
        r = id_map[rid]
        r["y"] = round(max(WALL_BUFFER, min(target_y, H - r["height"] - WALL_BUFFER)), 1)
        if target_x is not None:
            r["x"] = round(max(WALL_BUFFER, min(target_x, W - r["width"] - WALL_BUFFER)), 1)

    # Garage: top-left corner
    if "garage" in id_map:
        g = id_map["garage"]
        g["x"], g["y"] = WALL_BUFFER, WALL_BUFFER

        # Mudroom: right of garage
        if "mudroom" in id_map:
            m = id_map["mudroom"]
            m["x"] = round(g["x"] + g["width"] + 0.2, 1)
            m["y"] = WALL_BUFFER

    # Foyer: front, right of garage/mudroom
    if "foyer" in id_map:
        ref_x = WALL_BUFFER
        if "mudroom" in id_map:
            m = id_map["mudroom"]
            ref_x = m["x"] + m["width"] + 0.2
        elif "garage" in id_map:
            g = id_map["garage"]
            ref_x = g["x"] + g["width"] + 0.2
        move("foyer", WALL_BUFFER, ref_x)

    # Patio / Deck: rear (bottom of plan)
    for oid in ("patio", "deck"):
        if oid in id_map:
            r = id_map[oid]
            r["y"] = round(H - r["height"] - WALL_BUFFER, 1)

    # Bedrooms: back half
    for rid, r in id_map.items():
        if r["type"] in ("master_bedroom", "bedroom") and r["y"] < H * 0.4:
            r["y"] = round(H * 0.55, 1)

    return placed


def resolve_overlaps(placed: List[Dict], W: float, H: float,
                     max_iters: int = 20) -> List[Dict]:
    """
    Simple iterative overlap resolver: push overlapping rooms apart.
    Not perfect but good enough for post-HouseGAN cleanup.
    """
    def overlap(a, b):
        return (a["x"] < b["x"] + b["width"] and
                a["x"] + a["width"] > b["x"] and
                a["y"] < b["y"] + b["height"] and
                a["y"] + a["height"] > b["y"])

    def area_overlap(a, b):
        ox = min(a["x"]+a["width"], b["x"]+b["width"]) - max(a["x"], b["x"])
        oy = min(a["y"]+a["height"], b["y"]+b["height"]) - max(a["y"], b["y"])
        return max(0, ox) * max(0, oy)

    for _ in range(max_iters):
        moved = False
        for i, a in enumerate(placed):
            for j, b in enumerate(placed):
                if i >= j: continue
                if not overlap(a, b): continue

                # Push the smaller room away from the larger
                ao = area_overlap(a, b)
                if ao < 0.5: continue

                cx_a = a["x"] + a["width"]  / 2
                cx_b = b["x"] + b["width"]  / 2
                cy_a = a["y"] + a["height"] / 2
                cy_b = b["y"] + b["height"] / 2

                dx, dy = cx_b - cx_a, cy_b - cy_a
                if abs(dx) > abs(dy):
                    # Push horizontally
                    push = (a["width"] + b["width"]) / 2 - abs(dx) + 0.2
                    if dx > 0:
                        b["x"] = round(min(b["x"] + push, W - b["width"]), 1)
                    else:
                        b["x"] = round(max(b["x"] - push, 0), 1)
                else:
                    # Push vertically
                    push = (a["height"] + b["height"]) / 2 - abs(dy) + 0.2
                    if dy > 0:
                        b["y"] = round(min(b["y"] + push, H - b["height"]), 1)
                    else:
                        b["y"] = round(max(b["y"] - push, 0), 1)
                moved = True
        if not moved:
            break

    return placed


# ── Local Inference ───────────────────────────────────────────────────────────

_cached_model: Optional[OfficialGenerator] = None
_status: Optional[HouseGANStatus] = None
_local_checked: bool = False
_remote_attempted: bool = False
_remote_ok: bool = False
_logged_status: bool = False


def reset_housegan_runtime() -> None:
    """Test helper: clear process caches. Not used in generation."""
    global _cached_model, _status, _local_checked
    global _remote_attempted, _remote_ok, _logged_status
    _cached_model = None
    _status = None
    _local_checked = False
    _remote_attempted = False
    _remote_ok = False
    _logged_status = False


def _set_status(available: bool, source: str, reason: str | None) -> HouseGANStatus:
    global _status
    _status = HouseGANStatus(
        available=available,
        source=source,
        checkpoint_path=str(checkpoint_path()),
        reason=reason,
    )
    return _status


def _probe_local() -> Optional[OfficialGenerator]:
    """Load trained official weights once. Never treat a random network as trained."""
    global _cached_model, _local_checked
    if _cached_model is not None:
        _set_status(True, "local_trained", None)
        return _cached_model
    if _local_checked:
        return None
    _local_checked = True
    path = checkpoint_path()
    if not path.exists():
        _set_status(False, "unavailable", "checkpoint_missing")
        return None
    try:
        from .model import load_pretrained
        model = load_pretrained(str(path), device=housegan_device())
        _cached_model = model
        _set_status(True, "local_trained", None)
        return model
    except Exception as e:
        print(f"[HouseGAN] Failed to load local weights: {e}")
        _cached_model = None
        _set_status(False, "load_failed", f"load_failed: {e}")
        return None


def get_housegan_status() -> HouseGANStatus:
    """Local checkpoint probe only. Does not call the remote Space."""
    if _cached_model is not None:
        return _set_status(True, "local_trained", None)
    if _remote_ok and _status and _status.source == "remote":
        return _status
    _probe_local()
    if _status is not None:
        return _status
    return _set_status(False, "unavailable", "checkpoint_missing")


def _log_status_once() -> None:
    global _logged_status
    if _logged_status:
        return
    _logged_status = True
    st = get_housegan_status()
    print(
        f"[HouseGAN] available={st.available} source={st.source} "
        f"reason={st.reason} remote_enabled={int(remote_enabled())}"
    )


def _get_local_model() -> Optional[OfficialGenerator]:
    """Load HouseGAN++ from local trained weights if available."""
    return _probe_local()


def _high_occupancy_nodes(masks: torch.Tensor, threshold: float = 0.25) -> list[int]:
    """Rooms whose tanh occupancy fraction is high enough to freeze for a refine pass."""
    occ = masks
    if occ.dim() == 4:
        occ = occ[:, 0]
    frac = (occ > 0).float().mean(dim=(1, 2))
    return [i for i, v in enumerate(frac.tolist()) if v >= threshold]


def _run_local(diagram: BubbleDiagram,
               num_samples: int = 5,
               refine_passes: int = 1) -> List[List[Dict]]:
    """Run official HouseGAN++ locally, return num_samples candidate layouts."""
    model = _get_local_model()
    if model is None:
        raise RuntimeError("No local HouseGAN++ weights found.")

    device = next(model.parameters()).device
    results = []
    refine_n = max(0, min(2, int(refine_passes)))
    with torch.no_grad():
        for _ in range(num_samples):
            z, given_m, given_y, given_w = pack_official_inputs(diagram, device=device)
            masks = model(z, given_m, given_y, given_w)
            for _pass in range(refine_n):
                try:
                    fixed = _high_occupancy_nodes(masks)
                    if not fixed:
                        break
                    z, given_m, given_y, given_w = pack_official_inputs(
                        diagram, device=device, z=z, prev_masks=masks, fixed_nodes=fixed,
                    )
                    masks = model(z, given_m, given_y, given_w)
                except Exception:
                    break
            masks_np = official_masks_to_nchw(masks).detach().cpu().numpy()
            # Official occupancy is tanh; treat values > 0 as occupied.
            bboxes = masks_to_bboxes(masks_np, threshold=0.0)
            placed = scale_bboxes_to_feet(bboxes, diagram.rooms,
                                           diagram.house_w, diagram.house_h)
            placed = apply_us_conventions(placed, diagram.house_w, diagram.house_h)
            placed = resolve_overlaps(placed, diagram.house_w, diagram.house_h)
            results.append(placed)

    return results


# ── Remote Inference (HuggingFace Space) ─────────────────────────────────────

async def _run_remote(diagram: BubbleDiagram,
                      num_samples: int = 3) -> List[List[Dict]]:
    """Call HouseGAN++ running on Hugging Face Spaces (free ZeroGPU)."""
    payload = {
        "data": [
            diagram.hg_type_vector.tolist(),
            diagram.binary_adj.tolist(),
            diagram.house_w,
            diagram.house_h,
            num_samples,
        ]
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(HF_SPACE_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # HF Spaces Gradio API returns {"data": [...]}
    raw_layouts = data["data"][0]   # list of num_samples layouts

    results = []
    for layout in raw_layouts:
        placed = []
        for room, box in zip(diagram.rooms, layout):
            x1, y1, x2, y2 = box
            w = max(room.min_w, round((x2 - x1) * diagram.house_w, 1))
            h = max(room.min_h, round((y2 - y1) * diagram.house_h, 1))
            placed.append({
                "id": room.id, "name": room.name,
                "type": room.buildify_type,
                "x": round(x1 * diagram.house_w, 1),
                "y": round(y1 * diagram.house_h, 1),
                "width": w, "height": h,
                "zone": room.zone,
            })
        placed = apply_us_conventions(placed, diagram.house_w, diagram.house_h)
        placed = resolve_overlaps(placed, diagram.house_w, diagram.house_h)
        results.append(placed)

    return results


# ── Main entry point ──────────────────────────────────────────────────────────

async def generate_layouts(
    diagram: BubbleDiagram,
    num_variants: int = 3,
    mode: str = "auto",          # "auto" | "local" | "remote"
    refine_passes: int = 1,
) -> List[List[Dict]]:
    """
    Generate floor plan room layouts from a bubble diagram.

    Returns num_variants candidate layouts, each as a list of room dicts
    with keys: id, name, type, x, y, width, height, zone.

    Default: local trained checkpoint only. Remote HF is opt-in
    (KIYUB_HOUSEGAN_REMOTE_ENABLED=1). Untrained networks are never used.
    """
    global _remote_attempted, _remote_ok
    _log_status_once()

    if mode in ("auto", "local"):
        model = _get_local_model()
        if model is not None:
            try:
                layouts = _run_local(
                    diagram, num_samples=num_variants, refine_passes=refine_passes,
                )
                print(f"[HouseGAN] local inference produced {len(layouts)} layout(s)")
                return layouts
            except Exception as e:
                print(f"[HouseGAN] Local inference failed: {e}")
                if mode == "local":
                    raise

    if mode in ("auto", "remote"):
        if not remote_enabled():
            if mode == "remote":
                print("[HouseGAN] Remote requested but KIYUB_HOUSEGAN_REMOTE_ENABLED=0")
            return []
        if _remote_attempted and not _remote_ok:
            print("[HouseGAN] Remote already unavailable this process; skipping")
            return []
        _remote_attempted = True
        try:
            layouts = await _run_remote(diagram, num_samples=num_variants)
            _remote_ok = True
            _set_status(True, "remote", None)
            print(f"[HouseGAN] remote inference produced {len(layouts)} layout(s)")
            return layouts
        except Exception as e:
            _remote_ok = False
            _set_status(False, "unavailable", "remote_unavailable")
            print(f"[HouseGAN] Remote inference failed: {e}")

    return []

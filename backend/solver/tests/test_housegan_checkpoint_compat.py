"""Official HouseGAN++ checkpoint vs KIYUB HouseGANGenerator. strict=True only."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import torch

from moe.housegan.bubble_diagram import build_bubble_diagram
from moe.housegan.inference import (
    WEIGHTS_DIR,
    checkpoint_path,
    generate_layouts,
    masks_to_bboxes,
    reset_housegan_runtime,
    scale_bboxes_to_feet,
)
from moe.housegan.model import HouseGANGenerator, unwrap_state_dict
from moe.housegan.official_adapter import official_masks_to_nchw, pack_official_inputs
from moe.housegan.official_generator import Generator as OfficialGenerator

OFFICIAL_CKPT = WEIGHTS_DIR / "pretrained.pth"
ALIAS_CKPT = WEIGHTS_DIR / "housegan_pp.pt"


def _official_path() -> Path | None:
    for p in (OFFICIAL_CKPT, ALIAS_CKPT, checkpoint_path()):
        if p.exists() and p.stat().st_size > 1024:
            return p
    return None


def _require_official_ckpt() -> Path:
    path = _official_path()
    if path is None:
        pytest.skip(
            "Official HouseGAN++ checkpoint not present. "
            "Download pretrained.pth into backend/moe/housegan/weights/ "
            "(gitignored; see backend/moe/housegan/weights/README.md)."
        )
    return path


def _report_mismatch(model: torch.nn.Module, state: dict) -> tuple[list, list, list]:
    model_sd = model.state_dict()
    missing = sorted(k for k in model_sd if k not in state)
    unexpected = sorted(k for k in state if k not in model_sd)
    shape_mismatch = []
    for k in model_sd:
        if k not in state:
            continue
        got, exp = state[k], model_sd[k]
        if torch.is_tensor(got) and tuple(got.shape) != tuple(exp.shape):
            shape_mismatch.append((k, tuple(got.shape), tuple(exp.shape)))
    print("missing_keys:", missing[:40], "count=", len(missing))
    print("unexpected_keys:", unexpected[:40], "count=", len(unexpected))
    print("shape_mismatches:", shape_mismatch[:20], "count=", len(shape_mismatch))
    return missing, unexpected, shape_mismatch


def _program_diagram():
    return build_bubble_diagram({
        "bedrooms": 3,
        "bathrooms": 2,
        "garage": "none",
        "outdoor": "none",
        "homeOffice": False,
        "primarySuite": True,
        "formalDining": False,
        "openPlan": False,
        "sqft": 1800,
        "laundry": "room",
    })


def test_architecture_keys_do_not_overlap():
    kiyub = set(HouseGANGenerator().state_dict().keys())
    official = set(OfficialGenerator().state_dict().keys())
    assert kiyub.isdisjoint(official)
    with pytest.raises(RuntimeError):
        HouseGANGenerator().load_state_dict(OfficialGenerator().state_dict(), strict=True)


def test_kiyub_generator_cannot_load_official_strict():
    path = _require_official_ckpt()
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    state = unwrap_state_dict(ckpt)
    model = HouseGANGenerator()
    missing, unexpected, shapes = _report_mismatch(model, state)
    assert missing or unexpected or shapes, "architectures unexpectedly matched"
    with pytest.raises(RuntimeError):
        model.load_state_dict(state, strict=True)


def test_official_generator_loads_strict():
    path = _require_official_ckpt()
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    state = unwrap_state_dict(ckpt)
    model = OfficialGenerator()
    missing, unexpected, shapes = _report_mismatch(model, state)
    assert missing == []
    assert unexpected == []
    assert shapes == []
    model.load_state_dict(state, strict=True)
    model.eval()


def test_official_inference_produces_one_layout():
    path = _require_official_ckpt()
    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    model = OfficialGenerator()
    model.load_state_dict(unwrap_state_dict(ckpt), strict=True)
    model.eval()
    diagram = _program_diagram()
    z, given_m, given_y, given_w = pack_official_inputs(diagram, device="cpu")
    with torch.no_grad():
        masks = model(z, given_m, given_y, given_w)
    masks_nchw = official_masks_to_nchw(masks)
    assert masks_nchw.shape[0] == diagram.n
    assert tuple(masks_nchw.shape[-2:]) == (64, 64)
    bboxes = masks_to_bboxes(masks_nchw.cpu().numpy(), threshold=0.0)
    placed = scale_bboxes_to_feet(bboxes, diagram.rooms, diagram.house_w, diagram.house_h)
    assert len(placed) == diagram.n
    assert all(r["width"] > 0 and r["height"] > 0 for r in placed)


def test_generate_layouts_creates_candidate_when_checkpoint_present(monkeypatch):
    path = _require_official_ckpt()
    monkeypatch.setattr("moe.housegan.inference.WEIGHTS_DIR", path.parent)
    reset_housegan_runtime()
    layouts = asyncio.run(generate_layouts(_program_diagram(), num_variants=1, mode="local"))
    assert layouts, "official backend must produce at least one layout"
    assert len(layouts[0]) >= 6
    rooms = layouts[0]
    assert {r["type"] for r in rooms}  # non-empty types
    assert all("x" in r and "width" in r for r in rooms)

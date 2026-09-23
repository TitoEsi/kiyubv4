"""Reversible generation audit. Does not change scoring, selection, or FloorPlan schema.

Run from backend/:
  .venv/Scripts/python.exe audit_generation.py

Writes audit_last_run.json. KIYUB_AUDIT is unused unless this script is run.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).parent
OUT_PATH = ROOT / "audit_last_run.json"

LIVE = {
    "lotShape": "rectangle",
    "lotWidth": 20,
    "lotDepth": 30,
    "bedrooms": 3,
    "bathrooms": 2,
    "openPlan": False,
    "primarySuite": True,
    "homeOffice": True,
    "formalDining": False,
    "garage": "2car",
    "laundry": "room",
    "outdoor": "patio",
    "sqft": 1800,
    "stories": 1,
    "style": "modern",
    "ceilingHeight": "standard",
}


def _now() -> float:
    return time.perf_counter()


def _geom_fingerprint(plans: list) -> dict:
    if not plans:
        return {"n_plans": 0, "rooms": []}
    rooms = plans[0].get("rooms") or []
    return {
        "n_plans": len(plans),
        "n_rooms": len(rooms),
        "types": [r.get("type") for r in rooms],
        "boxes": [
            {
                "type": r.get("type"),
                "x": r.get("x"),
                "y": r.get("y"),
                "w": r.get("width"),
                "h": r.get("height"),
            }
            for r in rooms
        ],
    }


def probe_moe() -> dict:
    import torch
    from moe.config import MOEConfig
    from moe.inference import load_model
    from moe.data import encode_constraints
    from moe.experts import EXPERT_NAMES

    cfg = MOEConfig()
    weights = ROOT / "moe" / "weights" / cfg.model_filename
    t0 = _now()
    model = load_model(cfg)
    load_s = _now() - t0
    vec = encode_constraints(
        bedrooms=3, bathrooms=2, sqft=1800, stories=1,
        style="modern", open_plan=False, primary_suite=True,
        home_office=True, formal_dining=False,
        garage="2car", laundry="room", outdoor="patio",
        ceiling_height="standard", config=cfg,
    ).unsqueeze(0)
    t1 = _now()
    with torch.no_grad():
        w = model.get_expert_weights(vec)
    infer_s = _now() - t1
    weights_list = [round(float(x), 6) for x in w[0].tolist()]
    return {
        "name": "MOE",
        "stands_for": "Mixture of Experts",
        "architecture": "ConstraintEncoder + SparseTopK gating (top-4 of 8 MLP experts)",
        "weights_path": str(weights),
        "weights_exist": weights.exists(),
        "weights_bytes": weights.stat().st_size if weights.exists() else 0,
        "device": str(next(model.parameters()).device),
        "cuda_available": torch.cuda.is_available(),
        "param_count": model.count_parameters(),
        "load_s": round(load_s, 4),
        "inference_s": round(infer_s, 4),
        "input_shape": list(vec.shape),
        "output_shape": list(w.shape),
        "expert_names": list(EXPERT_NAMES),
        "expert_weights": dict(zip(EXPERT_NAMES, weights_list)),
        "weight_sum": round(sum(weights_list), 6),
        "valid_finite": all(x == x for x in weights_list),
    }


def probe_housegan() -> dict:
    from moe.housegan.inference import WEIGHTS_DIR, HF_SPACE_URL, _get_local_model, generate_layouts
    from moe.housegan.bubble_diagram import build_bubble_diagram
    import httpx

    local_w = WEIGHTS_DIR / "housegan_pp.pt"
    t0 = _now()
    local_model = _get_local_model()
    local_load_s = _now() - t0
    remote = {"url": HF_SPACE_URL, "status": None, "error": None, "elapsed_s": None}
    t1 = _now()
    try:
        resp = httpx.post(HF_SPACE_URL, json={"data": []}, timeout=15.0)
        remote["status"] = resp.status_code
        remote["body_preview"] = (resp.text or "")[:200]
    except Exception as exc:
        remote["error"] = f"{type(exc).__name__}: {exc}"
    remote["elapsed_s"] = round(_now() - t1, 4)

    layouts = None
    gen_s = None
    gen_error = None
    try:
        diagram = build_bubble_diagram(LIVE)
        t2 = _now()
        layouts = asyncio.run(generate_layouts(diagram, num_variants=1, mode="auto"))
        gen_s = round(_now() - t2, 4)
    except Exception as exc:
        gen_error = f"{type(exc).__name__}: {exc}"

    return {
        "local_weights_path": str(local_w),
        "local_weights_exist": local_w.exists(),
        "weights_dir_exists": WEIGHTS_DIR.exists(),
        "local_model_loaded": local_model is not None,
        "local_load_s": round(local_load_s, 4),
        "remote": remote,
        "generate_layouts_s": gen_s,
        "generate_layouts_error": gen_error,
        "n_layouts": len(layouts) if layouts else 0,
        "layout_preview": (layouts[0][:2] if layouts else None),
    }


def probe_rag() -> dict:
    from rag import RAGSystem, OLLAMA_URL, EMBED_MODEL, CACHE_PATH, KB_PATH
    import httpx

    ollama = {"reachable": False, "error": None, "elapsed_s": None}
    t0 = _now()
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=3.0)
        ollama["reachable"] = r.status_code == 200
        ollama["status"] = r.status_code
    except Exception as exc:
        ollama["error"] = f"{type(exc).__name__}: {exc}"
    ollama["elapsed_s"] = round(_now() - t0, 4)

    system = RAGSystem()
    t1 = _now()
    asyncio.run(system.initialize())
    init_s = round(_now() - t1, 4)
    t2 = _now()
    hits = asyncio.run(system.retrieve("two car garage driveway foyer", top_k=5))
    retrieve_s = round(_now() - t2, 4)
    cache = {}
    if CACHE_PATH.exists():
        cache = json.loads(CACHE_PATH.read_text() or "{}")
    kb = json.loads(KB_PATH.read_text())
    return {
        "provider": "Ollama",
        "embed_model": EMBED_MODEL,
        "endpoint": f"{OLLAMA_URL}/api/embeddings",
        "ollama": ollama,
        "kb_chunks": len(kb.get("chunks") or []),
        "cache_path": str(CACHE_PATH),
        "cached_embeddings": len(cache),
        "initialize_s": init_s,
        "retrieve_s": retrieve_s,
        "retrieve_hits": len(hits),
        "retrieve_usable": bool(hits),
        "called_from_generate": False,
        "note": "rag.retrieve is not imported by /api/generate/moe",
    }


def _patch_strategy_timers(record: list):
    import solver.strategy_competition as sc

    orig = sc.evaluate_strategy

    def wrapped(*args, **kwargs):
        t0 = _now()
        ev = orig(*args, **kwargs)
        elapsed = round(_now() - t0, 4)
        q = (ev.result.quality_score or {}) if ev.result else {}
        cats = q.get("categories") or {}
        record.append({
            "strategy": ev.strategy,
            "valid": ev.valid,
            "solver_s": elapsed,
            "quality_score": ev.quality_score,
            "access_score": ev.access_score,
            "circulation_score": ev.circulation_score,
            "adjacency_score": ev.adjacency_score,
            "zoning_score": ev.zoning_score,
            "usability_score": ev.room_usability_score,
            "residual_area": ev.residual_area,
            "shape_score": cats.get("shape"),
            "vehicle_access": cats.get("vehicle_access"),
            "arrival": cats.get("arrival"),
        })
        return ev

    sc.evaluate_strategy = wrapped
    return orig


def run_predict() -> tuple[dict, dict]:
    from moe.inference import predict_floor_plan, _HOUSEGAN_AVAILABLE
    import moe.inference as inf

    hg_calls = {"n": 0, "returned": []}
    orig_hg = inf._place_rooms_housegan

    def hg_wrap(*args, **kwargs):
        hg_calls["n"] += 1
        t0 = _now()
        out = orig_hg(*args, **kwargs)
        hg_calls["returned"].append({
            "elapsed_s": round(_now() - t0, 4),
            "used": out is not None,
            "n_rooms": len(out) if out else 0,
        })
        return out

    inf._place_rooms_housegan = hg_wrap
    t0 = _now()
    moe = predict_floor_plan(LIVE, num_variants=3)
    elapsed = round(_now() - t0, 4)
    inf._place_rooms_housegan = orig_hg
    plans = moe.get("plans") or []
    return moe, {
        "elapsed_s": elapsed,
        "housegan_import_available": _HOUSEGAN_AVAILABLE,
        "housegan_calls": hg_calls["n"],
        "housegan_attempts": hg_calls["returned"],
        "n_plans": len(plans),
        "expert_weights": moe.get("expert_weights"),
        "confidence": moe.get("confidence"),
        "irc_compliant": moe.get("irc_compliant"),
        "plan_names": [p.get("name") for p in plans],
        "fingerprint": _geom_fingerprint(plans),
    }


def run_refine(moe: dict, label: str, env_overrides: dict | None = None) -> dict:
    prev = {}
    for k, v in (env_overrides or {}).items():
        prev[k] = os.environ.get(k)
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = str(v)
    strategy_rows: list = []
    orig = _patch_strategy_timers(strategy_rows)
    import solver.pipeline as pipe
    import solver.solver as slv

    plan_s = mass_s = quality_s = None
    orig_plan = pipe.build_spatial_plan
    orig_mass = pipe.plan_building_mass
    orig_score = slv.score_layout

    def plan_wrap(*a, **k):
        nonlocal plan_s
        t0 = _now()
        out = orig_plan(*a, **k)
        plan_s = round(_now() - t0, 4)
        return out

    def mass_wrap(*a, **k):
        nonlocal mass_s
        t0 = _now()
        out = orig_mass(*a, **k)
        mass_s = round(_now() - t0, 4)
        return out

    def score_wrap(*a, **k):
        nonlocal quality_s
        t0 = _now()
        out = orig_score(*a, **k)
        quality_s = round((quality_s or 0) + (_now() - t0), 4)
        return out

    pipe.build_spatial_plan = plan_wrap
    pipe.plan_building_mass = mass_wrap
    slv.score_layout = score_wrap

    t0 = _now()
    try:
        result = pipe.refine_generation(LIVE, moe)
    finally:
        pipe.build_spatial_plan = orig_plan
        pipe.plan_building_mass = orig_mass
        slv.score_layout = orig_score
        import solver.strategy_competition as sc
        sc.evaluate_strategy = orig
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    elapsed = round(_now() - t0, 4)
    q = result.get("quality_score") or {}
    cats = q.get("categories") or {}
    return {
        "label": label,
        "elapsed_s": elapsed,
        "architectural_planning_s": plan_s,
        "building_mass_s": mass_s,
        "quality_s": quality_s,
        "status": result.get("status"),
        "validated": result.get("validated"),
        "irc_compliant": result.get("irc_compliant"),
        "selected_strategy": result.get("selected_strategy"),
        "expert_weights_echoed": bool(result.get("expert_weights")),
        "confidence_echoed": result.get("confidence"),
        "n_strategy_evals": len(strategy_rows),
        "strategy_evaluations": strategy_rows,
        "quality_overall": q.get("overall"),
        "categories": cats,
        "fingerprint": _geom_fingerprint(result.get("plans") or []),
        "planning_issues": ((result.get("planning") or {}).get("issues") or [])[:8],
        "access": result.get("access"),
    }


def main() -> None:
    report: dict = {
        "note": "Audit measurements only. Not professional architectural approval.",
        "live_constraints": LIVE,
        "probes": {},
        "predict": {},
        "contribution": {},
        "errors": [],
    }
    try:
        report["probes"]["moe"] = probe_moe()
    except Exception:
        report["errors"].append({"probe": "moe", "trace": traceback.format_exc()})
    try:
        report["probes"]["housegan"] = probe_housegan()
    except Exception:
        report["errors"].append({"probe": "housegan", "trace": traceback.format_exc()})
    try:
        report["probes"]["rag"] = probe_rag()
    except Exception:
        report["errors"].append({"probe": "rag", "trace": traceback.format_exc()})

    try:
        moe, pred_meta = run_predict()
        report["predict"] = pred_meta
    except Exception:
        moe = {"plans": [], "expert_weights": {}, "confidence": 0, "irc_compliant": False}
        report["errors"].append({"probe": "predict_floor_plan", "trace": traceback.format_exc()})

    empty = {"plans": [], "expert_weights": {}, "confidence": 0, "irc_compliant": False}
    try:
        report["contribution"]["baseline_multi"] = run_refine(
            moe, "baseline_MULTI_STRATEGY=1", {"KIYUB_MULTI_STRATEGY": "1"},
        )
    except Exception:
        report["errors"].append({"probe": "baseline", "trace": traceback.format_exc()})
    try:
        report["contribution"]["empty_moe_multi"] = run_refine(
            empty, "empty_moe_MULTI_STRATEGY=1", {"KIYUB_MULTI_STRATEGY": "1"},
        )
    except Exception:
        report["errors"].append({"probe": "empty_moe", "trace": traceback.format_exc()})
    try:
        report["contribution"]["hybrid_hints"] = run_refine(
            moe, "MULTI_STRATEGY=0_hybrid_hints", {"KIYUB_MULTI_STRATEGY": "0"},
        )
    except Exception:
        report["errors"].append({"probe": "hybrid", "trace": traceback.format_exc()})

    base = (report["contribution"].get("baseline_multi") or {}).get("fingerprint")
    empty_fp = (report["contribution"].get("empty_moe_multi") or {}).get("fingerprint")
    hybrid_fp = (report["contribution"].get("hybrid_hints") or {}).get("fingerprint")
    report["contribution"]["moe_changes_geometry_when_multi_on"] = base != empty_fp
    report["contribution"]["hints_change_geometry_when_multi_off"] = base != hybrid_fp
    report["contribution"]["baseline_equals_empty_moe"] = base == empty_fp

    try:
        from fastapi.testclient import TestClient
        from main import app

        t0 = _now()
        with TestClient(app) as client:
            resp = client.post("/api/generate/moe", json=LIVE)
        elapsed = round(_now() - t0, 4)
        body = {}
        try:
            body = resp.json()
        except Exception:
            body = {"raw": (resp.text or "")[:400]}
        plans = body.get("plans") or []
        report["live_http"] = {
            "status_code": resp.status_code,
            "elapsed_s": elapsed,
            "status": body.get("status"),
            "validated": body.get("validated"),
            "selected_strategy": body.get("selected_strategy"),
            "expert_weights_echoed": bool(body.get("expert_weights")),
            "confidence": body.get("confidence"),
            "irc_compliant": body.get("irc_compliant"),
            "fingerprint": _geom_fingerprint(plans),
            "quality_overall": (body.get("quality_score") or {}).get("overall"),
            "http_matches_baseline_geom": _geom_fingerprint(plans) == base,
        }
    except Exception:
        report["errors"].append({"probe": "live_http", "trace": traceback.format_exc()})

    OUT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("[AUDIT] wrote", OUT_PATH)
    print("[AUDIT] errors", len(report["errors"]))
    if report.get("contribution", {}).get("baseline_multi"):
        b = report["contribution"]["baseline_multi"]
        print("[AUDIT] baseline", b.get("status"), "strategy", b.get("selected_strategy"), "s", b.get("elapsed_s"))


if __name__ == "__main__":
    main()

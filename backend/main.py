import asyncio
import io
import json
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Literal, Optional

from generator import generate_floor_plan
from exporter import export_to_dxf, export_to_pdf
from cost import estimate_cost, REGION_MULTIPLIERS
from scoring import score_design
from moe.inference import predict_floor_plan, load_model, LotConstraintError, compute_buildable_envelope
from solver.pipeline import refine_generation
from solver.room_program import envelope_from_constraints
from moe.api_auth import key_store, get_api_key
from moe.config import MOEConfig
from moe.experts import EXPERT_NAMES
from moe.housegan.inference import get_housegan_status
from workflow.api import router as workflow_router
from workflow.db import SessionLocal, init_db
from workflow.seed import seed_users

app = FastAPI(title="KIYUB v4 API")
app.include_router(workflow_router)


@app.on_event("startup")
async def startup_event():
    from rag import rag
    try:
        rag.load()
    except Exception as e:
        print(f"[RAG] Init warning: {e} — generation will work without RAG context.")
    # Pre-load MOE model
    try:
        load_model()
    except Exception as e:
        print(f"[MOE] Init warning: {e} — MOE generation may be unavailable.")
    try:
        init_db()
        db = SessionLocal()
        try:
            seed_users(db)
        finally:
            db.close()
    except Exception as e:
        print(f"[WORKFLOW] Init warning: {e} — project workflow may be unavailable.")


import os

ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request models ────────────────────────────────────────────────────────────

class Constraints(BaseModel):
    # Site
    lotShape: Literal["rectangle", "square", "l_shape", "irregular"] = "rectangle"
    lotWidth: float = 20.0
    lotDepth: float = 30.0

    # Basics
    bedrooms: int = 3
    bathrooms: int = 2
    sqft: int = 1800
    stories: int = 1
    style: str = "modern"

    # Layout options
    openPlan: bool = False
    primarySuite: bool = True
    homeOffice: bool = False
    formalDining: bool = False

    # Spaces
    garage: str = "2car"
    laundry: str = "room"
    outdoor: str = "patio"

    # Style
    ceilingHeight: str = "standard"


class ExportRequest(BaseModel):
    floor_plan: dict


class CostRequest(BaseModel):
    floor_plan: dict
    region: str = "National Average"


class ScoreRequest(BaseModel):
    floor_plan: dict


class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    floor_plan: dict
    messages: list[ChatMessage]


class AuthRequest(BaseModel):
    email: str = ""
    tier: str = "free"
    password: Optional[str] = None
    role: str = "CLIENT"


class UpgradeRequest(BaseModel):
    api_key: str
    tier: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/generate")
async def generate(constraints: Constraints):
    try:
        c = constraints.model_dump()
        plans = await asyncio.gather(
            generate_floor_plan(c, 0),
            generate_floor_plan(c, 1),
            generate_floor_plan(c, 2),
        )
        return {"plans": list(plans)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def validate_constraints_feasibility(c: dict) -> list:
    """
    Check whether the requested constraints are physically feasible.
    Returns a list of issues (may be empty). Each issue:
      {"field": str, "severity": "error"|"warning", "message": str, "detail": str}
    Errors block generation; warnings are informational only.
    """
    issues = []
    sqft         = c.get("sqft", 1800)
    bedrooms     = c.get("bedrooms", 3)       # total incl. primary
    bathrooms    = c.get("bathrooms", 2)
    primary_suite = c.get("primarySuite", True)
    home_office  = c.get("homeOffice", False)
    formal_dining = c.get("formalDining", False)
    laundry      = c.get("laundry", "room")
    garage       = c.get("garage", "2car")
    stories      = c.get("stories", 1)

    secondary = max(0, bedrooms - 1)
    shared_baths = max(0, bathrooms - 1)

    # ── Base overhead (kitchen + living + hallway + foyer) ────────────────
    min_sqft = 168 + 120 + 200 + 40   # = 528

    # ── Primary bedroom cluster ───────────────────────────────────────────
    min_sqft += 240 if primary_suite else 168   # bed + ensuite + closet

    # ── Secondary bedrooms ────────────────────────────────────────────────
    min_sqft += secondary * 100

    # ── Shared bathrooms ──────────────────────────────────────────────────
    min_sqft += shared_baths * 40

    # ── Optional rooms ────────────────────────────────────────────────────
    if home_office:    min_sqft += 90
    if formal_dining:  min_sqft += 121
    if laundry == "room": min_sqft += 30

    # ── ERROR: lot shape / dimensions ─────────────────────────────────────
    lot_shape = c.get("lotShape", "rectangle")
    try:
        lot_width = float(c.get("lotWidth", 20.0))
    except (TypeError, ValueError):
        lot_width = 0.0
    try:
        lot_depth = float(c.get("lotDepth", 30.0))
    except (TypeError, ValueError):
        lot_depth = 0.0

    if lot_shape in ("l_shape", "irregular"):
        label = "L-shaped" if lot_shape == "l_shape" else "irregular"
        issues.append({
            "field": "lotShape",
            "severity": "error",
            "message": f"{label.capitalize()} lots are not yet supported.",
            "detail": (
                "True L-shaped and irregular lot geometry is not implemented. "
                "Choose rectangle or square for this phase."
            ),
        })

    if lot_width <= 0:
        issues.append({
            "field": "lotWidth",
            "severity": "error",
            "message": "Lot width must be greater than zero.",
            "detail": "Enter a lot width greater than 0 meters.",
        })
    if lot_depth <= 0:
        issues.append({
            "field": "lotDepth",
            "severity": "error",
            "message": "Lot depth must be greater than zero.",
            "detail": "Enter a lot depth greater than 0 meters.",
        })

    if lot_shape not in ("l_shape", "irregular") and lot_width > 0 and lot_depth > 0:
        try:
            env = compute_buildable_envelope(c)
            buildable_area = env["buildable_width"] * env["buildable_depth"] * max(1, stories)
            needed = max(sqft, min_sqft)
            if needed > buildable_area:
                issues.append({
                    "field": "lotWidth",
                    "severity": "error",
                    "message": "This lot is too small for the requested home.",
                    "detail": (
                        f"After placeholder setbacks the buildable envelope is "
                        f"{env['buildable_width']:.1f} ft × {env['buildable_depth']:.1f} ft "
                        f"({buildable_area:,.0f} sqft across {stories} "
                        f"{'story' if stories == 1 else 'stories'}). "
                        f"The requested configuration needs about {needed:,} sqft. "
                        f"Increase the lot, reduce size, or remove rooms. "
                        "These setbacks are conceptual only, not Philippine building-code values."
                    ),
                })
        except LotConstraintError as e:
            issues.append(e.as_issue())

    # ── ERROR: total sqft below minimum ───────────────────────────────────
    if sqft < min_sqft:
        parts = []
        if secondary: parts.append(f"{secondary} secondary bedroom{'s' if secondary != 1 else ''}")
        parts.append(f"{bathrooms} bathroom{'s' if bathrooms != 1 else ''}")
        if home_office: parts.append("home office")
        if formal_dining: parts.append("formal dining")
        issues.append({
            "field": "sqft",
            "severity": "error",
            "message": "Not enough space for this configuration.",
            "detail": (
                f"Your selections ({', '.join(parts)}) require at least {min_sqft:,} sqft of "
                f"living space. You set {sqft:,} sqft. "
                f"Increase the size to {min_sqft:,}+ sqft, or remove bedrooms/rooms."
            ),
        })

    # ── ERROR: too many bedrooms for sqft ────────────────────────────────
    base_overhead = 528 + (240 if primary_suite else 168)
    max_secondary = max(0, (sqft - base_overhead) // 100)
    if secondary > max_secondary and sqft >= min_sqft:
        issues.append({
            "field": "bedrooms",
            "severity": "error",
            "message": f"{bedrooms} bedrooms is not feasible in {sqft:,} sqft.",
            "detail": (
                f"After essential rooms, only {int(sqft - base_overhead):,} sqft remains for "
                f"secondary bedrooms ({int(max_secondary)} max at 100 sqft each). "
                f"Use {int(max_secondary) + 1} total bedrooms or increase to "
                f"{int(base_overhead + secondary * 100):,}+ sqft."
            ),
        })

    # ── WARNING: bathrooms > bedrooms + 1 ────────────────────────────────
    if bathrooms > bedrooms + 1:
        issues.append({
            "field": "bathrooms",
            "severity": "warning",
            "message": f"{bathrooms} bathrooms for {bedrooms} bedrooms is unusual.",
            "detail": (
                f"Standard practice is 1 bathroom per bedroom or 1 shared bathroom per "
                f"2 bedrooms. Consider {min(bathrooms, bedrooms)} bathrooms."
            ),
        })

    # ── WARNING: 2-story with tiny footprint ─────────────────────────────
    if stories == 2 and sqft < 1200:
        issues.append({
            "field": "stories",
            "severity": "warning",
            "message": "Two-story layout under 1,200 sqft is cramped.",
            "detail": "Staircase overhead is significant in small homes. Consider single-story or increase to 1,200+ sqft.",
        })

    # ── WARNING: 3-car garage on small home ──────────────────────────────
    if garage == "3car" and sqft < 1800:
        issues.append({
            "field": "garage",
            "severity": "warning",
            "message": "A 3-car garage is disproportionate for this home size.",
            "detail": f"3-car garages suit homes 1,800+ sqft. With {sqft:,} sqft, a 1 or 2-car garage is more appropriate.",
        })

    return issues


def _generation_debug(constraints: dict, moe: dict, result: dict, timings: dict | None = None) -> dict:
    """Lightweight pipeline trace. Does not change geometry. Not professional approval."""
    hg = get_housegan_status()
    moe_plans = moe.get("plans") or []
    envelope = None
    try:
        envelope = compute_buildable_envelope(constraints)
    except Exception as exc:
        envelope = {"error": str(exc)}
    plan0 = (result.get("plans") or [{}])[0]
    q = result.get("quality_score") or {}
    cats = q.get("categories") or {}
    debug = {
        "input": {
            "lotShape": constraints.get("lotShape"),
            "lotWidth_m": constraints.get("lotWidth"),
            "lotDepth_m": constraints.get("lotDepth"),
            "stories": constraints.get("stories"),
            "bedrooms": constraints.get("bedrooms"),
            "bathrooms": constraints.get("bathrooms"),
        },
        "site": {
            "width": constraints.get("lotWidth"),
            "depth": constraints.get("lotDepth"),
        },
        "housegan": {
            "available": hg.available,
            "source": hg.source,
            "reason": hg.reason,
            "status": "active" if hg.available else "unavailable",
            "plan_count": sum(
                1 for p in moe_plans
                if p.get("generator") == "moe+housegan" or p.get("used_housegan")
            ),
            "moe_plan_count": len(moe_plans),
        },
        "buildify_moe": {
            "generators": [p.get("generator") for p in moe_plans],
            "plan_count": len(moe_plans),
            "adjacency": "bubble_diagram_weighted",
        },
        "ortools": {
            "status": result.get("status"),
            "selected_strategy": result.get("selected_strategy"),
            "selected_source": result.get("selected_source"),
            "strategy_count": len(result.get("strategy_evaluations") or []),
            "plan_generator": plan0.get("generator"),
            "envelope_ft": {
                "totalWidth": plan0.get("totalWidth"),
                "totalHeight": plan0.get("totalHeight"),
            },
        },
        "candidates": result.get("strategy_evaluations") or [],
        "winner": result.get("winner") or result.get("selected_strategy"),
        "evaluation": {
            "overall": q.get("overall"),
            "categories": cats,
            "diagnostics": result.get("diagnostics") or q.get("diagnostics"),
            "circulation_ratio": result.get("circulation_ratio") or q.get("circulation_ratio"),
            "objective_breakdown": q.get("objective_breakdown"),
        },
        "program": result.get("program"),
        "program_validation": result.get("program_validation"),
        "topology_count": result.get("topology_count"),
        "ruleset": result.get("ruleset"),
        "refinement": result.get("refinement") or [],
        "timings": {**(timings or {}), **(result.get("timings") or {})},
        "buildable_envelope": envelope,
        "scene_site_m": {
            "width": constraints.get("lotWidth"),
            "depth": constraints.get("lotDepth"),
        },
        "note": "Internal generation debug. Not professional architectural approval or code compliance.",
    }
    print("[KIYUB v4 DEBUG]")
    print(json.dumps(debug, indent=2, default=str))
    return debug


# ── MOE Endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/generate/moe")
async def generate_moe(constraints: Constraints, request: Request):
    """Generate floor plans using the MOE AI model."""
    try:
        # Check API key for tier limits
        api_key = get_api_key(request)
        config = MOEConfig()
        num_variants = 3  # default

        if api_key:
            record = key_store.validate_key(api_key)
            if record:
                if not key_store.check_limit(api_key):
                    raise HTTPException(
                        status_code=429,
                        detail="Daily generation limit reached. Upgrade to Pro for unlimited."
                    )
                num_variants = config.TIER_VARIANTS.get(record["tier"], 3)
                key_store.record_usage(api_key, "generation")

        c = constraints.model_dump()
        print("[KIYUB POST] /api/generate/moe")
        print(json.dumps(c, indent=2, default=str))

        # Feasibility check — block generation for impossible configurations
        issues = validate_constraints_feasibility(c)
        hard_errors = [i for i in issues if i["severity"] == "error"]
        if hard_errors:
            raise HTTPException(
                status_code=422,
                detail={"validation_errors": issues},
            )

        from rag import rag
        rag_meta = await rag.retrieve_for_generate(c)

        try:
            t_moe = time.perf_counter()
            moe = predict_floor_plan(c, num_variants=num_variants)
            moe_s = round(time.perf_counter() - t_moe, 3)
        except LotConstraintError as e:
            try:
                envelope_from_constraints(c)
            except LotConstraintError:
                raise HTTPException(
                    status_code=422,
                    detail={"validation_errors": [e.as_issue()]},
                )
            moe = {
                "plans": [],
                "expert_weights": {},
                "confidence": 0,
                "irc_compliant": False,
            }
            moe_s = 0.0

        t_ref = time.perf_counter()
        result = refine_generation(c, moe)
        refine_s = round(time.perf_counter() - t_ref, 3)
        timings = {
            "buildify_moe_s": moe_s,
            "housegan_s": None,
            "refine_generation_s": refine_s,
            "total_s": round(moe_s + refine_s, 3),
        }
        result["applied_constraints"] = c
        result["rag_available"] = rag_meta["rag_available"]
        result["rag_reason"] = rag_meta["rag_reason"]
        result["rag_context"] = rag_meta["rag_context"]
        result["generation_debug"] = _generation_debug(c, moe, result, timings)
        return result
    except HTTPException:
        raise
    except LotConstraintError as e:
        raise HTTPException(
            status_code=422,
            detail={"validation_errors": [e.as_issue()]},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/moe/experts")
async def moe_experts(constraints: Constraints):
    """Get expert activation weights for given constraints."""
    try:
        c = constraints.model_dump()
        result = predict_floor_plan(c, num_variants=1)
        return {
            "expert_weights": result["expert_weights"],
            "expert_names": EXPERT_NAMES,
            "confidence": result["confidence"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def auth_register(req: AuthRequest):
    """Register an API key, or a workflow user when password is provided."""
    if req.password:
        from workflow.auth import create_token, hash_password
        from workflow.db import SessionLocal
        from workflow.models import User
        from workflow.audit import log_event
        from workflow.state import ROLES
        from workflow.services import serialize_user
        role = (req.role or "CLIENT").upper()
        if role not in ROLES or role in ("MAIN_ADMIN", "IT_PERSONNEL"):
            raise HTTPException(status_code=403, detail="Cannot self-register this role")
        db = SessionLocal()
        try:
            email = req.email.lower().strip()
            if db.query(User).filter(User.email == email).one_or_none():
                raise HTTPException(status_code=409, detail="Email already registered")
            approved = role == "CLIENT"
            user = User(email=email, password_hash=hash_password(req.password), role=role, approved=approved)
            db.add(user)
            db.flush()
            log_event(db, event_type="ACCOUNT_MODIFIED", actor_id=user.id, target=user.id, metadata={"created": True})
            db.commit()
            db.refresh(user)
            if role == "ARCHITECT":
                return {"user": serialize_user(user), "message": "Architect account created. Wait for IT approval before logging in."}
            return {"token": create_token(user), "user": serialize_user(user)}
        finally:
            db.close()
    try:
        record = key_store.create_key(tier=req.tier, email=req.email)
        return {
            "api_key": record["key"],
            "tier": record["tier"],
            "message": f"API key created. Tier: {record['tier']}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/auth/usage")
async def auth_usage(request: Request):
    """Get usage stats for the current API key."""
    api_key = get_api_key(request)
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required in X-API-Key header.")
    usage = key_store.get_usage(api_key)
    if not usage:
        raise HTTPException(status_code=401, detail="Invalid API key.")
    return usage


@app.post("/api/auth/upgrade")
async def auth_upgrade(req: UpgradeRequest):
    """Upgrade an API key to a higher tier."""
    result = key_store.upgrade_key(req.api_key, req.tier)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found.")
    return {"tier": req.tier, "message": f"Upgraded to {req.tier} tier."}


@app.post("/api/export/dxf")
async def export_dxf(request: ExportRequest):
    try:
        dxf_bytes = export_to_dxf(request.floor_plan)
        name = request.floor_plan.get("name", "floor_plan").replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(dxf_bytes),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{name}.dxf"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/pdf")
async def export_pdf(request: ExportRequest):
    try:
        pdf_bytes = export_to_pdf(request.floor_plan)
        name = str(request.floor_plan.get("name", "floor_plan")).replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cost/regions")
async def cost_regions():
    return {"regions": list(REGION_MULTIPLIERS.keys())}


@app.post("/api/cost")
async def cost(request: CostRequest):
    try:
        return estimate_cost(request.floor_plan, request.region)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/score")
async def score(request: ScoreRequest):
    try:
        return score_design(request.floor_plan)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


CHAT_SYSTEM = """You are KIYUB v4, an AI-assisted residential floor-plan design assistant.
You help users refine conceptual floor plans. The user will share their current floor plan data
and ask questions or request modifications.
This is a conceptual design tool. Do not claim building-code compliance or licensed architectural approval.


When asked to modify a plan, respond with:
1. A brief explanation of your suggested changes (2-3 sentences)
2. A JSON block inside ```json ... ``` with the COMPLETE updated floor plan (same structure, all rooms)

When answering questions (not modifications), just respond with helpful architectural advice.
Keep answers concise and practical. Focus on US residential standards.
"""


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        plan_summary = _summarize_plan(request.floor_plan)
        system_context = f"{CHAT_SYSTEM}\n\nCurrent floor plan:\n{plan_summary}"

        messages = [{"role": "system", "content": system_context}]
        for m in request.messages:
            messages.append({"role": m.role, "content": m.content})

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "http://localhost:11434/api/chat",
                json={"model": "llama3.2", "messages": messages, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()

        reply = data.get("message", {}).get("content", "Sorry, no response.")
        updated_plan = _extract_plan_from_reply(reply, request.floor_plan)

        return {"reply": reply, "updated_plan": updated_plan}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _summarize_plan(plan: dict) -> str:
    rooms = plan.get("rooms", [])
    lines = [
        f"Name: {plan.get('name', 'Plan')}",
        f"Footprint: {plan.get('totalWidth', 0)}ft × {plan.get('totalHeight', 0)}ft",
        f"Ceiling height: {plan.get('ceilingHeight', 9)}ft",
        f"Rooms ({len(rooms)}):",
    ]
    for r in rooms:
        lines.append(f"  - {r['name']} ({r.get('type','')}) {r['width']}×{r['height']}ft at ({r['x']},{r['y']})")
    return "\n".join(lines)


def _extract_plan_from_reply(reply: str, original: dict) -> Optional[dict]:
    import re
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", reply)
    if not m:
        return None
    try:
        plan = json.loads(m.group(1))
        if "rooms" in plan:
            return plan
    except Exception:
        pass
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

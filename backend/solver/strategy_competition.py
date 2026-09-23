"""Multi-strategy competition. Soft preferences, existing quality, deterministic pick.

Does not drop rooms. Does not change lot or questionnaire counts.
Not professional architectural approval.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .building_mass import BuildingMass
from .models import Envelope, RoomProgram, SolveResult
from .solver import solve
from .spatial_plan import SpatialPlan
from .spatial_planner import COMPETITION_STRATEGIES, generate_strategy_candidates


def candidate_count() -> int:
    try:
        return max(1, min(5, int(os.environ.get("KIYUB_CANDIDATE_COUNT", "5"))))
    except (TypeError, ValueError):
        return 5


@dataclass
class LayoutCandidate:
    id: str
    source: str  # spatial | housegan | moe_fallback
    strategy: str
    spatial: SpatialPlan | None = None
    hints: dict | None = None
    result: SolveResult | None = None
    evaluation: "StrategyEvaluation | None" = None

    def as_dict(self) -> dict:
        q = (self.result.quality_score or {}) if self.result else {}
        cats = q.get("categories") or {}
        hard = q.get("hard_failures") or []
        if self.result and self.result.validation:
            hard = [e.as_dict() for e in self.result.validation.errors]
        topo = None
        if self.spatial:
            topo = {
                "strategy": self.spatial.strategy.name,
                "relation_count": len(self.spatial.relations),
                "cluster_count": len(self.spatial.clusters),
            }
        return {
            "id": self.id,
            "source": self.source,
            "strategy": self.strategy,
            "topology": topo,
            "valid": bool(self.evaluation and self.evaluation.valid),
            "hard_failures": hard,
            "metrics": {
                "overall": q.get("overall"),
                "circulation": cats.get("circulation"),
                "adjacency": cats.get("adjacency"),
                "proportion": cats.get("room_proportion") or cats.get("shape"),
                "daylight": cats.get("daylight_potential"),
                "utilization": cats.get("site_utilization"),
                "furniture": q.get("furniture_clearance_score"),
                "zoning": cats.get("zoning"),
                "circulation_ratio": q.get("circulation_ratio"),
            },
            "objective_breakdown": q.get("objective_breakdown"),
            "final_score": q.get("overall"),
            "scores": {
                "overall": q.get("overall"),
                "circulation": cats.get("circulation"),
                "adjacency": cats.get("adjacency"),
                "proportion": cats.get("room_proportion") or cats.get("shape"),
                "daylight": cats.get("daylight_potential"),
                "utilization": cats.get("site_utilization"),
                "furniture": q.get("furniture_clearance_score"),
                "zoning": cats.get("zoning"),
            },
        }


@dataclass
class StrategyEvaluation:
    strategy: str
    valid: bool
    result: SolveResult | None = None
    quality_score: int | None = None
    residual_area: int | None = None
    largest_residual_region: int | None = None
    residual_region_count: int | None = None
    mass_occupancy: float | None = None
    cluster_cohesion: float | None = None
    circulation_clearance: int | None = None
    furniture_score: int | None = None
    door_clearance_score: int | None = None
    fixture_clearance_score: int | None = None
    room_usability_score: int | None = None
    access_score: int | None = None
    circulation_score: int | None = None
    adjacency_score: int | None = None
    zoning_score: int | None = None
    issues: int = 0
    source: str = "spatial"
    spatial: SpatialPlan | None = None
    hints: dict | None = None
    candidate_id: str = ""
    proportion_score: int | None = None
    daylight_score: int | None = None
    utilization_score: int | None = None
    service_score: int | None = None

    def as_dict(self) -> dict:
        q = (self.result.quality_score or {}) if self.result else {}
        hard = q.get("hard_failures") or []
        if self.result and self.result.validation:
            hard = [e.as_dict() for e in self.result.validation.errors]
        topo = None
        if self.spatial:
            topo = {
                "strategy": self.spatial.strategy.name,
                "relation_count": len(self.spatial.relations),
            }
        return {
            "id": self.candidate_id or self.strategy,
            "strategy": self.strategy,
            "source": self.source,
            "topology": topo,
            "valid": self.valid,
            "hard_failures": hard,
            "quality_score": self.quality_score,
            "final_score": self.quality_score,
            "metrics": {
                "circulation": self.circulation_score,
                "adjacency": self.adjacency_score,
                "proportion": self.proportion_score,
                "daylight": self.daylight_score,
                "utilization": self.utilization_score,
                "furniture": self.furniture_score,
                "zoning": self.zoning_score,
                "service": self.service_score,
                "circulation_ratio": q.get("circulation_ratio"),
            },
            "objective_breakdown": q.get("objective_breakdown"),
            "scores": {
                "circulation": self.circulation_score,
                "adjacency": self.adjacency_score,
                "proportion": self.proportion_score,
                "daylight": self.daylight_score,
                "utilization": self.utilization_score,
                "furniture": self.furniture_score,
                "zoning": self.zoning_score,
                "service": self.service_score,
            },
        }

    def selection_key(self) -> tuple:
        """Lower is better. Organization before leftover packing."""
        order = {n: i for i, n in enumerate(COMPETITION_STRATEGIES)}
        if not self.valid:
            return (1, 0, 0, 0, 0, 0, 0, order.get(self.strategy, 99))
        return (
            0,
            -(self.quality_score or 0),
            -(self.access_score or 0),
            -(self.circulation_score if self.circulation_score is not None else self.circulation_clearance or 0),
            -(self.adjacency_score or 0),
            -(self.zoning_score or 0),
            -(self.room_usability_score or 0),
            self.residual_area if self.residual_area is not None else 10**9,
            order.get(self.strategy, 99),
        )


def evaluation_from_result(
    name: str,
    result: SolveResult,
    source: str = "spatial",
    spatial: SpatialPlan | None = None,
    hints: dict | None = None,
    candidate_id: str = "",
) -> StrategyEvaluation:
    q = result.quality_score or {}
    cats = q.get("categories") or {}
    res = q.get("residual") or {}
    cl = q.get("clusters") or {}
    valid = result.status == "valid" and bool(result.layout) and result.validated
    return StrategyEvaluation(
        strategy=name,
        valid=valid,
        result=result,
        quality_score=q.get("overall") if valid else None,
        residual_area=q.get("building_residual_area"),
        largest_residual_region=res.get("largest_residual_region"),
        residual_region_count=res.get("residual_region_count"),
        mass_occupancy=q.get("mass_occupancy_ratio"),
        cluster_cohesion=cl.get("mean_cohesion"),
        circulation_clearance=q.get("circulation_clearance_score"),
        furniture_score=q.get("furniture_clearance_score"),
        door_clearance_score=q.get("door_clearance_score"),
        fixture_clearance_score=q.get("fixture_clearance_score"),
        room_usability_score=q.get("room_usability_score"),
        access_score=cats.get("vehicle_access"),
        circulation_score=cats.get("circulation"),
        adjacency_score=cats.get("adjacency"),
        zoning_score=q.get("zoning_score") or cats.get("public_private"),
        issues=len(q.get("usability_issues") or []),
        source=source,
        spatial=spatial,
        hints=hints,
        candidate_id=candidate_id or name,
        proportion_score=cats.get("room_proportion") or cats.get("shape"),
        daylight_score=cats.get("daylight_potential"),
        utilization_score=cats.get("site_utilization"),
        service_score=cats.get("service_efficiency"),
    )


def log_evaluation(ev: StrategyEvaluation) -> None:
    if ev.valid:
        print(f"[KIYUB] Strategy {ev.strategy}: valid score={ev.quality_score} source={ev.source}")
    else:
        reason = (ev.result.reason if ev.result else "") or "infeasible"
        print(f"[KIYUB] Strategy {ev.strategy}: infeasible ({reason[:80]})")


def select_evaluation(evals: list[StrategyEvaluation]) -> StrategyEvaluation | None:
    valid = [e for e in evals if e.valid]
    if not valid:
        return None
    return min(valid, key=lambda e: e.selection_key())


def evaluate_strategy(
    program: RoomProgram,
    envelope: Envelope,
    spatial: SpatialPlan,
    mass: BuildingMass | None,
    use_clusters: bool = True,
    time_limit_s: float = 8.0,
    hints: dict[str, tuple[int, int, int, int]] | None = None,
    source: str = "spatial",
    candidate_id: str = "",
) -> StrategyEvaluation:
    name = spatial.strategy.name

    def _run(use_hints: dict | None, clusters: bool) -> SolveResult:
        return solve(
            program, envelope, hints=use_hints, time_limit_s=time_limit_s,
            spatial_plan=spatial, building_mass=mass, use_clusters=clusters,
        )

    result = _run(hints, use_clusters)
    if result.status != "valid" and use_clusters:
        print(f"[KIYUB] Strategy {name}: retrying without cluster terms")
        result = _run(hints, False)
    if result.status != "valid" and hints:
        print(f"[KIYUB] Strategy {name}: retrying without AI hints")
        result = _run(None, use_clusters)
        if result.status != "valid" and use_clusters:
            print(f"[KIYUB] Strategy {name}: retrying without cluster terms or AI hints")
            result = _run(None, False)
    return evaluation_from_result(
        name, result, source=source, spatial=spatial, hints=hints,
        candidate_id=candidate_id or name,
    )


def compete(
    program: RoomProgram,
    envelope: Envelope,
    mass: BuildingMass | None,
    use_clusters: bool = True,
    time_limit_s: float = 8.0,
    candidates: list[SpatialPlan] | None = None,
    hints: dict[str, tuple[int, int, int, int]] | None = None,
    extra_hints: dict[str, tuple[int, int, int, int]] | None = None,
    extra_source: str = "moe_fallback",
) -> tuple[StrategyEvaluation | None, list[StrategyEvaluation]]:
    plans = list(candidates or generate_strategy_candidates(program))
    count = candidate_count()
    plans = plans[:count]
    evals: list[StrategyEvaluation] = []
    for spatial in plans:
        ev = evaluate_strategy(
            program, envelope, spatial, mass,
            use_clusters=use_clusters, time_limit_s=time_limit_s,
            hints=None,
            source="spatial",
            candidate_id=spatial.strategy.name,
        )
        log_evaluation(ev)
        evals.append(ev)
    hint_pack = hints or extra_hints
    hint_source = "housegan" if hints else extra_source
    if hint_pack and plans:
        ev = evaluate_strategy(
            program, envelope, plans[0], mass,
            use_clusters=use_clusters, time_limit_s=time_limit_s,
            hints=hint_pack,
            source=hint_source,
            candidate_id=f"{plans[0].strategy.name}+{hint_source}",
        )
        log_evaluation(ev)
        evals.append(ev)
    winner = select_evaluation(evals)
    if winner:
        print(f"[KIYUB] Selected strategy: {winner.strategy} source={winner.source}")
    else:
        print("[KIYUB] Selected strategy: none (all infeasible)")
    return winner, evals

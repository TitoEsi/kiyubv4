"""Semantic relationship graph. Strengths, not CP-SAT packing rules."""

from __future__ import annotations

from .architectural_program import ArchitecturalProgram
from .room_graph import build_room_graph
from .spatial_plan import SemanticRelation


def build_planning_graph(arch: ArchitecturalProgram) -> list[SemanticRelation]:
    return build_room_graph(arch).semantic_relations()

"""Retired architectural styles: not accepted for generation, absent from generation knowledge."""
import json
from pathlib import Path

import pytest

from architectural_styles import RETIRED_STYLES

UI_STYLES = [
    "modern", "traditional", "contemporary", "japandi", "minimalist", "brutalist",
    "modern_tropical", "filipino_contemporary", "tropical_minimalist",
]


def test_retired_set_is_exactly_farmhouse_and_craftsman():
    assert RETIRED_STYLES == {"farmhouse", "craftsman"}
    assert not RETIRED_STYLES & set(UI_STYLES)


@pytest.mark.parametrize("style", sorted(RETIRED_STYLES))
def test_constraints_reject_retired_styles(style):
    pytest.importorskip("torch")
    from pydantic import ValidationError
    from main import Constraints

    with pytest.raises(ValidationError, match="no longer offered"):
        Constraints(style=style)


@pytest.mark.parametrize("style", UI_STYLES)
def test_constraints_accept_supported_styles(style):
    pytest.importorskip("torch")
    from main import Constraints

    assert Constraints(style=style).style == style


def test_knowledge_base_has_no_retired_style_chunks():
    kb = json.loads((Path(__file__).resolve().parents[1] / "arch_knowledge.json").read_text(encoding="utf-8"))
    assert kb["chunks"]
    for chunk in kb["chunks"]:
        text = f"{chunk.get('id', '')} {chunk.get('text', '')}".lower()
        assert "farmhouse" not in text and "craftsman" not in text


def test_encoder_slots_still_resolve_for_saved_data():
    pytest.importorskip("torch")
    from moe.data import encoder_style_name

    assert encoder_style_name("farmhouse") == "farmhouse"
    assert encoder_style_name("craftsman") == "craftsman"

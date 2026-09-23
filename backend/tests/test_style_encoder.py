import torch

from moe.config import MOEConfig
from moe.data import encode_constraints, encoder_style_name


def _vec(style: str):
    return encode_constraints(
        bedrooms=3,
        bathrooms=2,
        sqft=1800,
        stories=1,
        style=style,
        open_plan=False,
        primary_suite=True,
        home_office=False,
        formal_dining=False,
        garage="2car",
        laundry="room",
        outdoor="patio",
        ceiling_height="standard",
        config=MOEConfig(),
    )


def test_encoder_styles_length_frozen():
    cfg = MOEConfig()
    assert len(cfg.STYLES) == 8
    assert cfg.STYLES[0] == "modern"
    assert cfg.STYLES[3] == "ranch"


def test_ui_styles_map_onto_encoder_buckets():
    assert encoder_style_name("japandi") == "modern"
    assert encoder_style_name("minimalist") == "modern"
    assert encoder_style_name("brutalist") == "contemporary"
    assert encoder_style_name("ranch") == "ranch"
    assert torch.equal(_vec("japandi"), _vec("modern"))
    assert torch.equal(_vec("brutalist"), _vec("contemporary"))
    assert _vec("japandi").shape[-1] == _vec("modern").shape[-1]

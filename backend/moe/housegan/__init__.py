"""
HouseGAN++ integration for Buildify.

Public API:
  build_bubble_diagram(constraints) → BubbleDiagram
  generate_layouts(diagram, num_variants, mode) → List[List[Dict]]
"""
from .bubble_diagram import BubbleDiagram, BubbleRoom, build_bubble_diagram, diagram_summary
from .inference import (
    generate_layouts,
    get_housegan_status,
    HouseGANStatus,
    reset_housegan_runtime,
)
from .model import HouseGANGenerator, load_pretrained, unwrap_state_dict
from .official_generator import Generator as OfficialGenerator

__all__ = [
    "BubbleDiagram",
    "BubbleRoom",
    "build_bubble_diagram",
    "diagram_summary",
    "generate_layouts",
    "get_housegan_status",
    "HouseGANStatus",
    "HouseGANGenerator",
    "OfficialGenerator",
    "load_pretrained",
    "unwrap_state_dict",
    "reset_housegan_runtime",
]

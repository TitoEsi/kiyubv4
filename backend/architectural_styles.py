"""Architectural style policy shared by the generation API and the project workflow."""

# No longer offered. Saved briefs may still hold these; they stay readable but cannot generate.
RETIRED_STYLES = frozenset({"craftsman", "farmhouse"})


def retired_style_message(style: str) -> str:
    return f"The {style} style is no longer offered. Choose a supported architectural style."

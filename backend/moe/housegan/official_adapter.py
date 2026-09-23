"""Pack KIYUB BubbleDiagram tensors for the official HouseGAN++ Generator.

Does not change OR-Tools, ranking, or the evaluator.
Not professional architectural approval.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from .bubble_diagram import BubbleDiagram

# Official RPLAN ROOM_CLASS (1-indexed). One-hot index = class_id - 1, dim 18.
RPLAN_LIVING = 1
RPLAN_KITCHEN = 2
RPLAN_BEDROOM = 3
RPLAN_BATHROOM = 4
RPLAN_BALCONY = 5
RPLAN_ENTRANCE = 6
RPLAN_DINING = 7
RPLAN_STUDY = 8
RPLAN_STORAGE = 10
RPLAN_UNKNOWN = 16

NUM_RPLAN_TYPES = 18
NOISE_DIM = 128
MASK_SIZE = 64

# KIYUB HG_TYPES id → official RPLAN class id (not one-hot index).
KIYUB_HG_TO_RPLAN = {
    1: RPLAN_LIVING,     # living_room
    2: RPLAN_BEDROOM,    # master_bedroom
    3: RPLAN_KITCHEN,    # kitchen
    4: RPLAN_BATHROOM,   # bathroom
    5: RPLAN_DINING,     # dining_room
    6: RPLAN_BEDROOM,    # bedroom
    7: RPLAN_STUDY,      # home_office
    8: RPLAN_BEDROOM,    # bedroom_guest
    9: RPLAN_BALCONY,    # balcony / patio / deck
    10: RPLAN_ENTRANCE,  # foyer
    11: RPLAN_STORAGE,   # closet
    12: RPLAN_STORAGE,   # laundry
    13: RPLAN_UNKNOWN,   # hallway
    14: RPLAN_STORAGE,   # garage
    15: RPLAN_STORAGE,   # mudroom
}


def rplan_class_id(hg_type: int) -> int:
    return KIYUB_HG_TO_RPLAN.get(int(hg_type), RPLAN_UNKNOWN)


def one_hot_types(hg_types, device: torch.device | str = "cpu") -> torch.Tensor:
    """(N,) KIYUB hg type ids → (N, 18) official one-hot."""
    n = len(hg_types)
    y = torch.zeros(n, NUM_RPLAN_TYPES, dtype=torch.float32, device=device)
    for i, hg in enumerate(hg_types):
        cid = rplan_class_id(hg)
        idx = max(0, min(NUM_RPLAN_TYPES - 1, cid - 1))
        y[i, idx] = 1.0
    return y


def edge_list_from_adj(adj, device: torch.device | str = "cpu") -> torch.Tensor:
    """Dense (N,N) binary adj → (E, 3) [src, +1, dst] for i < j."""
    n = int(adj.shape[0])
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if float(adj[i, j]) >= 0.4:
                edges.append([i, 1, j])
    if not edges:
        return torch.zeros(0, 3, dtype=torch.long, device=device)
    return torch.tensor(edges, dtype=torch.long, device=device)


def unconstrained_masks(n: int, device: torch.device | str = "cpu") -> torch.Tensor:
    """Official _init_input when prev masks are None and no nodes are fixed.

    Channel 0: -1 occupancy. Channel 1: 0 (not a given/fixed node).
    """
    occupancy = torch.full((n, 1, MASK_SIZE, MASK_SIZE), -1.0, device=device)
    valid = torch.zeros((n, 1, MASK_SIZE, MASK_SIZE), device=device)
    return torch.cat([occupancy, valid], dim=1)


def given_m_from_previous(
    prev_masks: torch.Tensor | None,
    fixed_nodes: list[int] | None,
    n: int,
    device: torch.device | str = "cpu",
) -> torch.Tensor:
    """Official fix_nodes: occupancy from prev tanh, validity=1 on fixed rooms.

    prev_masks: (N, 64, 64) or (N, 1, 64, 64) tanh occupancy.
    """
    given_m = unconstrained_masks(n, device=device)
    if prev_masks is None or not fixed_nodes:
        return given_m
    occ = prev_masks.to(device)
    if occ.dim() == 4:
        occ = occ[:, 0]
    for i in fixed_nodes:
        if i < 0 or i >= n:
            continue
        given_m[i, 0] = occ[i]
        given_m[i, 1] = 1.0
    return given_m


def pack_official_inputs(
    diagram: "BubbleDiagram",
    device: torch.device | str = "cpu",
    z: torch.Tensor | None = None,
    prev_masks: torch.Tensor | None = None,
    fixed_nodes: list[int] | None = None,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Return z, given_m, given_y, given_w on device."""
    n = diagram.n
    given_y = one_hot_types(diagram.hg_type_vector, device=device)
    given_w = edge_list_from_adj(diagram.binary_adj, device=device)
    given_m = given_m_from_previous(prev_masks, fixed_nodes, n, device=device)
    if z is None:
        z = torch.randn(n, NOISE_DIM, dtype=torch.float32, device=device)
    else:
        z = z.to(device)
    return z, given_m, given_y, given_w


def official_masks_to_nchw(masks: torch.Tensor) -> torch.Tensor:
    """Official (N, 64, 64) tanh → (N, 1, 64, 64) for masks_to_bboxes."""
    if masks.dim() == 3:
        return masks.unsqueeze(1)
    return masks

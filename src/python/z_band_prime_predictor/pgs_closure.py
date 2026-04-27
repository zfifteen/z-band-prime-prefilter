"""Pure PGS candidate-closure classifier."""

from __future__ import annotations

import numpy as np


PGS_CLOSED = 0
PGS_OPEN = 1
WHEEL_OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})


def pgs_closure_segment(anchor_p: int, candidate_bound: int) -> np.ndarray:
    """Return PGS closure status for candidates after one anchor."""
    anchor_p = int(anchor_p)
    candidate_bound = int(candidate_bound)
    if candidate_bound < 1:
        raise ValueError("candidate_bound must be positive")

    statuses = np.full(candidate_bound, PGS_CLOSED, dtype=np.uint8)
    for offset in range(1, candidate_bound + 1):
        if (anchor_p + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30:
            statuses[offset - 1] = PGS_OPEN
    return statuses

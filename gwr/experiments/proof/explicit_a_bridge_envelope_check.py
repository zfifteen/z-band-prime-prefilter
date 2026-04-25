#!/usr/bin/env python3
"""Evaluate the explicit-A bridge envelope at the retained handoff points."""

from __future__ import annotations

import json
import math


THETA = 0.525
CONSERVATIVE_C = 1.5379
AUDIT_HANDOFF = 5_000_000_000
DUSART_HANDOFF = 5_571_362_243_795


def a_max(p0: int) -> float:
    """Return the one-point leading-constant budget at handoff p0."""
    log_p0 = math.log(p0)
    return (p0 ** (1.0 - THETA)) * log_p0 * math.exp(
        -CONSERVATIVE_C * log_p0 / math.log(log_p0)
    )


def envelope(p0: int, leading_constant: float) -> float:
    """Return E_{theta,c,A}(p0)."""
    log_p0 = math.log(p0)
    return (
        leading_constant
        * (p0 ** (THETA - 1.0))
        * (log_p0 ** -1.0)
        * math.exp(CONSERVATIVE_C * log_p0 / math.log(log_p0))
    )


def main() -> int:
    """Print the retained bridge budgets as deterministic JSON."""
    audit_budget = a_max(AUDIT_HANDOFF)
    dusart_budget = a_max(DUSART_HANDOFF)
    payload = {
        "theta": THETA,
        "conservative_c": CONSERVATIVE_C,
        "audit_handoff": AUDIT_HANDOFF,
        "audit_a_max": audit_budget,
        "audit_envelope_at_A_1": envelope(AUDIT_HANDOFF, 1.0),
        "dusart_handoff": DUSART_HANDOFF,
        "dusart_a_max": dusart_budget,
        "dusart_envelope_at_A_1": envelope(DUSART_HANDOFF, 1.0),
        "audit_budget_matches_retained_value": math.isclose(
            audit_budget,
            14.246224287129907,
            rel_tol=0.0,
            abs_tol=1e-14,
        ),
        "dusart_budget_matches_retained_value": math.isclose(
            dusart_budget,
            52.627783539395274,
            rel_tol=0.0,
            abs_tol=1e-12,
        ),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

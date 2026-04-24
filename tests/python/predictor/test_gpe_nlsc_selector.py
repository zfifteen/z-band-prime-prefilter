"""Tests for the Milestone 2 GPE NLSC selector surface."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor import (
    GPENLSCSelectorState,
    InsufficientBoundarySelectorStateError,
    UndefinedNLSCSelectorBranchError,
    oracle_nlsc_selector_row,
    select_d4_nlsc_boundary_prime,
    validate_d4_nlsc_selector,
)


def state_from_exact_d4_row(row) -> GPENLSCSelectorState:
    """Return the explicit development state for one exact d=4 row."""
    return GPENLSCSelectorState(
        boundary_offset=row.boundary_offset,
        threat_horizon=row.threat_horizon,
    )


def test_d4_nlsc_oracle_rows_include_square_threat_horizon():
    """Dominant d=4 rows should expose the exact S_+(w) ceiling."""
    row = oracle_nlsc_selector_row(13)

    assert row.current_prime == 13
    assert row.winner == 14
    assert row.winner_divisor_class == 4
    assert row.next_prime == 17
    assert row.threat_horizon == 25
    assert row.nlsc_margin == 8
    assert row.square_phase_utilization == (3, 11)


def test_d4_nlsc_selector_matches_exact_boundary_on_branch_examples():
    """The branch harness should compare selected boundaries to exact rows."""
    validations = validate_d4_nlsc_selector(
        current_primes=(13, 73),
        selector=select_d4_nlsc_boundary_prime,
        state_factory=state_from_exact_d4_row,
    )

    assert [item.observed_next_prime for item in validations] == [17, 79]
    assert all(item.matches_oracle for item in validations)
    assert all(item.inside_threat_horizon for item in validations)


def test_d4_nlsc_selector_fails_without_boundary_law_state():
    """The NLSC ceiling alone must not be treated as exact boundary selection."""
    row = oracle_nlsc_selector_row(13)

    try:
        select_d4_nlsc_boundary_prime(
            row.current_prime,
            GPENLSCSelectorState(threat_horizon=row.threat_horizon),
            row.winner,
            row.winner_divisor_class,
        )
    except InsufficientBoundarySelectorStateError as exc:
        assert "does not determine the exact boundary offset" in str(exc)
    else:
        raise AssertionError("missing d=4 branch law state should fail explicitly")


def test_nlsc_selector_reports_unresolved_non_d4_branch():
    """Non-d4 rows should remain explicit unresolved branch targets."""
    row = oracle_nlsc_selector_row(23)

    assert row.winner_divisor_class == 3
    assert row.threat_horizon is None

    try:
        select_d4_nlsc_boundary_prime(
            row.current_prime,
            GPENLSCSelectorState(),
            row.winner,
            row.winner_divisor_class,
        )
    except UndefinedNLSCSelectorBranchError as exc:
        assert "d(w)=3" in str(exc)
    else:
        raise AssertionError("non-d4 branch should fail as an unresolved selector target")

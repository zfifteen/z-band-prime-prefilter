"""Bound-obstruction tests for the minimal PGS generator."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    PGSUnresolvedError,
    emit_record,
)


FIRST_GAP_ABOVE_128 = {
    "p": 1357201,
    "q": 1357333,
    "gap": 132,
}


def test_default_bound_fails_at_first_gap_above_128():
    """The default 128-wide chamber is not universal."""
    with pytest.raises(PGSUnresolvedError) as excinfo:
        emit_record(FIRST_GAP_ABOVE_128["p"])

    assert (
        str(excinfo.value)
        == "PGS selector did not resolve p=1357201 within bound=128"
    )


def test_gap_sized_chamber_resolves_the_same_anchor():
    """The obstruction is the bound, not the resolved-survivor rule."""
    assert emit_record(
        FIRST_GAP_ABOVE_128["p"],
        candidate_bound=FIRST_GAP_ABOVE_128["gap"],
    ) == {
        "p": FIRST_GAP_ABOVE_128["p"],
        "q": FIRST_GAP_ABOVE_128["q"],
    }

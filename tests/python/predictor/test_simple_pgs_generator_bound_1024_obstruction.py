"""1024-bound obstruction tests for the minimal PGS generator."""

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


FIRST_GAP_ABOVE_1024 = {
    "p": 1693182318746371,
    "q": 1693182318747503,
    "gap": 1132,
}


def test_bound_1024_fails_at_first_certified_gap_above_1024():
    """A 1024-wide chamber is not universal on prime inputs >= 5."""
    with pytest.raises(PGSUnresolvedError) as excinfo:
        emit_record(FIRST_GAP_ABOVE_1024["p"], candidate_bound=1024)

    assert (
        str(excinfo.value)
        == "PGS selector did not resolve p=1693182318746371 within bound=1024"
    )


def test_gap_sized_chamber_resolves_the_1024_bound_obstruction_anchor():
    """The 1024 obstruction is chamber width, not a selector misfire."""
    assert emit_record(
        FIRST_GAP_ABOVE_1024["p"],
        candidate_bound=FIRST_GAP_ABOVE_1024["gap"],
    ) == {
        "p": FIRST_GAP_ABOVE_1024["p"],
        "q": FIRST_GAP_ABOVE_1024["q"],
    }

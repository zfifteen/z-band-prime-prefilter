"""Tests for the exact composite-field interval engine."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import sympy


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


def naive_divisor_count(n: int) -> int:
    """Compute the exact divisor count with direct integer enumeration."""
    count = 0
    root = math.isqrt(n)
    for divisor in range(1, root + 1):
        if n % divisor != 0:
            continue
        count += 1 if divisor * divisor == n else 2
    return count


def test_divisor_counts_segment_matches_naive_small_interval():
    """The exact interval engine should match direct counting on a small range."""
    lo = 1
    hi = 64

    observed = divisor_counts_segment(lo, hi)
    expected = [naive_divisor_count(n) for n in range(lo, hi)]

    assert observed.tolist() == expected


def test_divisor_counts_segment_matches_oracle_near_10e18():
    """The exact interval engine should stay correct on a real interval near 10^18."""
    lo = 10**18 - 32
    hi = lo + 16

    observed = divisor_counts_segment(lo, hi)
    expected = [sympy.divisor_count(n) for n in range(lo, hi)]

    assert observed.tolist() == expected

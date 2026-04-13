#!/usr/bin/env python3
"""Scan exact prime gaps for the coarse residual-class window surrogate.

This script checks only the relaxed condition

    d(k) = D, d(w) <= D_w, delta_actual = w - k > Delta_D

inside exact consecutive-prime gaps.

It does not encode the retained-frontier winner-class restrictions used in
`residual_class_closure_20260412_2048.json`, and it does not filter by the
square-free retained-branch hypotheses such as `first_d4_offset = null` and
`square_margin > 0`.

So a violation reported here refutes only that coarse surrogate. It does not,
by itself, refute the narrower retained theorem target.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


DEFAULT_CLASS_WINDOWS = {
    10: {"winner_divisor_bound": 8, "delta": 14},
    14: {"winner_divisor_bound": 12, "delta": 7},
    18: {"winner_divisor_bound": 16, "delta": 5},
    20: {"winner_divisor_bound": 18, "delta": 4},
    22: {"winner_divisor_bound": 20, "delta": 1},
    26: {"winner_divisor_bound": 24, "delta": 2},
    27: {"winner_divisor_bound": 24, "delta": 1},
    28: {"winner_divisor_bound": 27, "delta": 4},
    30: {"winner_divisor_bound": 28, "delta": 1},
    36: {"winner_divisor_bound": 32, "delta": 4},
    40: {"winner_divisor_bound": 36, "delta": 2},
    42: {"winner_divisor_bound": 40, "delta": 1},
    44: {"winner_divisor_bound": 40, "delta": 1},
    50: {"winner_divisor_bound": 48, "delta": 2},
    52: {"winner_divisor_bound": 48, "delta": 1},
    54: {"winner_divisor_bound": 48, "delta": 2},
    56: {"winner_divisor_bound": 48, "delta": 2},
    60: {"winner_divisor_bound": 56, "delta": 1},
}


@dataclass(frozen=True)
class ResidualClassWindow:
    """One residual class with the coarse winner-divisor upper bound and delta."""

    D: int
    winner_divisor_bound: int
    delta: int


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan exact consecutive-prime gaps for violations of the coarse "
            "residual-class window surrogate d(w) <= D_w."
        ),
    )
    parser.add_argument(
        "--lo",
        type=int,
        default=2,
        help="Inclusive lower bound for the exact scan.",
    )
    parser.add_argument(
        "--hi",
        type=int,
        default=20_000_001,
        help="Exclusive upper bound for the exact scan.",
    )
    parser.add_argument(
        "--residual-closure-json",
        type=Path,
        default=ROOT / "output" / "gwr_proof" / "residual_class_closure_20260412_2048.json",
        help="Residual-class closure artifact that defines the target classes.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def load_residual_classes(path: Path) -> list[ResidualClassWindow]:
    """Load the class list and coarse window bounds from the closure artifact."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = payload["results"]
    classes: list[ResidualClassWindow] = []
    for key in sorted(results, key=lambda raw: int(raw)):
        divisor_class = int(key)
        if divisor_class not in DEFAULT_CLASS_WINDOWS:
            raise RuntimeError(f"no retained class-window entry for D={divisor_class}")
        row = DEFAULT_CLASS_WINDOWS[divisor_class]
        classes.append(
            ResidualClassWindow(
                D=divisor_class,
                winner_divisor_bound=int(row["winner_divisor_bound"]),
                delta=int(row["delta"]),
            )
        )
    return classes


def _result_row(divisor_class: ResidualClassWindow) -> dict[str, object]:
    """Create one JSON-ready result row."""
    return {
        "D": divisor_class.D,
        "delta_observed": divisor_class.delta,
        "status": "OPEN",
        "lemma": None,
        "min_p_threshold": None,
        "violation": None,
    }


def scan_window_violations(
    lo: int,
    hi: int,
    residual_classes: list[ResidualClassWindow],
) -> dict[str, object]:
    """Return the first exact coarse-surrogate violation for each class."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    classes_by_D = {row.D: row for row in residual_classes}
    results = {row.D: _result_row(row) for row in residual_classes}
    unresolved = set(classes_by_D)

    for left_prime_raw, right_prime_raw in zip(primes[:-1], primes[1:]):
        if not unresolved:
            break

        left_prime = int(left_prime_raw)
        right_prime = int(right_prime_raw)
        if right_prime - left_prime < 4:
            continue

        left_index = left_prime - lo + 1
        right_index = right_prime - lo
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]
        winner_divisor_count = int(np.min(gap_divisors))
        winner_index = int(np.flatnonzero(gap_divisors == winner_divisor_count)[0])
        winner_value = int(gap_values[winner_index])

        if winner_index == 0:
            continue

        earlier_values = gap_values[:winner_index]
        earlier_divisors = gap_divisors[:winner_index]
        divisor_classes_present = set(int(value) for value in np.unique(earlier_divisors))

        for divisor_class in sorted(unresolved & divisor_classes_present):
            row = classes_by_D[divisor_class]
            if winner_divisor_count > row.winner_divisor_bound:
                continue

            earlier_indices = np.flatnonzero(earlier_divisors == divisor_class)
            if earlier_indices.size == 0:
                continue

            leftmost_k = int(earlier_values[int(earlier_indices[0])])
            delta_actual = winner_value - leftmost_k
            if delta_actual <= row.delta:
                continue

            results[divisor_class]["status"] = "VIOLATION_FOUND"
            results[divisor_class]["violation"] = {
                "p": left_prime,
                "q": right_prime,
                "k": leftmost_k,
                "w": winner_value,
                "delta_actual": delta_actual,
            }
            unresolved.remove(divisor_class)

    return {
        "search_interval": {"lo": lo, "hi": hi},
        "all_classes_resolved": not unresolved,
        "open_classes": sorted(unresolved),
        "results": [results[row.D] for row in residual_classes],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the exact coarse-surrogate window scan."""
    args = build_parser().parse_args(argv)
    residual_classes = load_residual_classes(args.residual_closure_json)
    payload = scan_window_violations(args.lo, args.hi, residual_classes)
    payload["source_artifacts"] = [
        str(args.residual_closure_json.relative_to(ROOT)),
        "output/gwr_proof/prime_gap_admissibility_frontier_1e9_checkpoints.json",
        "gwr/findings/prime_gap_admissibility_theorem.md",
    ]
    payload["warning"] = (
        "This artifact tests only the relaxed surrogate d(w)<=D_w. It does not apply "
        "the retained winner-class filter or the retained branch hypotheses "
        "first_d4_offset = null and square_margin > 0."
    )
    payload["method"] = (
        "Exact consecutive-prime gap scan of the coarse surrogate. For each residual class "
        "D, record the first gap with a left-of-winner carrier k satisfying d(k)=D, a winner "
        "w satisfying d(w)<=D_w, and delta_actual=w-k greater than Delta_D."
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

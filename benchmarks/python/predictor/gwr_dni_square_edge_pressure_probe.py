#!/usr/bin/env python3
"""Measure square-branch cutoff pressure by within-gap square position.

The mixed-scale cutoff note showed that the square branch carries the visible
log-squared tail. This probe tests a sharper claim inside that branch:

high cutoff-utilization rows are driven less by whole-gap size than by the
prime square landing late inside its enclosing prime gap.

For each odd prime p, let q = prevprime(p^2) and q^+ = nextprime(q). The probe
records:

- square offset: p^2 - q
- gap width: q^+ - q
- left share: (p^2 - q) / (q^+ - q)
- gap/cutoff ratio: (q^+ - q) / C(q)
- utilization: (p^2 - q) / C(q)

It emits one JSON summary and one frontier CSV of utilization-record rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from pathlib import Path

import gmpy2
from sympy import primerange


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MIN_PRIME = 3
DEFAULT_MAX_PRIME = 10_000_000
DEFAULT_OUTPUT_DIR = ROOT / "output" / "gwr_proof" / "square_edge_pressure_probe_1e7"
CSV_FIELDS = [
    "p",
    "previous_prime",
    "next_prime",
    "offset",
    "gap_width",
    "left_share",
    "gap_cutoff_ratio",
    "dynamic_cutoff",
    "dynamic_cutoff_utilization",
    "o_q",
    "elapsed_seconds",
]
QUANTILES = [0.9, 0.95, 0.99, 0.999]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Probe square-branch cutoff pressure by within-gap square position.",
    )
    parser.add_argument(
        "--min-prime",
        type=int,
        default=DEFAULT_MIN_PRIME,
        help="Smallest odd prime p to test via p^2.",
    )
    parser.add_argument(
        "--max-prime",
        type=int,
        default=DEFAULT_MAX_PRIME,
        help="Largest odd prime p to test via p^2.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and CSV artifacts.",
    )
    return parser


def _first_tested_prime(min_prime: int) -> int:
    """Return the first odd prime at or above the requested lower bound."""
    if min_prime <= 3:
        return 3
    return int(gmpy2.next_prime(min_prime - 1))


def _previous_prime_before_square(square: int) -> int:
    """Return the prime immediately below one odd prime square."""
    candidate = square - 2
    while not gmpy2.is_prime(candidate):
        candidate -= 2
    return int(candidate)


def _first_open_offset(residue: int) -> int:
    """Return the first even offset whose residue class is open mod 30."""
    for offset in (2, 4, 6, 8, 10, 12):
        candidate = (residue + offset) % 30
        if candidate % 3 != 0 and candidate % 5 != 0:
            return offset
    raise RuntimeError(f"no wheel-open offset found for residue {residue}")


def _dynamic_cutoff(q: int) -> int:
    """Return the dynamic log-squared cutoff for prime q."""
    return max(64, math.ceil(0.5 * math.log(q) ** 2))


def _row_for_prime_square(p: int, started_at: float) -> dict[str, object]:
    """Return the square-branch geometry row for one prime p."""
    square = p * p
    previous_prime = _previous_prime_before_square(square)
    next_prime = int(gmpy2.next_prime(previous_prime))
    offset = square - previous_prime
    gap_width = next_prime - previous_prime
    dynamic_cutoff = _dynamic_cutoff(previous_prime)

    return {
        "p": int(p),
        "previous_prime": int(previous_prime),
        "next_prime": int(next_prime),
        "offset": int(offset),
        "gap_width": int(gap_width),
        "left_share": float(offset) / float(gap_width),
        "gap_cutoff_ratio": float(gap_width) / float(dynamic_cutoff),
        "dynamic_cutoff": int(dynamic_cutoff),
        "dynamic_cutoff_utilization": float(offset) / float(dynamic_cutoff),
        "o_q": int(_first_open_offset(previous_prime % 30)),
        "elapsed_seconds": time.time() - started_at,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write one LF-terminated CSV file."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _top_quantile_summary(rows: list[dict[str, object]], quantile: float) -> dict[str, object]:
    """Return one exact top-utilization quantile summary."""
    if not 0.0 < quantile < 1.0:
        raise ValueError("quantile must lie strictly between 0 and 1")
    if not rows:
        raise ValueError("rows must not be empty")

    ordered = sorted(rows, key=lambda row: float(row["dynamic_cutoff_utilization"]))
    threshold_index = min(int(len(ordered) * quantile), len(ordered) - 1)
    threshold = float(ordered[threshold_index]["dynamic_cutoff_utilization"])
    subset = [
        row for row in rows if float(row["dynamic_cutoff_utilization"]) >= threshold
    ]

    subset_count = len(subset)
    if subset_count < 1:
        raise ValueError("top-quantile subset must not be empty")

    return {
        "quantile": quantile,
        "utilization_threshold": threshold,
        "row_count": subset_count,
        "mean_left_share": sum(float(row["left_share"]) for row in subset) / subset_count,
        "mean_gap_cutoff_ratio": sum(float(row["gap_cutoff_ratio"]) for row in subset)
        / subset_count,
        "share_left_share_ge_0_75": sum(
            float(row["left_share"]) >= 0.75 for row in subset
        )
        / subset_count,
        "share_left_share_ge_0_90": sum(
            float(row["left_share"]) >= 0.90 for row in subset
        )
        / subset_count,
        "share_gap_cutoff_ratio_ge_0_75": sum(
            float(row["gap_cutoff_ratio"]) >= 0.75 for row in subset
        )
        / subset_count,
        "share_gap_cutoff_ratio_ge_1_00": sum(
            float(row["gap_cutoff_ratio"]) >= 1.0 for row in subset
        )
        / subset_count,
        "o_q_counts": {
            "2": sum(int(row["o_q"]) == 2 for row in subset),
            "4": sum(int(row["o_q"]) == 4 for row in subset),
            "6": sum(int(row["o_q"]) == 6 for row in subset),
        },
    }


def run_probe(
    min_prime: int,
    max_prime: int,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Probe square-branch edge pressure on one deterministic prime range."""
    if min_prime < 3:
        raise ValueError("min_prime must be at least 3")
    if max_prime < min_prime:
        raise ValueError("max_prime must be at least min_prime")

    started_at = time.time()
    all_rows: list[dict[str, object]] = []
    frontier_rows: list[dict[str, object]] = []
    first_tested_prime: int | None = None
    last_tested_prime: int | None = None
    max_utilization = -1.0
    max_row: dict[str, object] | None = None

    for prime_value in primerange(_first_tested_prime(min_prime), max_prime + 1):
        p = int(prime_value)
        row = _row_for_prime_square(p, started_at)
        all_rows.append(row)
        if first_tested_prime is None:
            first_tested_prime = p
        last_tested_prime = p

        utilization = float(row["dynamic_cutoff_utilization"])
        if utilization > max_utilization:
            max_utilization = utilization
            max_row = row
            frontier_rows.append(row)

    tested_prime_count = len(all_rows)
    if tested_prime_count < 1 or max_row is None:
        raise ValueError("probe interval produced no prime-square rows")

    summary = {
        "min_prime": int(min_prime),
        "max_prime": int(max_prime),
        "tested_prime_count": tested_prime_count,
        "first_tested_prime": first_tested_prime,
        "last_tested_prime": last_tested_prime,
        "max_dynamic_cutoff_utilization": max_utilization,
        "max_row": max_row,
        "mean_left_share": sum(float(row["left_share"]) for row in all_rows)
        / tested_prime_count,
        "mean_gap_cutoff_ratio": sum(float(row["gap_cutoff_ratio"]) for row in all_rows)
        / tested_prime_count,
        "share_left_share_ge_0_75": sum(
            float(row["left_share"]) >= 0.75 for row in all_rows
        )
        / tested_prime_count,
        "share_left_share_ge_0_90": sum(
            float(row["left_share"]) >= 0.90 for row in all_rows
        )
        / tested_prime_count,
        "share_gap_cutoff_ratio_ge_0_75": sum(
            float(row["gap_cutoff_ratio"]) >= 0.75 for row in all_rows
        )
        / tested_prime_count,
        "share_gap_cutoff_ratio_ge_1_00": sum(
            float(row["gap_cutoff_ratio"]) >= 1.0 for row in all_rows
        )
        / tested_prime_count,
        "o_q_counts": {
            "2": sum(int(row["o_q"]) == 2 for row in all_rows),
            "4": sum(int(row["o_q"]) == 4 for row in all_rows),
            "6": sum(int(row["o_q"]) == 6 for row in all_rows),
        },
        "top_utilization_quantiles": [
            _top_quantile_summary(all_rows, quantile) for quantile in QUANTILES
        ],
        "frontier_row_count": len(frontier_rows),
        "elapsed_seconds": time.time() - started_at,
    }
    return frontier_rows, summary


def main(argv: list[str] | None = None) -> int:
    """Run the square-edge pressure probe and write artifacts."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    frontier_rows, summary = run_probe(
        min_prime=args.min_prime,
        max_prime=args.max_prime,
    )

    summary_path = args.output_dir / "gwr_dni_square_edge_pressure_probe_summary.json"
    frontier_path = args.output_dir / "gwr_dni_square_edge_pressure_probe_frontier.csv"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(frontier_path, frontier_rows)

    max_row = summary["max_row"]
    print(
        "gwr-dni-square-edge-pressure-probe:"
        f" primes={summary['tested_prime_count']}"
        f" max_utilization={summary['max_dynamic_cutoff_utilization']}"
        f" max_p={max_row['p']}"
        f" left_share={max_row['left_share']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

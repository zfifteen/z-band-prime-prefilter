#!/usr/bin/env python3
"""Scan the dominant d=4 square-threat closure frontier."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment
from z_band_prime_gap_ridge.runs import build_even_window_starts


DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_EXACT_LIMIT = 1_000_000
DEFAULT_SCALES = (
    100_000_000,
    1_000_000_000,
    10_000_000_000,
    100_000_000_000,
    1_000_000_000_000,
    10_000_000_000_000,
    100_000_000_000_000,
    1_000_000_000_000_000,
    10_000_000_000_000_000,
    100_000_000_000_000_000,
    1_000_000_000_000_000_000,
)
DEFAULT_WINDOW_SIZE = 2_000_000
DEFAULT_WINDOW_COUNT = 2
DEFAULT_FRONTIER_SIZE = 20
DEFAULT_PRIME_BUFFER = 100_000
CSV_FIELDS = [
    "scale",
    "window_mode",
    "interval_lo",
    "interval_hi",
    "p",
    "w",
    "q",
    "gap_size",
    "winner_offset",
    "q_offset",
    "winner_d",
    "S_plus_w",
    "square_threat_distance",
    "margin",
    "closure_utilization",
    "log_score_w",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Scan the dominant d=4 square-threat closure frontier.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and CSV artifacts.",
    )
    parser.add_argument(
        "--exact-limit",
        type=int,
        default=DEFAULT_EXACT_LIMIT,
        help="Exact natural-number limit for the full-range scan.",
    )
    parser.add_argument(
        "--scales",
        type=int,
        nargs="+",
        default=list(DEFAULT_SCALES),
        help="Deterministic even-band scales to test.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=DEFAULT_WINDOW_SIZE,
        help="Window size for deterministic even-band sweeps.",
    )
    parser.add_argument(
        "--window-count",
        type=int,
        default=DEFAULT_WINDOW_COUNT,
        help="Number of even windows per scale.",
    )
    parser.add_argument(
        "--frontier-size",
        type=int,
        default=DEFAULT_FRONTIER_SIZE,
        help="Number of tightest positive-margin d=4 rows to retain.",
    )
    parser.add_argument(
        "--prime-buffer",
        type=int,
        default=DEFAULT_PRIME_BUFFER,
        help="Prime lookup buffer above sqrt(max scanned value).",
    )
    return parser


def build_prime_lookup(lo: int, hi: int, prime_buffer: int) -> np.ndarray:
    """Build a local prime table for one interval's square-threat queries."""
    root_lo = max(2, math.isqrt(max(lo, 2)) - 1)
    root_hi = math.isqrt(hi) + prime_buffer
    divisor_count = divisor_counts_segment(root_lo, root_hi + 1)
    values = np.arange(root_lo, root_hi + 1, dtype=np.int64)
    primes = values[divisor_count == 2]
    if primes.size == 0:
        raise RuntimeError("prime lookup construction failed")
    return primes


def first_prime_square_after(n: int, prime_lookup: np.ndarray) -> int:
    """Return the first prime square strictly larger than n."""
    root_floor = math.isqrt(n)
    prime_index = int(np.searchsorted(prime_lookup, root_floor, side="right"))
    if prime_index >= prime_lookup.size:
        raise RuntimeError("prime lookup buffer too small for square-threat scan")
    prime_value = int(prime_lookup[prime_index])
    return prime_value * prime_value


def log_score(value: int, divisor_count: int) -> float:
    """Return the implemented raw-Z log-score."""
    return (1.0 - divisor_count / 2.0) * math.log(value)


def _row_sort_key(row: dict[str, object]) -> tuple[float, int, int, int]:
    """Return the frontier ordering key."""
    return (
        float(row["margin"]),
        -float(row["closure_utilization"]),
        int(row["scale"]),
        int(row["p"]),
    )


def _retain_frontier(
    frontier_rows: list[dict[str, object]],
    candidate_row: dict[str, object],
    frontier_size: int,
) -> None:
    """Retain the tightest positive-margin rows only."""
    frontier_rows.append(candidate_row)
    frontier_rows.sort(key=_row_sort_key)
    if len(frontier_rows) > frontier_size:
        del frontier_rows[frontier_size:]


def analyze_interval(
    lo: int,
    hi: int,
    scale: int,
    window_mode: str,
    *,
    frontier_size: int,
    prime_buffer: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Scan one exact interval and return summary plus frontier rows."""
    started = time.perf_counter()
    prime_lookup = build_prime_lookup(lo=lo, hi=hi, prime_buffer=prime_buffer)
    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]
    log_values = np.log(values.astype(np.float64))

    frontier_rows: list[dict[str, object]] = []
    d4_gap_count = 0
    min_margin: int | None = None
    max_utilization = 0.0
    min_margin_row: dict[str, object] | None = None

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]
        scores = (
            (1.0 - gap_divisors.astype(np.float64) / 2.0)
            * log_values[left_index:right_index]
        )
        winner_index = int(np.argmax(scores))
        winner_n = int(gap_values[winner_index])
        winner_d = int(gap_divisors[winner_index])
        if winner_d != 4:
            continue

        d4_gap_count += 1
        square_threat = first_prime_square_after(winner_n, prime_lookup)
        margin = int(square_threat - int(right_prime))
        if margin <= 0:
            raise AssertionError(
                f"d=4 square-threat closure violated: p={left_prime}, q={right_prime}, "
                f"w={winner_n}, S_+(w)={square_threat}"
            )

        square_threat_distance = int(square_threat - winner_n)
        q_offset = int(right_prime - left_prime)
        winner_offset = int(winner_n - left_prime)
        closure_utilization = float(q_offset - winner_offset) / float(square_threat_distance)
        row = {
            "scale": int(scale),
            "window_mode": window_mode,
            "interval_lo": int(lo),
            "interval_hi": int(hi),
            "p": int(left_prime),
            "w": winner_n,
            "q": int(right_prime),
            "gap_size": q_offset,
            "winner_offset": winner_offset,
            "q_offset": q_offset,
            "winner_d": winner_d,
            "S_plus_w": square_threat,
            "square_threat_distance": square_threat_distance,
            "margin": margin,
            "closure_utilization": closure_utilization,
            "log_score_w": float(log_score(winner_n, winner_d)),
        }

        if min_margin is None or margin < min_margin:
            min_margin = margin
            min_margin_row = row
        if closure_utilization > max_utilization:
            max_utilization = closure_utilization

        _retain_frontier(frontier_rows, row, frontier_size)

    if d4_gap_count == 0:
        raise RuntimeError("interval produced no d=4 winner gaps")

    summary = {
        "scale": int(scale),
        "window_mode": window_mode,
        "lo": int(lo),
        "hi": int(hi),
        "d4_gap_count": d4_gap_count,
        "min_margin": min_margin,
        "min_margin_row": min_margin_row,
        "max_closure_utilization": max_utilization,
        "runtime_seconds": time.perf_counter() - started,
    }
    return summary, frontier_rows


def aggregate_frontier(rows: Sequence[dict[str, object]], frontier_size: int) -> list[dict[str, object]]:
    """Return the global tight-margin frontier."""
    ordered = sorted(rows, key=_row_sort_key)
    return ordered[:frontier_size]


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    """Write one LF-terminated CSV file."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """Run the d=4 square-threat frontier scan and write artifacts."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    summaries: list[dict[str, object]] = []
    all_frontier_candidates: list[dict[str, object]] = []

    exact_summary, exact_frontier = analyze_interval(
        lo=2,
        hi=args.exact_limit + 1,
        scale=args.exact_limit,
        window_mode="exact",
        frontier_size=args.frontier_size,
        prime_buffer=args.prime_buffer,
    )
    summaries.append(exact_summary)
    all_frontier_candidates.extend(exact_frontier)

    for scale in args.scales:
        starts = build_even_window_starts(scale, args.window_size, args.window_count)
        for start in starts:
            summary, frontier_rows = analyze_interval(
                lo=start,
                hi=start + args.window_size,
                scale=scale,
                window_mode="even",
                frontier_size=args.frontier_size,
                prime_buffer=args.prime_buffer,
            )
            summaries.append(summary)
            all_frontier_candidates.extend(frontier_rows)

    frontier = aggregate_frontier(all_frontier_candidates, args.frontier_size)
    if not frontier:
        raise RuntimeError("frontier scan produced no d=4 rows")

    summary = {
        "parameters": {
            "exact_limit": int(args.exact_limit),
            "scales": list(int(scale) for scale in args.scales),
            "window_size": int(args.window_size),
            "window_count": int(args.window_count),
            "frontier_size": int(args.frontier_size),
            "prime_buffer": int(args.prime_buffer),
        },
        "interval_summaries": summaries,
        "global_min_margin": int(frontier[0]["margin"]),
        "global_min_margin_row": frontier[0],
        "global_max_closure_utilization": max(
            float(interval_summary["max_closure_utilization"]) for interval_summary in summaries
        ),
        "frontier": frontier,
        "runtime_seconds": time.perf_counter() - started,
    }

    summary_path = args.output_dir / "d4_square_threat_frontier_summary.json"
    frontier_path = args.output_dir / "d4_square_threat_frontier.csv"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    write_csv(frontier_path, frontier)

    print(
        "d4-square-threat-frontier:"
        f" rows={len(frontier)}"
        f" global_min_margin={summary['global_min_margin']}"
        f" runtime_seconds={summary['runtime_seconds']:.3f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

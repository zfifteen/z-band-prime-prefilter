#!/usr/bin/env python3
"""Exact earlier-candidate local-dominator scan on a fixed integer interval."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan exact prime gaps on an interval and verify that every true "
            "earlier candidate has a later admissible dominator."
        ),
    )
    parser.add_argument(
        "--lo",
        type=int,
        default=2,
        help="Inclusive lower bound of the natural-number interval.",
    )
    parser.add_argument(
        "--hi",
        type=int,
        default=20_000_001,
        help="Exclusive upper bound of the natural-number interval.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    parser.add_argument(
        "--window",
        action="append",
        default=None,
        help="Optional repeated window in lo:hi form. If provided, emit a combined artifact.",
    )
    return parser


def score_strictly_greater(
    left_n: int,
    left_divisor_count: int,
    right_n: int,
    right_divisor_count: int,
) -> bool:
    """Return whether the score at the left value is strictly greater."""
    if left_divisor_count < 3 or right_divisor_count < 3:
        raise ValueError("exact score comparison requires composite inputs")

    return pow(left_n, left_divisor_count - 2) < pow(right_n, right_divisor_count - 2)


def rank_from_offset_counts(offset_counts: dict[int, int], rank: int) -> int:
    """Return the smallest offset whose cumulative count reaches the given rank."""
    cumulative = 0
    for offset in sorted(offset_counts):
        cumulative += offset_counts[offset]
        if cumulative >= rank:
            return offset
    raise RuntimeError("rank exceeds offset count total")


def scan_interval(lo: int, hi: int) -> tuple[int, int, int, dict[int, int]]:
    """Return the exact local-dominator counts on one integer interval."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    gap_count = 0
    earlier_candidate_count = 0
    unresolved_count = 0
    offset_counts: dict[int, int] = {}

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        gap_count += 1
        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]

        winner_divisor_count = int(np.min(gap_divisors))
        winner_index = int(np.flatnonzero(gap_divisors == winner_divisor_count)[0])

        for earlier_index in range(winner_index):
            earlier_candidate_count += 1
            earlier_value = int(gap_values[earlier_index])
            earlier_divisor_count = int(gap_divisors[earlier_index])

            resolved = False
            for later_index in range(earlier_index + 1, gap_values.size):
                later_value = int(gap_values[later_index])
                later_divisor_count = int(gap_divisors[later_index])
                if score_strictly_greater(
                    later_value,
                    later_divisor_count,
                    earlier_value,
                    earlier_divisor_count,
                ):
                    offset = later_value - earlier_value
                    offset_counts[offset] = offset_counts.get(offset, 0) + 1
                    resolved = True
                    break

            if not resolved:
                unresolved_count += 1

    return gap_count, earlier_candidate_count, unresolved_count, offset_counts


def summarize_counts(
    gap_count: int,
    earlier_candidate_count: int,
    unresolved_count: int,
    offset_counts: dict[int, int],
) -> dict[str, int]:
    """Return the JSON summary fields from exact counts."""
    if earlier_candidate_count == 0:
        raise RuntimeError("interval contains no true earlier candidates")

    median_rank = (earlier_candidate_count + 1) // 2
    percentile_99_rank = (99 * earlier_candidate_count + 99) // 100
    return {
        "gap_count": gap_count,
        "earlier_candidate_count": earlier_candidate_count,
        "unresolved_count": unresolved_count,
        "median_offset": rank_from_offset_counts(offset_counts, median_rank),
        "99th_percentile_offset": rank_from_offset_counts(offset_counts, percentile_99_rank),
        "worst_offset": max(offset_counts),
    }


def analyze_interval(lo: int, hi: int) -> dict[str, int]:
    """Return the exact local-dominator summary on one integer interval."""
    gap_count, earlier_candidate_count, unresolved_count, offset_counts = scan_interval(lo, hi)
    return summarize_counts(
        gap_count,
        earlier_candidate_count,
        unresolved_count,
        offset_counts,
    )


def parse_window(raw_window: str) -> tuple[int, int]:
    """Parse one CLI window argument in lo:hi form."""
    parts = raw_window.split(":")
    if len(parts) != 2:
        raise ValueError(f"invalid window {raw_window!r}")
    return int(parts[0]), int(parts[1])


def main(argv: list[str] | None = None) -> int:
    """Run the exact scan and emit the JSON artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.window:
        windows = [parse_window(raw_window) for raw_window in args.window]
        window_payloads = []
        total_gap_count = 0
        total_earlier_candidate_count = 0
        total_unresolved_count = 0
        total_offset_counts: dict[int, int] = {}

        for lo, hi in windows:
            gap_count, earlier_candidate_count, unresolved_count, offset_counts = scan_interval(lo, hi)
            summary = summarize_counts(
                gap_count,
                earlier_candidate_count,
                unresolved_count,
                offset_counts,
            )
            summary["window"] = [lo, hi]
            window_payloads.append(summary)
            total_gap_count += gap_count
            total_earlier_candidate_count += earlier_candidate_count
            total_unresolved_count += unresolved_count
            for offset, count in offset_counts.items():
                total_offset_counts[offset] = total_offset_counts.get(offset, 0) + count

        payload = {
            "windows": window_payloads,
            "overall": summarize_counts(
                total_gap_count,
                total_earlier_candidate_count,
                total_unresolved_count,
                total_offset_counts,
            ),
        }
    else:
        payload = analyze_interval(args.lo, args.hi)
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Scan whether the first later drop in divisor count already kills each hard low-divisor candidate."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


SPOILER_SCAN_PATH = ROOT / "gwr" / "experiments" / "proof" / "earlier_spoiler_scan.py"
TARGET_CLASSES = (4, 6, 8, 12, 16)


def load_spoiler_scan_module():
    """Load the exact score-comparison helper directly from file."""
    module_name = "earlier_spoiler_scan_runtime_first_descent"
    spec = importlib.util.spec_from_file_location(module_name, SPOILER_SCAN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load earlier_spoiler_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


SPOILER_SCAN = load_spoiler_scan_module()


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "For hard low-divisor earlier candidates, test whether the first later "
            "composite with a smaller divisor count already beats them exactly."
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
    return parser


def analyze_interval(lo: int, hi: int) -> dict[str, object]:
    """Return the first-descent profile for the hard low-divisor classes."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    candidate_count = 0
    unresolved_count = 0
    class_counts: dict[int, int] = {divisor_count_value: 0 for divisor_count_value in TARGET_CLASSES}
    class_resolved_counts: dict[int, int] = {divisor_count_value: 0 for divisor_count_value in TARGET_CLASSES}
    class_max_offsets: dict[int, int] = {divisor_count_value: 0 for divisor_count_value in TARGET_CLASSES}
    pair_counts: dict[tuple[int, int], int] = {}
    pair_resolved_counts: dict[tuple[int, int], int] = {}
    unresolved_examples: list[dict[str, int]] = []

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]

        winner_divisor_count = int(np.min(gap_divisors))
        winner_index = int(np.flatnonzero(gap_divisors == winner_divisor_count)[0])

        for earlier_index in range(winner_index):
            earlier_value = int(gap_values[earlier_index])
            earlier_divisor_count = int(gap_divisors[earlier_index])
            if earlier_divisor_count not in TARGET_CLASSES:
                continue

            candidate_count += 1
            class_counts[earlier_divisor_count] += 1

            first_descent_index = None
            for later_index in range(earlier_index + 1, gap_values.size):
                later_divisor_count = int(gap_divisors[later_index])
                if later_divisor_count < earlier_divisor_count:
                    first_descent_index = later_index
                    break

            if first_descent_index is None:
                raise RuntimeError("No later smaller-divisor composite found before the winner")

            first_descent_value = int(gap_values[first_descent_index])
            first_descent_divisor_count = int(gap_divisors[first_descent_index])
            offset = first_descent_value - earlier_value
            class_max_offsets[earlier_divisor_count] = max(
                class_max_offsets[earlier_divisor_count],
                offset,
            )
            pair_key = (earlier_divisor_count, first_descent_divisor_count)
            pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1

            if SPOILER_SCAN.score_strictly_greater(
                first_descent_value,
                first_descent_divisor_count,
                earlier_value,
                earlier_divisor_count,
            ):
                class_resolved_counts[earlier_divisor_count] += 1
                pair_resolved_counts[pair_key] = pair_resolved_counts.get(pair_key, 0) + 1
                continue

            unresolved_count += 1
            if len(unresolved_examples) < 20:
                unresolved_examples.append(
                    {
                        "left_prime": int(left_prime),
                        "right_prime": int(right_prime),
                        "earlier_value": earlier_value,
                        "earlier_divisor_count": earlier_divisor_count,
                        "first_descent_value": first_descent_value,
                        "first_descent_divisor_count": first_descent_divisor_count,
                        "offset": offset,
                    }
                )

    class_summary = []
    for divisor_count_value in TARGET_CLASSES:
        count = class_counts[divisor_count_value]
        resolved = class_resolved_counts[divisor_count_value]
        class_summary.append(
            {
                "earlier_divisor_count": divisor_count_value,
                "count": count,
                "resolved_by_first_descent_count": resolved,
                "unresolved_by_first_descent_count": count - resolved,
                "max_first_descent_offset": class_max_offsets[divisor_count_value],
            }
        )

    pair_summary = []
    for (earlier_divisor_count, first_descent_divisor_count), count in sorted(pair_counts.items()):
        resolved = pair_resolved_counts.get((earlier_divisor_count, first_descent_divisor_count), 0)
        pair_summary.append(
            {
                "earlier_divisor_count": earlier_divisor_count,
                "first_descent_divisor_count": first_descent_divisor_count,
                "count": count,
                "resolved_by_first_descent_count": resolved,
                "unresolved_by_first_descent_count": count - resolved,
            }
        )

    return {
        "interval": {"lo": lo, "hi": hi},
        "target_classes": list(TARGET_CLASSES),
        "candidate_count": candidate_count,
        "unresolved_by_first_descent_count": unresolved_count,
        "class_summary": class_summary,
        "pair_summary": pair_summary,
        "unresolved_examples": unresolved_examples,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the first-descent scan and emit a JSON artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_interval(args.lo, args.hi)
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

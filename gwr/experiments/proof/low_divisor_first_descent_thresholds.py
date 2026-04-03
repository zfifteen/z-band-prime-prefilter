#!/usr/bin/env python3
"""Profile first-descent pair types against the generic b < 2a domination threshold."""

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
    module_name = "earlier_spoiler_scan_runtime_first_descent_thresholds"
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
            "For hard low-divisor first-descent pairs, compare observed earlier "
            "values to the universal domination threshold implied by b < 2a."
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


def automatic_threshold(earlier_divisor_count: int, first_descent_divisor_count: int) -> int:
    """Return the least integer a for which b < 2a already forces score descent domination."""
    if not (earlier_divisor_count > first_descent_divisor_count >= 3):
        raise ValueError("threshold requires a strict drop to a composite divisor count")

    exponent = earlier_divisor_count - first_descent_divisor_count
    threshold_power = 1 << (first_descent_divisor_count - 2)
    candidate = 1
    while pow(candidate, exponent) < threshold_power:
        candidate += 1
    return candidate


def analyze_interval(lo: int, hi: int) -> dict[str, object]:
    """Return the observed pair profile against the generic automatic threshold."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    pair_stats: dict[tuple[int, int], dict[str, int]] = {}

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

            first_descent_index = None
            for later_index in range(earlier_index + 1, gap_values.size):
                if int(gap_divisors[later_index]) < earlier_divisor_count:
                    first_descent_index = later_index
                    break

            if first_descent_index is None:
                raise RuntimeError("No later smaller-divisor composite found before the winner")

            first_descent_value = int(gap_values[first_descent_index])
            first_descent_divisor_count = int(gap_divisors[first_descent_index])
            pair_key = (earlier_divisor_count, first_descent_divisor_count)
            stats = pair_stats.get(pair_key)
            if stats is None:
                stats = {
                    "count": 0,
                    "min_earlier_value": earlier_value,
                    "max_offset": 0,
                    "exact_failure_count": 0,
                }

            stats["count"] += 1
            stats["min_earlier_value"] = min(stats["min_earlier_value"], earlier_value)
            stats["max_offset"] = max(stats["max_offset"], first_descent_value - earlier_value)
            if not SPOILER_SCAN.score_strictly_greater(
                first_descent_value,
                first_descent_divisor_count,
                earlier_value,
                earlier_divisor_count,
            ):
                stats["exact_failure_count"] += 1
            pair_stats[pair_key] = stats

    pair_summary = []
    for (earlier_divisor_count, first_descent_divisor_count), stats in sorted(pair_stats.items()):
        threshold = automatic_threshold(earlier_divisor_count, first_descent_divisor_count)
        pair_summary.append(
            {
                "earlier_divisor_count": earlier_divisor_count,
                "first_descent_divisor_count": first_descent_divisor_count,
                "count": stats["count"],
                "min_earlier_value": stats["min_earlier_value"],
                "max_offset": stats["max_offset"],
                "automatic_threshold": threshold,
                "all_observed_values_above_threshold": stats["min_earlier_value"] >= threshold,
                "exact_failure_count": stats["exact_failure_count"],
            }
        )

    return {
        "interval": {"lo": lo, "hi": hi},
        "target_classes": list(TARGET_CLASSES),
        "pair_summary": pair_summary,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the pair-threshold scan and emit a JSON artifact."""
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

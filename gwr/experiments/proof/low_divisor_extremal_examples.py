#!/usr/bin/env python3
"""Extract exact extremal low-divisor spoiler examples from prime gaps."""

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
    module_name = "earlier_spoiler_scan_runtime_extremal"
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
            "Extract one exact extremal example for each target low-divisor "
            "earlier-spoiler class."
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
    """Return exact extremal examples for the target low-divisor classes."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    max_offset_by_class: dict[int, int] = {}
    extremal_examples: dict[int, dict[str, int]] = {}

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

            for later_index in range(earlier_index + 1, gap_values.size):
                later_value = int(gap_values[later_index])
                later_divisor_count = int(gap_divisors[later_index])
                if SPOILER_SCAN.score_strictly_greater(
                    later_value,
                    later_divisor_count,
                    earlier_value,
                    earlier_divisor_count,
                ):
                    offset = later_value - earlier_value
                    current_max = max_offset_by_class.get(earlier_divisor_count)
                    if current_max is None or offset > current_max:
                        max_offset_by_class[earlier_divisor_count] = offset
                        extremal_examples[earlier_divisor_count] = {
                            "left_prime": int(left_prime),
                            "right_prime": int(right_prime),
                            "earlier_value": earlier_value,
                            "earlier_divisor_count": earlier_divisor_count,
                            "dominator_value": later_value,
                            "dominator_divisor_count": later_divisor_count,
                            "offset": offset,
                        }
                    break

    return {
        "interval": {"lo": lo, "hi": hi},
        "target_classes": list(TARGET_CLASSES),
        "max_offset_by_class": max_offset_by_class,
        "extremal_examples": [
            extremal_examples[divisor_count_value]
            for divisor_count_value in TARGET_CLASSES
            if divisor_count_value in extremal_examples
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the extremal-example extractor and emit a JSON artifact."""
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

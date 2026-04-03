#!/usr/bin/env python3
"""Scan large intervals exactly, in chunks, for earlier-16 / first-descent-15 cases."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from sympy import nextprime, prevprime


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


SPOILER_SCAN_PATH = ROOT / "gwr" / "experiments" / "proof" / "earlier_spoiler_scan.py"
EARLIER_DIVISOR_COUNT = 16
FIRST_DESCENT_DIVISOR_COUNT = 15


def load_spoiler_scan_module():
    """Load the exact score-comparison helper directly from file."""
    module_name = "earlier_spoiler_scan_runtime_pair_16_15"
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
            "Scan a large interval in exact chunks for earlier divisor-count 16 "
            "candidates whose first divisor descent has divisor count 15."
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
        default=200_000_001,
        help="Exclusive upper bound of the natural-number interval.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=5_000_000,
        help="Width of each exact chunk scan.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def chunk_bounds(lo: int, hi: int, chunk_size: int) -> list[tuple[int, int]]:
    """Return the exact chunk bounds."""
    bounds = []
    chunk_lo = lo
    while chunk_lo < hi:
        chunk_hi = min(chunk_lo + chunk_size, hi)
        bounds.append((chunk_lo, chunk_hi))
        chunk_lo = chunk_hi
    return bounds


def analyze_chunk(chunk_lo: int, chunk_hi: int) -> dict[str, object]:
    """Return the exact pair-16-15 profile for one chunk."""
    extended_lo = 2 if chunk_lo <= 2 else int(prevprime(chunk_lo))
    extended_hi = int(nextprime(chunk_hi - 1)) + 1

    divisor_count = divisor_counts_segment(extended_lo, extended_hi)
    values = np.arange(extended_lo, extended_hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    pair_count = 0
    exact_failure_count = 0
    min_earlier_value: int | None = None
    max_offset = 0
    top_examples: list[dict[str, int]] = []

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        if not (chunk_lo <= int(left_prime) < chunk_hi):
            continue

        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        left_index = int(left_prime - extended_lo + 1)
        right_index = int(right_prime - extended_lo)
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]

        winner_divisor_count = int(np.min(gap_divisors))
        winner_index = int(np.flatnonzero(gap_divisors == winner_divisor_count)[0])

        for earlier_index in range(winner_index):
            earlier_value = int(gap_values[earlier_index])
            earlier_divisor_count = int(gap_divisors[earlier_index])
            if earlier_divisor_count != EARLIER_DIVISOR_COUNT:
                continue

            first_descent_index = None
            for later_index in range(earlier_index + 1, gap_values.size):
                later_divisor_count = int(gap_divisors[later_index])
                if later_divisor_count < EARLIER_DIVISOR_COUNT:
                    first_descent_index = later_index
                    break

            if first_descent_index is None:
                raise RuntimeError("No later smaller-divisor composite found before the winner")

            first_descent_value = int(gap_values[first_descent_index])
            first_descent_divisor_count = int(gap_divisors[first_descent_index])
            if first_descent_divisor_count != FIRST_DESCENT_DIVISOR_COUNT:
                continue

            offset = first_descent_value - earlier_value
            pair_count += 1
            min_earlier_value = (
                earlier_value if min_earlier_value is None else min(min_earlier_value, earlier_value)
            )
            max_offset = max(max_offset, offset)

            if not SPOILER_SCAN.score_strictly_greater(
                first_descent_value,
                first_descent_divisor_count,
                earlier_value,
                earlier_divisor_count,
            ):
                exact_failure_count += 1

            example = {
                "left_prime": int(left_prime),
                "right_prime": int(right_prime),
                "earlier_value": earlier_value,
                "first_descent_value": first_descent_value,
                "offset": offset,
            }
            top_examples.append(example)
            top_examples.sort(key=lambda row: (-row["offset"], row["left_prime"], row["earlier_value"]))
            del top_examples[20:]

    return {
        "chunk_lo": chunk_lo,
        "chunk_hi": chunk_hi,
        "pair_count": pair_count,
        "exact_failure_count": exact_failure_count,
        "min_earlier_value": min_earlier_value,
        "max_offset": max_offset,
        "top_examples": top_examples,
    }


def analyze_interval(lo: int, hi: int, chunk_size: int) -> dict[str, object]:
    """Return the exact chunked scan profile for the 16 -> 15 pair."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    total_pair_count = 0
    total_exact_failure_count = 0
    min_earlier_value: int | None = None
    max_offset = 0
    top_examples: list[dict[str, int]] = []
    chunk_summaries: list[dict[str, int | None]] = []

    for chunk_lo, chunk_hi in chunk_bounds(lo, hi, chunk_size):
        chunk_payload = analyze_chunk(chunk_lo, chunk_hi)
        total_pair_count += int(chunk_payload["pair_count"])
        total_exact_failure_count += int(chunk_payload["exact_failure_count"])
        if chunk_payload["min_earlier_value"] is not None:
            min_earlier_value = (
                int(chunk_payload["min_earlier_value"])
                if min_earlier_value is None
                else min(min_earlier_value, int(chunk_payload["min_earlier_value"]))
            )
        max_offset = max(max_offset, int(chunk_payload["max_offset"]))
        chunk_summaries.append(
            {
                "chunk_lo": chunk_lo,
                "chunk_hi": chunk_hi,
                "pair_count": int(chunk_payload["pair_count"]),
                "exact_failure_count": int(chunk_payload["exact_failure_count"]),
                "min_earlier_value": (
                    None
                    if chunk_payload["min_earlier_value"] is None
                    else int(chunk_payload["min_earlier_value"])
                ),
                "max_offset": int(chunk_payload["max_offset"]),
            }
        )
        top_examples.extend(chunk_payload["top_examples"])
        top_examples.sort(key=lambda row: (-row["offset"], row["left_prime"], row["earlier_value"]))
        del top_examples[20:]

    return {
        "interval": {"lo": lo, "hi": hi},
        "chunk_size": chunk_size,
        "pair": {
            "earlier_divisor_count": EARLIER_DIVISOR_COUNT,
            "first_descent_divisor_count": FIRST_DESCENT_DIVISOR_COUNT,
        },
        "pair_count": total_pair_count,
        "exact_failure_count": total_exact_failure_count,
        "min_earlier_value": min_earlier_value,
        "max_offset": max_offset,
        "chunk_summary": chunk_summaries,
        "top_examples": top_examples,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the chunked pair scan and emit a JSON artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_interval(args.lo, args.hi, args.chunk_size)
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

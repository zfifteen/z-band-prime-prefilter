#!/usr/bin/env python3
"""Scan the low-divisor hard regime for earlier spoiler candidates and their first dominators."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment

SCRIPT_PATH = (
    ROOT / "gwr" / "experiments" / "proof" / "earlier_spoiler_local_dominator_scan.py"
)


def load_module():
    """Load the local-dominator scan module directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "earlier_spoiler_local_dominator_scan_runtime",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load earlier_spoiler_local_dominator_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["earlier_spoiler_local_dominator_scan_runtime"] = module
    spec.loader.exec_module(module)
    return module


LOCAL_DOMINATOR_SCAN = load_module()
HARD_CLASSES = (4, 6, 8, 12, 16)


@dataclass(frozen=True)
class HardClassRow:
    """One hard-class summary row."""

    earlier_divisor_count: int
    count: int
    min_offset: int
    max_offset: int

    def to_dict(self) -> dict[str, int]:
        """Return a JSON-ready mapping."""
        return asdict(self)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract the low-divisor hard regime from the exact earlier-spoiler "
            "local-dominator scan."
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
    """Return the exact hard-regime projection of the local-dominator scan."""
    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    overall_earlier_candidate_count = 0
    unresolved_candidate_count = 0
    class_rows: dict[int, HardClassRow] = {}
    examples: list[dict[str, int]] = []

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
            overall_earlier_candidate_count += 1
            if earlier_divisor_count not in HARD_CLASSES:
                continue

            first_offset = None
            first_dominator_value = None
            first_dominator_divisor_count = None
            for later_index in range(earlier_index + 1, gap_values.size):
                later_value = int(gap_values[later_index])
                later_divisor_count = int(gap_divisors[later_index])
                if LOCAL_DOMINATOR_SCAN.score_strictly_greater(
                    later_value,
                    later_divisor_count,
                    earlier_value,
                    earlier_divisor_count,
                ):
                    first_offset = later_value - earlier_value
                    first_dominator_value = later_value
                    first_dominator_divisor_count = later_divisor_count
                    break

            if first_offset is None:
                unresolved_candidate_count += 1
                continue

            row = class_rows.get(earlier_divisor_count)
            if row is None:
                class_rows[earlier_divisor_count] = HardClassRow(
                    earlier_divisor_count=earlier_divisor_count,
                    count=1,
                    min_offset=first_offset,
                    max_offset=first_offset,
                )
            else:
                class_rows[earlier_divisor_count] = HardClassRow(
                    earlier_divisor_count=earlier_divisor_count,
                    count=row.count + 1,
                    min_offset=min(row.min_offset, first_offset),
                    max_offset=max(row.max_offset, first_offset),
                )

            if len(examples) < 20:
                examples.append(
                    {
                        "left_prime": int(left_prime),
                        "right_prime": int(right_prime),
                        "earlier_value": earlier_value,
                        "earlier_divisor_count": earlier_divisor_count,
                        "dominator_value": int(first_dominator_value),
                        "dominator_divisor_count": int(first_dominator_divisor_count),
                        "offset": first_offset,
                    }
                )

    hard_rows = [
        class_rows[divisor_count_value].to_dict()
        for divisor_count_value in HARD_CLASSES
        if divisor_count_value in class_rows
    ]

    return {
        "interval": {"lo": lo, "hi": hi},
        "hard_classes": list(HARD_CLASSES),
        "earlier_candidate_count": overall_earlier_candidate_count,
        "unresolved_candidate_count": unresolved_candidate_count,
        "hard_class_summary": hard_rows,
        "examples": examples,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the hard-regime scan and emit a JSON artifact."""
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

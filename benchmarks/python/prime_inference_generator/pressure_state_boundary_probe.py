#!/usr/bin/env python3
"""Offline pressure-state collision probe for boundary theorem discovery.

This script is not part of pure generation. It may use classical labels to
measure collisions, but each pressure state reports whether its own features are
eligible for future pure generation.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from .transition_state_boundary_probe import (
        WHEEL_OPEN_RESIDUES_MOD30,
        first_open_offset,
        first_wheel_witness,
        jsonable,
        legal_prefix_tokens,
        state_key,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from transition_state_boundary_probe import (
        WHEEL_OPEN_RESIDUES_MOD30,
        first_open_offset,
        first_wheel_witness,
        jsonable,
        legal_prefix_tokens,
        state_key,
    )

from sympy import divisor_count, factorint, isprime, nextprime, prevprime, primerange


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "pressure_state_boundary_probe_summary.json"
ROWS_FILENAME = "pressure_state_boundary_probe_rows.jsonl"
PRESSURE_STATE_NAMES = [
    "square_pressure_state",
    "semiprime_pressure_state",
    "higher_divisor_pressure_state",
    "threat_schedule_state",
    "previous_chamber_pressure_state",
    "carrier_plus_pressure_state",
    "previous_chamber_plus_square_pressure_state",
    "previous_chamber_plus_higher_divisor_pressure_state",
    "previous_chamber_plus_threat_schedule_state",
    "previous_chamber_plus_square_and_higher_pressure_state",
    "previous_chamber_plus_square_and_threat_state",
]
PRESSURE_STATE_LEGALITY = {
    "square_pressure_state": {
        "eligible_for_pure_generation": True,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": False,
        "uses_previous_gap_context": False,
    },
    "semiprime_pressure_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": False,
    },
    "higher_divisor_pressure_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": False,
    },
    "threat_schedule_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": False,
    },
    "previous_chamber_pressure_state": {
        "eligible_for_pure_generation": True,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": False,
        "uses_previous_gap_context": True,
    },
    "carrier_plus_pressure_state": {
        "eligible_for_pure_generation": True,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": False,
        "uses_previous_gap_context": True,
    },
    "previous_chamber_plus_square_pressure_state": {
        "eligible_for_pure_generation": True,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": False,
        "uses_previous_gap_context": True,
    },
    "previous_chamber_plus_higher_divisor_pressure_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": True,
    },
    "previous_chamber_plus_threat_schedule_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": True,
    },
    "previous_chamber_plus_square_and_higher_pressure_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": True,
    },
    "previous_chamber_plus_square_and_threat_state": {
        "eligible_for_pure_generation": False,
        "uses_future_boundary_offset": False,
        "uses_current_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
        "uses_exact_factorization": True,
        "uses_previous_gap_context": True,
    },
}


def build_parser() -> argparse.ArgumentParser:
    """Build the pressure-state probe CLI."""
    parser = argparse.ArgumentParser(
        description="Offline PGS pressure-state boundary collision probe.",
    )
    parser.add_argument(
        "--start-prime",
        type=int,
        default=11,
        help="First anchor prime in the labeled surface.",
    )
    parser.add_argument(
        "--max-anchor",
        type=int,
        default=10_000,
        help="Largest anchor prime in the labeled surface.",
    )
    parser.add_argument(
        "--prefix-len",
        type=int,
        default=8,
        help="Fixed rightward prefix length used for pressure features.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def square_offsets(anchor_prime: int, prefix_len: int) -> tuple[int, ...]:
    """Return offsets of square numbers in one fixed prefix."""
    lo = anchor_prime + 1
    hi = anchor_prime + prefix_len
    root = math.isqrt(lo - 1) + 1
    offsets: list[int] = []
    while root * root <= hi:
        offsets.append(root * root - anchor_prime)
        root += 1
    return tuple(offsets)


def next_square_offset(anchor_prime: int) -> int:
    """Return offset to the next square after the anchor."""
    root = math.isqrt(anchor_prime) + 1
    return root * root - anchor_prime


def exact_divisor_family(n: int) -> str:
    """Return exact factorization family for theorem discovery."""
    factors = factorint(n)
    exponent_sum = sum(int(exponent) for exponent in factors.values())
    if len(factors) == 1 and exponent_sum == 1:
        return "prime"
    if len(factors) == 1:
        return "prime_power"
    if exponent_sum == 2:
        return "semiprime"
    return "composite"


def bucket_gap(width: int | None) -> str | None:
    """Return a compact previous-gap bucket."""
    if width is None:
        return None
    if width <= 4:
        return "G_LE_4"
    if width <= 8:
        return "G_LE_8"
    if width <= 16:
        return "G_LE_16"
    if width <= 32:
        return "G_LE_32"
    return "G_GT_32"


def prefix_rows(anchor_prime: int, prefix_len: int) -> list[dict[str, Any]]:
    """Return prefix rows with legal and exact theorem-search features."""
    rows: list[dict[str, Any]] = []
    for offset in range(1, prefix_len + 1):
        n = anchor_prime + offset
        legal_tokens = legal_prefix_tokens(n)
        d_value = int(divisor_count(n))
        rows.append(
            {
                "offset": offset,
                "n": n,
                "wheel_open": n % 30 in WHEEL_OPEN_RESIDUES_MOD30,
                "is_prime_label": bool(isprime(n)),
                "divisor_count": d_value,
                "divisor_bucket": "D6_PLUS" if d_value >= 6 else f"D{d_value}",
                "exact_family": exact_divisor_family(n),
                **legal_tokens,
            }
        )
    return rows


def first_lower_threat(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return exact first lower-divisor threat after the first composite carrier."""
    composites = [row for row in rows if int(row["divisor_count"]) > 2]
    if not composites:
        return {
            "exact_carrier_offset": None,
            "exact_carrier_divisor_count": None,
            "first_lower_threat_offset": None,
        }

    carrier = min(
        composites,
        key=lambda row: (int(row["divisor_count"]), int(row["offset"])),
    )
    carrier_d = int(carrier["divisor_count"])
    for row in rows:
        if int(row["offset"]) <= int(carrier["offset"]):
            continue
        if int(row["divisor_count"]) < carrier_d:
            return {
                "exact_carrier_offset": int(carrier["offset"]),
                "exact_carrier_divisor_count": carrier_d,
                "first_lower_threat_offset": int(row["offset"]),
            }

    return {
        "exact_carrier_offset": int(carrier["offset"]),
        "exact_carrier_divisor_count": carrier_d,
        "first_lower_threat_offset": None,
    }


def build_pressure_row(anchor_prime: int, prefix_len: int) -> dict[str, Any]:
    """Build one labeled row for pressure-state theorem discovery."""
    if anchor_prime <= 2:
        previous_prime_value = None
    else:
        previous_prime_value = int(prevprime(anchor_prime))
    next_prime_value = int(nextprime(anchor_prime))
    rows = prefix_rows(anchor_prime, prefix_len)
    legal_witness = first_wheel_witness(rows)
    threat = first_lower_threat(rows)
    previous_gap_width = (
        None if previous_prime_value is None else anchor_prime - previous_prime_value
    )
    semiprime_offsets = tuple(
        int(row["offset"]) for row in rows if row["exact_family"] == "semiprime"
    )
    high_divisor_offsets = tuple(
        int(row["offset"]) for row in rows if int(row["divisor_count"]) >= 6
    )
    divisor_bucket_ladder = tuple(str(row["divisor_bucket"]) for row in rows)

    row: dict[str, Any] = {
        "anchor_prime": anchor_prime,
        "next_prime": next_prime_value,
        "next_gap_width": next_prime_value - anchor_prime,
        "anchor_mod30": anchor_prime % 30,
        "first_open_offset": first_open_offset(anchor_prime),
        "prefix_len": prefix_len,
        "previous_gap_width": previous_gap_width,
        "previous_gap_bucket": bucket_gap(previous_gap_width),
        "next_square_offset": next_square_offset(anchor_prime),
        "square_offsets": square_offsets(anchor_prime, prefix_len),
        "semiprime_offsets": semiprime_offsets,
        "semiprime_count": len(semiprime_offsets),
        "high_divisor_offsets": high_divisor_offsets,
        "high_divisor_count": len(high_divisor_offsets),
        "divisor_bucket_ladder": divisor_bucket_ladder,
        "open_unknown_ladder": tuple(row["open_unknown_token"] for row in rows),
        "composite_witness_ladder": tuple(
            row["composite_witness_token"] for row in rows
        ),
    }
    row.update(legal_witness)
    row.update(threat)
    return row


def pressure_state_vectors(row: dict[str, Any]) -> dict[str, Any]:
    """Return pressure-state vectors for one labeled row."""
    square_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["next_square_offset"],
        row["square_offsets"],
    )
    semiprime_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["semiprime_count"],
        row["semiprime_offsets"],
    )
    higher_divisor_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["high_divisor_count"],
        row["high_divisor_offsets"],
        row["divisor_bucket_ladder"],
    )
    threat_schedule_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["exact_carrier_offset"],
        row["exact_carrier_divisor_count"],
        row["first_lower_threat_offset"],
    )
    previous_chamber_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
    )
    carrier_plus_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["first_witness_offset"],
        row["first_witness_factor"],
        row["next_square_offset"],
        row["square_offsets"],
        row["previous_gap_bucket"],
    )
    previous_chamber_plus_square_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
        row["next_square_offset"],
        row["square_offsets"],
    )
    previous_chamber_plus_higher_divisor_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
        row["high_divisor_count"],
        row["high_divisor_offsets"],
        row["divisor_bucket_ladder"],
    )
    previous_chamber_plus_threat_schedule_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
        row["exact_carrier_offset"],
        row["exact_carrier_divisor_count"],
        row["first_lower_threat_offset"],
    )
    previous_chamber_plus_square_and_higher_pressure_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
        row["next_square_offset"],
        row["square_offsets"],
        row["high_divisor_count"],
        row["high_divisor_offsets"],
        row["divisor_bucket_ladder"],
    )
    previous_chamber_plus_square_and_threat_state = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
        row["next_square_offset"],
        row["square_offsets"],
        row["exact_carrier_offset"],
        row["exact_carrier_divisor_count"],
        row["first_lower_threat_offset"],
    )
    return {
        "square_pressure_state": square_pressure_state,
        "semiprime_pressure_state": semiprime_pressure_state,
        "higher_divisor_pressure_state": higher_divisor_pressure_state,
        "threat_schedule_state": threat_schedule_state,
        "previous_chamber_pressure_state": previous_chamber_pressure_state,
        "carrier_plus_pressure_state": carrier_plus_pressure_state,
        "previous_chamber_plus_square_pressure_state": (
            previous_chamber_plus_square_pressure_state
        ),
        "previous_chamber_plus_higher_divisor_pressure_state": (
            previous_chamber_plus_higher_divisor_pressure_state
        ),
        "previous_chamber_plus_threat_schedule_state": (
            previous_chamber_plus_threat_schedule_state
        ),
        "previous_chamber_plus_square_and_higher_pressure_state": (
            previous_chamber_plus_square_and_higher_pressure_state
        ),
        "previous_chamber_plus_square_and_threat_state": (
            previous_chamber_plus_square_and_threat_state
        ),
    }


def collision_report(rows: list[dict[str, Any]], state_vector_name: str) -> dict[str, Any]:
    """Return one pressure-state collision report."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        vector = pressure_state_vectors(row)[state_vector_name]
        buckets[state_key(vector)].append(row)

    first_collision_examples: list[dict[str, Any]] = []
    collision_count = 0
    max_bucket_size = 0
    for key, bucket in buckets.items():
        labels = sorted({int(row["next_gap_width"]) for row in bucket})
        max_bucket_size = max(max_bucket_size, len(bucket))
        if len(labels) < 2:
            continue

        collision_count += 1
        if len(first_collision_examples) < 5:
            first_collision_examples.append(
                {
                    "state_key": json.loads(key),
                    "boundary_offsets": labels,
                    "anchors": [int(row["anchor_prime"]) for row in bucket[:8]],
                    "bucket_size": len(bucket),
                }
            )

    distinct_state_count = len(buckets)
    zero_collision = collision_count == 0
    return {
        "state_vector_name": state_vector_name,
        **PRESSURE_STATE_LEGALITY[state_vector_name],
        "row_count": len(rows),
        "distinct_state_count": distinct_state_count,
        "collision_count": collision_count,
        "collision_rate": (
            0.0 if distinct_state_count == 0 else collision_count / distinct_state_count
        ),
        "first_collision_examples": first_collision_examples,
        "max_bucket_size": max_bucket_size,
        "zero_collision": zero_collision,
        "zero_collision_and_eligible": (
            zero_collision
            and bool(
                PRESSURE_STATE_LEGALITY[state_vector_name][
                    "eligible_for_pure_generation"
                ]
            )
        ),
    }


def run_probe(start_prime: int, max_anchor: int, prefix_len: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the offline pressure-state collision probe."""
    if prefix_len < 1:
        raise ValueError("prefix_len must be at least 1")
    if max_anchor < start_prime:
        raise ValueError("max_anchor must be at least start_prime")
    if not isprime(start_prime):
        raise ValueError("start_prime must be prime")

    started = time.perf_counter()
    anchors = [int(prime) for prime in primerange(start_prime, max_anchor + 1)]
    rows = [build_pressure_row(anchor_prime, prefix_len) for anchor_prime in anchors]
    reports = [collision_report(rows, name) for name in PRESSURE_STATE_NAMES]
    first_zero_eligible = next(
        (
            report["state_vector_name"]
            for report in reports
            if report["zero_collision_and_eligible"]
        ),
        None,
    )
    summary = {
        "mode": "offline_pressure_state_theorem_search",
        "start_prime": start_prime,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "row_count": len(rows),
        "state_vectors": reports,
        "first_zero_collision_eligible_state_vector": first_zero_eligible,
        "runtime_seconds": time.perf_counter() - started,
    }
    return rows, summary


def write_artifacts(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    """Write LF-terminated JSONL rows and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / ROWS_FILENAME
    with rows_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(jsonable(row), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"rows_path": rows_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run the pressure-state probe and write artifacts."""
    args = build_parser().parse_args(argv)
    rows, summary = run_probe(
        start_prime=args.start_prime,
        max_anchor=args.max_anchor,
        prefix_len=args.prefix_len,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

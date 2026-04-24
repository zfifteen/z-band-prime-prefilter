#!/usr/bin/env python3
"""Forensics for pressure-state boundary collisions.

This script is offline theorem discovery. It inspects collision buckets for a
pressure state and reports which legal or theorem-search observables separate
the colliding anchors.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    from .pressure_state_boundary_probe import (
        PRESSURE_STATE_LEGALITY,
        build_pressure_row,
        pressure_state_vectors,
    )
    from .transition_state_boundary_probe import jsonable, state_key
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from pressure_state_boundary_probe import (
        PRESSURE_STATE_LEGALITY,
        build_pressure_row,
        pressure_state_vectors,
    )
    from transition_state_boundary_probe import jsonable, state_key

from sympy import isprime, primerange


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "pressure_collision_forensics_summary.json"
BUCKETS_FILENAME = "pressure_collision_forensics_buckets.jsonl"
DEFAULT_STATE_VECTOR = "previous_chamber_pressure_state"


def build_parser() -> argparse.ArgumentParser:
    """Build the pressure-collision forensics CLI."""
    parser = argparse.ArgumentParser(
        description="Offline pressure-state collision forensics.",
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
        "--state-vector",
        default=DEFAULT_STATE_VECTOR,
        help="Pressure state vector to inspect.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def ordered_collision_buckets(
    rows: list[dict[str, Any]],
    state_vector_name: str,
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Return pressure-state collision buckets in first-anchor order."""
    buckets: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        vector = pressure_state_vectors(row)[state_vector_name]
        key = state_key(vector)
        if key not in buckets:
            buckets[key] = []
        buckets[key].append(row)

    collisions: list[tuple[str, list[dict[str, Any]]]] = []
    for key, bucket in buckets.items():
        labels = {int(row["next_gap_width"]) for row in bucket}
        if len(labels) > 1:
            collisions.append((key, bucket))
    return collisions


def varying_fields(bucket: list[dict[str, Any]], fields: list[str]) -> list[str]:
    """Return fields whose values vary inside one collision bucket."""
    varying: list[str] = []
    for field in fields:
        values = {state_key(row[field]) for row in bucket}
        if len(values) > 1:
            varying.append(field)
    return varying


def candidate_missing_observable(varying: list[str]) -> list[str]:
    """Map varying fields to candidate next observable families."""
    candidates: list[str] = []
    if "previous_gap_width" in varying:
        candidates.append("previous_gap_width_class")
    if "previous_gap_bucket" in varying:
        candidates.append("previous_gap_bucket_refinement")
    if "first_open_offset" in varying:
        candidates.append("current_first_open_offset")
    if "open_unknown_ladder" in varying:
        candidates.append("current_open_unknown_pattern")
    if "composite_witness_ladder" in varying:
        candidates.append("current_legal_composite_ladder")
    if "next_square_offset" in varying or "square_offsets" in varying:
        candidates.append("square_pressure_plus_previous_chamber")
    if "semiprime_offsets" in varying or "semiprime_count" in varying:
        candidates.append("semiprime_pressure_plus_previous_chamber")
    if "high_divisor_offsets" in varying or "high_divisor_count" in varying:
        candidates.append("higher_divisor_pressure_plus_previous_chamber")
    if "exact_carrier_offset" in varying or "exact_carrier_divisor_count" in varying:
        candidates.append("previous_plus_exact_carrier_pressure")
    if "first_lower_threat_offset" in varying:
        candidates.append("previous_plus_threat_schedule")
    if not candidates:
        candidates.append("unidentified_pressure_splitter")
    return candidates


def forensic_bucket(
    state_vector_name: str,
    shared_state_key: str,
    bucket: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return one pressure-collision forensic record."""
    compare_fields = [
        "previous_gap_width",
        "previous_gap_bucket",
        "first_open_offset",
        "open_unknown_ladder",
        "composite_witness_ladder",
        "next_square_offset",
        "square_offsets",
        "semiprime_count",
        "semiprime_offsets",
        "high_divisor_count",
        "high_divisor_offsets",
        "exact_carrier_offset",
        "exact_carrier_divisor_count",
        "first_lower_threat_offset",
    ]
    varying = varying_fields(bucket, compare_fields)
    per_anchor = []
    for row in bucket:
        per_anchor.append(
            {
                "anchor_prime": int(row["anchor_prime"]),
                "boundary_offset": int(row["next_gap_width"]),
                "previous_gap_width": row["previous_gap_width"],
                "previous_gap_bucket": row["previous_gap_bucket"],
                "first_open_offset": row["first_open_offset"],
                "open_unknown_ladder": jsonable(row["open_unknown_ladder"]),
                "composite_witness_ladder": jsonable(row["composite_witness_ladder"]),
                "next_square_offset": row["next_square_offset"],
                "square_offsets": jsonable(row["square_offsets"]),
                "semiprime_count": row["semiprime_count"],
                "semiprime_offsets": jsonable(row["semiprime_offsets"]),
                "high_divisor_count": row["high_divisor_count"],
                "high_divisor_offsets": jsonable(row["high_divisor_offsets"]),
                "exact_carrier_offset": row["exact_carrier_offset"],
                "exact_carrier_divisor_count": row["exact_carrier_divisor_count"],
                "first_lower_threat_offset": row["first_lower_threat_offset"],
            }
        )

    return {
        "state_vector_name": state_vector_name,
        "shared_previous_state": json.loads(shared_state_key),
        "boundary_offsets_observed": sorted(
            {int(row["next_gap_width"]) for row in bucket}
        ),
        "anchors_by_bucket": [int(row["anchor_prime"]) for row in bucket],
        "legal_feature_deltas": {
            "varying_fields": varying,
            "per_anchor": per_anchor,
        },
        "candidate_missing_observable": candidate_missing_observable(varying),
    }


def run_forensics(
    start_prime: int,
    max_anchor: int,
    prefix_len: int,
    state_vector_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run pressure-state collision forensics."""
    if prefix_len < 1:
        raise ValueError("prefix_len must be at least 1")
    if max_anchor < start_prime:
        raise ValueError("max_anchor must be at least start_prime")
    if not isprime(start_prime):
        raise ValueError("start_prime must be prime")
    if state_vector_name not in PRESSURE_STATE_LEGALITY:
        raise ValueError(f"unknown pressure state vector {state_vector_name}")

    anchors = [int(prime) for prime in primerange(start_prime, max_anchor + 1)]
    rows = [build_pressure_row(anchor_prime, prefix_len) for anchor_prime in anchors]
    collisions = ordered_collision_buckets(rows, state_vector_name)
    records = [
        forensic_bucket(state_vector_name, key, bucket)
        for key, bucket in collisions
    ]
    counts: dict[str, int] = {}
    for record in records:
        for candidate in record["candidate_missing_observable"]:
            counts[candidate] = counts.get(candidate, 0) + 1

    summary = {
        "mode": "offline_pressure_collision_forensics",
        "start_prime": start_prime,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "state_vector_name": state_vector_name,
        "row_count": len(rows),
        "collision_bucket_count": len(records),
        "written_collision_bucket_count": len(records),
        "state_legality": PRESSURE_STATE_LEGALITY[state_vector_name],
        "candidate_missing_observable_counts": counts,
    }
    return records, summary


def write_artifacts(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL bucket records and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    buckets_path = output_dir / BUCKETS_FILENAME
    with buckets_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(jsonable(record), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"buckets_path": buckets_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run pressure-state collision forensics and write artifacts."""
    args = build_parser().parse_args(argv)
    records, summary = run_forensics(
        start_prime=args.start_prime,
        max_anchor=args.max_anchor,
        prefix_len=args.prefix_len,
        state_vector_name=args.state_vector,
    )
    write_artifacts(records, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

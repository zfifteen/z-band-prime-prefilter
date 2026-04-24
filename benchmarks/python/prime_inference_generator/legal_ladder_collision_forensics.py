#!/usr/bin/env python3
"""Collision forensics for legal ladder transition states.

This script is offline theorem discovery, not pure generation. It compares
legal state collisions against contaminated perfect ladder states to identify
which forbidden information separates the colliding cases.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

try:
    from .transition_state_boundary_probe import (
        STATE_VECTOR_LEAKAGE,
        build_row,
        jsonable,
        state_key,
        state_vectors_for_row,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from transition_state_boundary_probe import (
        STATE_VECTOR_LEAKAGE,
        build_row,
        jsonable,
        state_key,
        state_vectors_for_row,
    )

from sympy import isprime, primerange


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "legal_ladder_collision_forensics_summary.json"
BUCKETS_FILENAME = "legal_ladder_collision_forensics_buckets.jsonl"
DEFAULT_STATE_VECTOR = "known_composite_divisor_ladder"
CONTAMINATED_STATE_VECTORS = (
    "carrier_ladder",
    "previous_gap_ladder",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the collision-forensics CLI."""
    parser = argparse.ArgumentParser(
        description="Offline legal-ladder collision forensics.",
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
        help="Fixed rightward prefix length used for local state features.",
    )
    parser.add_argument(
        "--state-vector",
        default=DEFAULT_STATE_VECTOR,
        help="Legal state vector to inspect.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum collision buckets to write.",
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
    """Return legal-state collision buckets in first-anchor order."""
    buckets: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    for row in rows:
        vectors = state_vectors_for_row(row)
        key = state_key(vectors[state_vector_name])
        if key not in buckets:
            buckets[key] = []
        buckets[key].append(row)

    collisions: list[tuple[str, list[dict[str, Any]]]] = []
    for key, bucket in buckets.items():
        boundary_offsets = {int(row["next_gap_width"]) for row in bucket}
        if len(boundary_offsets) > 1:
            collisions.append((key, bucket))
    return collisions


def unique_state_keys(bucket: list[dict[str, Any]], state_vector_name: str) -> list[Any]:
    """Return unique JSON-decoded state keys for one bucket."""
    values: OrderedDict[str, Any] = OrderedDict()
    for row in bucket:
        vector = state_vectors_for_row(row)[state_vector_name]
        key = state_key(vector)
        if key not in values:
            values[key] = json.loads(key)
    return list(values.values())


def varying_fields(bucket: list[dict[str, Any]], fields: list[str]) -> list[str]:
    """Return fields that differ inside one legal collision bucket."""
    varying: list[str] = []
    for field in fields:
        values = {state_key(row[field]) for row in bucket}
        if len(values) > 1:
            varying.append(field)
    return varying


def candidate_missing_observable(varying: list[str]) -> list[str]:
    """Name the missing observable family suggested by varying fields."""
    candidates: list[str] = []
    if "prime_marker_offsets" in varying:
        candidates.append("prime_marker_positions")
    if "masked_divisor_ladder" in varying or "family_ladder" in varying:
        candidates.append("prime_marker_masked_ladder")
    if any(field.startswith("first_carrier") for field in varying):
        candidates.append("contaminated_carrier_identity")
    if "previous_gap_width" in varying:
        candidates.append("previous_gap_width")
    if not candidates:
        candidates.append("unidentified_nonlegal_splitter")
    return candidates


def forensic_bucket(
    state_vector_name: str,
    legal_state_key: str,
    bucket: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return one collision-forensics record."""
    fields_to_compare = [
        "prime_marker_offsets",
        "masked_divisor_ladder",
        "family_ladder",
        "first_carrier_offset",
        "first_carrier_divisor_count",
        "first_carrier_family",
        "previous_gap_width",
    ]
    varying = varying_fields(bucket, fields_to_compare)

    per_anchor = []
    for row in bucket:
        per_anchor.append(
            {
                "anchor_prime": int(row["anchor_prime"]),
                "boundary_offset": int(row["next_gap_width"]),
                "prime_marker_offsets": jsonable(row["prime_marker_offsets"]),
                "masked_divisor_ladder": jsonable(row["masked_divisor_ladder"]),
                "family_ladder": jsonable(row["family_ladder"]),
                "first_carrier_offset": row["first_carrier_offset"],
                "first_carrier_divisor_count": row["first_carrier_divisor_count"],
                "first_carrier_family": row["first_carrier_family"],
                "previous_gap_width": row["previous_gap_width"],
            }
        )

    return {
        "state_vector_name": state_vector_name,
        "legal_state_key": json.loads(legal_state_key),
        "boundary_offsets_observed": sorted(
            {int(row["next_gap_width"]) for row in bucket}
        ),
        "anchors_with_same_legal_state": [
            int(row["anchor_prime"]) for row in bucket
        ],
        "contaminated_carrier_ladder_keys": unique_state_keys(
            bucket,
            "carrier_ladder",
        ),
        "contaminated_previous_gap_ladder_keys": unique_state_keys(
            bucket,
            "previous_gap_ladder",
        ),
        "difference_between_legal_and_illegal_keys": {
            "varying_for_contaminated_keys": varying,
            "per_anchor": per_anchor,
        },
        "candidate_missing_observable": candidate_missing_observable(varying),
    }


def run_forensics(
    start_prime: int,
    max_anchor: int,
    prefix_len: int,
    state_vector_name: str,
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run legal ladder collision forensics."""
    if prefix_len < 1:
        raise ValueError("prefix_len must be at least 1")
    if max_anchor < start_prime:
        raise ValueError("max_anchor must be at least start_prime")
    if limit < 1:
        raise ValueError("limit must be at least 1")
    if not isprime(start_prime):
        raise ValueError("start_prime must be prime")
    if state_vector_name not in STATE_VECTOR_LEAKAGE:
        raise ValueError(f"unknown state vector {state_vector_name}")
    if not STATE_VECTOR_LEAKAGE[state_vector_name]:
        raise ValueError(f"missing leakage metadata for {state_vector_name}")
    if any(STATE_VECTOR_LEAKAGE[state_vector_name].values()):
        raise ValueError(f"{state_vector_name} is not a legal state vector")

    anchors = [int(prime) for prime in primerange(start_prime, max_anchor + 1)]
    rows = [build_row(anchor_prime, prefix_len) for anchor_prime in anchors]
    collisions = ordered_collision_buckets(rows, state_vector_name)
    bucket_records = [
        forensic_bucket(state_vector_name, key, bucket)
        for key, bucket in collisions[:limit]
    ]
    summary = {
        "mode": "offline_collision_forensics",
        "start_prime": start_prime,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "state_vector_name": state_vector_name,
        "row_count": len(rows),
        "collision_bucket_count": len(collisions),
        "written_collision_bucket_count": len(bucket_records),
        "limit": limit,
        "contaminated_comparison_state_vectors": list(CONTAMINATED_STATE_VECTORS),
        "candidate_missing_observable_counts": {},
    }
    counts: dict[str, int] = {}
    for record in bucket_records:
        for candidate in record["candidate_missing_observable"]:
            counts[candidate] = counts.get(candidate, 0) + 1
    summary["candidate_missing_observable_counts"] = counts
    return bucket_records, summary


def write_artifacts(
    bucket_records: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL bucket records and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    buckets_path = output_dir / BUCKETS_FILENAME
    with buckets_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in bucket_records:
            handle.write(json.dumps(jsonable(record), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"buckets_path": buckets_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run legal ladder collision forensics and write artifacts."""
    args = build_parser().parse_args(argv)
    bucket_records, summary = run_forensics(
        start_prime=args.start_prime,
        max_anchor=args.max_anchor,
        prefix_len=args.prefix_len,
        state_vector_name=args.state_vector,
        limit=args.limit,
    )
    write_artifacts(bucket_records, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

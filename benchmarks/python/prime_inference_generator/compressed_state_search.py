#!/usr/bin/env python3
"""Compression search for legal multiplicity-pressure states.

This script is offline theorem discovery. It starts from the rejected
high-dimensional multiplicity pressure signal and coarsens it into lower
resolution state vectors. Classical next-gap labels are used only for collision
measurement.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

try:
    from .legal_candidate_hardening_probe import (
        build_rows,
        multiplicity_ladder,
        state_key,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from legal_candidate_hardening_probe import (
        build_rows,
        multiplicity_ladder,
        state_key,
    )


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "compressed_state_search_summary.json"
CANDIDATES_FILENAME = "compressed_state_search_candidates.jsonl"
COMPRESSED_CANDIDATES = [
    "multiplicity_pressure_bucketed",
    "multiplicity_pressure_mod_wheel",
    "multiplicity_pressure_histogram",
    "multiplicity_pressure_run_lengths",
    "multiplicity_pressure_coarse_counts",
    "multiplicity_pressure_quantized",
    "multiplicity_pressure_family_only",
    "multiplicity_pressure_without_offsets",
    "multiplicity_pressure_prefix_histogram",
    "multiplicity_pressure_low_medium_high",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the compressed-state search CLI."""
    parser = argparse.ArgumentParser(
        description="Offline compression search for legal multiplicity states.",
    )
    parser.add_argument(
        "--start-anchor",
        type=int,
        default=11,
        help="Inclusive lower bound for prime anchors.",
    )
    parser.add_argument(
        "--max-anchor",
        type=int,
        default=100_000,
        help="Inclusive upper bound for prime anchors.",
    )
    parser.add_argument(
        "--prefix-len",
        type=int,
        default=32,
        help="Fixed rightward prefix length used for compressed states.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def jsonable(value: Any) -> Any:
    """Convert tuples in nested values into JSON arrays."""
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


def base_context(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return the legal transition context shared by compressed states."""
    return (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
    )


def parse_multiplicity_token(token: str) -> tuple[int, int, int, int]:
    """Return exponent sum, distinct factor count, max exponent, repeated flag."""
    if token == "OPEN_UNKNOWN":
        return 0, 0, 0, 0
    exponent_sum = 0
    distinct_count = 0
    max_exponent = 0
    for part in token.removeprefix("MUL_").split("_"):
        if "^" not in part:
            continue
        exponent = int(part.split("^", 1)[1])
        exponent_sum += exponent
        distinct_count += 1
        max_exponent = max(max_exponent, exponent)
    return exponent_sum, distinct_count, max_exponent, int(max_exponent > 1)


def strength_bucket(token: str) -> str:
    """Return a coarse multiplicity-strength bucket."""
    exponent_sum, _, _, _ = parse_multiplicity_token(token)
    if exponent_sum == 0:
        return "S0"
    if exponent_sum == 1:
        return "S1"
    if exponent_sum == 2:
        return "S2"
    return "S3_PLUS"


def quantized_strength(token: str) -> int:
    """Return numeric multiplicity strength capped at 3."""
    exponent_sum, _, _, _ = parse_multiplicity_token(token)
    return min(exponent_sum, 3)


def low_medium_high(token: str) -> str:
    """Return low, medium, high, or open multiplicity pressure."""
    exponent_sum, _, _, _ = parse_multiplicity_token(token)
    if exponent_sum == 0:
        return "OPEN"
    if exponent_sum == 1:
        return "LOW"
    if exponent_sum == 2:
        return "MEDIUM"
    return "HIGH"


def family_only(token: str) -> str:
    """Return multiplicity family without exact factors."""
    exponent_sum, distinct_count, max_exponent, _ = parse_multiplicity_token(token)
    if exponent_sum == 0:
        return "OPEN"
    if distinct_count == 1 and max_exponent == 1:
        return "SINGLE_LINEAR"
    if distinct_count == 1:
        return "SINGLE_POWER"
    if max_exponent == 1:
        return "MIXED_LINEAR"
    return "MIXED_WITH_POWER"


def run_lengths(values: tuple[Any, ...]) -> tuple[tuple[str, int], ...]:
    """Return run lengths for consecutive equal values."""
    if not values:
        return ()
    runs: list[tuple[str, int]] = []
    current = values[0]
    length = 1
    for value in values[1:]:
        if value == current:
            length += 1
            continue
        runs.append((str(current), length))
        current = value
        length = 1
    runs.append((str(current), length))
    return tuple(runs)


def histogram(values: tuple[Any, ...]) -> tuple[tuple[str, int], ...]:
    """Return a deterministic histogram for tuple values."""
    counts = Counter(str(value) for value in values)
    return tuple(sorted(counts.items()))


def row_ladder(row: dict[str, Any]) -> tuple[str, ...]:
    """Return the source multiplicity ladder for one row."""
    return multiplicity_ladder(int(row["anchor_prime"]), int(row["prefix_len"]))


def compressed_state_vectors(row: dict[str, Any]) -> dict[str, Any]:
    """Return coarsened legal multiplicity-pressure state vectors."""
    ladder = row_ladder(row)
    buckets = tuple(strength_bucket(token) for token in ladder)
    quantized = tuple(quantized_strength(token) for token in ladder)
    families = tuple(family_only(token) for token in ladder)
    lmh = tuple(low_medium_high(token) for token in ladder)
    non_open_tokens = tuple(token for token in ladder if token != "OPEN_UNKNOWN")
    strengths = tuple(parse_multiplicity_token(token)[0] for token in ladder)
    repeated_count = sum(parse_multiplicity_token(token)[3] for token in ladder)
    occupied_count = len(non_open_tokens)
    high_count = sum(1 for strength in strengths if strength >= 3)
    medium_count = sum(1 for strength in strengths if strength == 2)
    first_occupied = next(
        (index for index, token in enumerate(ladder, start=1) if token != "OPEN_UNKNOWN"),
        None,
    )
    mod_wheel_counts = Counter(
        ((int(row["anchor_prime"]) + offset) % 30, strength_bucket(token))
        for offset, token in enumerate(ladder, start=1)
    )
    context = base_context(row)

    return {
        "multiplicity_pressure_bucketed": context + (buckets,),
        "multiplicity_pressure_mod_wheel": context
        + (tuple(sorted(mod_wheel_counts.items())),),
        "multiplicity_pressure_histogram": context + (histogram(ladder),),
        "multiplicity_pressure_run_lengths": context + (run_lengths(buckets),),
        "multiplicity_pressure_coarse_counts": context
        + (
            occupied_count,
            first_occupied,
            medium_count,
            high_count,
            repeated_count,
            max(strengths) if strengths else 0,
        ),
        "multiplicity_pressure_quantized": context + (quantized,),
        "multiplicity_pressure_family_only": context + (families,),
        "multiplicity_pressure_without_offsets": context
        + (tuple(sorted(non_open_tokens)),),
        "multiplicity_pressure_prefix_histogram": context
        + (
            histogram(buckets),
            histogram(families),
            occupied_count,
            high_count,
        ),
        "multiplicity_pressure_low_medium_high": context + (lmh,),
    }


def entropy_estimate(bucket_sizes: list[int], row_count: int) -> float:
    """Return Shannon entropy of state-bucket membership in bits."""
    if row_count == 0:
        return 0.0
    entropy = 0.0
    for size in bucket_sizes:
        probability = size / row_count
        entropy -= probability * math.log2(probability)
    return entropy


def candidate_report(rows: list[dict[str, Any]], candidate_name: str) -> dict[str, Any]:
    """Return compression and collision metrics for one compressed state."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        vector = compressed_state_vectors(row)[candidate_name]
        buckets[state_key(vector)].append(row)

    collision_count = 0
    singleton_bucket_count = 0
    max_bucket_size = 0
    collision_examples: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        labels = sorted({int(row["next_gap_width"]) for row in bucket})
        bucket_size = len(bucket)
        max_bucket_size = max(max_bucket_size, bucket_size)
        if bucket_size == 1:
            singleton_bucket_count += 1
        if len(labels) < 2:
            continue
        collision_count += 1
        if len(collision_examples) < 5:
            collision_examples.append(
                {
                    "state_key": json.loads(key),
                    "boundary_offsets": labels,
                    "anchors": [int(row["anchor_prime"]) for row in bucket[:8]],
                    "bucket_size": bucket_size,
                }
            )

    row_count = len(rows)
    distinct_state_count = len(buckets)
    bucket_sizes = [len(bucket) for bucket in buckets.values()]
    distinct_state_ratio = 0.0 if row_count == 0 else distinct_state_count / row_count
    singleton_bucket_rate = (
        0.0 if distinct_state_count == 0 else singleton_bucket_count / distinct_state_count
    )
    mean_bucket_size = 0.0 if distinct_state_count == 0 else row_count / distinct_state_count
    compression_score = 1.0 - distinct_state_ratio
    passes_collision_gate = collision_count == 0
    passes_compression_gate = (
        distinct_state_ratio <= 0.5 and singleton_bucket_rate <= 0.75
    )
    return {
        "candidate_name": candidate_name,
        "row_count": row_count,
        "distinct_state_count": distinct_state_count,
        "distinct_state_ratio": distinct_state_ratio,
        "singleton_bucket_rate": singleton_bucket_rate,
        "max_bucket_size": max_bucket_size,
        "mean_bucket_size": mean_bucket_size,
        "singleton_bucket_count": singleton_bucket_count,
        "collision_count": collision_count,
        "collision_rate": (
            0.0 if distinct_state_count == 0 else collision_count / distinct_state_count
        ),
        "compression_score": compression_score,
        "state_entropy_estimate": entropy_estimate(bucket_sizes, row_count),
        "collision_examples": collision_examples,
        "passes_collision_gate": passes_collision_gate,
        "passes_compression_gate": passes_compression_gate,
        "passes_frontier_gate": passes_collision_gate and passes_compression_gate,
    }


def run_search(
    start_anchor: int,
    max_anchor: int,
    prefix_len: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the compressed legal state search."""
    started = time.perf_counter()
    rows = build_rows(start_anchor, max_anchor, prefix_len)
    reports = [candidate_report(rows, name) for name in COMPRESSED_CANDIDATES]
    frontier_survivors = [
        report["candidate_name"]
        for report in reports
        if report["passes_frontier_gate"]
    ]
    lowest_collision = min(report["collision_count"] for report in reports)
    best_compression = max(report["compression_score"] for report in reports)
    summary = {
        "mode": "offline_compressed_legal_state_search",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "row_count": len(rows),
        "compression_gate": {
            "distinct_state_ratio_max": 0.5,
            "singleton_bucket_rate_max": 0.75,
            "collision_count_required": 0,
        },
        "candidates": reports,
        "frontier_survivors": frontier_survivors,
        "lowest_collision_count": lowest_collision,
        "best_compression_score": best_compression,
        "boundary_law_005_status": "not_approved",
        "runtime_seconds": time.perf_counter() - started,
    }
    return reports, summary


def write_artifacts(
    reports: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL candidate reports and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = output_dir / CANDIDATES_FILENAME
    with candidates_path.open("w", encoding="utf-8", newline="\n") as handle:
        for report in reports:
            handle.write(json.dumps(jsonable(report), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"candidates_path": candidates_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run compressed legal state search and write artifacts."""
    args = build_parser().parse_args(argv)
    reports, summary = run_search(
        start_anchor=args.start_anchor,
        max_anchor=args.max_anchor,
        prefix_len=args.prefix_len,
    )
    write_artifacts(reports, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

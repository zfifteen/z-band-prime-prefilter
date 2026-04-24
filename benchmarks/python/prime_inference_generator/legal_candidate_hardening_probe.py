#!/usr/bin/env python3
"""Hardening probe for legal zero-collision boundary-state candidates.

This script is offline theorem discovery. It uses next-gap labels only to
measure collisions. The candidate state vectors below use deterministic
composite-witness and power-signature features, not prime markers or divisor
count ladders.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

from sympy import nextprime, prevprime, primerange


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "legal_candidate_hardening_summary.json"
CANDIDATES_FILENAME = "legal_candidate_hardening_candidates.jsonl"
WHEEL_OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})
HARDENING_CANDIDATES = [
    "multiplicity_pressure_without_primality",
    "power_signature_pressure",
    "bounded_composite_witness_pressure",
]
BOUNDED_WITNESS_FACTORS = (2, 3, 5, 7, 11, 13, 17, 19)


def build_parser() -> argparse.ArgumentParser:
    """Build the legal-candidate hardening CLI."""
    parser = argparse.ArgumentParser(
        description="Offline hardening probe for legal pressure candidates.",
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
        help="Fixed rightward prefix length used for legal state features.",
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


def state_key(value: Any) -> str:
    """Return one deterministic JSON key for a state vector."""
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"))


def first_open_offset(anchor_prime: int) -> int:
    """Return the first positive offset whose residue is open mod 30."""
    for offset in range(1, 31):
        if (anchor_prime + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30:
            return offset
    raise RuntimeError(f"no wheel-open offset found for anchor {anchor_prime}")


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


def witness_token(n: int) -> str:
    """Return a bounded witness token, or OPEN_UNKNOWN."""
    witnesses = tuple(
        factor
        for factor in BOUNDED_WITNESS_FACTORS
        if factor < n and n % factor == 0
    )
    if not witnesses:
        return "OPEN_UNKNOWN"
    return "WITNESS_" + "_".join(str(factor) for factor in witnesses[:3])


def witness_ladder(anchor_prime: int, prefix_len: int) -> tuple[str, ...]:
    """Return bounded composite-witness tokens for one prefix."""
    return tuple(
        witness_token(anchor_prime + offset) for offset in range(1, prefix_len + 1)
    )


def first_witness_offset(tokens: tuple[str, ...]) -> int | None:
    """Return the first one-based offset with a bounded witness."""
    for offset, token in enumerate(tokens, start=1):
        if token != "OPEN_UNKNOWN":
            return offset
    return None


def small_factor_multiplicity_token(n: int) -> str:
    """Return multiplicity exponents for bounded factors only."""
    parts: list[str] = []
    residual = n
    for factor in BOUNDED_WITNESS_FACTORS:
        exponent = 0
        while residual % factor == 0:
            residual //= factor
            exponent += 1
        if exponent:
            parts.append(f"{factor}^{exponent}")
    if not parts:
        return "OPEN_UNKNOWN"
    return "MUL_" + "_".join(parts)


def multiplicity_ladder(anchor_prime: int, prefix_len: int) -> tuple[str, ...]:
    """Return bounded-factor multiplicity tokens for one prefix."""
    return tuple(
        small_factor_multiplicity_token(anchor_prime + offset)
        for offset in range(1, prefix_len + 1)
    )


def integer_power_offsets(
    anchor_prime: int,
    prefix_len: int,
    exponent: int,
) -> tuple[int, ...]:
    """Return offsets of exact integer powers in a fixed prefix."""
    offsets: list[int] = []
    lo = anchor_prime + 1
    hi = anchor_prime + prefix_len
    root = 1
    while root**exponent < lo:
        root += 1
    while root**exponent <= hi:
        offsets.append(root**exponent - anchor_prime)
        root += 1
    return tuple(offsets)


def next_integer_power_offset(anchor_prime: int, exponent: int) -> int:
    """Return offset to the next exact integer power after the anchor."""
    if exponent == 2:
        root = math.isqrt(anchor_prime) + 1
    else:
        root = 1
        while root**exponent <= anchor_prime:
            root += 1
    return root**exponent - anchor_prime


def build_rows(start_anchor: int, max_anchor: int, prefix_len: int) -> list[dict[str, Any]]:
    """Build labeled rows with legal candidate inputs and classical labels."""
    if prefix_len < 1:
        raise ValueError("prefix_len must be at least 1")
    if max_anchor < start_anchor:
        raise ValueError("max_anchor must be at least start_anchor")

    anchors = [int(prime) for prime in primerange(start_anchor, max_anchor + 1)]
    if not anchors:
        raise ValueError("surface contains no prime anchors")

    rows: list[dict[str, Any]] = []
    for index, anchor_prime in enumerate(anchors):
        previous_prime = (
            int(prevprime(anchor_prime)) if index == 0 else anchors[index - 1]
        )
        next_prime_value = (
            anchors[index + 1]
            if index + 1 < len(anchors)
            else int(nextprime(anchor_prime))
        )
        previous_gap_width = anchor_prime - previous_prime
        rows.append(
            {
                "anchor_prime": anchor_prime,
                "next_gap_width": next_prime_value - anchor_prime,
                "anchor_mod30": anchor_prime % 30,
                "first_open_offset": first_open_offset(anchor_prime),
                "previous_gap_width": previous_gap_width,
                "previous_gap_bucket": bucket_gap(previous_gap_width),
                "prefix_len": prefix_len,
            }
        )
    return rows


def base_context(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return legal transition context shared by the three candidates."""
    return (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
    )


def bounded_composite_witness_pressure(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return bounded witness pressure without prime identity."""
    ladder = witness_ladder(int(row["anchor_prime"]), int(row["prefix_len"]))
    witness_count = sum(1 for token in ladder if token != "OPEN_UNKNOWN")
    return base_context(row) + (
        witness_count,
        first_witness_offset(ladder),
        ladder,
    )


def power_signature_pressure(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return integer-power pressure without divisor counts."""
    anchor_prime = int(row["anchor_prime"])
    prefix_len = int(row["prefix_len"])
    return base_context(row) + (
        next_integer_power_offset(anchor_prime, 2),
        next_integer_power_offset(anchor_prime, 3),
        integer_power_offsets(anchor_prime, prefix_len, 2),
    )


def multiplicity_pressure_without_primality(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return bounded-factor multiplicity pressure without prime identity."""
    ladder = multiplicity_ladder(int(row["anchor_prime"]), int(row["prefix_len"]))
    return base_context(row) + (
        tuple(token for token in ladder if token != "OPEN_UNKNOWN"),
        ladder,
    )


def candidate_vector_functions() -> dict[str, Callable[[dict[str, Any]], Any]]:
    """Return the approved legal hardening candidates."""
    return {
        "multiplicity_pressure_without_primality": (
            multiplicity_pressure_without_primality
        ),
        "power_signature_pressure": power_signature_pressure,
        "bounded_composite_witness_pressure": bounded_composite_witness_pressure,
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


def hardening_status(
    collision_count: int,
    distinct_state_ratio: float,
    singleton_bucket_rate: float,
) -> tuple[str, bool, bool]:
    """Return hardening status, table-like flag, and pass flag."""
    table_like = distinct_state_ratio >= 0.95 or singleton_bucket_rate >= 0.95
    if collision_count != 0:
        return "failed_collision_gate", table_like, False
    if table_like:
        return "quarantined_table_like_state", table_like, False
    return "passes_current_hardening_surface", table_like, True


def candidate_report(
    rows: list[dict[str, Any]],
    candidate_name: str,
    vector_for_row: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """Return collision and anti-table metrics for one candidate."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[state_key(vector_for_row(row))].append(row)

    collision_count = 0
    max_bucket_size = 0
    singleton_bucket_count = 0
    first_collision_examples: list[dict[str, Any]] = []
    for key, bucket in buckets.items():
        labels = sorted({int(row["next_gap_width"]) for row in bucket})
        bucket_size = len(bucket)
        max_bucket_size = max(max_bucket_size, bucket_size)
        if bucket_size == 1:
            singleton_bucket_count += 1
        if len(labels) < 2:
            continue
        collision_count += 1
        if len(first_collision_examples) < 5:
            first_collision_examples.append(
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
    mean_bucket_size = 0.0 if distinct_state_count == 0 else row_count / distinct_state_count
    distinct_state_ratio = 0.0 if row_count == 0 else distinct_state_count / row_count
    singleton_bucket_rate = (
        0.0 if distinct_state_count == 0 else singleton_bucket_count / distinct_state_count
    )
    status, table_like_state, passes_hardening_gate = hardening_status(
        collision_count,
        distinct_state_ratio,
        singleton_bucket_rate,
    )
    return {
        "candidate_name": candidate_name,
        "eligible_for_pure_generation": True,
        "row_count": row_count,
        "distinct_state_count": distinct_state_count,
        "distinct_state_ratio": distinct_state_ratio,
        "collision_count": collision_count,
        "collision_rate": (
            0.0 if distinct_state_count == 0 else collision_count / distinct_state_count
        ),
        "max_bucket_size": max_bucket_size,
        "mean_bucket_size": mean_bucket_size,
        "singleton_bucket_count": singleton_bucket_count,
        "singleton_bucket_rate": singleton_bucket_rate,
        "state_entropy_estimate": entropy_estimate(bucket_sizes, row_count),
        "uses_anchor_value": False,
        "uses_future_boundary": False,
        "uses_prime_marker": False,
        "uses_full_divisor_count": False,
        "uses_exact_factorization": False,
        "uses_scan_to_first_prime": False,
        "uses_old_walker": False,
        "first_collision_examples": first_collision_examples,
        "zero_collision": collision_count == 0,
        "zero_collision_and_eligible": collision_count == 0,
        "table_like_state": table_like_state,
        "hardening_gate_status": status,
        "passes_hardening_gate": passes_hardening_gate,
    }


def run_probe(
    start_anchor: int,
    max_anchor: int,
    prefix_len: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run one legal-candidate hardening surface."""
    started = time.perf_counter()
    rows = build_rows(start_anchor, max_anchor, prefix_len)
    reports = [
        candidate_report(rows, candidate_name, vector_for_row)
        for candidate_name, vector_for_row in candidate_vector_functions().items()
    ]
    first_zero = next(
        (
            report["candidate_name"]
            for report in reports
            if report["zero_collision_and_eligible"]
        ),
        None,
    )
    summary = {
        "mode": "offline_legal_candidate_hardening",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "row_count": len(rows),
        "candidates": reports,
        "first_zero_collision_eligible_state_vector": first_zero,
        "hardening_gate_survivors": [
            report["candidate_name"]
            for report in reports
            if report["passes_hardening_gate"]
        ],
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
    """Run legal-candidate hardening and write artifacts."""
    args = build_parser().parse_args(argv)
    reports, summary = run_probe(
        start_anchor=args.start_anchor,
        max_anchor=args.max_anchor,
        prefix_len=args.prefix_len,
    )
    write_artifacts(reports, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

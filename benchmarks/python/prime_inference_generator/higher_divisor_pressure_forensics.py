#!/usr/bin/env python3
"""Forensics for contaminated higher-divisor pressure signals.

This script is offline theorem discovery. It audits exact higher-divisor
pressure states, then tests legal pressure approximations without changing the
pure generator.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

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
SUMMARY_FILENAME = "higher_divisor_pressure_forensics_summary.json"
EXACT_AUDITS_FILENAME = "higher_divisor_pressure_forensics_exact_states.jsonl"
CANDIDATES_FILENAME = "higher_divisor_pressure_forensics_candidates.jsonl"
EXACT_HIGHER_DIVISOR_STATES = [
    "higher_divisor_pressure_state",
    "previous_chamber_plus_higher_divisor_pressure_state",
    "previous_chamber_plus_square_and_higher_pressure_state",
]
LEGALIZATION_CANDIDATES = [
    "wheel_closed_density_pressure",
    "small_factor_witness_pressure",
    "bounded_composite_witness_pressure",
    "power_signature_pressure",
    "square_cube_power_pressure",
    "multiplicity_pressure_without_primality",
    "residue_class_pressure",
    "early_composite_run_pressure",
]
SMALL_WITNESS_FACTORS = (2, 3, 5, 7, 11)
BOUNDED_WITNESS_FACTORS = (2, 3, 5, 7, 11, 13, 17, 19)


class Component:
    """One named state-vector component."""

    def __init__(
        self,
        name: str,
        value: Callable[[dict[str, Any]], Any],
        legal_for_pure_generation: bool,
        reason: str,
    ) -> None:
        self.name = name
        self.value = value
        self.legal_for_pure_generation = legal_for_pure_generation
        self.reason = reason


def build_parser() -> argparse.ArgumentParser:
    """Build the higher-divisor pressure forensics CLI."""
    parser = argparse.ArgumentParser(
        description="Offline higher-divisor pressure legality forensics.",
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
        default=32,
        help="Fixed rightward prefix length used for pressure features.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def collision_report_for_vectors(
    rows: list[dict[str, Any]],
    state_vector_name: str,
    vector_for_row: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    """Return a collision report for one explicit vector function."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        buckets[state_key(vector_for_row(row))].append(row)

    collision_count = 0
    max_bucket_size = 0
    first_collision_examples: list[dict[str, Any]] = []
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
    return {
        "state_vector_name": state_vector_name,
        "row_count": len(rows),
        "distinct_state_count": distinct_state_count,
        "collision_count": collision_count,
        "collision_rate": (
            0.0 if distinct_state_count == 0 else collision_count / distinct_state_count
        ),
        "first_collision_examples": first_collision_examples,
        "max_bucket_size": max_bucket_size,
        "zero_collision": collision_count == 0,
    }


def wheel_closed_run_lengths(tokens: tuple[str, ...]) -> tuple[int, ...]:
    """Return lengths of consecutive wheel-closed runs."""
    runs: list[int] = []
    current = 0
    for token in tokens:
        if token == "CLOSED_WHEEL":
            current += 1
            continue
        if current:
            runs.append(current)
            current = 0
    if current:
        runs.append(current)
    return tuple(runs)


def first_matching_offset(tokens: tuple[str, ...], prefix: str) -> int | None:
    """Return the first one-based offset whose token starts with a prefix."""
    for index, token in enumerate(tokens, start=1):
        if token.startswith(prefix):
            return index
    return None


def witness_token(n: int, factors: tuple[int, ...]) -> str:
    """Return a concrete bounded witness token, or OPEN_UNKNOWN."""
    witnesses = tuple(factor for factor in factors if factor < n and n % factor == 0)
    if not witnesses:
        return "OPEN_UNKNOWN"
    return "WITNESS_" + "_".join(str(factor) for factor in witnesses[:3])


def witness_ladder(
    anchor_prime: int,
    prefix_len: int,
    factors: tuple[int, ...],
) -> tuple[str, ...]:
    """Return bounded composite-witness tokens for one prefix."""
    return tuple(
        witness_token(anchor_prime + offset, factors)
        for offset in range(1, prefix_len + 1)
    )


def witness_density(tokens: tuple[str, ...]) -> tuple[int, int | None, tuple[str, ...]]:
    """Return witness count, first witness offset, and compact witness ladder."""
    witness_count = sum(1 for token in tokens if token != "OPEN_UNKNOWN")
    first_witness = first_matching_offset(tokens, "WITNESS_")
    return witness_count, first_witness, tokens


def small_factor_multiplicity_token(n: int) -> str:
    """Return multiplicity exponents for fixed small witnesses only."""
    parts: list[str] = []
    residual = n
    for factor in SMALL_WITNESS_FACTORS:
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
    """Return fixed-small-factor multiplicity tokens for one prefix."""
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


def residue_ladder(anchor_prime: int, prefix_len: int, modulus: int) -> tuple[int, ...]:
    """Return prefix residues for a fixed modulus."""
    return tuple((anchor_prime + offset) % modulus for offset in range(1, prefix_len + 1))


def base_legal_context(row: dict[str, Any]) -> tuple[Any, ...]:
    """Return the legal transition context shared by legalization candidates."""
    return (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["previous_gap_bucket"],
    )


def legalization_candidate_vectors(row: dict[str, Any]) -> dict[str, Any]:
    """Return legal higher-divisor pressure approximations for one row."""
    prefix_len = int(row["prefix_len"])
    anchor_prime = int(row["anchor_prime"])
    open_unknown_ladder = tuple(row["open_unknown_ladder"])
    composite_witness_ladder = tuple(row["composite_witness_ladder"])
    small_witness_ladder = witness_ladder(
        anchor_prime,
        prefix_len,
        SMALL_WITNESS_FACTORS,
    )
    bounded_witness_ladder = witness_ladder(
        anchor_prime,
        prefix_len,
        BOUNDED_WITNESS_FACTORS,
    )
    small_count, small_first, small_tokens = witness_density(small_witness_ladder)
    bounded_count, bounded_first, bounded_tokens = witness_density(
        bounded_witness_ladder
    )
    square_offsets = integer_power_offsets(anchor_prime, prefix_len, 2)
    cube_offsets = integer_power_offsets(anchor_prime, prefix_len, 3)
    fourth_power_offsets = integer_power_offsets(anchor_prime, prefix_len, 4)
    mult_ladder = multiplicity_ladder(anchor_prime, prefix_len)
    context = base_legal_context(row)

    return {
        "wheel_closed_density_pressure": context
        + (
            open_unknown_ladder.count("CLOSED_WHEEL"),
            first_matching_offset(open_unknown_ladder, "CLOSED_WHEEL"),
            wheel_closed_run_lengths(open_unknown_ladder),
            open_unknown_ladder,
        ),
        "small_factor_witness_pressure": context
        + (
            small_count,
            small_first,
            small_tokens,
        ),
        "bounded_composite_witness_pressure": context
        + (
            bounded_count,
            bounded_first,
            bounded_tokens,
        ),
        "power_signature_pressure": context
        + (
            next_integer_power_offset(anchor_prime, 2),
            next_integer_power_offset(anchor_prime, 3),
            square_offsets,
        ),
        "square_cube_power_pressure": context
        + (
            square_offsets,
            cube_offsets,
            fourth_power_offsets,
        ),
        "multiplicity_pressure_without_primality": context
        + (
            tuple(token for token in mult_ladder if token != "OPEN_UNKNOWN"),
            mult_ladder,
        ),
        "residue_class_pressure": context
        + (
            residue_ladder(anchor_prime, prefix_len, 30),
            residue_ladder(anchor_prime, prefix_len, 210),
        ),
        "early_composite_run_pressure": context
        + (
            wheel_closed_run_lengths(open_unknown_ladder),
            wheel_closed_run_lengths(
                tuple(
                    "CLOSED_WHEEL" if token != "OPEN_UNKNOWN" else "OPEN_UNKNOWN"
                    for token in bounded_witness_ladder
                )
            ),
            composite_witness_ladder,
        ),
    }


def exact_components(state_vector_name: str) -> list[Component]:
    """Return named components for exact higher-divisor state ablation."""
    shared = [
        Component(
            "anchor_mod30",
            lambda row: row["anchor_mod30"],
            True,
            "anchor residue is known at emission time",
        ),
        Component(
            "first_open_offset",
            lambda row: row["first_open_offset"],
            True,
            "wheel-open offset is residue arithmetic",
        ),
    ]
    previous = [
        Component(
            "previous_gap_bucket",
            lambda row: row["previous_gap_bucket"],
            True,
            "previous accepted boundary can carry prior chamber context",
        )
    ]
    square = [
        Component(
            "next_square_offset",
            lambda row: row["next_square_offset"],
            True,
            "next integer square is PGS-native arithmetic",
        ),
        Component(
            "square_offsets",
            lambda row: row["square_offsets"],
            True,
            "square offsets are PGS-native arithmetic",
        ),
    ]
    higher = [
        Component(
            "high_divisor_count",
            lambda row: row["high_divisor_count"],
            False,
            "requires exact divisor count across the prefix",
        ),
        Component(
            "high_divisor_offsets",
            lambda row: row["high_divisor_offsets"],
            False,
            "requires exact divisor-count thresholding",
        ),
        Component(
            "divisor_bucket_ladder",
            lambda row: row["divisor_bucket_ladder"],
            False,
            "contains full divisor buckets, including d=2 prime markers",
        ),
    ]
    if state_vector_name == "higher_divisor_pressure_state":
        return shared + higher
    if state_vector_name == "previous_chamber_plus_higher_divisor_pressure_state":
        return shared + previous + higher
    if state_vector_name == "previous_chamber_plus_square_and_higher_pressure_state":
        return shared + previous + square + higher
    raise ValueError(f"unknown exact higher-divisor state {state_vector_name}")


def feature_component_records(components: list[Component]) -> list[dict[str, Any]]:
    """Return JSON-ready component metadata."""
    return [
        {
            "name": component.name,
            "legal_for_pure_generation": component.legal_for_pure_generation,
            "reason": component.reason,
        }
        for component in components
    ]


def ablation_report(
    rows: list[dict[str, Any]],
    state_vector_name: str,
    components: list[Component],
    removed_component: Component,
) -> dict[str, Any]:
    """Return a collision report after removing one component."""
    kept = [component for component in components if component != removed_component]
    report = collision_report_for_vectors(
        rows,
        f"{state_vector_name}__without__{removed_component.name}",
        lambda row: tuple(component.value(row) for component in kept),
    )
    return {
        "removed_component": removed_component.name,
        "component_legal_for_pure_generation": (
            removed_component.legal_for_pure_generation
        ),
        "collision_count": report["collision_count"],
        "distinct_state_count": report["distinct_state_count"],
        "zero_collision": report["zero_collision"],
    }


def ineligibility_flags(state_vector_name: str) -> dict[str, bool]:
    """Return explicit contamination flags for an exact pressure state."""
    legality = PRESSURE_STATE_LEGALITY[state_vector_name]
    return {
        "uses_exact_factorization": bool(legality["uses_exact_factorization"]),
        "uses_prime_marker": bool(legality["uses_prime_marker_d2"]),
        "uses_future_boundary": bool(legality["uses_future_boundary_offset"]),
        "uses_scan_to_first_prime": bool(legality["uses_stop_at_first_prime"]),
        "uses_d2_recognition": bool(legality["uses_prime_marker_d2"]),
        "uses_full_divisor_count": bool(legality["uses_exact_factorization"]),
        "uses_old_walker": False,
    }


def ineligibility_reasons(flags: dict[str, bool]) -> list[str]:
    """Return compact reason labels from contamination flags."""
    reasons: list[str] = []
    if flags["uses_exact_factorization"]:
        reasons.append("EXACT_FACTORIZATION")
    if flags["uses_prime_marker"]:
        reasons.append("PRIME_MARKER")
    if flags["uses_future_boundary"]:
        reasons.append("FUTURE_BOUNDARY")
    if flags["uses_scan_to_first_prime"]:
        reasons.append("SCAN_TO_FIRST_PRIME")
    if flags["uses_d2_recognition"]:
        reasons.append("D2_RECOGNITION")
    if flags["uses_full_divisor_count"]:
        reasons.append("FULL_DIVISOR_COUNT")
    if flags["uses_old_walker"]:
        reasons.append("OLD_WALKER")
    return reasons


def minimal_illegal_component(
    full_report: dict[str, Any],
    components: list[Component],
    ablations: list[dict[str, Any]],
) -> str | None:
    """Return the smallest necessary illegal component, if the run exposes one."""
    if not full_report["zero_collision"]:
        return None
    ablation_by_name = {
        str(report["removed_component"]): report for report in ablations
    }
    necessary = [
        component
        for component in components
        if not component.legal_for_pure_generation
        and not ablation_by_name[component.name]["zero_collision"]
    ]
    if not necessary:
        return None
    priority = {
        "high_divisor_count": 0,
        "high_divisor_offsets": 1,
        "divisor_bucket_ladder": 2,
    }
    return min(necessary, key=lambda component: priority[component.name]).name


def exact_state_audit(rows: list[dict[str, Any]], state_vector_name: str) -> dict[str, Any]:
    """Audit one contaminated exact higher-divisor pressure state."""
    components = exact_components(state_vector_name)
    full_report = collision_report_for_vectors(
        rows,
        state_vector_name,
        lambda row: pressure_state_vectors(row)[state_vector_name],
    )
    ablations = [
        ablation_report(rows, state_vector_name, components, component)
        for component in components
    ]
    flags = ineligibility_flags(state_vector_name)
    component_name = minimal_illegal_component(full_report, components, ablations)
    return {
        "state_vector_name": state_vector_name,
        "collision_count": full_report["collision_count"],
        "eligible_for_pure_generation": bool(
            PRESSURE_STATE_LEGALITY[state_vector_name]["eligible_for_pure_generation"]
        ),
        "ineligibility_reasons": ineligibility_reasons(flags),
        **flags,
        "feature_components": feature_component_records(components),
        "component_ablation_results": ablations,
        "minimal_illegal_component": component_name,
        "zero_collision": full_report["zero_collision"],
        "first_collision_examples": full_report["first_collision_examples"],
    }


def legalization_candidate_report(
    rows: list[dict[str, Any]],
    candidate_name: str,
) -> dict[str, Any]:
    """Return one legal approximation collision report."""
    report = collision_report_for_vectors(
        rows,
        candidate_name,
        lambda row: legalization_candidate_vectors(row)[candidate_name],
    )
    return {
        **report,
        "eligible_for_pure_generation": True,
        "uses_exact_factorization": False,
        "uses_prime_marker": False,
        "uses_future_boundary": False,
        "uses_scan_to_first_prime": False,
        "uses_d2_recognition": False,
        "uses_full_divisor_count": False,
        "uses_old_walker": False,
        "zero_collision_and_eligible": report["zero_collision"],
    }


def run_forensics(
    start_prime: int,
    max_anchor: int,
    prefix_len: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Run higher-divisor pressure forensics and legalization candidates."""
    if prefix_len < 1:
        raise ValueError("prefix_len must be at least 1")
    if max_anchor < start_prime:
        raise ValueError("max_anchor must be at least start_prime")
    if not isprime(start_prime):
        raise ValueError("start_prime must be prime")

    started = time.perf_counter()
    anchors = [int(prime) for prime in primerange(start_prime, max_anchor + 1)]
    rows = [build_pressure_row(anchor_prime, prefix_len) for anchor_prime in anchors]
    exact_audits = [
        exact_state_audit(rows, state_name)
        for state_name in EXACT_HIGHER_DIVISOR_STATES
    ]
    candidate_reports = [
        legalization_candidate_report(rows, candidate_name)
        for candidate_name in LEGALIZATION_CANDIDATES
    ]
    first_zero_eligible = next(
        (
            report["state_vector_name"]
            for report in candidate_reports
            if report["zero_collision_and_eligible"]
        ),
        None,
    )
    minimal_components = {
        audit["state_vector_name"]: audit["minimal_illegal_component"]
        for audit in exact_audits
    }
    summary = {
        "mode": "offline_higher_divisor_pressure_forensics",
        "start_prime": start_prime,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "row_count": len(rows),
        "audited_exact_states": EXACT_HIGHER_DIVISOR_STATES,
        "legalization_candidates": LEGALIZATION_CANDIDATES,
        "exact_state_audits": exact_audits,
        "legalization_candidate_results": candidate_reports,
        "first_zero_collision_eligible_state_vector": first_zero_eligible,
        "minimal_illegal_component": minimal_components,
        "runtime_seconds": time.perf_counter() - started,
    }
    return exact_audits, candidate_reports, summary


def write_artifacts(
    exact_audits: list[dict[str, Any]],
    candidate_reports: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL records and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    exact_path = output_dir / EXACT_AUDITS_FILENAME
    with exact_path.open("w", encoding="utf-8", newline="\n") as handle:
        for audit in exact_audits:
            handle.write(json.dumps(jsonable(audit), sort_keys=True) + "\n")

    candidates_path = output_dir / CANDIDATES_FILENAME
    with candidates_path.open("w", encoding="utf-8", newline="\n") as handle:
        for report in candidate_reports:
            handle.write(json.dumps(jsonable(report), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "exact_audits_path": exact_path,
        "candidates_path": candidates_path,
        "summary_path": summary_path,
    }


def main(argv: list[str] | None = None) -> int:
    """Run higher-divisor pressure forensics and write artifacts."""
    args = build_parser().parse_args(argv)
    exact_audits, candidate_reports, summary = run_forensics(
        start_prime=args.start_prime,
        max_anchor=args.max_anchor,
        prefix_len=args.prefix_len,
    )
    write_artifacts(exact_audits, candidate_reports, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

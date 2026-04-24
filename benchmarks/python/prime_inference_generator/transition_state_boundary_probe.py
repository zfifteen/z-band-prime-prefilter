#!/usr/bin/env python3
"""Offline transition-state collision probe for boundary theorem discovery.

This script is not part of pure generation. It may use classical prime labels
because it searches for theorem candidates rather than emitting inferred primes.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from sympy import divisor_count, factorint, isprime, nextprime, prevprime, primerange


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "transition_state_boundary_probe_summary.json"
ROWS_FILENAME = "transition_state_boundary_probe_rows.jsonl"
WHEEL_OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})
STATE_VECTOR_NAMES = [
    "wheel",
    "wheel_prefix",
    "wheel_open_pattern",
    "open_unknown_ladder",
    "composite_witness_ladder",
    "known_composite_divisor_ladder",
    "carrier_ladder_no_prime_mask",
    "carrier_plus_open_unknown_ladder",
    "previous_gap_ladder_no_prime_mask",
    "carrier",
    "carrier_ladder",
    "previous_gap_carrier",
    "previous_gap_ladder",
]
STATE_VECTOR_LEAKAGE = {
    "wheel": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "wheel_prefix": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "wheel_open_pattern": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "open_unknown_ladder": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "composite_witness_ladder": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "known_composite_divisor_ladder": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "carrier_ladder_no_prime_mask": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "carrier_plus_open_unknown_ladder": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "previous_gap_ladder_no_prime_mask": {
        "uses_boundary_offset": False,
        "uses_gap_width": True,
        "uses_prime_marker_d2": False,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": False,
    },
    "carrier": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
    },
    "carrier_ladder": {
        "uses_boundary_offset": False,
        "uses_gap_width": False,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
    },
    "previous_gap_carrier": {
        "uses_boundary_offset": False,
        "uses_gap_width": True,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
    },
    "previous_gap_ladder": {
        "uses_boundary_offset": False,
        "uses_gap_width": True,
        "uses_prime_marker_d2": True,
        "uses_stop_at_first_prime": False,
        "uses_nextprime_or_isprime": True,
    },
}


def build_parser() -> argparse.ArgumentParser:
    """Build the theorem-search probe CLI."""
    parser = argparse.ArgumentParser(
        description="Offline PGS transition-state collision probe.",
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
        default=200,
        help="Largest anchor prime in the labeled surface.",
    )
    parser.add_argument(
        "--prefix-len",
        type=int,
        default=8,
        help="Fixed rightward prefix length used for local state features.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def first_open_offset(anchor_prime: int) -> int:
    """Return the first positive offset whose residue is open mod 30."""
    for offset in range(1, 31):
        if (anchor_prime + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30:
            return offset
    raise RuntimeError(f"no wheel-open offset found for anchor {anchor_prime}")


def divisor_family(n: int) -> str:
    """Return a compact divisor-family label for one integer."""
    factors = factorint(n)
    exponent_sum = sum(int(exponent) for exponent in factors.values())
    if len(factors) == 1:
        return "prime_power"
    if exponent_sum == 2:
        return "semiprime"
    return "composite"


def wheel_closure_witness(n: int) -> int | None:
    """Return a wheel-basis factor for wheel-closed values."""
    if n % 30 in WHEEL_OPEN_RESIDUES_MOD30:
        return None
    for factor in (2, 3, 5):
        if n % factor == 0:
            return factor
    return None


def wheel_basis_exact_divisor_count(n: int) -> int | None:
    """Return d(n) when the wheel-basis factors fully determine it."""
    residual = n
    divisor_total = 1
    for factor in (2, 3, 5):
        exponent = 0
        while residual % factor == 0:
            residual //= factor
            exponent += 1
        if exponent:
            divisor_total *= exponent + 1

    if residual == 1:
        return divisor_total
    return None


def legal_prefix_tokens(n: int) -> dict[str, Any]:
    """Return PGS-legal prefix tokens without prime identity."""
    witness = wheel_closure_witness(n)
    if witness is None:
        return {
            "open_unknown_token": "OPEN_UNKNOWN",
            "composite_witness_token": "OPEN_UNKNOWN",
            "known_divisor_token": "OPEN_UNKNOWN",
            "known_divisor_count": None,
            "wheel_witness_factor": None,
        }

    exact_d = wheel_basis_exact_divisor_count(n)
    return {
        "open_unknown_token": "CLOSED_WHEEL",
        "composite_witness_token": f"CLOSED_BY_{witness}",
        "known_divisor_token": (
            f"C{exact_d}" if exact_d is not None else f"CLOSED_BY_{witness}"
        ),
        "known_divisor_count": exact_d,
        "wheel_witness_factor": witness,
    }


def prefix_profile(anchor_prime: int, prefix_len: int) -> list[dict[str, Any]]:
    """Return local prefix profile with prime positions masked as open_unknown."""
    profile: list[dict[str, Any]] = []
    for offset in range(1, prefix_len + 1):
        n = anchor_prime + offset
        d_value = int(divisor_count(n))
        prime_label = bool(isprime(n))
        legal_tokens = legal_prefix_tokens(n)
        profile.append(
            {
                "offset": offset,
                "n": n,
                "wheel_open": n % 30 in WHEEL_OPEN_RESIDUES_MOD30,
                "masked_divisor_count": None if prime_label else d_value,
                "family": "open_unknown" if prime_label else divisor_family(n),
                **legal_tokens,
            }
        )
    return profile


def first_carrier(profile: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the leftmost minimum-divisor composite carrier in one prefix."""
    composites = [row for row in profile if row["masked_divisor_count"] is not None]
    if not composites:
        return {
            "first_carrier_offset": None,
            "first_carrier_divisor_count": None,
            "first_carrier_family": None,
        }

    best = min(
        composites,
        key=lambda row: (int(row["masked_divisor_count"]), int(row["offset"])),
    )
    return {
        "first_carrier_offset": int(best["offset"]),
        "first_carrier_divisor_count": int(best["masked_divisor_count"]),
        "first_carrier_family": str(best["family"]),
    }


def legal_first_known_carrier(profile: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the first minimum known divisor-class carrier from legal tokens."""
    known = [row for row in profile if row["known_divisor_count"] is not None]
    if not known:
        return {
            "legal_carrier_offset": None,
            "legal_carrier_divisor_count": None,
            "legal_carrier_family": None,
        }

    best = min(
        known,
        key=lambda row: (int(row["known_divisor_count"]), int(row["offset"])),
    )
    return {
        "legal_carrier_offset": int(best["offset"]),
        "legal_carrier_divisor_count": int(best["known_divisor_count"]),
        "legal_carrier_family": str(best["known_divisor_token"]),
    }


def first_wheel_witness(profile: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the first wheel-closed composite witness in one prefix."""
    for row in profile:
        if row["wheel_witness_factor"] is not None:
            return {
                "first_witness_offset": int(row["offset"]),
                "first_witness_factor": int(row["wheel_witness_factor"]),
            }
    return {
        "first_witness_offset": None,
        "first_witness_factor": None,
    }


def build_row(anchor_prime: int, prefix_len: int) -> dict[str, Any]:
    """Build one labeled transition-state row."""
    next_prime_value = int(nextprime(anchor_prime))
    previous_prime_value = int(prevprime(anchor_prime)) if anchor_prime > 2 else None
    profile = prefix_profile(anchor_prime, prefix_len)
    carrier = first_carrier(profile)
    legal_carrier = legal_first_known_carrier(profile)
    legal_witness = first_wheel_witness(profile)
    masked_ladder = tuple(row["masked_divisor_count"] for row in profile)
    family_ladder = tuple(row["family"] for row in profile)
    open_unknown_ladder = tuple(row["open_unknown_token"] for row in profile)
    composite_witness_ladder = tuple(
        row["composite_witness_token"] for row in profile
    )
    known_composite_divisor_ladder = tuple(
        row["known_divisor_token"] for row in profile
    )
    prime_marker_offsets = tuple(
        int(row["offset"]) for row in profile if row["masked_divisor_count"] is None
    )
    wheel_open_ladder = tuple(bool(row["wheel_open"]) for row in profile)
    next_gap_width = next_prime_value - anchor_prime

    row: dict[str, Any] = {
        "anchor_prime": anchor_prime,
        "next_prime": next_prime_value,
        "next_gap_width": next_gap_width,
        "previous_gap_width": (
            None if previous_prime_value is None else anchor_prime - previous_prime_value
        ),
        "anchor_mod30": anchor_prime % 30,
        "first_open_offset": first_open_offset(anchor_prime),
        "prefix_len": prefix_len,
        "masked_divisor_ladder": masked_ladder,
        "family_ladder": family_ladder,
        "open_unknown_ladder": open_unknown_ladder,
        "composite_witness_ladder": composite_witness_ladder,
        "known_composite_divisor_ladder": known_composite_divisor_ladder,
        "prime_marker_offsets": prime_marker_offsets,
        "boundary_offset_within_prefix": next_gap_width <= prefix_len,
        "prefix_contains_boundary_prime_marker": next_gap_width in prime_marker_offsets,
        "wheel_open_ladder": wheel_open_ladder,
    }
    row.update(carrier)
    row.update(legal_carrier)
    row.update(legal_witness)
    return row


def state_vectors_for_row(row: dict[str, Any]) -> dict[str, Any]:
    """Return candidate transition-state vectors for one row."""
    wheel = (
        row["anchor_mod30"],
        row["first_open_offset"],
    )
    carrier = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["first_carrier_offset"],
        row["first_carrier_divisor_count"],
        row["first_carrier_family"],
    )
    ladder = carrier + (
        row["masked_divisor_ladder"],
        row["family_ladder"],
    )
    previous_gap_carrier = carrier + (
        row["previous_gap_width"],
    )
    previous_gap_ladder = ladder + (
        row["previous_gap_width"],
    )
    wheel_open_pattern = (
        row["anchor_mod30"],
        row["wheel_open_ladder"],
    )
    open_unknown_ladder = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["open_unknown_ladder"],
    )
    composite_witness_ladder = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["composite_witness_ladder"],
    )
    known_composite_divisor_ladder = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["known_composite_divisor_ladder"],
    )
    carrier_ladder_no_prime_mask = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["legal_carrier_offset"],
        row["legal_carrier_divisor_count"],
        row["legal_carrier_family"],
        row["known_composite_divisor_ladder"],
    )
    carrier_plus_open_unknown_ladder = (
        row["anchor_mod30"],
        row["first_open_offset"],
        row["first_witness_offset"],
        row["first_witness_factor"],
        row["open_unknown_ladder"],
    )
    previous_gap_ladder_no_prime_mask = carrier_ladder_no_prime_mask + (
        row["previous_gap_width"],
    )

    return {
        "wheel": wheel,
        "wheel_prefix": wheel + (row["wheel_open_ladder"],),
        "wheel_open_pattern": wheel_open_pattern,
        "open_unknown_ladder": open_unknown_ladder,
        "composite_witness_ladder": composite_witness_ladder,
        "known_composite_divisor_ladder": known_composite_divisor_ladder,
        "carrier_ladder_no_prime_mask": carrier_ladder_no_prime_mask,
        "carrier_plus_open_unknown_ladder": carrier_plus_open_unknown_ladder,
        "previous_gap_ladder_no_prime_mask": previous_gap_ladder_no_prime_mask,
        "carrier": carrier,
        "carrier_ladder": ladder,
        "previous_gap_carrier": previous_gap_carrier,
        "previous_gap_ladder": previous_gap_ladder,
    }


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


def leakage_audit(rows: list[dict[str, Any]], state_vector_name: str) -> dict[str, Any]:
    """Return leakage indicators for one state-vector definition."""
    leakage = STATE_VECTOR_LEAKAGE[state_vector_name]
    row_count = len(rows)
    boundary_hits = sum(1 for row in rows if row["boundary_offset_within_prefix"])
    boundary_marker_hits = sum(
        1 for row in rows if row["prefix_contains_boundary_prime_marker"]
    )
    state_contains_boundary_token_count = (
        boundary_marker_hits if leakage["uses_prime_marker_d2"] else 0
    )
    eligible = not any(
        bool(leakage[field])
        for field in (
            "uses_boundary_offset",
            "uses_gap_width",
            "uses_prime_marker_d2",
            "uses_stop_at_first_prime",
            "uses_nextprime_or_isprime",
        )
    )

    return {
        **leakage,
        "boundary_offset_within_prefix_rate": (
            0.0 if row_count == 0 else boundary_hits / row_count
        ),
        "state_contains_boundary_token_rate": (
            0.0 if row_count == 0 else state_contains_boundary_token_count / row_count
        ),
        "eligible_for_pure_generation": eligible,
    }


def collision_report(rows: list[dict[str, Any]], state_vector_name: str) -> dict[str, Any]:
    """Return collision report for one state-vector definition."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        vector = state_vectors_for_row(row)[state_vector_name]
        buckets[state_key(vector)].append(row)

    collision_examples: list[dict[str, Any]] = []
    collision_count = 0
    max_bucket_size = 0
    for key, bucket in buckets.items():
        labels = sorted({int(row["next_gap_width"]) for row in bucket})
        max_bucket_size = max(max_bucket_size, len(bucket))
        if len(labels) < 2:
            continue

        collision_count += 1
        if len(collision_examples) < 5:
            collision_examples.append(
                {
                    "state_key": json.loads(key),
                    "labels": labels,
                    "anchors": [int(row["anchor_prime"]) for row in bucket[:8]],
                    "bucket_size": len(bucket),
                }
            )

    zero_collision = collision_count == 0
    leakage = leakage_audit(rows, state_vector_name)
    return {
        "state_vector": state_vector_name,
        "row_count": len(rows),
        "distinct_state_count": len(buckets),
        "collision_count": collision_count,
        "collision_examples": collision_examples,
        "max_bucket_size": max_bucket_size,
        "zero_collision": zero_collision,
        **leakage,
        "zero_collision_and_eligible": (
            zero_collision and bool(leakage["eligible_for_pure_generation"])
        ),
    }


def run_probe(start_prime: int, max_anchor: int, prefix_len: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the offline transition-state probe."""
    if prefix_len < 1:
        raise ValueError("prefix_len must be at least 1")
    if max_anchor < start_prime:
        raise ValueError("max_anchor must be at least start_prime")
    if not isprime(start_prime):
        raise ValueError("start_prime must be prime")

    started = time.perf_counter()
    anchors = [int(prime) for prime in primerange(start_prime, max_anchor + 1)]
    rows = [build_row(anchor_prime, prefix_len) for anchor_prime in anchors]
    reports = [collision_report(rows, name) for name in STATE_VECTOR_NAMES]
    first_zero = next(
        (report["state_vector"] for report in reports if report["zero_collision"]),
        None,
    )
    first_zero_eligible = next(
        (
            report["state_vector"]
            for report in reports
            if report["zero_collision_and_eligible"]
        ),
        None,
    )
    summary = {
        "mode": "offline_theorem_search",
        "start_prime": start_prime,
        "max_anchor": max_anchor,
        "prefix_len": prefix_len,
        "row_count": len(rows),
        "state_vectors": reports,
        "first_zero_collision_state_vector": first_zero,
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
    """Run the offline transition-state theorem-search probe."""
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

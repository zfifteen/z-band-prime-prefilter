#!/usr/bin/env python3
"""Offline probe for GWR-style right-boundary pressure ceilings.

This script tests a conservative ceiling shape: a certified composite carrier
followed by a later certified lower-divisor threat. Classical labels are
attached only after the label-free ceiling and composite-exclusion passes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        COMPOSITE_WITNESS_FACTORS,
        SINGLE_HOLE_WITNESS_FACTORS,
        WHEEL_OPEN_RESIDUES_MOD30,
        run_probe as run_exclusion_probe,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        COMPOSITE_WITNESS_FACTORS,
        SINGLE_HOLE_WITNESS_FACTORS,
        WHEEL_OPEN_RESIDUES_MOD30,
        run_probe as run_exclusion_probe,
    )


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "right_boundary_pressure_ceiling_probe_summary.json"
ROWS_FILENAME = "right_boundary_pressure_ceiling_probe_rows.jsonl"
KNOWN_PRIME_BASIS_PREFIX = (2, 3, 5)
CEILING_STATUS_CANDIDATE = "CANDIDATE_GWR_PRESSURE_CEILING"


def build_parser() -> argparse.ArgumentParser:
    """Build the right-boundary pressure ceiling CLI."""
    parser = argparse.ArgumentParser(
        description="Offline GWR right-boundary pressure ceiling probe.",
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
        default=10_000,
        help="Inclusive upper bound for prime anchors.",
    )
    parser.add_argument(
        "--candidate-bound",
        type=int,
        default=64,
        help="Largest candidate boundary offset before ceiling.",
    )
    parser.add_argument(
        "--witness-bound",
        type=int,
        default=97,
        help="Largest positive witness factor used by the offline eliminator.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def jsonable(value: Any) -> Any:
    """Convert nested tuples and Counters into JSON-ready values."""
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, Counter):
        return {str(key): int(count) for key, count in sorted(value.items())}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


def candidate_offsets(anchor_p: int, candidate_bound: int) -> list[int]:
    """Return wheel-open candidate offsets in a finite search window."""
    return [
        offset
        for offset in range(1, candidate_bound + 1)
        if (anchor_p + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30
    ]


def known_basis(witness_bound: int) -> tuple[int, ...]:
    """Return the explicit small-prime basis available to this probe."""
    basis = (
        *KNOWN_PRIME_BASIS_PREFIX,
        *COMPOSITE_WITNESS_FACTORS,
        *SINGLE_HOLE_WITNESS_FACTORS,
    )
    return tuple(factor for factor in basis if factor <= witness_bound)


def certified_divisor_class(n: int, witness_bound: int) -> dict[str, Any] | None:
    """Return a positive divisor-class certificate for n, if available."""
    basis = known_basis(witness_bound)
    for base in basis:
        for exponent in range(2, 7):
            if base**exponent == n:
                return {
                    "divisor_class": exponent + 1,
                    "family": "known_basis_prime_power",
                    "certificate": {"base": base, "exponent": exponent},
                }

    for index, left in enumerate(basis):
        for right in basis[index + 1 :]:
            if left * right == n:
                return {
                    "divisor_class": 4,
                    "family": "known_basis_semiprime",
                    "certificate": {"left": left, "right": right},
                }
    return None


def first_carrier(
    anchor_p: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any] | None:
    """Return first composite with a certified divisor class."""
    for offset in range(1, candidate_bound + 1):
        n = anchor_p + offset
        certificate = certified_divisor_class(n, witness_bound)
        if certificate is None:
            continue
        return {
            "carrier_w": n,
            "carrier_offset": offset,
            "carrier_d": certificate["divisor_class"],
            "carrier_d_status": "certified_positive_structure",
            "carrier_certificate": certificate["certificate"],
            "carrier_family": certificate["family"],
        }
    return None


def first_lower_divisor_threat_after(
    anchor_p: int,
    carrier_offset: int,
    carrier_d: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any] | None:
    """Return first later certified lower-divisor threat after the carrier."""
    for offset in range(carrier_offset + 1, candidate_bound + 1):
        n = anchor_p + offset
        certificate = certified_divisor_class(n, witness_bound)
        if certificate is None:
            continue
        if int(certificate["divisor_class"]) >= carrier_d:
            continue
        return {
            "threat_T": offset,
            "threat_n": n,
            "threat_d": certificate["divisor_class"],
            "threat_type": "certified_lower_divisor_pressure",
            "threat_family": certificate["family"],
            "threat_certificate": certificate["certificate"],
        }
    return None


def pressure_ceiling(anchor_p: int, candidate_bound: int, witness_bound: int) -> dict[str, Any]:
    """Return candidate right-boundary pressure ceiling, if one is found."""
    carrier = first_carrier(anchor_p, candidate_bound, witness_bound)
    if carrier is None:
        return {
            "ceiling_status": "NO_LEGAL_CARRIER",
            "carrier_w": None,
            "carrier_offset": None,
            "carrier_d": None,
            "carrier_d_status": "not_available",
            "carrier_family": None,
            "threat_T": None,
            "threat_type": None,
        }
    threat = first_lower_divisor_threat_after(
        anchor_p,
        int(carrier["carrier_offset"]),
        int(carrier["carrier_d"]),
        candidate_bound,
        witness_bound,
    )
    if threat is None:
        return {
            **carrier,
            "ceiling_status": "NO_LEGAL_THREAT",
            "threat_T": None,
            "threat_type": None,
        }
    return {
        **carrier,
        **threat,
        "ceiling_status": CEILING_STATUS_CANDIDATE,
    }


def status_counts_below_ceiling(row: dict[str, Any], threat_T: int | None) -> dict[str, Any]:
    """Return candidate status counts below a ceiling offset."""
    offsets_before = list(row["candidate_offsets"])
    if threat_T is None:
        offsets_after = offsets_before
    else:
        offsets_after = [offset for offset in offsets_before if int(offset) < threat_T]

    records_by_offset = {
        int(record["offset"]): record for record in row["candidate_status_records"]
    }
    survivors: list[int] = []
    unresolved: list[int] = []
    rejected: list[int] = []
    for offset in offsets_after:
        status = records_by_offset[int(offset)]["status"]
        if status == CANDIDATE_STATUS_RESOLVED_SURVIVOR:
            survivors.append(int(offset))
        elif status == CANDIDATE_STATUS_UNRESOLVED:
            unresolved.append(int(offset))
        elif status == CANDIDATE_STATUS_REJECTED:
            rejected.append(int(offset))

    unique_survivor = survivors[0] if len(survivors) == 1 and not unresolved else None
    return {
        "candidate_count_before_ceiling": len(offsets_before),
        "candidate_count_after_ceiling": len(offsets_after),
        "survivor_count": len(survivors),
        "unresolved_count": len(unresolved),
        "rejected_count": len(rejected),
        "survivors": survivors,
        "unresolved": unresolved,
        "unique_survivor": unique_survivor,
    }


def ceiling_record(row: dict[str, Any], candidate_bound: int, witness_bound: int) -> dict[str, Any]:
    """Return one pressure-ceiling probe row."""
    anchor_p = int(row["anchor_p"])
    actual = int(row["actual_boundary_offset_label"])
    ceiling = pressure_ceiling(anchor_p, candidate_bound, witness_bound)
    threat_T = ceiling["threat_T"]
    counts = status_counts_below_ceiling(row, threat_T)
    true_before_T = threat_T is not None and actual < int(threat_T)
    ceiling_rejects_true_boundary = threat_T is not None and actual >= int(threat_T)
    unique = counts["unique_survivor"]
    if ceiling["ceiling_status"] != CEILING_STATUS_CANDIDATE:
        failure_reason = ceiling["ceiling_status"]
    elif ceiling_rejects_true_boundary:
        failure_reason = "TRUE_BOUNDARY_NOT_BEFORE_CEILING"
    elif unique is None:
        failure_reason = "NO_UNIQUE_BOUNDARY_BEFORE_CEILING"
    elif unique != actual:
        failure_reason = "UNIQUE_SURVIVOR_LABEL_MISMATCH"
    else:
        failure_reason = None

    return {
        "anchor_p": anchor_p,
        **ceiling,
        **counts,
        "actual_boundary_label_after_audit": actual,
        "true_boundary_before_T": true_before_T,
        "true_boundary_rejected_count": 1 if ceiling_rejects_true_boundary else 0,
        "ceiling_rejects_true_boundary": ceiling_rejects_true_boundary,
        "unique_survivor_matches_label": unique == actual if unique is not None else False,
        "failure_reason": failure_reason,
    }


def run_probe(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run right-boundary pressure ceiling probe."""
    started = time.perf_counter()
    rows, exclusion_summary = run_probe_exclusion(
        start_anchor,
        max_anchor,
        candidate_bound,
        witness_bound,
    )
    records = [
        ceiling_record(row, candidate_bound, witness_bound)
        for row in rows
    ]
    ceiling_records = [
        record
        for record in records
        if record["ceiling_status"] == CEILING_STATUS_CANDIDATE
    ]
    unique_records = [
        record for record in ceiling_records if record["unique_survivor"] is not None
    ]
    unique_matches = [
        record for record in unique_records if record["unique_survivor_matches_label"]
    ]
    safety_violations = [
        record for record in ceiling_records if record["ceiling_rejects_true_boundary"]
    ]
    status_counts = Counter(record["ceiling_status"] for record in records)
    failure_counts = Counter(
        record["failure_reason"] if record["failure_reason"] is not None else "NONE"
        for record in records
    )
    summary = {
        "mode": "offline_right_boundary_pressure_ceiling_probe",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "row_count": len(records),
        "ceiling_status_counts": status_counts,
        "candidate_pressure_ceiling_count": len(ceiling_records),
        "true_boundary_before_T_count": sum(
            1 for record in ceiling_records if record["true_boundary_before_T"]
        ),
        "ceiling_safety_violation_count": len(safety_violations),
        "true_boundary_rejected_count": len(safety_violations),
        "unique_survivor_count": len(unique_records),
        "unique_survivor_match_count": len(unique_matches),
        "unique_survivor_match_rate": (
            0.0 if not unique_records else len(unique_matches) / len(unique_records)
        ),
        "average_candidate_count_before_ceiling": (
            0.0
            if not records
            else statistics_mean(
                record["candidate_count_before_ceiling"] for record in records
            )
        ),
        "average_candidate_count_after_ceiling": (
            0.0
            if not records
            else statistics_mean(
                record["candidate_count_after_ceiling"] for record in records
            )
        ),
        "average_survivor_count_after_ceiling": (
            0.0
            if not records
            else statistics_mean(record["survivor_count"] for record in records)
        ),
        "failure_reason_counts": failure_counts,
        "first_failure_examples": [
            record for record in records if record["failure_reason"] is not None
        ][:5],
        "exclusion_summary": {
            "true_boundary_rejected_count": exclusion_summary[
                "true_boundary_rejected_count"
            ],
            "true_boundary_status_counts": exclusion_summary[
                "true_boundary_status_counts"
            ],
            "unique_resolved_survivor_count": exclusion_summary[
                "unique_resolved_survivor_count"
            ],
        },
        "boundary_law_005_status": "not_approved",
        "runtime_seconds": time.perf_counter() - started,
    }
    return records, summary


def run_probe_exclusion(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the integrated composite-exclusion probe used as input."""
    return run_exclusion_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
    )


def statistics_mean(values: Any) -> float:
    """Return an arithmetic mean without importing a larger statistics surface."""
    items = [float(value) for value in values]
    if not items:
        return 0.0
    return sum(items) / len(items)


def write_artifacts(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL rows and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = output_dir / ROWS_FILENAME
    with rows_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(jsonable(record), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"rows_path": rows_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run the right-boundary pressure ceiling probe and write artifacts."""
    args = build_parser().parse_args(argv)
    records, summary = run_probe(
        start_anchor=args.start_anchor,
        max_anchor=args.max_anchor,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(records, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

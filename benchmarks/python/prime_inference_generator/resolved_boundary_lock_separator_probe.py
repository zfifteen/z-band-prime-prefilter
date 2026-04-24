#!/usr/bin/env python3
"""Forensics for resolved-boundary lock separators.

This probe compares true resolved boundaries against false resolved survivors.
It is offline theorem discovery only: labels are used after the strongest safe
eliminator has produced candidate records.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

try:
    from .composite_exclusion_boundary_probe import run_probe
    from .resolved_boundary_absorption_safety_probe import (
        LOCK_PREDICATE,
        candidate_carrier,
        interval_pressure,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import run_probe
    from resolved_boundary_absorption_safety_probe import (
        LOCK_PREDICATE,
        candidate_carrier,
        interval_pressure,
    )


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "resolved_boundary_lock_separator_probe_summary.json"
RECORDS_FILENAME = "resolved_boundary_lock_separator_probe_records.jsonl"
LOCK_PREDICATES = (
    "carrier_preservation_no_reset_lock",
    "no_reset_lock",
    "carrier_shared_lock",
    "extension_changes_carrier_lock",
    "reset_evidence_lock",
    "higher_divisor_pressure_lock",
    "no_higher_divisor_pressure_lock",
    "zero_closure_support_lock",
    "positive_closure_support_lock",
    "previous_gap_exact_match_lock",
    "previous_gap_bucket_match_lock",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the lock separator probe CLI."""
    parser = argparse.ArgumentParser(
        description="Offline resolved-boundary lock separator probe.",
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
        help="Largest candidate boundary offset.",
    )
    parser.add_argument(
        "--witness-bound",
        type=int,
        default=97,
        help="Largest positive witness factor.",
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
        return {
            str(key): int(count)
            for key, count in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


def gap_width_class(width: int | None) -> str | None:
    """Return a compact width class."""
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


def candidate_record_by_offset(row: dict[str, Any], offset: int) -> dict[str, Any]:
    """Return the candidate record for one offset."""
    for record in row["candidate_status_records"]:
        if int(record["offset"]) == offset:
            return record
    raise ValueError(f"candidate offset {offset} not present for anchor {row['anchor_p']}")


def carrier_identity(carrier: dict[str, Any]) -> tuple[Any, ...]:
    """Return the comparable identity for one carrier."""
    return (
        carrier["carrier_offset"],
        carrier["carrier_d"],
        carrier["carrier_family"],
    )


def relation_to_true(candidate_offset: int, actual_offset: int) -> str:
    """Return candidate relation to the audited boundary label."""
    if candidate_offset < actual_offset:
        return "before_true"
    if candidate_offset > actual_offset:
        return "after_true"
    return "at_true"


def previous_gap_for_row(
    row: dict[str, Any],
    previous_row: dict[str, Any] | None,
) -> int | None:
    """Return the previous gap width from the measured anchor sequence."""
    if previous_row is None:
        return None
    return int(row["anchor_p"]) - int(previous_row["anchor_p"])


def pressure_union(
    anchor_p: int,
    start_offset: int,
    end_offsets: list[int],
    carrier_d: int | None,
    witness_bound: int,
) -> dict[str, list[int]]:
    """Return legal pressure evidence from start to each later offset."""
    reset_offsets: set[int] = set()
    higher_offsets: set[int] = set()
    square_offsets: set[int] = set()
    semiprime_offsets: set[int] = set()
    for end_offset in end_offsets:
        if end_offset <= start_offset:
            continue
        pressure = interval_pressure(
            anchor_p,
            start_offset,
            end_offset,
            carrier_d,
            witness_bound,
        )
        reset_offsets.update(int(offset) for offset in pressure["reset_evidence_offsets"])
        higher_offsets.update(
            int(offset) for offset in pressure["higher_divisor_pressure_offsets"]
        )
        square_offsets.update(int(offset) for offset in pressure["square_pressure_offsets"])
        semiprime_offsets.update(
            int(offset) for offset in pressure["semiprime_pressure_offsets"]
        )

    return {
        "reset_offsets": sorted(reset_offsets),
        "higher_divisor_offsets": sorted(higher_offsets),
        "square_offsets": sorted(square_offsets),
        "semiprime_offsets": sorted(semiprime_offsets),
    }


def closure_counts(candidate_record: dict[str, Any]) -> dict[str, int | bool]:
    """Return closure support counts for one resolved candidate."""
    reasons = list(candidate_record.get("closure_reasons", []))
    positive_witness_count = sum(
        1
        for reason in reasons
        if str(reason).startswith("SINGLE_HOLE_POSITIVE_WITNESS_FACTOR")
    )
    power_count = sum(
        1 for reason in reasons if str(reason).startswith("POWER_CLOSURE")
    )
    return {
        "single_hole_closure_used": bool(
            candidate_record.get("single_hole_positive_witness_closure")
        ),
        "closure_support_count": len(reasons),
        "positive_witness_closure_count": positive_witness_count,
        "power_closure_count": power_count,
    }


def resolved_record(
    row: dict[str, Any],
    previous_row: dict[str, Any] | None,
    resolved_offset: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Return one resolved-boundary lock separator record."""
    anchor_p = int(row["anchor_p"])
    actual = int(row["actual_boundary_offset_label"])
    unresolved_offsets = [int(offset) for offset in row["unresolved"]]
    later_unresolved = [
        offset for offset in unresolved_offsets if offset > resolved_offset
    ]
    candidate_record = candidate_record_by_offset(row, resolved_offset)
    carrier = candidate_carrier(anchor_p, resolved_offset, witness_bound)
    true_carrier = candidate_carrier(anchor_p, actual, witness_bound)
    later_carriers = [
        candidate_carrier(anchor_p, offset, witness_bound)
        for offset in later_unresolved
    ]
    carrier_id = carrier_identity(carrier)
    later_carrier_ids = [carrier_identity(item) for item in later_carriers]
    extension_preserves_carrier = (
        bool(later_carrier_ids)
        and all(item == carrier_id for item in later_carrier_ids)
    )
    extension_changes_carrier = any(item != carrier_id for item in later_carrier_ids)
    pressure_to_later = pressure_union(
        anchor_p,
        resolved_offset,
        later_unresolved,
        carrier["carrier_d"],
        witness_bound,
    )
    pressure_to_true = pressure_union(
        anchor_p,
        resolved_offset,
        [actual],
        carrier["carrier_d"],
        witness_bound,
    )
    previous_gap = previous_gap_for_row(row, previous_row)
    absorbs_all = bool(later_unresolved)
    would_eliminate_true = resolved_offset != actual and actual in later_unresolved
    return {
        "anchor_p": anchor_p,
        "resolved_candidate_offset": resolved_offset,
        "resolved_candidate_is_true_label": resolved_offset == actual,
        "actual_boundary_offset_label": actual,
        "candidate_relation_to_true": relation_to_true(resolved_offset, actual),
        "later_unresolved_candidate_count": len(later_unresolved),
        "absorbs_all_later_unresolved_bool": absorbs_all,
        "would_rule_a_eliminate_true_boundary_candidate": would_eliminate_true,
        "carrier_offset": carrier["carrier_offset"],
        "carrier_divisor_count": carrier["carrier_d"],
        "carrier_family": carrier["carrier_family"],
        "carrier_same_as_true_candidate": (
            carrier_identity(carrier) == carrier_identity(true_carrier)
        ),
        "carrier_changes_when_extended_to_true_boundary": (
            carrier_identity(carrier) != carrier_identity(true_carrier)
        ),
        "carrier_changes_when_extended_to_next_unresolved": extension_changes_carrier,
        "extension_preserves_carrier": extension_preserves_carrier,
        "extension_changes_carrier": extension_changes_carrier,
        "reset_evidence_between_candidate_and_true_boundary": (
            pressure_to_true["reset_offsets"]
        ),
        "reset_evidence_between_candidate_and_later_unresolved": (
            pressure_to_later["reset_offsets"]
        ),
        "higher_divisor_pressure_between_candidate_and_true": (
            pressure_to_true["higher_divisor_offsets"]
        ),
        "higher_divisor_pressure_between_candidate_and_later_unresolved": (
            pressure_to_later["higher_divisor_offsets"]
        ),
        "square_pressure_between_candidate_and_true": pressure_to_true[
            "square_offsets"
        ],
        "square_pressure_between_candidate_and_later_unresolved": pressure_to_later[
            "square_offsets"
        ],
        "semiprime_pressure_between_candidate_and_true": pressure_to_true[
            "semiprime_offsets"
        ],
        "semiprime_pressure_between_candidate_and_later_unresolved": (
            pressure_to_later["semiprime_offsets"]
        ),
        **closure_counts(candidate_record),
        "previous_chamber_pressure": {
            "previous_anchor_p": (
                None if previous_row is None else int(previous_row["anchor_p"])
            ),
            "previous_gap_width": previous_gap,
            "previous_gap_width_class": gap_width_class(previous_gap),
        },
        "previous_gap_width_class": gap_width_class(previous_gap),
    }


def lock_predicate_selected(
    predicate_name: str,
    record: dict[str, Any],
) -> bool:
    """Return whether a candidate lock predicate selects this record."""
    absorbs = bool(record["absorbs_all_later_unresolved_bool"])
    if not absorbs:
        return False
    if predicate_name == "carrier_preservation_no_reset_lock":
        return (
            bool(record["extension_preserves_carrier"])
            and not bool(record["reset_evidence_between_candidate_and_later_unresolved"])
        )
    if predicate_name == "no_reset_lock":
        return not bool(record["reset_evidence_between_candidate_and_later_unresolved"])
    if predicate_name == "carrier_shared_lock":
        return bool(record["extension_preserves_carrier"])
    if predicate_name == "extension_changes_carrier_lock":
        return bool(record["extension_changes_carrier"])
    if predicate_name == "reset_evidence_lock":
        return bool(record["reset_evidence_between_candidate_and_later_unresolved"])
    if predicate_name == "higher_divisor_pressure_lock":
        return bool(
            record["higher_divisor_pressure_between_candidate_and_later_unresolved"]
        )
    if predicate_name == "no_higher_divisor_pressure_lock":
        return not bool(
            record["higher_divisor_pressure_between_candidate_and_later_unresolved"]
        )
    if predicate_name == "zero_closure_support_lock":
        return int(record["closure_support_count"]) == 0
    if predicate_name == "positive_closure_support_lock":
        return int(record["closure_support_count"]) > 0
    if predicate_name == "previous_gap_exact_match_lock":
        previous_gap = record["previous_chamber_pressure"]["previous_gap_width"]
        return previous_gap is not None and int(previous_gap) == int(
            record["resolved_candidate_offset"]
        )
    if predicate_name == "previous_gap_bucket_match_lock":
        return record["previous_gap_width_class"] == gap_width_class(
            int(record["resolved_candidate_offset"])
        )
    raise ValueError(f"unknown lock predicate: {predicate_name}")


def lock_report(
    records: list[dict[str, Any]],
    predicate_name: str,
) -> dict[str, Any]:
    """Return post-label safety metrics for one lock predicate."""
    selected_records = [
        record for record in records if lock_predicate_selected(predicate_name, record)
    ]
    true_locked = [
        record
        for record in selected_records
        if bool(record["resolved_candidate_is_true_label"])
    ]
    false_locked = [
        record
        for record in selected_records
        if not bool(record["resolved_candidate_is_true_label"])
    ]
    first_false_examples = [
        {
            "anchor_p": record["anchor_p"],
            "resolved_candidate_offset": record["resolved_candidate_offset"],
            "actual_boundary_offset_label": record["actual_boundary_offset_label"],
            "candidate_relation_to_true": record["candidate_relation_to_true"],
        }
        for record in false_locked[:5]
    ]
    return {
        "predicate_name": predicate_name,
        "eligible_for_pure_generation": True,
        "resolved_candidate_count": len(records),
        "locked_count": len(selected_records),
        "true_locked_count": len(true_locked),
        "false_locked_count": len(false_locked),
        "selection_made_count": len(selected_records),
        "selection_wrong_count": len(false_locked),
        "selection_abstain_count": len(records) - len(selected_records),
        "passes_zero_wrong_gate": len(false_locked) == 0 and len(true_locked) > 0,
        "first_false_examples": first_false_examples,
    }


def candidate_lock_separator_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Return coarse candidate feature counts by true/false label."""
    counts: Counter[str] = Counter()
    for record in records:
        prefix = "true" if bool(record["resolved_candidate_is_true_label"]) else "false"
        relation = str(record["candidate_relation_to_true"])
        counts[f"{prefix}_{relation}"] += 1
        if bool(record["extension_preserves_carrier"]):
            counts[f"{prefix}_extension_preserves_carrier"] += 1
        if bool(record["extension_changes_carrier"]):
            counts[f"{prefix}_extension_changes_carrier"] += 1
        if bool(record["reset_evidence_between_candidate_and_later_unresolved"]):
            counts[f"{prefix}_reset_evidence_to_later"] += 1
        if bool(record["higher_divisor_pressure_between_candidate_and_later_unresolved"]):
            counts[f"{prefix}_higher_divisor_pressure_to_later"] += 1
        if int(record["closure_support_count"]) == 0:
            counts[f"{prefix}_zero_closure_support"] += 1
        if int(record["closure_support_count"]) > 0:
            counts[f"{prefix}_positive_closure_support"] += 1
    return dict(sorted(counts.items()))


def run_forensics(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run resolved-boundary lock separator forensics."""
    started = time.perf_counter()
    rows, probe_summary = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate=LOCK_PREDICATE,
    )
    records: list[dict[str, Any]] = []
    previous_row: dict[str, Any] | None = None
    for row in rows:
        for resolved_offset in row["survivors"]:
            records.append(
                resolved_record(row, previous_row, int(resolved_offset), witness_bound)
            )
        previous_row = row

    reports = [lock_report(records, name) for name in LOCK_PREDICATES]
    zero_wrong = [
        report["predicate_name"]
        for report in reports
        if bool(report["passes_zero_wrong_gate"])
    ]
    true_count = sum(
        1 for record in records if bool(record["resolved_candidate_is_true_label"])
    )
    false_count = len(records) - true_count
    summary = {
        "mode": "offline_resolved_boundary_lock_separator_probe",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "single_hole_positive_witness_closure_enabled": True,
        "carrier_locked_pressure_ceiling_enabled": True,
        "carrier_lock_predicate": LOCK_PREDICATE,
        "row_count": probe_summary["row_count"],
        "resolved_candidate_count": len(records),
        "true_resolved_candidate_count": true_count,
        "false_resolved_candidate_count": false_count,
        "candidate_lock_separator_counts": candidate_lock_separator_counts(records),
        "lock_predicate_reports": reports,
        "zero_wrong_lock_candidates": zero_wrong,
        "boundary_law_005_status": "not_approved",
        "prime_emission_status": "forbidden",
        "true_boundary_rejected_count": probe_summary[
            "true_boundary_rejected_count"
        ],
        "runtime_seconds": time.perf_counter() - started,
    }
    return records, summary


def write_artifacts(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL records and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / RECORDS_FILENAME
    with records_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(jsonable(record), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"records_path": records_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run the lock separator probe and write artifacts."""
    args = build_parser().parse_args(argv)
    records, summary = run_forensics(
        start_anchor=args.start_anchor,
        max_anchor=args.max_anchor,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(records, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Offline probe for previous-chamber reset lock candidates."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .composite_exclusion_boundary_probe import run_probe
    from .higher_divisor_pressure_lock_activation_profile import first_open_offset
    from .higher_divisor_pressure_lock_hardening import has_higher_divisor_pressure
    from .lock_near_miss_profile import (
        parse_surface,
        pressure_offsets,
        previous_chamber_signal,
    )
    from .resolved_boundary_absorption_safety_probe import (
        candidate_carrier,
        carrier_identity,
    )
    from .resolved_boundary_lock_separator_probe import gap_width_class, jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import run_probe
    from higher_divisor_pressure_lock_activation_profile import first_open_offset
    from higher_divisor_pressure_lock_hardening import has_higher_divisor_pressure
    from lock_near_miss_profile import (
        parse_surface,
        pressure_offsets,
        previous_chamber_signal,
    )
    from resolved_boundary_absorption_safety_probe import (
        candidate_carrier,
        carrier_identity,
    )
    from resolved_boundary_lock_separator_probe import gap_width_class, jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "previous_chamber_reset_lock_summary.json"
RECORDS_FILENAME = "previous_chamber_reset_lock_records.jsonl"
DEFAULT_SURFACES = ("11..1000000", "100000..200000", "1000000..1100000")
LOCK_PREDICATES = (
    "previous_gap_width_class_lock",
    "previous_carrier_family_lock",
    "previous_first_open_transition_lock",
    "previous_to_current_carrier_shift_lock",
    "previous_square_pressure_reset_lock",
    "previous_higher_divisor_reset_lock",
    "previous_chamber_signature_lock",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the previous-chamber lock probe CLI."""
    parser = argparse.ArgumentParser(
        description="Offline previous-chamber reset lock probe.",
    )
    parser.add_argument(
        "--surfaces",
        nargs="+",
        default=list(DEFAULT_SURFACES),
        help="Inclusive anchor surfaces formatted as START..MAX.",
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


def previous_pressure(
    previous_left_prime: int,
    previous_gap_width: int,
    previous_carrier: dict[str, Any],
    witness_bound: int,
) -> dict[str, list[int]]:
    """Return previous-chamber pressure after its carrier."""
    carrier_offset = previous_carrier["carrier_offset"]
    if carrier_offset is None:
        return {
            "higher_divisor_pressure_offsets": [],
            "reset_evidence_offsets": [],
            "square_pressure_offsets": [],
            "semiprime_pressure_offsets": [],
        }
    return pressure_offsets(
        previous_left_prime,
        int(carrier_offset),
        previous_gap_width,
        previous_carrier["carrier_d"],
        witness_bound,
    )


def transition_signature(
    previous_gap_width: int,
    previous_carrier: dict[str, Any],
    previous_first_open: int | None,
    current_carrier: dict[str, Any],
    current_first_open: int | None,
    resolved_candidate_offset: int,
) -> str:
    """Return a compact previous-to-current transition signature."""
    return "|".join(
        [
            f"PG:{gap_width_class(previous_gap_width)}",
            f"PCF:{previous_carrier['carrier_family']}",
            f"PCD:{previous_carrier['carrier_d']}",
            f"PFO:{previous_first_open}",
            f"CCF:{current_carrier['carrier_family']}",
            f"CCD:{current_carrier['carrier_d']}",
            f"CFO:{current_first_open}",
            f"CO:{gap_width_class(resolved_candidate_offset)}",
        ]
    )


def reset_signature(
    previous_pressure_record: dict[str, list[int]],
    previous_carrier: dict[str, Any],
    current_carrier: dict[str, Any],
) -> str:
    """Return a compact reset-lock signature."""
    carrier_shift = carrier_identity(previous_carrier) != carrier_identity(current_carrier)
    return "|".join(
        [
            f"H:{int(bool(previous_pressure_record['higher_divisor_pressure_offsets']))}",
            f"S:{int(bool(previous_pressure_record['square_pressure_offsets']))}",
            f"SP:{int(bool(previous_pressure_record['semiprime_pressure_offsets']))}",
            f"R:{int(bool(previous_pressure_record['reset_evidence_offsets']))}",
            f"SHIFT:{int(carrier_shift)}",
        ]
    )


def target_row(
    row: dict[str, Any],
    previous_row: dict[str, Any] | None,
    witness_bound: int,
) -> bool:
    """Return whether a row belongs to the near-miss target population."""
    if previous_row is None:
        return False
    anchor_p = int(row["anchor_p"])
    previous_gap_width = anchor_p - int(previous_row["anchor_p"])
    if not previous_chamber_signal(previous_gap_width):
        return False
    actual = int(row["actual_boundary_offset_label"])
    survivors = [int(offset) for offset in row["survivors"]]
    unresolved = [int(offset) for offset in row["unresolved"]]
    if actual not in survivors:
        return False
    later_unresolved = [offset for offset in unresolved if offset > actual]
    if not later_unresolved:
        return False
    return not has_higher_divisor_pressure(
        anchor_p,
        actual,
        later_unresolved,
        witness_bound,
    )


def candidate_record(
    row: dict[str, Any],
    previous_row: dict[str, Any],
    resolved_candidate_offset: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Return one previous-chamber reset lock candidate record."""
    anchor_p = int(row["anchor_p"])
    previous_left_prime = int(previous_row["anchor_p"])
    previous_right_prime = anchor_p
    previous_gap_width = previous_right_prime - previous_left_prime
    actual = int(row["actual_boundary_offset_label"])
    unresolved = [int(offset) for offset in row["unresolved"]]
    later_unresolved = [
        offset for offset in unresolved if offset > resolved_candidate_offset
    ]
    previous_carrier = candidate_carrier(
        previous_left_prime,
        previous_gap_width,
        witness_bound,
    )
    previous_pressure_record = previous_pressure(
        previous_left_prime,
        previous_gap_width,
        previous_carrier,
        witness_bound,
    )
    current_carrier = candidate_carrier(
        anchor_p,
        resolved_candidate_offset,
        witness_bound,
    )
    previous_first_open = first_open_offset(previous_left_prime)
    current_first_open = first_open_offset(anchor_p)
    return {
        "anchor_p": anchor_p,
        "previous_left_prime": previous_left_prime,
        "previous_right_prime": previous_right_prime,
        "previous_gap_width": previous_gap_width,
        "previous_gap_width_class": gap_width_class(previous_gap_width),
        "previous_gwr_carrier_offset": previous_carrier["carrier_offset"],
        "previous_gwr_carrier_d": previous_carrier["carrier_d"],
        "previous_gwr_carrier_family": previous_carrier["carrier_family"],
        "previous_first_open_offset": previous_first_open,
        "previous_square_pressure": previous_pressure_record[
            "square_pressure_offsets"
        ],
        "previous_higher_divisor_pressure": previous_pressure_record[
            "higher_divisor_pressure_offsets"
        ],
        "previous_semiprime_state": (
            "HAS_SEMIPRIME_PRESSURE"
            if previous_pressure_record["semiprime_pressure_offsets"]
            else "NO_SEMIPRIME_PRESSURE"
        ),
        "previous_semiprime_pressure": previous_pressure_record[
            "semiprime_pressure_offsets"
        ],
        "resolved_candidate_offset": resolved_candidate_offset,
        "resolved_candidate_is_true_label": resolved_candidate_offset == actual,
        "actual_boundary_offset_label": actual,
        "later_unresolved_count": len(later_unresolved),
        "absorbs_all_later_unresolved_bool": bool(later_unresolved),
        "current_carrier_offset": current_carrier["carrier_offset"],
        "current_carrier_d": current_carrier["carrier_d"],
        "current_carrier_family": current_carrier["carrier_family"],
        "current_first_open_offset": current_first_open,
        "previous_to_current_transition_signature": transition_signature(
            previous_gap_width,
            previous_carrier,
            previous_first_open,
            current_carrier,
            current_first_open,
            resolved_candidate_offset,
        ),
        "reset_lock_signature": reset_signature(
            previous_pressure_record,
            previous_carrier,
            current_carrier,
        ),
    }


def lock_selected(predicate_name: str, record: dict[str, Any]) -> bool:
    """Return whether one predicate selects a resolved candidate."""
    if not bool(record["absorbs_all_later_unresolved_bool"]):
        return False
    previous_class = record["previous_gap_width_class"]
    current_class = gap_width_class(int(record["resolved_candidate_offset"]))
    previous_family = record["previous_gwr_carrier_family"]
    current_family = record["current_carrier_family"]
    previous_carrier = (
        record["previous_gwr_carrier_offset"],
        record["previous_gwr_carrier_d"],
        previous_family,
    )
    current_carrier = (
        record["current_carrier_offset"],
        record["current_carrier_d"],
        current_family,
    )
    if predicate_name == "previous_gap_width_class_lock":
        return previous_class == current_class
    if predicate_name == "previous_carrier_family_lock":
        return previous_family is not None and previous_family == current_family
    if predicate_name == "previous_first_open_transition_lock":
        return (
            record["previous_first_open_offset"]
            == record["current_first_open_offset"]
        )
    if predicate_name == "previous_to_current_carrier_shift_lock":
        return (
            previous_family is not None
            and current_family is not None
            and previous_carrier != current_carrier
        )
    if predicate_name == "previous_square_pressure_reset_lock":
        return bool(record["previous_square_pressure"])
    if predicate_name == "previous_higher_divisor_reset_lock":
        return bool(record["previous_higher_divisor_pressure"])
    if predicate_name == "previous_chamber_signature_lock":
        return (
            previous_class == current_class
            and previous_family is not None
            and previous_family == current_family
            and record["previous_first_open_offset"]
            == record["current_first_open_offset"]
        )
    raise ValueError(f"unknown predicate: {predicate_name}")


def predicate_report(
    records: list[dict[str, Any]],
    predicate_name: str,
) -> dict[str, Any]:
    """Return zero-wrong metrics for one previous-chamber predicate."""
    selected = [
        record for record in records if lock_selected(predicate_name, record)
    ]
    true_selected = [
        record for record in selected if bool(record["resolved_candidate_is_true_label"])
    ]
    false_selected = [
        record for record in selected if not bool(record["resolved_candidate_is_true_label"])
    ]
    selected_total = len(selected)
    return {
        "predicate_name": predicate_name,
        "eligible_for_pure_generation": True,
        "lock_true_selected": len(true_selected),
        "lock_false_selected": len(false_selected),
        "lock_wrong_count": len(false_selected),
        "lock_abstain_count": len(records) - selected_total,
        "selection_accuracy_when_made": (
            0.0 if selected_total == 0 else len(true_selected) / selected_total
        ),
        "passes_zero_wrong_gate": (
            len(false_selected) == 0 and len(true_selected) > 0
        ),
        "first_false_examples": [
            {
                "anchor_p": record["anchor_p"],
                "resolved_candidate_offset": record["resolved_candidate_offset"],
                "actual_boundary_offset_label": record[
                    "actual_boundary_offset_label"
                ],
                "previous_to_current_transition_signature": record[
                    "previous_to_current_transition_signature"
                ],
                "reset_lock_signature": record["reset_lock_signature"],
            }
            for record in false_selected[:5]
        ],
    }


def surface_records(
    surface: str,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return candidate records for one surface."""
    start_anchor, max_anchor = parse_surface(surface)
    rows, _ = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
        enable_higher_divisor_pressure_locked_absorption=False,
    )
    records: list[dict[str, Any]] = []
    target_row_count = 0
    previous_row: dict[str, Any] | None = None
    for row in rows:
        if previous_row is not None and target_row(row, previous_row, witness_bound):
            target_row_count += 1
            for resolved_offset in row["survivors"]:
                records.append(
                    candidate_record(
                        row,
                        previous_row,
                        int(resolved_offset),
                        witness_bound,
                    )
                )
        previous_row = row
    return records, {
        "surface": surface,
        "row_count": len(rows),
        "target_row_count": target_row_count,
        "candidate_count": len(records),
    }


def best_report(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the best zero-wrong report, or the least-wrong report."""
    zero_wrong = [
        report for report in reports if bool(report["passes_zero_wrong_gate"])
    ]
    if zero_wrong:
        return max(zero_wrong, key=lambda report: int(report["lock_true_selected"]))
    return min(
        reports,
        key=lambda report: (
            int(report["lock_wrong_count"]),
            -int(report["lock_true_selected"]),
            str(report["predicate_name"]),
        ),
    )


def count_by(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Return sorted string-keyed counts for one field."""
    counts = Counter(str(record[field]) for record in records)
    return {
        key: value
        for key, value in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }


def run_probe_matrix(
    surfaces: list[str],
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the previous-chamber reset lock probe."""
    started = time.perf_counter()
    all_records: list[dict[str, Any]] = []
    surface_summaries: list[dict[str, Any]] = []
    for surface in surfaces:
        records, summary = surface_records(surface, candidate_bound, witness_bound)
        all_records.extend(records)
        surface_summaries.append(summary)

    reports = [
        predicate_report(all_records, predicate_name)
        for predicate_name in LOCK_PREDICATES
    ]
    selected_report = best_report(reports)
    true_candidate_count = sum(
        1 for record in all_records if bool(record["resolved_candidate_is_true_label"])
    )
    false_candidate_count = len(all_records) - true_candidate_count
    summary = {
        "mode": "offline_previous_chamber_reset_lock_probe",
        "surfaces": surfaces,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "candidate_count": len(all_records),
        "true_candidate_count": true_candidate_count,
        "false_candidate_count": false_candidate_count,
        "previous_chamber_signal_count": len(all_records),
        "predicate_reports": reports,
        "zero_wrong_lock_candidates": [
            report["predicate_name"]
            for report in reports
            if bool(report["passes_zero_wrong_gate"])
        ],
        "best_lock_candidate": selected_report["predicate_name"],
        "lock_true_selected": selected_report["lock_true_selected"],
        "lock_false_selected": selected_report["lock_false_selected"],
        "lock_wrong_count": selected_report["lock_wrong_count"],
        "lock_abstain_count": selected_report["lock_abstain_count"],
        "selection_accuracy_when_made": selected_report[
            "selection_accuracy_when_made"
        ],
        "transition_signature_counts": count_by(
            all_records,
            "previous_to_current_transition_signature",
        ),
        "reset_lock_signature_counts": count_by(
            all_records,
            "reset_lock_signature",
        ),
        "surface_summaries": surface_summaries,
        "boundary_law_005_status": "candidate_not_approved_for_generation",
        "prime_emission_status": "forbidden",
        "runtime_seconds": time.perf_counter() - started,
    }
    return all_records, summary


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
    return {
        "records_path": records_path,
        "summary_path": summary_path,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the previous-chamber reset lock probe and write artifacts."""
    args = build_parser().parse_args(argv)
    records, summary = run_probe_matrix(
        surfaces=args.surfaces,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(records, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

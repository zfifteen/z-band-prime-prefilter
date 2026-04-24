#!/usr/bin/env python3
"""Autopsy for the Boundary Law 005B integration failure at anchor 3137."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .composite_exclusion_boundary_probe import (
        certified_divisor_class,
        first_legal_carrier,
        higher_divisor_pressure_lock_selected,
        previous_carrier_shift_lock_selected,
        run_probe,
        single_hole_positive_witness,
    )
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        certified_divisor_class,
        first_legal_carrier,
        higher_divisor_pressure_lock_selected,
        previous_carrier_shift_lock_selected,
        run_probe,
        single_hole_positive_witness,
    )
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "boundary_law_005b_failure_autopsy_summary.json"
RECORD_FILENAME = "boundary_law_005b_failure_autopsy_record.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the 005B failure autopsy CLI."""
    parser = argparse.ArgumentParser(
        description="Offline autopsy for the 005B failure at anchor 3137.",
    )
    parser.add_argument(
        "--anchor",
        type=int,
        default=3137,
        help="Anchor prime for the failure autopsy.",
    )
    parser.add_argument(
        "--start-anchor",
        type=int,
        default=11,
        help="Inclusive lower bound used to reconstruct previous-anchor state.",
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
        help="Directory for JSON artifacts.",
    )
    return parser


def row_for_anchor(rows: list[dict[str, Any]], anchor: int) -> dict[str, Any]:
    """Return one row by anchor."""
    for row in rows:
        if int(row["anchor_p"]) == anchor:
            return row
    raise ValueError(f"anchor not found in surface: {anchor}")


def previous_row_for_anchor(
    rows: list[dict[str, Any]],
    anchor: int,
) -> dict[str, Any]:
    """Return the immediately preceding anchor row."""
    for index, row in enumerate(rows):
        if int(row["anchor_p"]) != anchor:
            continue
        if index == 0:
            raise ValueError("failure anchor has no previous row in surface")
        return rows[index - 1]
    raise ValueError(f"anchor not found in surface: {anchor}")


def candidate_record_by_offset(
    row: dict[str, Any],
    offset: int,
) -> dict[str, Any]:
    """Return one candidate record by offset."""
    for record in row["candidate_status_records"]:
        if int(record["offset"]) == offset:
            return record
    raise ValueError(f"candidate offset not found: {offset}")


def pressure_signature(
    anchor_p: int,
    start_offset: int,
    stop_offsets: list[int],
    carrier_d: int | None,
    witness_bound: int,
) -> dict[str, Any]:
    """Return legal pressure evidence after one candidate offset."""
    if not stop_offsets or carrier_d is None:
        return {
            "higher_divisor_pressure_offsets": [],
            "reset_evidence_offsets": [],
            "semiprime_pressure_offsets": [],
            "square_pressure_offsets": [],
            "certified_offsets": [],
        }
    pressure = {
        "higher_divisor_pressure_offsets": [],
        "reset_evidence_offsets": [],
        "semiprime_pressure_offsets": [],
        "square_pressure_offsets": [],
        "certified_offsets": [],
    }
    for offset in range(start_offset + 1, max(stop_offsets)):
        certificate = certified_divisor_class(anchor_p + offset, witness_bound)
        if certificate is None:
            continue
        divisor_class = int(certificate["divisor_class"])
        family = str(certificate["family"])
        pressure["certified_offsets"].append(
            {
                "offset": offset,
                "n": anchor_p + offset,
                "divisor_class": divisor_class,
                "family": family,
                "certificate": certificate["certificate"],
            }
        )
        if divisor_class > int(carrier_d):
            pressure["higher_divisor_pressure_offsets"].append(offset)
        if divisor_class <= int(carrier_d):
            pressure["reset_evidence_offsets"].append(offset)
        if family == "known_basis_semiprime":
            pressure["semiprime_pressure_offsets"].append(offset)
        payload = certificate["certificate"]
        if (
            family == "known_basis_prime_power"
            and int(payload.get("exponent", 0)) == 2
        ):
            pressure["square_pressure_offsets"].append(offset)
    return pressure


def lock_features(
    anchor_p: int,
    previous_anchor_p: int,
    candidate_offset: int,
    later_unresolved_offsets: list[int],
    witness_bound: int,
) -> dict[str, Any]:
    """Return 005A and 005B lock features for one candidate."""
    previous_gap_width = anchor_p - previous_anchor_p
    previous_carrier = first_legal_carrier(
        previous_anchor_p,
        previous_gap_width,
        witness_bound,
    )
    current_carrier = first_legal_carrier(
        anchor_p,
        candidate_offset,
        witness_bound,
    )
    current_carrier_d = current_carrier["carrier_d"]
    return {
        "candidate_offset": candidate_offset,
        "candidate_n": anchor_p + candidate_offset,
        "later_unresolved_offsets": later_unresolved_offsets,
        "previous_anchor_p": previous_anchor_p,
        "previous_gap_width": previous_gap_width,
        "previous_carrier": previous_carrier,
        "current_carrier": current_carrier,
        "carrier_shift_signature": (
            f"previous={previous_carrier['carrier_offset']},"
            f"{previous_carrier['carrier_d']},"
            f"{previous_carrier['carrier_family']}|"
            f"current={current_carrier['carrier_offset']},"
            f"{current_carrier['carrier_d']},"
            f"{current_carrier['carrier_family']}"
        ),
        "005b_previous_carrier_shift_selected": (
            previous_carrier_shift_lock_selected(
                anchor_p,
                previous_anchor_p,
                candidate_offset,
                later_unresolved_offsets,
                witness_bound,
            )
        ),
        "005a_higher_divisor_pressure_selected": (
            higher_divisor_pressure_lock_selected(
                anchor_p,
                candidate_offset,
                later_unresolved_offsets,
                witness_bound,
            )
        ),
        "pressure_signature": pressure_signature(
            anchor_p,
            candidate_offset,
            later_unresolved_offsets,
            None if current_carrier_d is None else int(current_carrier_d),
            witness_bound,
        ),
    }


def base_rows(
    start_anchor: int,
    anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> list[dict[str, Any]]:
    """Return rows before any 005 absorption rule is applied."""
    rows, _ = run_probe(
        start_anchor=start_anchor,
        max_anchor=anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
    )
    return rows


def b_only_rows(
    start_anchor: int,
    anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> list[dict[str, Any]]:
    """Return rows with 005B-only absorption enabled."""
    rows, _ = run_probe(
        start_anchor=start_anchor,
        max_anchor=anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
        enable_previous_carrier_shift_locked_absorption=True,
    )
    return rows


def run_autopsy(
    anchor: int,
    start_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the 005B failure autopsy record and summary."""
    started = time.perf_counter()
    base_surface = base_rows(start_anchor, anchor, candidate_bound, witness_bound)
    integrated_surface = b_only_rows(
        start_anchor,
        anchor,
        candidate_bound,
        witness_bound,
    )
    pre_row = row_for_anchor(base_surface, anchor)
    previous_row = previous_row_for_anchor(base_surface, anchor)
    integrated_row = row_for_anchor(integrated_surface, anchor)

    actual_offset = int(pre_row["actual_boundary_offset_label"])
    false_absorber_offsets = [
        int(offset)
        for offset in integrated_row[
            "previous_carrier_shift_locked_absorption"
        ]["absorber_offsets"]
        if int(offset) != actual_offset
    ]
    if not false_absorber_offsets:
        raise ValueError("005B failure absorber was not reproduced")
    false_absorber_offset = false_absorber_offsets[0]
    pre_unresolved = [int(offset) for offset in pre_row["unresolved"]]
    later_for_false = [
        offset for offset in pre_unresolved if offset > false_absorber_offset
    ]
    later_for_true = [offset for offset in pre_unresolved if offset > actual_offset]
    false_record_pre = candidate_record_by_offset(pre_row, false_absorber_offset)
    true_record_pre = candidate_record_by_offset(pre_row, actual_offset)
    true_record_after = candidate_record_by_offset(integrated_row, actual_offset)
    false_absorber_n = anchor + false_absorber_offset
    actual_boundary_n = anchor + actual_offset
    false_boundary_extended_witness = single_hole_positive_witness(
        false_absorber_n,
        witness_bound,
    )
    actual_boundary_extended_witness = single_hole_positive_witness(
        actual_boundary_n,
        witness_bound,
    )
    absorption_targets = [
        int(offset)
        for offset in integrated_row[
            "previous_carrier_shift_locked_absorption"
        ]["absorbed_offsets"]
    ]
    target_row_conditions = {
        "previous_row_available": True,
        "previous_chamber_signal_present": (
            anchor - int(previous_row["anchor_p"]) <= 16
        ),
        "actual_boundary_resolved_before_absorption": (
            actual_offset in [int(offset) for offset in pre_row["survivors"]]
        ),
        "later_unresolved_after_actual_boundary": bool(later_for_true),
        "higher_divisor_pressure_lock_absent_at_actual_boundary": (
            not higher_divisor_pressure_lock_selected(
                anchor,
                actual_offset,
                later_for_true,
                witness_bound,
            )
        ),
    }
    record = {
        "anchor_p": anchor,
        "false_absorber_offset": false_absorber_offset,
        "false_absorber_n": false_absorber_n,
        "actual_boundary_offset": actual_offset,
        "actual_boundary_n": actual_boundary_n,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "previous_anchor_p": int(previous_row["anchor_p"]),
        "previous_boundary_offset_label": int(
            previous_row["actual_boundary_offset_label"]
        ),
        "resolved_survivor_offsets": [
            int(offset) for offset in pre_row["survivors"]
        ],
        "unresolved_candidate_offsets": pre_unresolved,
        "rejected_candidate_offsets": [int(offset) for offset in pre_row["rejected"]],
        "005B_lock_features_for_false_absorber": lock_features(
            anchor,
            int(previous_row["anchor_p"]),
            false_absorber_offset,
            later_for_false,
            witness_bound,
        ),
        "005B_lock_features_for_true_boundary": lock_features(
            anchor,
            int(previous_row["anchor_p"]),
            actual_offset,
            later_for_true,
            witness_bound,
        ),
        "005A_lock_features_for_false_absorber": {
            "selected": higher_divisor_pressure_lock_selected(
                anchor,
                false_absorber_offset,
                later_for_false,
                witness_bound,
            ),
            "pressure_signature": pressure_signature(
                anchor,
                false_absorber_offset,
                later_for_false,
                int(
                    first_legal_carrier(
                        anchor,
                        false_absorber_offset,
                        witness_bound,
                    )["carrier_d"]
                ),
                witness_bound,
            ),
        },
        "carrier_for_false_absorber": first_legal_carrier(
            anchor,
            false_absorber_offset,
            witness_bound,
        ),
        "carrier_for_true_boundary": first_legal_carrier(
            anchor,
            actual_offset,
            witness_bound,
        ),
        "previous_chamber_features": {
            "previous_anchor_p": int(previous_row["anchor_p"]),
            "previous_boundary_offset_label": int(
                previous_row["actual_boundary_offset_label"]
            ),
            "previous_boundary_n": anchor,
            "previous_gap_width": anchor - int(previous_row["anchor_p"]),
            "previous_carrier": first_legal_carrier(
                int(previous_row["anchor_p"]),
                anchor - int(previous_row["anchor_p"]),
                witness_bound,
            ),
        },
        "carrier_shift_signature": lock_features(
            anchor,
            int(previous_row["anchor_p"]),
            false_absorber_offset,
            later_for_false,
            witness_bound,
        )["carrier_shift_signature"],
        "higher_divisor_pressure_signature": pressure_signature(
            anchor,
            false_absorber_offset,
            later_for_false,
            int(
                first_legal_carrier(
                    anchor,
                    false_absorber_offset,
                    witness_bound,
                )["carrier_d"]
            ),
            witness_bound,
        ),
        "single_hole_closure_usage": {
            "false_absorber_used_single_hole_closure": bool(
                false_record_pre.get("single_hole_positive_witness_closure")
            ),
            "false_absorber_closure_reasons": list(
                false_record_pre.get("closure_reasons", [])
            ),
            "false_absorber_closed_offset": false_record_pre.get(
                "single_hole_closed_offset"
            ),
            "true_boundary_used_single_hole_closure": bool(
                true_record_pre.get("single_hole_positive_witness_closure")
            ),
            "true_boundary_unresolved_interior_offsets": list(
                true_record_pre.get("unresolved_interior_offsets", [])
            ),
        },
        "candidate_boundary_witnesses": {
            "false_absorber_extended_positive_witness": (
                false_boundary_extended_witness
            ),
            "actual_boundary_extended_positive_witness": (
                actual_boundary_extended_witness
            ),
        },
        "absorption_targets_removed_by_false_absorber": absorption_targets,
        "why_true_boundary_was_absorbed_or_rejected": {
            "pre_absorption_status": true_record_pre["status"],
            "post_absorption_status": true_record_after["status"],
            "post_absorption_rule_family": true_record_after["rule_family"],
            "post_absorption_rejection_reasons": list(
                true_record_after["rejection_reasons"]
            ),
            "absorber_offset": true_record_after.get(
                "previous_carrier_shift_locked_absorption_absorber_offset"
            ),
        },
        "what_hardening_probe_missed": {
            "hardening_target_row_conditions": target_row_conditions,
            "missed_reason": (
                "The hardening probe only evaluated previous-chamber lock "
                "candidates in rows where the audited true boundary was already "
                "resolved before absorption. At anchor 3137, the true boundary "
                "offset 26 was unresolved, so the false resolved candidate at "
                "offset 12 was not tested as an absorber that could remove it."
            ),
        },
        "proposed_quarantine_conditions": [
            {
                "condition": "absorber_boundary_has_positive_witness_under_witness_bound",
                "fires_at_anchor_3137": false_boundary_extended_witness is not None,
                "label_free": True,
                "status": "candidate_guard_requires_broad_test",
            },
            {
                "condition": "absorber_depends_on_single_hole_positive_witness_closure",
                "fires_at_anchor_3137": bool(
                    false_record_pre.get("single_hole_positive_witness_closure")
                ),
                "label_free": True,
                "status": "candidate_guard_requires_broad_test",
            },
        ],
    }
    summary = {
        "mode": "offline_boundary_law_005b_failure_autopsy",
        "anchor_p": anchor,
        "false_absorber_offset": false_absorber_offset,
        "actual_boundary_offset": actual_offset,
        "005b_integration_status": "quarantined",
        "boundary_law_005b_status": "forensic_lead_not_absorption_rule",
        "prime_emission_status": "forbidden",
        "failure_reproduced": (
            actual_offset in absorption_targets
            and bool(true_record_after.get("previous_carrier_shift_locked_absorption_rejection"))
        ),
        "candidate_quarantine_condition_count": 2,
        "runtime_seconds": time.perf_counter() - started,
    }
    return record, summary


def write_artifacts(
    record: dict[str, Any],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSON artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    record_path = output_dir / RECORD_FILENAME
    record_path.write_text(
        json.dumps(jsonable(record), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "record_path": record_path,
        "summary_path": summary_path,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the 005B failure autopsy and write artifacts."""
    args = build_parser().parse_args(argv)
    record, summary = run_autopsy(
        anchor=args.anchor,
        start_anchor=args.start_anchor,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(record, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

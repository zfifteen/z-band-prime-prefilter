#!/usr/bin/env python3
"""Audit absorption-lock hardening populations against integration actions."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        higher_divisor_pressure_lock_selected,
        previous_carrier_shift_lock_selected,
        run_probe,
    )
    from .higher_divisor_pressure_lock_activation_profile import parse_surface
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        higher_divisor_pressure_lock_selected,
        previous_carrier_shift_lock_selected,
        run_probe,
    )
    from higher_divisor_pressure_lock_activation_profile import parse_surface
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "absorption_lock_action_population_audit_summary.json"
ROWS_FILENAME = "absorption_lock_action_population_audit_rows.jsonl"
DEFAULT_SURFACES = (
    "11..1000000",
    "100000..200000",
    "1000000..1100000",
)
LOCK_NAMES = (
    "005A_higher_divisor_pressure_lock",
    "005B_previous_to_current_carrier_shift_lock",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the absorption lock action-population audit CLI."""
    parser = argparse.ArgumentParser(
        description="Offline audit of lock hardening populations vs action populations.",
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


def candidate_key(surface: str, anchor_p: int, offset: int) -> str:
    """Return a stable candidate key scoped to one surface."""
    return f"{surface}|{anchor_p}|{offset}"


def later_unresolved_offsets(
    candidate_records: list[dict[str, Any]],
    resolved_offset: int,
) -> list[int]:
    """Return unresolved candidate offsets after a resolved offset."""
    return [
        int(candidate["offset"])
        for candidate in candidate_records
        if candidate["status"] == CANDIDATE_STATUS_UNRESOLVED
        and int(candidate["offset"]) > resolved_offset
    ]


def previous_chamber_signal(previous_anchor_p: int | None, anchor_p: int) -> bool:
    """Return whether the previous chamber lies in the current 005B regime."""
    return previous_anchor_p is not None and anchor_p - previous_anchor_p <= 16


def has_higher_lock_at_true_boundary(
    row: dict[str, Any],
    witness_bound: int,
) -> bool:
    """Return whether 005A already fires at the audited true boundary."""
    actual = int(row["actual_boundary_offset_label"])
    unresolved = [int(offset) for offset in row["unresolved"]]
    later_unresolved = [offset for offset in unresolved if offset > actual]
    return higher_divisor_pressure_lock_selected(
        int(row["anchor_p"]),
        actual,
        later_unresolved,
        witness_bound,
    )


def hardening_population_for_lock(
    lock_name: str,
    surface: str,
    rows: list[dict[str, Any]],
    witness_bound: int,
) -> set[str]:
    """Return candidate keys covered by the prior hardening population."""
    hardening_keys: set[str] = set()
    previous_anchor_p: int | None = None
    for row in rows:
        anchor_p = int(row["anchor_p"])
        actual = int(row["actual_boundary_offset_label"])
        survivors = [int(offset) for offset in row["survivors"]]
        unresolved = [int(offset) for offset in row["unresolved"]]
        if lock_name == "005A_higher_divisor_pressure_lock":
            for offset in survivors:
                hardening_keys.add(candidate_key(surface, anchor_p, offset))
        elif lock_name == "005B_previous_to_current_carrier_shift_lock":
            later_unresolved_after_true = [
                offset for offset in unresolved if offset > actual
            ]
            target_row = (
                previous_chamber_signal(previous_anchor_p, anchor_p)
                and actual in survivors
                and bool(later_unresolved_after_true)
                and not has_higher_lock_at_true_boundary(row, witness_bound)
            )
            if target_row:
                for offset in survivors:
                    hardening_keys.add(candidate_key(surface, anchor_p, offset))
        else:
            raise ValueError(f"unknown lock: {lock_name}")
        previous_anchor_p = anchor_p
    return hardening_keys


def lock_selects(
    lock_name: str,
    anchor_p: int,
    previous_anchor_p: int | None,
    resolved_offset: int,
    later_unresolved: list[int],
    witness_bound: int,
) -> bool:
    """Return whether one lock selects one resolved candidate."""
    if lock_name == "005A_higher_divisor_pressure_lock":
        return higher_divisor_pressure_lock_selected(
            anchor_p,
            resolved_offset,
            later_unresolved,
            witness_bound,
        )
    if lock_name == "005B_previous_to_current_carrier_shift_lock":
        return previous_carrier_shift_lock_selected(
            anchor_p,
            previous_anchor_p,
            resolved_offset,
            later_unresolved,
            witness_bound,
        )
    raise ValueError(f"unknown lock: {lock_name}")


def action_records_for_lock(
    lock_name: str,
    surface: str,
    rows: list[dict[str, Any]],
    witness_bound: int,
) -> list[dict[str, Any]]:
    """Return the candidates one lock actually acts on in integration order."""
    actions: list[dict[str, Any]] = []
    previous_anchor_p: int | None = None
    for row in rows:
        anchor_p = int(row["anchor_p"])
        actual = int(row["actual_boundary_offset_label"])
        candidate_records = [dict(record) for record in row["candidate_status_records"]]
        for record in candidate_records:
            if record["status"] != CANDIDATE_STATUS_RESOLVED_SURVIVOR:
                continue
            resolved_offset = int(record["offset"])
            later_unresolved = later_unresolved_offsets(
                candidate_records,
                resolved_offset,
            )
            if not lock_selects(
                lock_name,
                anchor_p,
                previous_anchor_p,
                resolved_offset,
                later_unresolved,
                witness_bound,
            ):
                continue
            absorbed_offsets: list[int] = []
            for candidate in candidate_records:
                candidate_offset = int(candidate["offset"])
                if candidate["status"] != CANDIDATE_STATUS_UNRESOLVED:
                    continue
                if candidate_offset <= resolved_offset:
                    continue
                candidate["status"] = CANDIDATE_STATUS_REJECTED
                absorbed_offsets.append(candidate_offset)
            if absorbed_offsets:
                actions.append(
                    {
                        "lock_name": lock_name,
                        "surface": surface,
                        "anchor_p": anchor_p,
                        "actual_boundary_offset_label": actual,
                        "resolved_candidate_offset": resolved_offset,
                        "candidate_key": candidate_key(
                            surface,
                            anchor_p,
                            resolved_offset,
                        ),
                        "candidate_is_true_boundary": resolved_offset == actual,
                        "true_boundary_status_before_action": row[
                            "true_boundary_status"
                        ],
                        "absorbed_offsets": absorbed_offsets,
                        "absorbed_true_boundary": actual in absorbed_offsets,
                        "wrong_absorption": resolved_offset != actual,
                    }
                )
        previous_anchor_p = anchor_p
    return actions


def audit_lock_surface(
    lock_name: str,
    surface: str,
    rows: list[dict[str, Any]],
    witness_bound: int,
) -> dict[str, Any]:
    """Return one lock/surface audit row."""
    hardening_keys = hardening_population_for_lock(
        lock_name,
        surface,
        rows,
        witness_bound,
    )
    actions = action_records_for_lock(lock_name, surface, rows, witness_bound)
    missed_actions = [
        action for action in actions if action["candidate_key"] not in hardening_keys
    ]
    wrong_actions = [action for action in actions if bool(action["wrong_absorption"])]
    true_boundary_rejected_actions = [
        action for action in actions if bool(action["absorbed_true_boundary"])
    ]
    row = {
        "lock_name": lock_name,
        "surface": surface,
        "hardening_candidate_count": len(hardening_keys),
        "integration_action_candidate_count": len(actions),
        "missed_action_candidate_count": len(missed_actions),
        "missed_action_false_absorber_count": sum(
            1
            for action in missed_actions
            if not bool(action["candidate_is_true_boundary"])
        ),
        "missed_action_true_boundary_unresolved_count": sum(
            1
            for action in missed_actions
            if action["true_boundary_status_before_action"]
            == CANDIDATE_STATUS_UNRESOLVED
        ),
        "wrong_absorption_count": len(wrong_actions),
        "true_boundary_rejected_count": len(true_boundary_rejected_actions),
        "requires_hardening_expansion": bool(missed_actions),
        "lock_quarantined_by_audit": bool(wrong_actions)
        or bool(true_boundary_rejected_actions),
        "first_missed_action_examples": missed_actions[:5],
        "first_wrong_absorption_examples": wrong_actions[:5],
        "first_true_boundary_rejection_examples": true_boundary_rejected_actions[:5],
    }
    return row


def aggregate_lock_rows(lock_name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return aggregate metrics for one lock across surfaces."""
    lock_rows = [row for row in rows if row["lock_name"] == lock_name]
    missed_examples: list[dict[str, Any]] = []
    wrong_examples: list[dict[str, Any]] = []
    for row in lock_rows:
        missed_examples.extend(row["first_missed_action_examples"])
        wrong_examples.extend(row["first_wrong_absorption_examples"])
    return {
        "lock_name": lock_name,
        "hardening_candidate_count": sum(
            int(row["hardening_candidate_count"]) for row in lock_rows
        ),
        "integration_action_candidate_count": sum(
            int(row["integration_action_candidate_count"]) for row in lock_rows
        ),
        "missed_action_candidate_count": sum(
            int(row["missed_action_candidate_count"]) for row in lock_rows
        ),
        "missed_action_false_absorber_count": sum(
            int(row["missed_action_false_absorber_count"]) for row in lock_rows
        ),
        "missed_action_true_boundary_unresolved_count": sum(
            int(row["missed_action_true_boundary_unresolved_count"])
            for row in lock_rows
        ),
        "wrong_absorption_count": sum(
            int(row["wrong_absorption_count"]) for row in lock_rows
        ),
        "true_boundary_rejected_count": sum(
            int(row["true_boundary_rejected_count"]) for row in lock_rows
        ),
        "requires_hardening_expansion": any(
            bool(row["requires_hardening_expansion"]) for row in lock_rows
        ),
        "lock_quarantined_by_audit": any(
            bool(row["lock_quarantined_by_audit"]) for row in lock_rows
        ),
        "first_missed_action_examples": missed_examples[:5],
        "first_wrong_absorption_examples": wrong_examples[:5],
    }


def run_audit(
    surfaces: list[str],
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the action-population audit."""
    started = time.perf_counter()
    audit_rows: list[dict[str, Any]] = []
    for surface in surfaces:
        start_anchor, max_anchor = parse_surface(surface)
        rows, _ = run_probe(
            start_anchor=start_anchor,
            max_anchor=max_anchor,
            candidate_bound=candidate_bound,
            enable_single_hole_positive_witness_closure=True,
            witness_bound=witness_bound,
            enable_carrier_locked_pressure_ceiling=True,
            carrier_lock_predicate="unresolved_alternatives_before_threat",
        )
        for lock_name in LOCK_NAMES:
            audit_rows.append(
                audit_lock_surface(
                    lock_name,
                    surface,
                    rows,
                    witness_bound,
                )
            )

    lock_reports = [
        aggregate_lock_rows(lock_name, audit_rows) for lock_name in LOCK_NAMES
    ]
    summary = {
        "mode": "offline_absorption_lock_action_population_audit",
        "surfaces": surfaces,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "lock_reports": lock_reports,
        "audit_rows": audit_rows,
        "all_live_locks_action_population_covered": all(
            int(report["missed_action_candidate_count"]) == 0
            for report in lock_reports
            if report["lock_name"] == "005A_higher_divisor_pressure_lock"
        ),
        "quarantined_locks": [
            report["lock_name"]
            for report in lock_reports
            if bool(report["lock_quarantined_by_audit"])
        ],
        "boundary_law_005_status": "candidate_grade_only",
        "boundary_law_005a_status": "candidate_grade_not_generator_approved",
        "boundary_law_005b_status": "quarantined",
        "prime_emission_status": "forbidden",
        "classical_labels_status": "external_audit_only",
        "runtime_seconds": time.perf_counter() - started,
    }
    return audit_rows, summary


def write_artifacts(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
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
    return {
        "rows_path": rows_path,
        "summary_path": summary_path,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the absorption-lock action-population audit."""
    args = build_parser().parse_args(argv)
    rows, summary = run_audit(
        surfaces=args.surfaces,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

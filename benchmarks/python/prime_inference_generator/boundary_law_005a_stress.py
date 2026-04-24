#!/usr/bin/env python3
"""One-axis stress test for Boundary Law 005A."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .absorption_lock_action_population_audit import run_audit
    from .composite_exclusion_boundary_probe import run_probe
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from absorption_lock_action_population_audit import run_audit
    from composite_exclusion_boundary_probe import run_probe
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "boundary_law_005a_stress_summary.json"
ROWS_FILENAME = "boundary_law_005a_stress_rows.jsonl"


def build_parser() -> argparse.ArgumentParser:
    """Build the 005A stress CLI."""
    parser = argparse.ArgumentParser(
        description="Offline one-axis stress test for Boundary Law 005A.",
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
        default=1_000_000,
        help="Inclusive upper bound for prime anchors.",
    )
    parser.add_argument(
        "--candidate-bound",
        type=int,
        default=128,
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


def absorption_failure_example(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the first 005A absorption failure example, if present."""
    for row in rows:
        actual = int(row["actual_boundary_offset_label"])
        if bool(row["true_boundary_rejected"]):
            return {
                "failure_type": "TRUE_BOUNDARY_REJECTED",
                "anchor_p": int(row["anchor_p"]),
                "actual_boundary_offset_label": actual,
                "true_boundary_status": row["true_boundary_status"],
                "survivors": row["survivors"],
                "unresolved": row["unresolved"],
            }
        absorbers = [
            int(offset)
            for offset in row["higher_divisor_pressure_locked_absorption"][
                "absorber_offsets"
            ]
        ]
        wrong_absorbers = [offset for offset in absorbers if offset != actual]
        if wrong_absorbers:
            return {
                "failure_type": "WRONG_ABSORPTION",
                "anchor_p": int(row["anchor_p"]),
                "actual_boundary_offset_label": actual,
                "wrong_absorber_offset": wrong_absorbers[0],
                "absorbed_offsets": row[
                    "higher_divisor_pressure_locked_absorption"
                ]["absorbed_offsets"],
            }
    return None


def stress_row(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Run the 005A stress row."""
    surface = f"{start_anchor}..{max_anchor}"
    rows, summary = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
        enable_higher_divisor_pressure_locked_absorption=True,
    )
    _, audit_summary = run_audit(
        surfaces=[surface],
        candidate_bound=candidate_bound,
        witness_bound=witness_bound,
    )
    audit_report = next(
        report
        for report in audit_summary["lock_reports"]
        if report["lock_name"] == "005A_higher_divisor_pressure_lock"
    )
    action_population_match = int(audit_report["missed_action_candidate_count"]) == 0
    first_failure = absorption_failure_example(rows)
    if first_failure is None and not action_population_match:
        first_failure = {
            "failure_type": "ACTION_POPULATION_MISMATCH",
            "first_missed_action_examples": audit_report[
                "first_missed_action_examples"
            ],
        }
    absorption_wrong_count = int(
        summary["higher_divisor_locked_absorption_wrong_count"]
    )
    true_boundary_rejected_count = int(summary["true_boundary_rejected_count"])
    false_absorbed_count = int(summary["false_resolved_survivor_absorbed_count"])
    applied_count = int(summary["higher_divisor_locked_absorption_applied_count"])
    row_count = int(summary["row_count"])
    hard_passed = (
        true_boundary_rejected_count == 0
        and absorption_wrong_count == 0
        and false_absorbed_count == 0
        and action_population_match
    )
    return {
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "anchor_range": surface,
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "row_count": row_count,
        "true_boundary_rejected_count": true_boundary_rejected_count,
        "absorption_wrong_count": absorption_wrong_count,
        "false_resolved_survivor_absorbed_count": false_absorbed_count,
        "unique_resolved_survivor_count": int(
            summary["unique_resolved_survivor_count"]
        ),
        "005A_applied_count": applied_count,
        "005A_correct_count": int(
            summary["higher_divisor_locked_absorption_correct_count"]
        ),
        "005A_wrong_count": absorption_wrong_count,
        "safe_abstain_count": row_count - applied_count,
        "action_population_match": action_population_match,
        "action_population_missed_count": int(
            audit_report["missed_action_candidate_count"]
        ),
        "hard_passed": hard_passed,
        "first_failure_example": first_failure,
    }


def run_stress(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the one-row 005A stress matrix."""
    started = time.perf_counter()
    row = stress_row(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        witness_bound=witness_bound,
    )
    summary = {
        "mode": "offline_boundary_law_005a_one_axis_stress",
        "stress_axis": "candidate_bound",
        "stress_row": row,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "anchor_range": row["anchor_range"],
        "hard_passed": bool(row["hard_passed"]),
        "boundary_law_005a_status": (
            "candidate_grade_stress_passed"
            if bool(row["hard_passed"])
            else "candidate_grade_stress_failed"
        ),
        "boundary_law_005_status": "candidate_grade_only",
        "prime_emission_status": "forbidden",
        "classical_labels_status": "external_audit_only",
        "runtime_seconds": time.perf_counter() - started,
    }
    return [row], summary


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
    """Run the 005A stress test and write artifacts."""
    args = build_parser().parse_args(argv)
    rows, summary = run_stress(
        start_anchor=args.start_anchor,
        max_anchor=args.max_anchor,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

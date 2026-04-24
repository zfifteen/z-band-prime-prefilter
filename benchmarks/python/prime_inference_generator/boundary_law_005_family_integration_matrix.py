#!/usr/bin/env python3
"""Offline integration matrix for Boundary Law 005A and 005B candidates."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .composite_exclusion_boundary_probe import run_probe
    from .higher_divisor_pressure_lock_activation_profile import parse_surface
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import run_probe
    from higher_divisor_pressure_lock_activation_profile import parse_surface
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "boundary_law_005_family_integration_matrix_summary.json"
ROWS_FILENAME = "boundary_law_005_family_integration_matrix_rows.jsonl"
DEFAULT_SURFACES = (
    "11..100000",
    "11..1000000",
    "100000..200000",
    "1000000..1100000",
)
MODE_CONFIGS = (
    {
        "mode_name": "005A_only",
        "enable_005a": True,
        "enable_005b": False,
        "locked_absorption_mode": "then",
    },
    {
        "mode_name": "005B_only",
        "enable_005a": False,
        "enable_005b": True,
        "locked_absorption_mode": "then",
    },
    {
        "mode_name": "005A_or_005B",
        "enable_005a": True,
        "enable_005b": True,
        "locked_absorption_mode": "or",
    },
    {
        "mode_name": "005A_then_005B",
        "enable_005a": True,
        "enable_005b": True,
        "locked_absorption_mode": "then",
    },
)


def build_parser() -> argparse.ArgumentParser:
    """Build the integration matrix CLI."""
    parser = argparse.ArgumentParser(
        description="Offline 005A/005B locked absorption integration matrix.",
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


def combined_absorption_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Return unique absorber counts across 005A and 005B reports."""
    applied_count = 0
    correct_count = 0
    wrong_count = 0
    false_resolved_survivor_absorbed_count = 0
    for row in rows:
        actual = int(row["actual_boundary_offset_label"])
        absorbers = {
            int(offset)
            for offset in row["higher_divisor_pressure_locked_absorption"][
                "absorber_offsets"
            ]
        }
        absorbers.update(
            int(offset)
            for offset in row["previous_carrier_shift_locked_absorption"][
                "absorber_offsets"
            ]
        )
        for absorber in absorbers:
            applied_count += 1
            if absorber == actual:
                correct_count += 1
            else:
                wrong_count += 1
                false_resolved_survivor_absorbed_count += 1
    return {
        "combined_applied_count": applied_count,
        "absorption_correct_count": correct_count,
        "absorption_wrong_count": wrong_count,
        "false_resolved_survivor_absorbed_count": (
            false_resolved_survivor_absorbed_count
        ),
    }


def run_mode_surface(
    surface: str,
    mode_config: dict[str, Any],
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Run one mode and surface row."""
    start_anchor, max_anchor = parse_surface(surface)
    rows, summary = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
        enable_higher_divisor_pressure_locked_absorption=bool(
            mode_config["enable_005a"]
        ),
        enable_previous_carrier_shift_locked_absorption=bool(
            mode_config["enable_005b"]
        ),
        locked_absorption_mode=str(mode_config["locked_absorption_mode"]),
    )
    combined = combined_absorption_counts(rows)
    hard_gate_passed = (
        int(summary["true_boundary_rejected_count"]) == 0
        and int(combined["absorption_wrong_count"]) == 0
        and int(combined["false_resolved_survivor_absorbed_count"]) == 0
    )
    return {
        "mode_name": mode_config["mode_name"],
        "surface": surface,
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "row_count": int(summary["row_count"]),
        "unique_resolved_survivor_count": int(
            summary["unique_resolved_survivor_count"]
        ),
        "true_boundary_rejected_count": int(
            summary["true_boundary_rejected_count"]
        ),
        "absorption_correct_count": combined["absorption_correct_count"],
        "absorption_wrong_count": combined["absorption_wrong_count"],
        "false_resolved_survivor_absorbed_count": combined[
            "false_resolved_survivor_absorbed_count"
        ],
        "005A_applied_count": int(
            summary["higher_divisor_locked_absorption_applied_count"]
        ),
        "005B_applied_count": int(
            summary["previous_carrier_shift_locked_absorption_applied_count"]
        ),
        "combined_applied_count": combined["combined_applied_count"],
        "hard_gate_passed": hard_gate_passed,
        "elimination_rule_set": summary["elimination_rule_set"],
    }


def run_matrix(
    surfaces: list[str],
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the offline 005 family integration matrix."""
    started = time.perf_counter()
    rows = [
        run_mode_surface(
            surface,
            mode_config,
            candidate_bound,
            witness_bound,
        )
        for mode_config in MODE_CONFIGS
        for surface in surfaces
    ]
    summary = {
        "mode": "offline_boundary_law_005_family_integration_matrix",
        "surfaces": surfaces,
        "mode_names": [str(config["mode_name"]) for config in MODE_CONFIGS],
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "matrix_rows": rows,
        "all_rows_hard_gate_passed": all(
            bool(row["hard_gate_passed"]) for row in rows
        ),
        "first_failed_row": next(
            (
                {
                    "mode_name": row["mode_name"],
                    "surface": row["surface"],
                }
                for row in rows
                if not bool(row["hard_gate_passed"])
            ),
            None,
        ),
        "boundary_law_005_status": "candidate_family_not_approved_for_generation",
        "prime_emission_status": "forbidden",
        "runtime_seconds": time.perf_counter() - started,
    }
    return rows, summary


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
    """Run the Boundary Law 005 family integration matrix."""
    args = build_parser().parse_args(argv)
    rows, summary = run_matrix(
        surfaces=args.surfaces,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

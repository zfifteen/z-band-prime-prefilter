#!/usr/bin/env python3
"""Hardening matrix for the previous-to-current carrier shift lock."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .previous_chamber_reset_lock_probe import (
        parse_surface,
        predicate_report,
        surface_records,
    )
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from previous_chamber_reset_lock_probe import (
        parse_surface,
        predicate_report,
        surface_records,
    )
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "previous_to_current_carrier_shift_lock_hardening_summary.json"
ROWS_FILENAME = "previous_to_current_carrier_shift_lock_hardening_rows.jsonl"
LOCK_NAME = "previous_to_current_carrier_shift_lock"
DEFAULT_SURFACES = (
    "11..10000",
    "11..100000",
    "11..1000000",
    "100000..200000",
    "1000000..1100000",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the carrier shift hardening CLI."""
    parser = argparse.ArgumentParser(
        description="Offline hardening for previous-to-current carrier shift lock.",
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


def surface_row(
    surface: str,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Return one hardening row for the carrier shift lock."""
    records, surface_summary = surface_records(
        surface,
        candidate_bound,
        witness_bound,
    )
    start_anchor, max_anchor = parse_surface(surface)
    report = predicate_report(records, LOCK_NAME)
    true_count = sum(
        1 for record in records if bool(record["resolved_candidate_is_true_label"])
    )
    false_count = len(records) - true_count
    true_selected = int(report["lock_true_selected"])
    false_selected = int(report["lock_false_selected"])
    return {
        "surface": surface,
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "row_count": int(surface_summary["row_count"]),
        "target_row_count": int(surface_summary["target_row_count"]),
        "candidate_count": len(records),
        "true_candidate_count": true_count,
        "false_candidate_count": false_count,
        "previous_to_current_carrier_shift_lock_true_selected": true_selected,
        "previous_to_current_carrier_shift_lock_false_selected": false_selected,
        "previous_to_current_carrier_shift_lock_wrong_count": false_selected,
        "selection_abstain_count": int(report["lock_abstain_count"]),
        "selection_accuracy_when_made": float(
            report["selection_accuracy_when_made"]
        ),
        "positive_selection_count": true_selected + false_selected,
        "passes_zero_wrong_gate": false_selected == 0,
    }


def run_hardening(
    surfaces: list[str],
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the carrier shift hardening matrix."""
    started = time.perf_counter()
    rows = [
        surface_row(
            surface,
            candidate_bound,
            witness_bound,
        )
        for surface in surfaces
    ]
    summary = {
        "mode": "offline_previous_to_current_carrier_shift_lock_hardening",
        "lock_name": LOCK_NAME,
        "surfaces": surfaces,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "surface_count": len(rows),
        "hardening_rows": rows,
        "all_surfaces_zero_wrong": all(
            bool(row["passes_zero_wrong_gate"]) for row in rows
        ),
        "first_failed_surface": next(
            (
                row["surface"]
                for row in rows
                if not bool(row["passes_zero_wrong_gate"])
            ),
            None,
        ),
        "surfaces_with_no_activation": [
            row["surface"]
            for row in rows
            if int(row["positive_selection_count"]) == 0
        ],
        "boundary_law_005b_status": "lead_not_approved_for_generation",
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
    """Run the carrier shift lock hardening matrix."""
    args = build_parser().parse_args(argv)
    rows, summary = run_hardening(
        surfaces=args.surfaces,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Hardening matrix for the higher-divisor pressure lock lead."""

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
        run_probe,
    )
    from .resolved_boundary_absorption_safety_probe import candidate_carrier
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        certified_divisor_class,
        run_probe,
    )
    from resolved_boundary_absorption_safety_probe import candidate_carrier
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "higher_divisor_pressure_lock_hardening_summary.json"
ROWS_FILENAME = "higher_divisor_pressure_lock_hardening_rows.jsonl"
LOCK_NAME = "higher_divisor_pressure_lock"
DEFAULT_MAX_ANCHORS = (10_000, 100_000, 1_000_000)


def build_parser() -> argparse.ArgumentParser:
    """Build the higher-divisor pressure lock hardening CLI."""
    parser = argparse.ArgumentParser(
        description="Offline hardening for higher-divisor pressure lock.",
    )
    parser.add_argument(
        "--start-anchor",
        type=int,
        default=11,
        help="Inclusive lower bound for prime anchors.",
    )
    parser.add_argument(
        "--max-anchors",
        type=int,
        nargs="+",
        default=list(DEFAULT_MAX_ANCHORS),
        help="Inclusive upper bounds for staged surfaces.",
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


def lock_report(summary: dict[str, Any]) -> dict[str, Any]:
    """Return the higher-divisor pressure lock report from one surface summary."""
    return summary[LOCK_NAME]


def has_higher_divisor_pressure(
    anchor_p: int,
    resolved_offset: int,
    later_unresolved: list[int],
    witness_bound: int,
) -> bool:
    """Return whether a resolved candidate has later higher-divisor pressure."""
    if not later_unresolved:
        return False
    carrier = candidate_carrier(anchor_p, resolved_offset, witness_bound)
    carrier_d = carrier["carrier_d"]
    if carrier_d is None:
        return False
    for offset in range(resolved_offset + 1, max(later_unresolved)):
        certificate = certified_divisor_class(anchor_p + offset, witness_bound)
        if certificate is None:
            continue
        if int(certificate["divisor_class"]) > int(carrier_d):
            return True
    return False


def surface_counts(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Return compact higher-divisor pressure lock counts for one surface."""
    rows, _ = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
    )
    true_count = 0
    false_count = 0
    true_selected = 0
    false_selected = 0
    for row in rows:
        anchor_p = int(row["anchor_p"])
        actual = int(row["actual_boundary_offset_label"])
        unresolved = [int(offset) for offset in row["unresolved"]]
        for resolved_offset in row["survivors"]:
            offset = int(resolved_offset)
            is_true = offset == actual
            if is_true:
                true_count += 1
            else:
                false_count += 1
            later_unresolved = [
                unresolved_offset
                for unresolved_offset in unresolved
                if unresolved_offset > offset
            ]
            selected = has_higher_divisor_pressure(
                anchor_p,
                offset,
                later_unresolved,
                witness_bound,
            )
            if selected and is_true:
                true_selected += 1
            elif selected:
                false_selected += 1

    selected_total = true_selected + false_selected
    resolved_total = true_count + false_count
    return {
        "row_count": len(rows),
        "true_resolved_candidate_count": true_count,
        "false_resolved_candidate_count": false_count,
        LOCK_NAME: {
            "true_selected": true_selected,
            "false_selected": false_selected,
            "wrong_count": false_selected,
            "selection_abstain_count": resolved_total - selected_total,
            "selection_accuracy_when_made": (
                0.0 if selected_total == 0 else true_selected / selected_total
            ),
        },
    }


def surface_row(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Run one hardening surface and return the compact row."""
    summary = surface_counts(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        witness_bound=witness_bound,
    )
    report = lock_report(summary)
    true_selected = int(report["true_selected"])
    false_selected = int(report["false_selected"])
    return {
        "surface": f"{start_anchor}..{max_anchor}",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "row_count": int(summary["row_count"]),
        "true_resolved_candidate_count": int(
            summary["true_resolved_candidate_count"]
        ),
        "false_resolved_candidate_count": int(
            summary["false_resolved_candidate_count"]
        ),
        "higher_divisor_pressure_lock_true_selected": true_selected,
        "higher_divisor_pressure_lock_false_selected": false_selected,
        "higher_divisor_pressure_lock_wrong_count": false_selected,
        "selection_abstain_count": int(report["selection_abstain_count"]),
        "selection_accuracy_when_made": float(
            report["selection_accuracy_when_made"]
        ),
        "passes_zero_wrong_gate": false_selected == 0 and true_selected > 0,
    }


def run_hardening(
    start_anchor: int,
    max_anchors: list[int],
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the staged hardening matrix."""
    started = time.perf_counter()
    rows = [
        surface_row(
            start_anchor=start_anchor,
            max_anchor=max_anchor,
            candidate_bound=candidate_bound,
            witness_bound=witness_bound,
        )
        for max_anchor in max_anchors
    ]
    summary = {
        "mode": "offline_higher_divisor_pressure_lock_hardening",
        "lock_name": LOCK_NAME,
        "start_anchor": start_anchor,
        "max_anchors": max_anchors,
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
        "boundary_law_005_status": "not_approved",
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
    return {"rows_path": rows_path, "summary_path": summary_path}


def main(argv: list[str] | None = None) -> int:
    """Run higher-divisor pressure lock hardening and write artifacts."""
    args = build_parser().parse_args(argv)
    rows, summary = run_hardening(
        start_anchor=args.start_anchor,
        max_anchors=args.max_anchors,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

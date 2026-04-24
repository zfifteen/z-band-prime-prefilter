#!/usr/bin/env python3
"""Residual forensics after carrier-locked pressure ceiling integration."""

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
        run_probe,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        run_probe,
    )


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "residual_after_locked_ceiling_forensics_summary.json"
RECORDS_FILENAME = "residual_after_locked_ceiling_forensics_records.jsonl"
LOCK_PREDICATE = "unresolved_alternatives_before_threat"


def build_parser() -> argparse.ArgumentParser:
    """Build the residual-forensics CLI."""
    parser = argparse.ArgumentParser(
        description="Residual forensics after carrier-locked ceiling integration.",
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
        return {str(key): int(count) for key, count in sorted(value.items())}
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    return value


def candidate_status_records(row: dict[str, Any], status: str) -> list[dict[str, Any]]:
    """Return candidate records with one status."""
    return [
        record
        for record in row["candidate_status_records"]
        if record["status"] == status
    ]


def reason_counts(records: list[dict[str, Any]]) -> Counter[str]:
    """Return unresolved reason counts for candidate records."""
    counts: Counter[str] = Counter()
    for record in records:
        reasons = list(record["unresolved_reasons"])
        if not reasons:
            counts.update(["NO_UNRESOLVED_REASON"])
        else:
            counts.update(str(reason) for reason in reasons)
    return counts


def pruned_offsets_by_previous_status(row: dict[str, Any]) -> dict[str, list[int]]:
    """Return carrier-ceiling pruned offsets grouped by prior status."""
    grouped: dict[str, list[int]] = {}
    for record in row["candidate_status_records"]:
        if not bool(record.get("carrier_locked_pressure_ceiling_rejection")):
            continue
        previous_status = str(
            record.get("carrier_locked_pressure_ceiling_previous_status")
        )
        grouped.setdefault(previous_status, []).append(int(record["offset"]))
    return grouped


def rule_pruning_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Return per-row rule pruning and closure attribution."""
    ceiling = row["carrier_locked_pressure_ceiling"]
    closure_offsets = [
        int(record["offset"])
        for record in row["candidate_status_records"]
        if bool(record.get("single_hole_positive_witness_closure"))
    ]
    rejection_counts: Counter[str] = Counter()
    for record in row["candidate_status_records"]:
        if record["status"] != CANDIDATE_STATUS_REJECTED:
            continue
        rejection_counts.update([str(record["rule_family"])])

    return {
        "single_hole_positive_witness_closure_offsets": closure_offsets,
        "carrier_locked_pressure_ceiling": {
            "applied": bool(ceiling.get("applied")),
            "carrier_lock_predicate": ceiling.get("carrier_lock_predicate"),
            "lock_components": ceiling.get("lock_components", {}),
            "threat_offset": ceiling.get("threat_offset"),
            "pruned_offsets": [
                int(offset) for offset in ceiling.get("pruned_offsets", [])
            ],
            "pruned_offsets_by_previous_status": (
                pruned_offsets_by_previous_status(row)
            ),
        },
        "rejection_rule_family_counts": rejection_counts,
    }


def residual_failure_pattern(row: dict[str, Any]) -> str:
    """Return the residual failure pattern for one post-integration row."""
    true_status = str(row["true_boundary_status"])
    if true_status == CANDIDATE_STATUS_REJECTED:
        return "true_boundary_rejected"
    if true_status == CANDIDATE_STATUS_UNRESOLVED:
        return "true_boundary_unresolved_chamber_completion"
    if true_status != CANDIDATE_STATUS_RESOLVED_SURVIVOR:
        return f"true_boundary_{true_status.lower()}"
    if bool(row["unique_resolved_survivor"]):
        return "unique_resolved_survivor"
    if int(row["survivor_count"]) > 1 and int(row["unresolved_count"]) > 0:
        return "true_resolved_not_unique_multiple_resolved_and_unresolved"
    if int(row["survivor_count"]) > 1:
        return "true_resolved_not_unique_multiple_resolved_survivors"
    if int(row["unresolved_count"]) > 0:
        return "true_resolved_not_unique_unresolved_alternatives"
    return "true_resolved_not_unique_other"


def forensic_record(row: dict[str, Any]) -> dict[str, Any]:
    """Return one residual forensic record."""
    unresolved_records = candidate_status_records(row, CANDIDATE_STATUS_UNRESOLVED)
    return {
        "anchor_p": int(row["anchor_p"]),
        "actual_boundary_offset_label": int(row["actual_boundary_offset_label"]),
        "true_boundary_status": row["true_boundary_status"],
        "residual_failure_pattern": residual_failure_pattern(row),
        "resolved_survivor_offsets": [int(offset) for offset in row["survivors"]],
        "unresolved_candidate_offsets": [
            int(offset) for offset in row["unresolved"]
        ],
        "rejected_candidate_offsets": [int(offset) for offset in row["rejected"]],
        "remaining_unresolved_reason_counts": reason_counts(unresolved_records),
        "which_rule_pruned_what": rule_pruning_summary(row),
    }


def run_forensics(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run residual forensics after the strongest safe locked-ceiling mode."""
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
    records = [forensic_record(row) for row in rows]
    pattern_counts = Counter(
        record["residual_failure_pattern"] for record in records
    )
    true_boundary_resolved_not_unique_count = sum(
        1
        for row in rows
        if row["true_boundary_status"] == CANDIDATE_STATUS_RESOLVED_SURVIVOR
        and not bool(row["unique_resolved_survivor"])
    )
    summary = {
        "mode": "offline_residual_after_locked_ceiling_forensics",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "single_hole_positive_witness_closure_enabled": True,
        "carrier_locked_pressure_ceiling_enabled": True,
        "carrier_lock_predicate": LOCK_PREDICATE,
        "row_count": probe_summary["row_count"],
        "unique_resolved_survivor_count": probe_summary[
            "unique_resolved_survivor_count"
        ],
        "true_boundary_rejected_count": probe_summary[
            "true_boundary_rejected_count"
        ],
        "true_boundary_unresolved_count": probe_summary[
            "true_boundary_unresolved_count"
        ],
        "true_boundary_resolved_not_unique_count": (
            true_boundary_resolved_not_unique_count
        ),
        "average_resolved_survivor_count": probe_summary[
            "average_resolved_survivor_count"
        ],
        "average_unresolved_count": probe_summary["average_unresolved_count"],
        "residual_failure_pattern_counts": pattern_counts,
        "carrier_locked_ceiling_applied_count": probe_summary[
            "carrier_locked_ceiling_applied_count"
        ],
        "carrier_locked_ceiling_false_candidate_pruned_count": probe_summary[
            "carrier_locked_ceiling_false_candidate_pruned_count"
        ],
        "first_examples": records[:10],
        "boundary_law_005_status": "not_approved",
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
    """Run residual forensics and write artifacts."""
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

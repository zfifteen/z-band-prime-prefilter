#!/usr/bin/env python3
"""Forensics for dominance among multiple resolved survivor candidates.

This script is offline theorem discovery. It runs the integrated
composite-exclusion eliminator, isolates anchors with resolved false-boundary
alternatives, and evaluates label-blind dominance rules against labels only
after selection.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable

try:
    from .composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        WHEEL_OPEN_RESIDUES_MOD30,
        bounded_composite_witness,
        power_closure_witness,
        run_probe,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        WHEEL_OPEN_RESIDUES_MOD30,
        bounded_composite_witness,
        power_closure_witness,
        run_probe,
    )

from sympy import divisor_count, factorint, prevprime


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "resolved_survivor_dominance_forensics_summary.json"
RECORDS_FILENAME = "resolved_survivor_dominance_forensics_records.jsonl"
DOMINANCE_RULES = [
    "earliest_resolved_boundary",
    "minimal_chamber_width",
    "strongest_gwr_carrier",
    "no_later_simpler_margin",
    "minimal_closure_support",
    "previous_chamber_transition_compatibility",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the resolved-survivor dominance forensics CLI."""
    parser = argparse.ArgumentParser(
        description="Offline dominance forensics for resolved survivor candidates.",
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
        help="Largest factor used by integrated single-hole closure.",
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


def exact_family(n: int) -> str:
    """Return exact factorization family for offline diagnostics."""
    factors = factorint(n)
    exponent_sum = sum(int(exponent) for exponent in factors.values())
    if len(factors) == 1 and exponent_sum == 1:
        return "prime"
    if len(factors) == 1:
        return "prime_power"
    if exponent_sum == 2:
        return "semiprime"
    return "composite"


def previous_gap_bucket(width: int) -> str:
    """Return compact previous-gap pressure bucket."""
    if width <= 4:
        return "G_LE_4"
    if width <= 8:
        return "G_LE_8"
    if width <= 16:
        return "G_LE_16"
    if width <= 32:
        return "G_LE_32"
    return "G_GT_32"


def first_open_offset(anchor_p: int) -> int:
    """Return the first positive wheel-open offset."""
    for offset in range(1, 31):
        if (anchor_p + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30:
            return offset
    raise RuntimeError(f"no wheel-open offset for anchor {anchor_p}")


def legal_witness_for_offset(anchor_p: int, offset: int) -> dict[str, Any] | None:
    """Return a legal composite witness for an interior offset, if present."""
    n = anchor_p + offset
    witness = bounded_composite_witness(n)
    if witness is not None:
        return {"offset": offset, "n": n, "witness_factor": witness}
    if n % 30 not in WHEEL_OPEN_RESIDUES_MOD30:
        for factor in (2, 3, 5):
            if n % factor == 0:
                return {"offset": offset, "n": n, "witness_factor": factor}
    return None


def interior_witnesses(anchor_p: int, candidate_offset: int) -> list[dict[str, Any]]:
    """Return known legal interior witnesses for a candidate chamber."""
    witnesses: list[dict[str, Any]] = []
    for offset in range(1, candidate_offset):
        witness = legal_witness_for_offset(anchor_p, offset)
        if witness is not None:
            witnesses.append(witness)
    return witnesses


def carrier_metadata(witnesses: list[dict[str, Any]]) -> dict[str, Any]:
    """Return offline GWR carrier metadata from known witnesses."""
    if not witnesses:
        return {
            "gwr_carrier_w": None,
            "gwr_carrier_offset": None,
            "gwr_carrier_divisor_count": None,
            "gwr_carrier_family": None,
        }
    carrier = min(
        witnesses,
        key=lambda record: (
            int(divisor_count(record["n"])),
            int(record["offset"]),
        ),
    )
    return {
        "gwr_carrier_w": int(carrier["n"]),
        "gwr_carrier_offset": int(carrier["offset"]),
        "gwr_carrier_divisor_count": int(divisor_count(carrier["n"])),
        "gwr_carrier_family": exact_family(carrier["n"]),
    }


def lower_divisor_threat_count(
    witnesses: list[dict[str, Any]],
    carrier_offset: int | None,
    carrier_d: int | None,
) -> int:
    """Return count of later known lower-divisor threats."""
    if carrier_offset is None or carrier_d is None:
        return 0
    count = 0
    for witness in witnesses:
        offset = int(witness["offset"])
        if offset <= carrier_offset:
            continue
        if int(divisor_count(witness["n"])) < carrier_d:
            count += 1
    return count


def square_offsets(anchor_p: int, candidate_offset: int) -> tuple[int, ...]:
    """Return interior square offsets for a proposed chamber."""
    offsets: list[int] = []
    lo = anchor_p + 1
    hi = anchor_p + candidate_offset - 1
    root = math.isqrt(lo - 1) + 1
    while root * root <= hi:
        offsets.append(root * root - anchor_p)
        root += 1
    return tuple(offsets)


def record_by_offset(row: dict[str, Any], offset: int) -> dict[str, Any]:
    """Return candidate status record for one offset."""
    for record in row["candidate_status_records"]:
        if int(record["offset"]) == offset:
            return record
    raise ValueError(f"candidate offset {offset} not present")


def resolved_metadata(row: dict[str, Any], candidate_offset: int) -> dict[str, Any]:
    """Return PGS metadata for one resolved survivor candidate."""
    anchor_p = int(row["anchor_p"])
    status_record = record_by_offset(row, candidate_offset)
    witnesses = interior_witnesses(anchor_p, candidate_offset)
    carrier = carrier_metadata(witnesses)
    closure_reasons = list(status_record.get("closure_reasons", []))
    closure_count = len(closure_reasons)
    power_closure_count = sum(1 for reason in closure_reasons if reason.startswith("POWER_CLOSURE"))
    small_factor_closure_count = sum(
        1
        for reason in closure_reasons
        if reason.startswith("SINGLE_HOLE_POSITIVE_WITNESS_FACTOR")
    )
    threat_count = lower_divisor_threat_count(
        witnesses,
        carrier["gwr_carrier_offset"],
        carrier["gwr_carrier_divisor_count"],
    )
    previous_prime = int(prevprime(anchor_p))
    previous_gap = anchor_p - previous_prime
    return {
        "candidate_offset": candidate_offset,
        "candidate_width": candidate_offset - 1,
        **carrier,
        "first_open_offset": first_open_offset(anchor_p),
        "resolved_interior_count": len(witnesses),
        "single_hole_closure_used": bool(
            status_record.get("single_hole_positive_witness_closure")
        ),
        "closure_count": closure_count,
        "square_pressure": {
            "interior_square_offsets": square_offsets(anchor_p, candidate_offset),
            "interior_square_count": len(square_offsets(anchor_p, candidate_offset)),
        },
        "power_closure_count": power_closure_count,
        "small_factor_witness_closure_count": small_factor_closure_count,
        "lower_divisor_threat_count": threat_count,
        "no_later_simpler_status": (
            "PASS_NO_KNOWN_THREAT" if threat_count == 0 else "KNOWN_THREAT"
        ),
        "previous_chamber_pressure": {
            "previous_gap_width": previous_gap,
            "previous_gap_bucket": previous_gap_bucket(previous_gap),
        },
    }


def dominance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return anchors with at least one resolved false-boundary alternative."""
    selected: list[dict[str, Any]] = []
    for row in rows:
        actual = int(row["actual_boundary_offset_label"])
        resolved = [
            int(record["offset"])
            for record in row["candidate_status_records"]
            if record["status"] == CANDIDATE_STATUS_RESOLVED_SURVIVOR
        ]
        false_resolved = [offset for offset in resolved if offset != actual]
        if false_resolved:
            selected.append(row)
    return selected


def forensic_record(row: dict[str, Any]) -> dict[str, Any]:
    """Return one dominance forensic record."""
    actual = int(row["actual_boundary_offset_label"])
    resolved = [
        int(record["offset"])
        for record in row["candidate_status_records"]
        if record["status"] == CANDIDATE_STATUS_RESOLVED_SURVIVOR
    ]
    false_resolved = [offset for offset in resolved if offset != actual]
    candidate_metadata = [
        resolved_metadata(row, offset)
        for offset in resolved
    ]
    return {
        "anchor_p": int(row["anchor_p"]),
        "actual_boundary_offset_label": actual,
        "resolved_survivor_offsets": resolved,
        "true_boundary_resolved_bool": actual in resolved,
        "false_resolved_survivor_offsets": false_resolved,
        "resolved_survivor_count": len(resolved),
        "unresolved_count": int(row["unresolved_count"]),
        "rejected_count": int(row["rejected_count"]),
        "resolved_survivor_metadata": candidate_metadata,
    }


def unique_minimum(
    metadata: list[dict[str, Any]],
    key: Callable[[dict[str, Any]], Any],
) -> int | None:
    """Return candidate offset with a unique minimum key, or abstain."""
    if not metadata:
        return None
    ranked = sorted(metadata, key=key)
    if len(ranked) > 1 and key(ranked[0]) == key(ranked[1]):
        return None
    return int(ranked[0]["candidate_offset"])


def select_candidate(rule_name: str, metadata: list[dict[str, Any]]) -> int | None:
    """Apply one label-blind dominance rule."""
    if rule_name in ("earliest_resolved_boundary", "minimal_chamber_width"):
        return unique_minimum(metadata, lambda item: item["candidate_offset"])
    if rule_name == "strongest_gwr_carrier":
        return unique_minimum(
            metadata,
            lambda item: (
                item["gwr_carrier_divisor_count"]
                if item["gwr_carrier_divisor_count"] is not None
                else 9999,
                item["gwr_carrier_offset"]
                if item["gwr_carrier_offset"] is not None
                else 9999,
            ),
        )
    if rule_name == "no_later_simpler_margin":
        return unique_minimum(
            metadata,
            lambda item: (
                item["lower_divisor_threat_count"],
                item["candidate_offset"],
            ),
        )
    if rule_name == "minimal_closure_support":
        return unique_minimum(
            metadata,
            lambda item: (
                item["closure_count"],
                item["candidate_offset"],
            ),
        )
    if rule_name == "previous_chamber_transition_compatibility":
        return unique_minimum(
            metadata,
            lambda item: (
                abs(
                    item["candidate_offset"]
                    - item["previous_chamber_pressure"]["previous_gap_width"]
                ),
                item["candidate_offset"],
            ),
        )
    raise ValueError(f"unknown dominance rule {rule_name}")


def rule_report(records: list[dict[str, Any]], rule_name: str) -> dict[str, Any]:
    """Return post-label evaluation for one dominance rule."""
    selection_made_count = 0
    selection_correct_count = 0
    selection_wrong_count = 0
    selection_abstain_count = 0
    first_wrong_examples: list[dict[str, Any]] = []
    for record in records:
        selected = select_candidate(rule_name, record["resolved_survivor_metadata"])
        actual = int(record["actual_boundary_offset_label"])
        if selected is None:
            selection_abstain_count += 1
            continue
        selection_made_count += 1
        if selected == actual:
            selection_correct_count += 1
        else:
            selection_wrong_count += 1
            if len(first_wrong_examples) < 5:
                first_wrong_examples.append(
                    {
                        "anchor_p": record["anchor_p"],
                        "selected_offset": selected,
                        "actual_boundary_offset_label": actual,
                        "resolved_survivor_offsets": (
                            record["resolved_survivor_offsets"]
                        ),
                    }
                )

    return {
        "rule_name": rule_name,
        "eligible_for_pure_generation": True,
        "anchors_tested": len(records),
        "selection_made_count": selection_made_count,
        "selection_correct_count": selection_correct_count,
        "selection_wrong_count": selection_wrong_count,
        "selection_abstain_count": selection_abstain_count,
        "selection_accuracy": (
            0.0
            if selection_made_count == 0
            else selection_correct_count / selection_made_count
        ),
        "passes_zero_wrong_gate": selection_wrong_count == 0,
        "first_wrong_examples": first_wrong_examples,
    }


def observable_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    """Return coarse observable counts separating true and false survivors."""
    counts: Counter[str] = Counter()
    for record in records:
        actual = int(record["actual_boundary_offset_label"])
        metadata = record["resolved_survivor_metadata"]
        true_items = [item for item in metadata if item["candidate_offset"] == actual]
        false_items = [item for item in metadata if item["candidate_offset"] != actual]
        if not true_items:
            counts["true_boundary_not_resolved"] += 1
            continue
        true_item = true_items[0]
        if any(item["candidate_offset"] < actual for item in false_items):
            counts["false_survivor_before_true"] += 1
        if any(item["candidate_offset"] > actual for item in false_items):
            counts["false_survivor_after_true"] += 1
        if true_item["closure_count"] == 0:
            counts["true_requires_no_closure"] += 1
        if true_item["closure_count"] > 0:
            counts["true_requires_closure"] += 1
        if any(item["closure_count"] > true_item["closure_count"] for item in false_items):
            counts["false_more_closure_than_true"] += 1
        if any(item["closure_count"] < true_item["closure_count"] for item in false_items):
            counts["false_less_closure_than_true"] += 1
        if any(
            item["lower_divisor_threat_count"]
            > true_item["lower_divisor_threat_count"]
            for item in false_items
        ):
            counts["false_more_threats_than_true"] += 1
        if any(
            item["lower_divisor_threat_count"]
            < true_item["lower_divisor_threat_count"]
            for item in false_items
        ):
            counts["false_fewer_threats_than_true"] += 1
    return dict(sorted(counts.items()))


def run_forensics(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run resolved-survivor dominance forensics."""
    started = time.perf_counter()
    rows, probe_summary = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
    )
    selected_rows = dominance_rows(rows)
    records = [forensic_record(row) for row in selected_rows]
    rule_reports = [rule_report(records, rule_name) for rule_name in DOMINANCE_RULES]
    resolved_counts = [record["resolved_survivor_count"] for record in records]
    summary = {
        "mode": "offline_resolved_survivor_dominance_forensics",
        "start_anchor": start_anchor,
        "max_anchor": max_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "row_count": probe_summary["row_count"],
        "anchors_with_false_resolved_survivors": len(records),
        "resolved_survivor_count_distribution": Counter(resolved_counts),
        "candidate_dominance_observable_counts": observable_counts(records),
        "dominance_rule_reports": rule_reports,
        "first_records": records[:5],
        "true_boundary_rejected_count": probe_summary[
            "true_boundary_rejected_count"
        ],
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
    """Run resolved-survivor dominance forensics and write artifacts."""
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

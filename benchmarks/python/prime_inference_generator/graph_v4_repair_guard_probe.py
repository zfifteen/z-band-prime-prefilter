#!/usr/bin/env python3
"""Probe positive guards for repairing graph v4 no-carrier domination."""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path
from typing import Any

from sympy import primerange

try:
    from .boundary_certificate_graph_solver import (
        base_relations,
        candidate_nodes,
        propagate_005a_r,
        propagate_unresolved_later_domination,
        propagate_unresolved_later_domination_v2,
        propagate_unresolved_later_domination_v3,
        target_no_carrier_reset_evidence_status,
    )
    from .composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        WHEEL_OPEN_RESIDUES_MOD30,
        bounded_composite_witness,
        certified_divisor_class,
        eliminate_candidates,
        first_legal_carrier,
        power_closure_witness,
    )
    from .offline_pgs_certificate_emitter import anchor_primes, first_prime_after
    from .resolved_boundary_lock_separator_probe import jsonable
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from boundary_certificate_graph_solver import (
        base_relations,
        candidate_nodes,
        propagate_005a_r,
        propagate_unresolved_later_domination,
        propagate_unresolved_later_domination_v2,
        propagate_unresolved_later_domination_v3,
        target_no_carrier_reset_evidence_status,
    )
    from composite_exclusion_boundary_probe import (
        CANDIDATE_STATUS_REJECTED,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        CANDIDATE_STATUS_UNRESOLVED,
        WHEEL_OPEN_RESIDUES_MOD30,
        bounded_composite_witness,
        certified_divisor_class,
        eliminate_candidates,
        first_legal_carrier,
        power_closure_witness,
    )
    from offline_pgs_certificate_emitter import anchor_primes, first_prime_after
    from resolved_boundary_lock_separator_probe import jsonable


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "graph_v4_repair_guard_probe_summary.json"
ROWS_FILENAME = "graph_v4_repair_guard_probe_rows.jsonl"
FOCUS_ANCHOR = 10193
GUARD_NAMES = (
    "target_positive_composite_witness",
    "target_power_witness",
    "target_wheel_closed",
    "target_independently_rejected",
    "target_beyond_locked_pressure_ceiling",
    "target_has_positive_nonboundary_certificate",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the graph v4 repair-guard probe CLI."""
    parser = argparse.ArgumentParser(
        description="Probe positive no-carrier target guards for graph v4 repair.",
    )
    parser.add_argument("--start-anchor", type=int, default=11)
    parser.add_argument("--small-max-anchor", type=int, default=10_000)
    parser.add_argument("--large-max-anchor", type=int, default=100_000)
    parser.add_argument("--focus-anchor", type=int, default=FOCUS_ANCHOR)
    parser.add_argument("--candidate-bound", type=int, default=128)
    parser.add_argument("--witness-bound", type=int, default=127)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def base_row(anchor_p: int, candidate_bound: int, witness_bound: int) -> dict[str, Any]:
    """Return the accepted pre-graph eliminator row for one anchor."""
    return eliminate_candidates(
        anchor_p,
        candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
        enable_higher_divisor_pressure_locked_absorption=False,
    )


def v3_nodes(
    anchor_p: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    """Return the active graph after accepted v3 propagation."""
    row = base_row(anchor_p, candidate_bound, witness_bound)
    nodes = candidate_nodes(row, witness_bound)
    relations = base_relations(row)
    relations.extend(propagate_005a_r(anchor_p, nodes, witness_bound))
    relations.extend(
        propagate_unresolved_later_domination(anchor_p, nodes, witness_bound)
    )
    relations.extend(
        propagate_unresolved_later_domination_v2(anchor_p, nodes, witness_bound)
    )
    relations.extend(
        propagate_unresolved_later_domination_v3(anchor_p, nodes, witness_bound)
    )
    return row, nodes


def active_offsets(nodes: dict[int, dict[str, Any]], status: str) -> list[int]:
    """Return active offsets for one graph status."""
    return [
        offset
        for offset, node in sorted(nodes.items())
        if node["status"] == status and not bool(node["absorbed"])
    ]


def first_prime_after_with_cap(anchor_p: int, cap: int) -> int | None:
    """Return the reporting-only next prime after the anchor within a fixed cap."""
    return next(primerange(anchor_p + 1, cap + 1), None)


def target_beyond_locked_pressure_ceiling(
    row: dict[str, Any],
    target_offset: int,
) -> bool:
    """Return whether a target lies beyond a selected pressure ceiling."""
    ceiling = row["carrier_locked_pressure_ceiling"]
    if not bool(ceiling.get("lock_selected")):
        return False
    threat_offset = ceiling.get("threat_offset")
    if threat_offset is None:
        return False
    return int(target_offset) >= int(threat_offset)


def guard_selected(
    guard_name: str,
    anchor_p: int,
    target_offset: int,
    nodes: dict[int, dict[str, Any]],
    row: dict[str, Any],
    witness_bound: int,
) -> bool:
    """Return whether one label-free positive non-boundary guard fires."""
    target_n = anchor_p + target_offset
    if guard_name == "target_positive_composite_witness":
        return bounded_composite_witness(target_n) is not None
    if guard_name == "target_power_witness":
        return power_closure_witness(target_n) is not None
    if guard_name == "target_wheel_closed":
        return target_n % 30 not in WHEEL_OPEN_RESIDUES_MOD30
    if guard_name == "target_independently_rejected":
        return nodes[target_offset]["initial_status"] == CANDIDATE_STATUS_REJECTED
    if guard_name == "target_beyond_locked_pressure_ceiling":
        return target_beyond_locked_pressure_ceiling(row, target_offset)
    if guard_name == "target_has_positive_nonboundary_certificate":
        return (
            bounded_composite_witness(target_n) is not None
            or power_closure_witness(target_n) is not None
            or certified_divisor_class(target_n, witness_bound) is not None
            or target_n % 30 not in WHEEL_OPEN_RESIDUES_MOD30
            or nodes[target_offset]["initial_status"] == CANDIDATE_STATUS_REJECTED
            or target_beyond_locked_pressure_ceiling(row, target_offset)
        )
    raise ValueError(f"unknown guard: {guard_name}")


def apply_repaired_v4(
    guard_name: str,
    anchor_p: int,
    nodes: dict[int, dict[str, Any]],
    row: dict[str, Any],
    witness_bound: int,
) -> tuple[int, list[dict[str, Any]]]:
    """Apply the repaired no-carrier v4 candidate with one positive guard."""
    applied = 0
    events: list[dict[str, Any]] = []
    while True:
        active_resolved = active_offsets(nodes, CANDIDATE_STATUS_RESOLVED_SURVIVOR)
        if len(active_resolved) != 1:
            return applied, events
        source_offset = active_resolved[0]
        source_node = nodes[source_offset]
        if bool(source_node["single_hole_closure_used"]):
            return applied, events
        later_unresolved = [
            offset
            for offset in active_offsets(nodes, CANDIDATE_STATUS_UNRESOLVED)
            if offset > source_offset
        ]
        if not later_unresolved:
            return applied, events
        target_offset = later_unresolved[0]
        target_carrier = first_legal_carrier(
            anchor_p,
            target_offset,
            witness_bound,
        )
        if target_carrier["carrier_d"] is not None:
            return applied, events
        reset_status = target_no_carrier_reset_evidence_status(
            anchor_p,
            source_offset,
            target_offset,
            source_node["carrier"],
            target_carrier,
            nodes,
            witness_bound,
        )
        if reset_status != "NO_ACTIVE_RESET_EVIDENCE":
            return applied, events
        if not guard_selected(
            guard_name,
            anchor_p,
            target_offset,
            nodes,
            row,
            witness_bound,
        ):
            return applied, events

        target_node = nodes[target_offset]
        target_node["status"] = CANDIDATE_STATUS_REJECTED
        target_node["absorbed"] = True
        target_node["absorbed_by"] = source_offset
        target_node["reset_evidence_status"] = reset_status
        target_node["rejection_reasons"].append(
            f"REPAIRED_V4_{guard_name}_BY_{source_offset}"
        )
        target_node["unresolved_reasons"] = []
        target_node["unresolved_interior_offsets"] = []
        event = {
            "guard_name": guard_name,
            "source_offset": source_offset,
            "target_offset": target_offset,
            "target_n": anchor_p + target_offset,
            "reset_evidence_status": reset_status,
        }
        events.append(event)
        applied += 1


def solve_with_guard(
    guard_name: str,
    anchor_p: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Return one anchor result under one repaired v4 guard."""
    row, original_nodes = v3_nodes(anchor_p, candidate_bound, witness_bound)
    nodes = copy.deepcopy(original_nodes)
    baseline_resolved = active_offsets(
        original_nodes,
        CANDIDATE_STATUS_RESOLVED_SURVIVOR,
    )
    baseline_unresolved = active_offsets(original_nodes, CANDIDATE_STATUS_UNRESOLVED)
    applied, events = apply_repaired_v4(
        guard_name,
        anchor_p,
        nodes,
        row,
        witness_bound,
    )
    resolved = active_offsets(nodes, CANDIDATE_STATUS_RESOLVED_SURVIVOR)
    unresolved = active_offsets(nodes, CANDIDATE_STATUS_UNRESOLVED)
    solved = len(resolved) == 1 and not unresolved
    q_hat = None if not solved else anchor_p + int(resolved[0])
    audit_first = None if q_hat is None else first_prime_after(anchor_p, q_hat)
    confirmed = solved and audit_first == q_hat
    return {
        "anchor_p": anchor_p,
        "guard_name": guard_name,
        "baseline_v3_solved": (
            len(baseline_resolved) == 1 and not baseline_unresolved
        ),
        "repaired_v4_applied_count": applied,
        "events": events,
        "solved": solved,
        "confirmed": confirmed,
        "q_hat": q_hat,
        "boundary_offset": None if not solved else int(resolved[0]),
        "audit_first_prime_after_anchor_to_q_hat": audit_first,
        "actual_next_prime_with_cap": first_prime_after_with_cap(
            anchor_p,
            anchor_p + max(10_000, candidate_bound * 16),
        ),
    }


def empty_surface_metrics(start_anchor: int, max_anchor: int, anchors: int) -> dict[str, Any]:
    """Return zeroed metrics for one guard on one surface."""
    return {
        "anchor_range": f"{start_anchor}..{max_anchor}",
        "anchors_evaluated": anchors,
        "baseline_v3_solved_count": 0,
        "allowed_v4_absorptions": 0,
        "solved_count_if_integrated": 0,
        "audit_confirmed_count_if_integrated": 0,
        "audit_failed_count_if_integrated": 0,
        "first_failure_if_any": None,
    }


def summarize_surface_all_guards(
    start_anchor: int,
    max_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, dict[str, Any]]:
    """Return surface metrics for all guards with one v3 pass per anchor."""
    anchors = anchor_primes(start_anchor, max_anchor)
    metrics = {
        guard_name: empty_surface_metrics(start_anchor, max_anchor, len(anchors))
        for guard_name in GUARD_NAMES
    }
    for anchor_p in anchors:
        row, original_nodes = v3_nodes(anchor_p, candidate_bound, witness_bound)
        baseline_resolved = active_offsets(
            original_nodes,
            CANDIDATE_STATUS_RESOLVED_SURVIVOR,
        )
        baseline_unresolved = active_offsets(
            original_nodes,
            CANDIDATE_STATUS_UNRESOLVED,
        )
        baseline_solved = len(baseline_resolved) == 1 and not baseline_unresolved
        for guard_name in GUARD_NAMES:
            guard_metrics = metrics[guard_name]
            if baseline_solved:
                guard_metrics["baseline_v3_solved_count"] += 1
            nodes = copy.deepcopy(original_nodes)
            applied, _ = apply_repaired_v4(
                guard_name,
                anchor_p,
                nodes,
                row,
                witness_bound,
            )
            guard_metrics["allowed_v4_absorptions"] += applied
            resolved = active_offsets(nodes, CANDIDATE_STATUS_RESOLVED_SURVIVOR)
            unresolved = active_offsets(nodes, CANDIDATE_STATUS_UNRESOLVED)
            if len(resolved) != 1 or unresolved:
                continue
            guard_metrics["solved_count_if_integrated"] += 1
            q_hat = anchor_p + int(resolved[0])
            audit_first = first_prime_after(anchor_p, q_hat)
            if audit_first == q_hat:
                guard_metrics["audit_confirmed_count_if_integrated"] += 1
                continue
            guard_metrics["audit_failed_count_if_integrated"] += 1
            if guard_metrics["first_failure_if_any"] is None:
                guard_metrics["first_failure_if_any"] = {
                    "anchor_p": anchor_p,
                    "q_hat": q_hat,
                    "boundary_offset": int(resolved[0]),
                    "audit_first_prime_after_anchor_to_q_hat": audit_first,
                    "actual_next_prime_with_cap": first_prime_after_with_cap(
                        anchor_p,
                        anchor_p + max(10_000, candidate_bound * 16),
                    ),
                    "repaired_v4_applied_count": applied,
                }
    return metrics


def focused_anchor_result(
    guard_name: str,
    focus_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> dict[str, Any]:
    """Return the anchor 10193 guard-blocking result."""
    result = solve_with_guard(
        guard_name,
        focus_anchor,
        candidate_bound,
        witness_bound,
    )
    actual_next = result["actual_next_prime_with_cap"]
    actual_offset = None if actual_next is None else int(actual_next) - focus_anchor
    absorbed_actual = any(
        int(event["target_offset"]) == actual_offset for event in result["events"]
    )
    return {
        "anchor_p": focus_anchor,
        "actual_next_prime": actual_next,
        "actual_boundary_offset": actual_offset,
        "guard_applied_count": result["repaired_v4_applied_count"],
        "guard_events": result["events"],
        "blocks_anchor_10193_failure_bool": not absorbed_actual,
        "would_emit_wrong_boundary_bool": (
            bool(result["solved"]) and not bool(result["confirmed"])
        ),
        "q_hat": result["q_hat"],
        "boundary_offset": result["boundary_offset"],
    }


def run_probe(
    start_anchor: int,
    small_max_anchor: int,
    large_max_anchor: int,
    focus_anchor: int,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run all candidate guards over the requested surfaces."""
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    small_by_guard = summarize_surface_all_guards(
        start_anchor,
        small_max_anchor,
        candidate_bound,
        witness_bound,
    )
    large_by_guard = summarize_surface_all_guards(
        start_anchor,
        large_max_anchor,
        candidate_bound,
        witness_bound,
    )
    for guard_name in GUARD_NAMES:
        focus = focused_anchor_result(
            guard_name,
            focus_anchor,
            candidate_bound,
            witness_bound,
        )
        small = small_by_guard[guard_name]
        large = large_by_guard[guard_name]
        viable = (
            bool(focus["blocks_anchor_10193_failure_bool"])
            and int(small["audit_failed_count_if_integrated"]) == 0
            and int(large["audit_failed_count_if_integrated"]) == 0
            and (
                int(small["solved_count_if_integrated"])
                > int(small["baseline_v3_solved_count"])
                or int(large["solved_count_if_integrated"])
                > int(large["baseline_v3_solved_count"])
            )
        )
        rows.append(
            {
                "guard_name": guard_name,
                "blocks_anchor_10193_failure_bool": focus[
                    "blocks_anchor_10193_failure_bool"
                ],
                "focus_anchor_result": focus,
                "allowed_v4_absorptions_11_10k": small["allowed_v4_absorptions"],
                "solved_count_11_10k_if_integrated": small[
                    "solved_count_if_integrated"
                ],
                "audit_failed_count_11_10k_if_integrated": small[
                    "audit_failed_count_if_integrated"
                ],
                "allowed_v4_absorptions_11_100k": large["allowed_v4_absorptions"],
                "solved_count_11_100k_if_integrated": large[
                    "solved_count_if_integrated"
                ],
                "audit_failed_count_11_100k_if_integrated": large[
                    "audit_failed_count_if_integrated"
                ],
                "first_failure_if_any": (
                    large["first_failure_if_any"] or small["first_failure_if_any"]
                ),
                "baseline_v3_solved_count_11_10k": small[
                    "baseline_v3_solved_count"
                ],
                "baseline_v3_solved_count_11_100k": large[
                    "baseline_v3_solved_count"
                ],
                "small_surface": small,
                "large_surface": large,
                "viable_guard_bool": viable,
            }
        )
    viable_guards = [row["guard_name"] for row in rows if row["viable_guard_bool"]]
    summary = {
        "mode": "offline_graph_v4_repair_guard_probe",
        "candidate_repaired_relation": (
            "unresolved_later_domination_target_no_carrier_"
            "with_positive_nonboundary_guard"
        ),
        "start_anchor": start_anchor,
        "small_surface": f"{start_anchor}..{small_max_anchor}",
        "large_surface": f"{start_anchor}..{large_max_anchor}",
        "focus_anchor": focus_anchor,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "guard_names": list(GUARD_NAMES),
        "guard_results": rows,
        "viable_guard_names": viable_guards,
        "recommended_guard": viable_guards[0] if viable_guards else None,
        "graph_v4_v5_quarantine_status": (
            "quarantined_outside_last_clean_surface_11_10000"
        ),
        "pure_emission_added": False,
        "solver_rules_changed": False,
        "production_approved": False,
        "cryptographic_use_approved": False,
        "classical_labels_status": "reporting_only_after_candidate_guard_action",
        "runtime_seconds": time.perf_counter() - started,
    }
    return rows, summary


def write_artifacts(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated repair-guard probe artifacts."""
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
    """Run the graph v4 repair-guard probe."""
    args = build_parser().parse_args(argv)
    rows, summary = run_probe(
        start_anchor=args.start_anchor,
        small_max_anchor=args.small_max_anchor,
        large_max_anchor=args.large_max_anchor,
        focus_anchor=args.focus_anchor,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(rows, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

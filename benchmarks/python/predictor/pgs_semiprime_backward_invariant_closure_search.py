#!/usr/bin/env python3
"""Search modulus-specific invariant closure laws after a fixed backward lane entry precondition."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
PREDICTOR_DIR = Path(__file__).resolve().parent
for path in (SOURCE_DIR, PREDICTOR_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pgs_semiprime_backward_law_search as lane_base
import pgs_semiprime_backward_layered_hybrid_entry_law_search as entry_base


DEFAULT_OUTPUT_DIR = ROOT / "output" / "semiprime_branch"
DEFAULT_MAX_N = 5_000
DEFAULT_MAX_STEPS = 24
SUMMARY_FILENAME = "pgs_semiprime_backward_invariant_closure_search_summary.json"
ENTRY_LAW = "layered_hybrid_exact_shape_entry_switch"
INVARIANT_LAW_ORDER = (
    "containing_gap_mod_n",
    "containing_gap_mod_entry",
    "prev_plus_containing_mod_n",
    "prev_plus_containing_mod_entry",
    "left_offset_mod_n",
    "left_offset_mod_entry",
    "right_offset_mod_n",
    "containing_winner_mod_n",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Search modulus-specific invariant closure laws after a fixed backward lane entry precondition.",
    )
    parser.add_argument(
        "--max-n",
        type=int,
        default=DEFAULT_MAX_N,
        help="Largest odd distinct semiprime N included in the toy corpus.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum closure steps per modulus after the fixed entry step.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the summary JSON artifact.",
    )
    return parser


def cyclic_distance(a: int, b: int, modulus: int) -> int:
    """Return the cyclic distance between two residues on one modulus."""
    delta = abs((a - b) % modulus)
    return min(delta, modulus - delta)


def invariant_state(modulus: int) -> dict[str, int | None]:
    """Return the fixed modulus-side invariant ingredients around N."""
    summary = lane_base.orient_anchor(modulus)
    previous_gap = next(gap for gap in summary["gaps"] if str(gap["role"]) == "previous")
    containing_gap = next(gap for gap in summary["gaps"] if str(gap["role"]) == "containing")
    following_gap = next(gap for gap in summary["gaps"] if str(gap["role"]) == "following")
    return {
        "containing_gap": int(containing_gap["gap_width"]),
        "prev_plus_containing": int(previous_gap["gap_width"]) + int(containing_gap["gap_width"]),
        "left_offset": int(containing_gap["anchor_offset_from_left"]),
        "right_offset": int(containing_gap["anchor_offset_from_right"]),
        "containing_winner": (
            None if containing_gap["winner_offset"] is None else int(containing_gap["winner_offset"])
        ),
        "following_gap": int(following_gap["gap_width"]),
    }


def invariant_target(law_id: str, modulus: int, entry_anchor: int, state: dict[str, int | None]) -> tuple[int, int] | None:
    """Return the searched modulus/remainder pair for one invariant law."""
    if law_id == "containing_gap_mod_n":
        modulus_value = state["containing_gap"]
        return modulus_value, modulus % modulus_value
    if law_id == "containing_gap_mod_entry":
        modulus_value = state["containing_gap"]
        return modulus_value, entry_anchor % modulus_value
    if law_id == "prev_plus_containing_mod_n":
        modulus_value = state["prev_plus_containing"]
        return modulus_value, modulus % modulus_value
    if law_id == "prev_plus_containing_mod_entry":
        modulus_value = state["prev_plus_containing"]
        return modulus_value, entry_anchor % modulus_value
    if law_id == "left_offset_mod_n":
        modulus_value = state["left_offset"]
        return None if modulus_value <= 1 else (modulus_value, modulus % modulus_value)
    if law_id == "left_offset_mod_entry":
        modulus_value = state["left_offset"]
        return None if modulus_value <= 1 else (modulus_value, entry_anchor % modulus_value)
    if law_id == "right_offset_mod_n":
        modulus_value = state["right_offset"]
        return None if modulus_value <= 1 else (modulus_value, modulus % modulus_value)
    if law_id == "containing_winner_mod_n":
        modulus_value = state["containing_winner"]
        return None if modulus_value is None or modulus_value <= 1 else (modulus_value, modulus % modulus_value)
    raise ValueError(f"unknown invariant law: {law_id}")


def rank_candidate(candidate: dict[str, object], modulus_value: int, target_remainder: int) -> tuple[object, ...]:
    """Return the invariant-preservation ranking key for one closure candidate."""
    candidate_n = int(candidate["n"])
    return (
        cyclic_distance(candidate_n, target_remainder, modulus_value),
        0 if str(candidate["kind"]) == "odd_semiprime" else 1,
        0 if bool(candidate["is_first_d4"]) else 1,
        0 if bool(candidate["is_gwr_winner"]) else 1,
        int(candidate["gap_width"]),
        -(int(candidate["offset"]) if candidate["offset"] is not None else -1),
        candidate_n,
    )


def run_case(law_id: str, modulus: int, max_steps: int) -> list[dict[str, object]]:
    """Run one deterministic invariant-closure trace for one modulus."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    left_factor, right_factor = lane_base.factor_pair(modulus)
    start_summary = lane_base.orient_anchor(modulus)
    start_candidates = lane_base.build_candidate_pool(start_summary, modulus, {modulus})
    odd_candidates = [candidate for candidate in start_candidates if str(candidate["kind"]) == "odd_semiprime"]

    if not odd_candidates:
        return [
            {
                "law_id": law_id,
                "n": modulus,
                "step": 0,
                "phase": "entry",
                "current_anchor": modulus,
                "selected_anchor": None,
                "factor_reach": False,
                "stop_reason": "no_entry_candidate",
            }
        ]

    entry_candidate = entry_base.select_entry_candidate(ENTRY_LAW, odd_candidates)
    lane_factors = sorted(lane_base.odd_candidate_lane_factors(entry_candidate, left_factor, right_factor))
    if not lane_factors:
        return [
            {
                "law_id": law_id,
                "n": modulus,
                "step": 0,
                "phase": "entry",
                "current_anchor": modulus,
                "selected_anchor": int(entry_candidate["n"]),
                "factor_reach": False,
                "stop_reason": "entry_not_lane",
            }
        ]

    state = invariant_state(modulus)
    target = invariant_target(law_id, modulus, int(entry_candidate["n"]), state)
    if target is None:
        return [
            {
                "law_id": law_id,
                "n": modulus,
                "step": 0,
                "phase": "entry",
                "current_anchor": modulus,
                "selected_anchor": int(entry_candidate["n"]),
                "factor_reach": False,
                "stop_reason": "invariant_undefined",
            }
        ]

    modulus_value, target_remainder = target
    current_anchor = int(entry_candidate["n"])
    visited = {modulus, current_anchor}
    trace_rows: list[dict[str, object]] = [
        {
            "law_id": law_id,
            "n": modulus,
            "step": 0,
            "phase": "entry",
            "current_anchor": modulus,
            "selected_anchor": current_anchor,
            "factor_reach": False,
            "stop_reason": None,
        }
    ]

    for step in range(1, max_steps + 1):
        summary = lane_base.orient_anchor(current_anchor)
        candidates = lane_base.build_candidate_pool(summary, current_anchor, visited)
        if not candidates:
            trace_rows.append(
                {
                    "law_id": law_id,
                    "n": modulus,
                    "step": step,
                    "phase": "closure",
                    "current_anchor": current_anchor,
                    "selected_anchor": None,
                    "factor_reach": False,
                    "stop_reason": "no_candidate",
                }
            )
            return trace_rows

        selected = min(
            candidates,
            key=lambda candidate: rank_candidate(candidate, modulus_value, target_remainder),
        )
        row = {
            "law_id": law_id,
            "n": modulus,
            "step": step,
            "phase": "closure",
            "current_anchor": current_anchor,
            "selected_anchor": int(selected["n"]),
            "factor_reach": False,
            "stop_reason": None,
        }

        if str(selected["kind"]) == "prime_boundary":
            row["factor_reach"] = int(selected["n"]) in (left_factor, right_factor)
            row["stop_reason"] = "factor_reach_terminal_prime" if row["factor_reach"] else "terminal_prime_miss"
            trace_rows.append(row)
            return trace_rows

        current_anchor = int(selected["n"])
        visited.add(current_anchor)
        trace_rows.append(row)

    trace_rows.append(
        {
            "law_id": law_id,
            "n": modulus,
            "step": max_steps + 1,
            "phase": "closure",
            "current_anchor": current_anchor,
            "selected_anchor": None,
            "factor_reach": False,
            "stop_reason": "max_steps_exhausted",
        }
    )
    return trace_rows


def summarize_trace(trace_rows: list[dict[str, object]]) -> dict[str, object]:
    """Return the terminal payload for one invariant-closure trace."""
    final_row = trace_rows[-1]
    return {
        "entry_lane": trace_rows[0]["stop_reason"] is None,
        "factor_reach": bool(final_row["factor_reach"]),
        "stop_reason": str(final_row["stop_reason"]),
        "step_count": len(trace_rows) - 1,
        "selected_anchor": final_row["selected_anchor"],
    }


def run_search(max_n: int, max_steps: int) -> dict[str, object]:
    """Run the invariant-closure law family over the toy corpus."""
    corpus = lane_base.generate_toy_corpus(max_n)
    traces_by_law: dict[str, list[dict[str, object]]] = {law_id: [] for law_id in INVARIANT_LAW_ORDER}

    for law_id in INVARIANT_LAW_ORDER:
        for modulus in corpus:
            trace = run_case(law_id, modulus, max_steps=max_steps)
            traces_by_law[law_id].append(summarize_trace(trace))

    law_summaries: dict[str, dict[str, object]] = {}
    best_law = INVARIANT_LAW_ORDER[0]
    best_factor_reach_count = -1
    entry_lane_count = 0
    if INVARIANT_LAW_ORDER:
        entry_lane_count = sum(int(bool(item["entry_lane"])) for item in traces_by_law[INVARIANT_LAW_ORDER[0]])

    for law_id in INVARIANT_LAW_ORDER:
        traces = traces_by_law[law_id]
        factor_reach_count = sum(int(bool(item["factor_reach"])) for item in traces)
        factor_steps = [int(item["step_count"]) for item in traces if bool(item["factor_reach"])]
        failure_reason_counts: dict[str, int] = {}
        for item in traces:
            if bool(item["factor_reach"]):
                continue
            stop_reason = str(item["stop_reason"])
            failure_reason_counts[stop_reason] = failure_reason_counts.get(stop_reason, 0) + 1
        first_factor_case = next(
            (int(corpus[index]) for index, item in enumerate(traces) if bool(item["factor_reach"])),
            None,
        )
        law_summaries[law_id] = {
            "factor_reach_count": factor_reach_count,
            "factor_reach_recall": (factor_reach_count / len(corpus)) if corpus else 0.0,
            "first_factor_case": first_factor_case,
            "median_steps_on_factor_reach": (
                float(statistics.median(factor_steps)) if factor_steps else None
            ),
            "failure_reason_counts": failure_reason_counts,
        }
        if factor_reach_count > best_factor_reach_count:
            best_factor_reach_count = factor_reach_count
            best_law = law_id

    return {
        "max_n": max_n,
        "case_count": len(corpus),
        "max_steps": max_steps,
        "fixed_entry_law": ENTRY_LAW,
        "entry_lane_count": entry_lane_count,
        "invariant_law_summaries": law_summaries,
        "best_law": best_law,
        "best_factor_reach_count": max(best_factor_reach_count, 0),
        "searched_family_falsified": max(best_factor_reach_count, 0) == 0,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the invariant-closure search and emit its summary JSON."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summary = run_search(max_n=args.max_n, max_steps=args.max_steps)
    summary_path = args.output_dir / SUMMARY_FILENAME
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Search two-step-memory pure-PGS transition laws on the toy semiprime lane surface."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
PREDICTOR_DIR = Path(__file__).resolve().parent
for path in (SOURCE_DIR, PREDICTOR_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import pgs_semiprime_backward_law_search as lane_base
import pgs_semiprime_backward_transition_law_search as one_step_base


DEFAULT_OUTPUT_DIR = ROOT / "output" / "semiprime_branch"
DEFAULT_MAX_N = 5_000
DEFAULT_MAX_STEPS = 24
SUMMARY_FILENAME = "pgs_semiprime_backward_two_step_transition_law_search_summary.json"

ENTRY_LAWS: dict[str, tuple[str, ...]] = {
    "winner_large_offset": ("winner", "role_prev", "large_offset", "small_n"),
    "small_gap_d4_large_offset": ("role_prev", "small_gap", "d4", "large_offset", "small_n"),
}

CONTINUATION_LAWS: dict[str, tuple[str, ...]] = {
    "repeat_role_repeat_offset": (
        "same_role",
        "same_offset_class",
        "winner",
        "large_offset",
        "small_n",
    ),
    "same_gap_change_repeat_offset": (
        "same_gap_change",
        "same_offset_class",
        "winner",
        "large_offset",
        "small_n",
    ),
    "repeat_role_gap_change": (
        "same_role",
        "same_gap_change",
        "d4",
        "large_offset",
        "small_n",
    ),
    "match_two_role_chain": (
        "repeat_previous_role_pattern",
        "d4",
        "large_offset",
        "small_n",
    ),
    "flip_after_repeat": (
        "flip_after_repeat",
        "d4",
        "large_offset",
        "small_n",
    ),
}

CLOSURE_LAWS: dict[str, tuple[str, ...]] = {
    "same_role_p_left": ("same_role", "p_left_first", "small_n"),
    "after_repeated_same_role_p_left": ("after_repeated_same_role", "p_left_first", "small_n"),
    "after_role_flip_p_left": ("after_role_flip", "p_left_first", "small_n"),
    "after_repeated_same_offset_p_left": ("after_repeated_same_offset", "p_left_first", "small_n"),
    "after_narrowing_p_prev": ("after_narrowing", "p_prev_first", "small_n"),
}

TWO_STEP_LAW_ORDER = tuple(
    f"{entry_id}__{continuation_id}__{closure_id}"
    for entry_id in ENTRY_LAWS
    for continuation_id in CONTINUATION_LAWS
    for closure_id in CLOSURE_LAWS
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Search two-step-memory pure-PGS transition laws on the toy semiprime lane surface.",
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
        help="Maximum backward steps per two-step transition-law trace.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the summary JSON artifact.",
    )
    return parser


def offset_class(offset: int | None) -> str:
    """Return the coarse offset class for one selected odd-semiprime carrier."""
    return one_step_base.offset_class(offset)


def gap_change(previous_gap_width: int | None, current_gap_width: int) -> str:
    """Return the coarse gap-width change class."""
    if previous_gap_width is None:
        return "start"
    if current_gap_width < previous_gap_width:
        return "narrower"
    if current_gap_width > previous_gap_width:
        return "wider"
    return "same"


@lru_cache(maxsize=None)
def cached_orient_anchor(anchor: int) -> dict[str, object]:
    """Return one cached exact three-gap neighborhood."""
    return lane_base.orient_anchor(anchor)


@lru_cache(maxsize=None)
def cached_candidate_universe(anchor: int) -> tuple[dict[str, object], ...]:
    """Return the full local candidate universe before visited filtering."""
    summary = cached_orient_anchor(anchor)
    return tuple(lane_base.build_candidate_pool(summary, anchor, set()))


def two_step_state(history: list[dict[str, object]]) -> dict[str, object] | None:
    """Return the current two-step memory state from the selected odd-semiprime history."""
    if not history:
        return None
    last = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    return {
        "role1": last["role"],
        "role2": None if previous is None else previous["role"],
        "offset1": last["offset_class"],
        "offset2": None if previous is None else previous["offset_class"],
        "gap1": last["gap_width"],
        "gap2": None if previous is None else previous["gap_width"],
        "gap_change1": gap_change(None if previous is None else previous["gap_width"], last["gap_width"]),
        "repeated_same_role": bool(previous is not None and previous["role"] == last["role"]),
        "role_flip": bool(previous is not None and previous["role"] != last["role"]),
        "repeated_same_offset": bool(previous is not None and previous["offset_class"] == last["offset_class"]),
    }


def compact_gap_snapshot(gap: dict[str, object]) -> dict[str, object]:
    """Return one compact gap record for trace-like step summaries."""
    return lane_base.compact_gap_snapshot(gap)


def parse_two_step_law_id(law_id: str) -> tuple[str, str, str]:
    """Split one two-step law identifier into entry, continuation, and closure ids."""
    entry_id, continuation_id, closure_id = law_id.split("__")
    return entry_id, continuation_id, closure_id


def feature_key(token: str, candidate: dict[str, object], state: dict[str, object] | None) -> object:
    """Return one ranking feature for the two-step family."""
    if token == "winner":
        return 0 if bool(candidate["is_gwr_winner"]) else 1
    if token == "d4":
        return 0 if bool(candidate["is_first_d4"]) else 1
    if token == "role_prev":
        return lane_base.role_priority(str(candidate["role"]))
    if token == "large_offset":
        return -(int(candidate["offset"]) if candidate["offset"] is not None else -1)
    if token == "small_n":
        return int(candidate["n"])
    if token == "small_gap":
        return int(candidate["gap_width"])
    if token == "same_role":
        return 0 if state is not None and str(candidate["role"]) == state["role1"] else 1
    if token == "same_offset_class":
        return 0 if state is not None and offset_class(candidate["offset"]) == state["offset1"] else 1
    if token == "same_gap_change":
        current_gap_change = gap_change(None if state is None else state["gap1"], int(candidate["gap_width"]))
        return 0 if state is not None and current_gap_change == state["gap_change1"] else 1
    if token == "repeat_previous_role_pattern":
        return 0 if state is not None and state["role2"] is not None and state["role1"] == state["role2"] else 1
    if token == "flip_after_repeat":
        return 0 if state is not None and state["repeated_same_role"] and str(candidate["role"]) != state["role1"] else 1
    if token == "p_left_first":
        return 0 if candidate["boundary_kind"] == "p_left" else 1
    if token == "p_prev_first":
        return 0 if candidate["boundary_kind"] == "p_prev" else 1
    if token == "after_repeated_same_role":
        return 0 if state is not None and state["repeated_same_role"] else 1
    if token == "after_role_flip":
        return 0 if state is not None and state["role_flip"] else 1
    if token == "after_repeated_same_offset":
        return 0 if state is not None and state["repeated_same_offset"] else 1
    if token == "after_narrowing":
        return 0 if state is not None and state["gap_change1"] == "narrower" else 1
    raise ValueError(f"unsupported two-step feature {token}")


def select_entry_candidate(entry_id: str, odd_candidates: list[dict[str, object]]) -> dict[str, object]:
    """Return the selected odd-semiprime entry candidate."""
    tokens = ENTRY_LAWS[entry_id]
    return min(
        odd_candidates,
        key=lambda candidate: tuple(feature_key(token, candidate, None) for token in tokens),
    )


def select_continuation_candidate(
    continuation_id: str,
    odd_candidates: list[dict[str, object]],
    state: dict[str, object],
) -> dict[str, object]:
    """Return the selected odd-semiprime continuation candidate."""
    tokens = CONTINUATION_LAWS[continuation_id]
    return min(
        odd_candidates,
        key=lambda candidate: tuple(feature_key(token, candidate, state) for token in tokens),
    )


def select_closure_candidate(
    closure_id: str,
    prime_candidates: list[dict[str, object]],
    state: dict[str, object] | None,
) -> dict[str, object]:
    """Return the selected prime-boundary closure nominee."""
    tokens = CLOSURE_LAWS[closure_id]
    return min(
        prime_candidates,
        key=lambda candidate: tuple(feature_key(token, candidate, state) for token in tokens),
    )


def closure_condition_matched(
    closure_id: str,
    candidate: dict[str, object],
    state: dict[str, object] | None,
) -> bool:
    """Return whether the dedicated two-step closure pattern is active."""
    if state is None:
        return True
    if closure_id == "same_role_p_left":
        return str(candidate["role"]) == state["role1"]
    if closure_id == "after_repeated_same_role_p_left":
        return state["repeated_same_role"]
    if closure_id == "after_role_flip_p_left":
        return state["role_flip"]
    if closure_id == "after_repeated_same_offset_p_left":
        return state["repeated_same_offset"]
    if closure_id == "after_narrowing_p_prev":
        return state["gap_change1"] == "narrower" and candidate["boundary_kind"] == "p_prev"
    raise ValueError(f"unsupported two-step closure law {closure_id}")


def selected_history_row(candidate: dict[str, object]) -> dict[str, object]:
    """Return the retained history row from one selected odd-semiprime carrier."""
    return {
        "role": str(candidate["role"]),
        "offset_class": offset_class(candidate["offset"]),
        "gap_width": int(candidate["gap_width"]),
    }


def run_case(law_id: str, modulus: int, max_steps: int) -> list[dict[str, object]]:
    """Run one deterministic two-step-memory transition trace."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    entry_id, continuation_id, closure_id = parse_two_step_law_id(law_id)
    left_factor, right_factor = lane_base.factor_pair(modulus)
    trace_rows: list[dict[str, object]] = []
    current_anchor = modulus
    visited = {modulus}
    lane_factor: int | None = None
    history: list[dict[str, object]] = []

    for step in range(1, max_steps + 1):
        summary = cached_orient_anchor(current_anchor)
        candidates = [
            dict(candidate)
            for candidate in cached_candidate_universe(current_anchor)
            if int(candidate["n"]) not in visited and int(candidate["n"]) < current_anchor
        ]
        odd_candidates = [candidate for candidate in candidates if str(candidate["kind"]) == "odd_semiprime"]
        prime_candidates = [candidate for candidate in candidates if str(candidate["kind"]) == "prime_boundary"]
        state = two_step_state(history)

        selected = None
        phase = None
        stop_reason = None
        lane_success = False
        factor_reach = False
        next_lane_factor = lane_factor

        if lane_factor is None:
            phase = "entry"
            if odd_candidates:
                selected = select_entry_candidate(entry_id, odd_candidates)
                selected_lane_factors = sorted(
                    lane_base.odd_candidate_lane_factors(selected, left_factor, right_factor)
                )
                if not selected_lane_factors:
                    stop_reason = "not_odd_semiprime_lane"
                else:
                    next_lane_factor = int(selected_lane_factors[0])
            elif prime_candidates:
                selected = select_closure_candidate(closure_id, prime_candidates, state)
                stop_reason = "terminal_prime_nominee"
                if int(selected["n"]) in (left_factor, right_factor):
                    lane_success = True
                    factor_reach = True
            else:
                stop_reason = "no_candidate"
        else:
            best_prime = None
            if prime_candidates:
                best_prime = select_closure_candidate(closure_id, prime_candidates, state)
            if best_prime is not None and closure_condition_matched(closure_id, best_prime, state):
                phase = "closure"
                selected = best_prime
                stop_reason = "lane_success_terminal_prime"
                lane_success = True
                if int(selected["n"]) == lane_factor:
                    factor_reach = True
            elif odd_candidates:
                phase = "continuation"
                selected = select_continuation_candidate(continuation_id, odd_candidates, state)
                selected_lane_factors = sorted(
                    lane_base.odd_candidate_lane_factors(selected, left_factor, right_factor)
                )
                if lane_factor not in selected_lane_factors:
                    stop_reason = "lane_broken"
            elif best_prime is not None:
                phase = "closure"
                selected = best_prime
                stop_reason = "lane_success_terminal_prime"
                lane_success = True
                if int(selected["n"]) == lane_factor:
                    factor_reach = True
            else:
                phase = "closure"
                stop_reason = "lane_success_terminal_no_candidate"
                lane_success = True

        selected_lane_factors = (
            []
            if selected is None or str(selected["kind"]) != "odd_semiprime"
            else sorted(lane_base.odd_candidate_lane_factors(selected, left_factor, right_factor))
        )
        row = {
            "law_id": law_id,
            "entry_law": entry_id,
            "continuation_law": continuation_id,
            "closure_law": closure_id,
            "n": modulus,
            "step": step,
            "phase": phase,
            "current_anchor": current_anchor,
            "selected_anchor": None if selected is None else int(selected["n"]),
            "selected_kind": None if selected is None else str(selected["kind"]),
            "selected_role": None if selected is None else str(selected["role"]),
            "selected_boundary_kind": None if selected is None else selected["boundary_kind"],
            "selected_is_gwr_winner": None if selected is None else bool(selected["is_gwr_winner"]),
            "selected_is_first_d4": None if selected is None else bool(selected["is_first_d4"]),
            "selected_offset": None if selected is None else selected["offset"],
            "selected_gap_width": None if selected is None else int(selected["gap_width"]),
            "selected_lane_factors": selected_lane_factors,
            "candidate_count": len(candidates),
            "odd_candidate_count": len(odd_candidates),
            "prime_candidate_count": len(prime_candidates),
            "prev_role_1": None if state is None else state["role1"],
            "prev_role_2": None if state is None else state["role2"],
            "prev_offset_class_1": None if state is None else state["offset1"],
            "prev_offset_class_2": None if state is None else state["offset2"],
            "prev_gap_width_1": None if state is None else state["gap1"],
            "prev_gap_width_2": None if state is None else state["gap2"],
            "prev_gap_change_1": None if state is None else state["gap_change1"],
            "prev_repeated_same_role": None if state is None else state["repeated_same_role"],
            "prev_role_flip": None if state is None else state["role_flip"],
            "lane_factor": next_lane_factor,
            "lane_success": lane_success,
            "factor_reach": factor_reach,
            "stop_reason": stop_reason,
            "gaps": [compact_gap_snapshot(gap) for gap in summary["gaps"]],
        }
        trace_rows.append(row)

        if stop_reason is not None:
            return trace_rows

        visited.add(int(selected["n"]))
        current_anchor = int(selected["n"])
        lane_factor = next_lane_factor
        history.append(selected_history_row(selected))
        history = history[-2:]

    trace_rows[-1]["stop_reason"] = "lane_success_exhausted" if lane_factor is not None else "max_steps_exhausted"
    trace_rows[-1]["lane_success"] = lane_factor is not None
    trace_rows[-1]["lane_factor"] = lane_factor
    return trace_rows


def summarize_trace(trace_rows: list[dict[str, object]]) -> dict[str, object]:
    """Return the terminal payload for one two-step transition trace."""
    final_row = trace_rows[-1]
    return {
        "lane_success": bool(final_row["lane_success"]),
        "factor_reach": bool(final_row["factor_reach"]),
        "stop_reason": str(final_row["stop_reason"]),
        "step_count": len(trace_rows),
        "selected_anchor": final_row["selected_anchor"],
        "lane_factor": final_row["lane_factor"],
    }


def run_search(max_n: int, max_steps: int) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Run the fixed two-step-memory transition-law family over the toy corpus."""
    corpus = lane_base.generate_toy_corpus(max_n)
    trace_rows: list[dict[str, object]] = []
    traces_by_law: dict[str, list[dict[str, object]]] = {law_id: [] for law_id in TWO_STEP_LAW_ORDER}

    for law_id in TWO_STEP_LAW_ORDER:
        for modulus in corpus:
            trace = run_case(law_id, modulus, max_steps=max_steps)
            trace_rows.extend(trace)
            traces_by_law[law_id].append(summarize_trace(trace))

    law_summaries: dict[str, dict[str, object]] = {}
    best_law = TWO_STEP_LAW_ORDER[0]
    best_lane_success_count = -1
    best_factor_reach_count = -1
    for law_id in TWO_STEP_LAW_ORDER:
        traces = traces_by_law[law_id]
        lane_success_count = sum(int(bool(item["lane_success"])) for item in traces)
        factor_reach_count = sum(int(bool(item["factor_reach"])) for item in traces)
        lane_steps = [int(item["step_count"]) for item in traces if bool(item["lane_success"])]
        failure_reason_counts: dict[str, int] = {}
        for item in traces:
            if bool(item["lane_success"]):
                continue
            stop_reason = str(item["stop_reason"])
            failure_reason_counts[stop_reason] = failure_reason_counts.get(stop_reason, 0) + 1
        first_lane_case = next(
            (int(corpus[index]) for index, item in enumerate(traces) if bool(item["lane_success"])),
            None,
        )
        law_summaries[law_id] = {
            "entry_law": parse_two_step_law_id(law_id)[0],
            "continuation_law": parse_two_step_law_id(law_id)[1],
            "closure_law": parse_two_step_law_id(law_id)[2],
            "lane_success_count": lane_success_count,
            "lane_success_recall": (lane_success_count / len(corpus)) if corpus else 0.0,
            "factor_reach_count": factor_reach_count,
            "factor_reach_recall": (factor_reach_count / len(corpus)) if corpus else 0.0,
            "first_lane_case": first_lane_case,
            "median_steps_on_lane_success": (
                float(statistics.median(lane_steps)) if lane_steps else None
            ),
            "failure_reason_counts": failure_reason_counts,
        }
        if (lane_success_count, factor_reach_count) > (best_lane_success_count, best_factor_reach_count):
            best_lane_success_count = lane_success_count
            best_factor_reach_count = factor_reach_count
            best_law = law_id

    baseline_summary = json.loads(
        (DEFAULT_OUTPUT_DIR / one_step_base.SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    baseline_best = int(baseline_summary["best_lane_success_count"])
    improvement_over_baseline = max(best_lane_success_count, 0) - baseline_best

    summary = {
        "max_n": max_n,
        "case_count": len(corpus),
        "max_steps": max_steps,
        "memory_fields": [
            "prev_role_1",
            "prev_role_2",
            "prev_offset_class_1",
            "prev_offset_class_2",
            "prev_gap_width_1",
            "prev_gap_width_2",
            "prev_gap_change_1",
            "prev_repeated_same_role",
            "prev_role_flip",
        ],
        "entry_laws": ENTRY_LAWS,
        "continuation_laws": CONTINUATION_LAWS,
        "closure_laws": CLOSURE_LAWS,
        "law_count": len(TWO_STEP_LAW_ORDER),
        "law_summaries": law_summaries,
        "best_law": best_law,
        "best_lane_success_count": max(best_lane_success_count, 0),
        "best_factor_reach_count": max(best_factor_reach_count, 0),
        "baseline_best_lane_success_count": baseline_best,
        "improvement_over_baseline": improvement_over_baseline,
        "searched_family_falsified": max(best_lane_success_count, 0) == 0,
    }
    return trace_rows, summary


def main(argv: list[str] | None = None) -> int:
    """Run the two-step transition-law search harness and emit the summary JSON."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    _trace_rows, summary = run_search(max_n=args.max_n, max_steps=args.max_steps)
    summary_path = args.output_dir / SUMMARY_FILENAME
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

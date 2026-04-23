#!/usr/bin/env python3
"""Search one-step-memory pure-PGS transition laws on the toy semiprime lane surface."""

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


DEFAULT_OUTPUT_DIR = ROOT / "output" / "semiprime_branch"
DEFAULT_MAX_N = 5_000
DEFAULT_MAX_STEPS = 24
TRACE_FILENAME = "pgs_semiprime_backward_transition_law_search_trace.jsonl"
SUMMARY_FILENAME = "pgs_semiprime_backward_transition_law_search_summary.json"

ENTRY_LAWS: dict[str, tuple[str, ...]] = {
    "winner_large_offset": ("winner", "role_prev", "large_offset", "small_n"),
    "d4_large_offset": ("d4", "role_prev", "large_offset", "small_n"),
    "dmin_large_offset": ("dmin", "role_prev", "large_offset", "small_n"),
    "small_gap_d4_large_offset": ("role_prev", "small_gap", "d4", "large_offset", "small_n"),
}

CONTINUATION_LAWS: dict[str, tuple[str, ...]] = {
    "same_role_same_offset_winner": (
        "same_role",
        "same_offset_class",
        "winner",
        "large_offset",
        "small_n",
    ),
    "same_role_same_gap_winner": (
        "same_role",
        "same_gap_width",
        "winner",
        "large_offset",
        "small_n",
    ),
    "same_offset_d4_large_offset": (
        "same_offset_class",
        "d4",
        "large_offset",
        "small_n",
    ),
    "same_gap_d4_large_offset": (
        "same_gap_width",
        "d4",
        "large_offset",
        "small_n",
    ),
    "same_role_deeper_offset": (
        "same_role",
        "deeper_offset_class",
        "large_offset",
        "small_n",
    ),
    "flip_role_same_gap": (
        "flip_role",
        "same_gap_width",
        "d4",
        "large_offset",
        "small_n",
    ),
}

CLOSURE_LAWS: dict[str, tuple[str, ...]] = {
    "same_role_p_left": ("same_role", "p_left_first", "small_n"),
    "flip_role_p_left": ("flip_role", "p_left_first", "small_n"),
    "same_role_p_prev": ("same_role", "p_prev_first", "small_n"),
    "p_left_only": ("p_left_first", "small_n"),
}

TRANSITION_LAW_ORDER = tuple(
    f"{entry_id}__{continuation_id}__{closure_id}"
    for entry_id in ENTRY_LAWS
    for continuation_id in CONTINUATION_LAWS
    for closure_id in CLOSURE_LAWS
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Search one-step-memory pure-PGS transition laws on the toy semiprime lane surface.",
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
        help="Maximum backward steps per transition-law trace.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the trace JSONL and summary JSON artifacts.",
    )
    return parser


def offset_class(offset: int | None) -> str:
    """Return the coarse offset class used in one-step transition memory."""
    if offset is None:
        return "prime"
    if offset <= 2:
        return "tight"
    if offset <= 6:
        return "mid"
    return "deep"


@lru_cache(maxsize=None)
def cached_orient_anchor(anchor: int) -> dict[str, object]:
    """Return one cached exact three-gap neighborhood."""
    return lane_base.orient_anchor(anchor)


@lru_cache(maxsize=None)
def cached_candidate_universe(anchor: int) -> tuple[dict[str, object], ...]:
    """Return the full local candidate universe before visited filtering."""
    summary = cached_orient_anchor(anchor)
    return tuple(lane_base.build_candidate_pool(summary, anchor, set()))


def transition_state(candidate: dict[str, object]) -> dict[str, object]:
    """Return the one-step memory payload from one selected odd-semiprime carrier."""
    return {
        "role": str(candidate["role"]),
        "d": 4,
        "gap_width": int(candidate["gap_width"]),
        "offset_class": offset_class(candidate["offset"]),
    }


def role_priority(role: str) -> int:
    """Return the deterministic role order."""
    return lane_base.role_priority(role)


def feature_key(token: str, candidate: dict[str, object], previous_state: dict[str, object] | None) -> object:
    """Return one ranking feature for an entry, continuation, or closure law."""
    if token == "winner":
        return 0 if bool(candidate["is_gwr_winner"]) else 1
    if token == "d4":
        return 0 if bool(candidate["is_first_d4"]) else 1
    if token == "dmin":
        return 0 if bool(candidate["is_first_dmin"]) else 1
    if token == "role_prev":
        return role_priority(str(candidate["role"]))
    if token == "large_offset":
        return -(int(candidate["offset"]) if candidate["offset"] is not None else -1)
    if token == "small_gap":
        return int(candidate["gap_width"])
    if token == "small_n":
        return int(candidate["n"])
    if token == "same_role":
        return 0 if previous_state is not None and str(candidate["role"]) == previous_state["role"] else 1
    if token == "flip_role":
        return 0 if previous_state is not None and str(candidate["role"]) != previous_state["role"] else 1
    if token == "same_gap_width":
        return 0 if previous_state is not None and int(candidate["gap_width"]) == previous_state["gap_width"] else 1
    if token == "same_offset_class":
        return 0 if previous_state is not None and offset_class(candidate["offset"]) == previous_state["offset_class"] else 1
    if token == "deeper_offset_class":
        rank = {"tight": 0, "mid": 1, "deep": 2, "prime": 3}
        current = rank[offset_class(candidate["offset"])]
        previous = rank[previous_state["offset_class"]] if previous_state is not None else 0
        return 0 if current >= previous else 1
    if token == "p_left_first":
        return 0 if candidate["boundary_kind"] == "p_left" else 1
    if token == "p_prev_first":
        return 0 if candidate["boundary_kind"] == "p_prev" else 1
    raise ValueError(f"unsupported transition feature {token}")


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
    previous_state: dict[str, object],
) -> dict[str, object]:
    """Return the selected odd-semiprime continuation candidate."""
    tokens = CONTINUATION_LAWS[continuation_id]
    return min(
        odd_candidates,
        key=lambda candidate: tuple(feature_key(token, candidate, previous_state) for token in tokens),
    )


def select_closure_candidate(
    closure_id: str,
    prime_candidates: list[dict[str, object]],
    previous_state: dict[str, object] | None,
) -> dict[str, object]:
    """Return the selected prime-boundary closure nominee."""
    tokens = CLOSURE_LAWS[closure_id]
    return min(
        prime_candidates,
        key=lambda candidate: tuple(feature_key(token, candidate, previous_state) for token in tokens),
    )


def closure_condition_matched(
    closure_id: str,
    candidate: dict[str, object],
    previous_state: dict[str, object] | None,
) -> bool:
    """Return whether the dedicated odd-semiprime-to-prime closure pattern is active."""
    if previous_state is None:
        return True
    if closure_id == "same_role_p_left":
        return str(candidate["role"]) == previous_state["role"]
    if closure_id == "flip_role_p_left":
        return str(candidate["role"]) != previous_state["role"]
    if closure_id == "same_role_p_prev":
        return (
            str(candidate["role"]) == previous_state["role"]
            and candidate["boundary_kind"] == "p_prev"
        )
    if closure_id == "p_left_only":
        return candidate["boundary_kind"] == "p_left"
    raise ValueError(f"unsupported closure law {closure_id}")


def parse_transition_law_id(law_id: str) -> tuple[str, str, str]:
    """Split one transition-law identifier into entry, continuation, and closure ids."""
    entry_id, continuation_id, closure_id = law_id.split("__")
    return entry_id, continuation_id, closure_id


def compact_gap_snapshot(gap: dict[str, object]) -> dict[str, object]:
    """Return one compact gap record for the trace JSONL."""
    return lane_base.compact_gap_snapshot(gap)


def run_case(law_id: str, modulus: int, max_steps: int) -> list[dict[str, object]]:
    """Run one deterministic one-step-memory transition trace."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    entry_id, continuation_id, closure_id = parse_transition_law_id(law_id)
    left_factor, right_factor = lane_base.factor_pair(modulus)
    trace_rows: list[dict[str, object]] = []
    current_anchor = modulus
    visited = {modulus}
    lane_factor: int | None = None
    previous_state: dict[str, object] | None = None

    for step in range(1, max_steps + 1):
        summary = cached_orient_anchor(current_anchor)
        candidates = [
            dict(candidate)
            for candidate in cached_candidate_universe(current_anchor)
            if int(candidate["n"]) not in visited and int(candidate["n"]) < current_anchor
        ]
        odd_candidates = [candidate for candidate in candidates if str(candidate["kind"]) == "odd_semiprime"]
        prime_candidates = [candidate for candidate in candidates if str(candidate["kind"]) == "prime_boundary"]

        selected = None
        phase = None
        stop_reason = None
        lane_success = False
        factor_reach = False
        next_lane_factor = lane_factor
        next_previous_state = previous_state

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
                    next_previous_state = transition_state(selected)
            elif prime_candidates:
                selected = select_closure_candidate(closure_id, prime_candidates, previous_state)
                stop_reason = "terminal_prime_nominee"
                if int(selected["n"]) in (left_factor, right_factor):
                    lane_success = True
                    factor_reach = True
            else:
                stop_reason = "no_candidate"
                lane_success = False
        else:
            best_prime = None
            if prime_candidates:
                best_prime = select_closure_candidate(closure_id, prime_candidates, previous_state)
            if best_prime is not None and closure_condition_matched(closure_id, best_prime, previous_state):
                phase = "closure"
                selected = best_prime
                stop_reason = "lane_success_terminal_prime"
                lane_success = True
                if int(selected["n"]) == lane_factor:
                    factor_reach = True
            elif odd_candidates:
                phase = "continuation"
                selected = select_continuation_candidate(continuation_id, odd_candidates, previous_state)
                selected_lane_factors = sorted(
                    lane_base.odd_candidate_lane_factors(selected, left_factor, right_factor)
                )
                if lane_factor not in selected_lane_factors:
                    stop_reason = "lane_broken"
                else:
                    next_previous_state = transition_state(selected)
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
            "selected_family": None if selected is None else selected["carrier_family"],
            "selected_is_gwr_winner": None if selected is None else bool(selected["is_gwr_winner"]),
            "selected_is_first_dmin": None if selected is None else bool(selected["is_first_dmin"]),
            "selected_is_first_d4": None if selected is None else bool(selected["is_first_d4"]),
            "selected_offset": None if selected is None else selected["offset"],
            "selected_gap_width": None if selected is None else int(selected["gap_width"]),
            "selected_lane_factors": selected_lane_factors,
            "candidate_count": len(candidates),
            "odd_candidate_count": len(odd_candidates),
            "prime_candidate_count": len(prime_candidates),
            "previous_role": None if previous_state is None else previous_state["role"],
            "previous_d": None if previous_state is None else previous_state["d"],
            "previous_gap_width": None if previous_state is None else previous_state["gap_width"],
            "previous_offset_class": None if previous_state is None else previous_state["offset_class"],
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
        previous_state = next_previous_state

    trace_rows[-1]["stop_reason"] = "lane_success_exhausted" if lane_factor is not None else "max_steps_exhausted"
    trace_rows[-1]["lane_success"] = lane_factor is not None
    trace_rows[-1]["lane_factor"] = lane_factor
    return trace_rows


def summarize_trace(trace_rows: list[dict[str, object]]) -> dict[str, object]:
    """Return the terminal payload for one transition trace."""
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
    """Run the fixed one-step-memory transition-law family over the toy corpus."""
    corpus = lane_base.generate_toy_corpus(max_n)
    trace_rows: list[dict[str, object]] = []
    traces_by_law: dict[str, list[dict[str, object]]] = {law_id: [] for law_id in TRANSITION_LAW_ORDER}

    for law_id in TRANSITION_LAW_ORDER:
        for modulus in corpus:
            trace = run_case(law_id, modulus, max_steps=max_steps)
            trace_rows.extend(trace)
            traces_by_law[law_id].append(summarize_trace(trace))

    law_summaries: dict[str, dict[str, object]] = {}
    best_law = TRANSITION_LAW_ORDER[0]
    best_lane_success_count = -1
    best_factor_reach_count = -1
    for law_id in TRANSITION_LAW_ORDER:
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
            "entry_law": parse_transition_law_id(law_id)[0],
            "continuation_law": parse_transition_law_id(law_id)[1],
            "closure_law": parse_transition_law_id(law_id)[2],
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
        (DEFAULT_OUTPUT_DIR / lane_base.SUMMARY_FILENAME).read_text(encoding="utf-8")
    )
    baseline_best = int(baseline_summary["best_lane_success_count"])
    improvement_over_baseline = max(best_lane_success_count, 0) - baseline_best

    summary = {
        "max_n": max_n,
        "case_count": len(corpus),
        "max_steps": max_steps,
        "memory_fields": [
            "prev_role",
            "prev_d",
            "prev_gap_width",
            "prev_offset_class",
        ],
        "entry_laws": ENTRY_LAWS,
        "continuation_laws": CONTINUATION_LAWS,
        "closure_laws": CLOSURE_LAWS,
        "law_count": len(TRANSITION_LAW_ORDER),
        "law_summaries": law_summaries,
        "best_law": best_law,
        "best_lane_success_count": max(best_lane_success_count, 0),
        "best_factor_reach_count": max(best_factor_reach_count, 0),
        "baseline_best_lane_success_count": baseline_best,
        "improvement_over_baseline": improvement_over_baseline,
        "searched_family_falsified": max(best_lane_success_count, 0) == 0,
    }
    return trace_rows, summary


def write_trace_jsonl(output_path: Path, trace_rows: list[dict[str, object]]) -> None:
    """Write the full per-step transition trace as JSONL."""
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        for row in trace_rows:
            handle.write(json.dumps(row, sort_keys=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run the transition-law search harness and emit artifacts."""
    parser = build_parser()
    args = parser.parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    trace_rows, summary = run_search(max_n=args.max_n, max_steps=args.max_steps)
    trace_path = args.output_dir / TRACE_FILENAME
    summary_path = args.output_dir / SUMMARY_FILENAME
    write_trace_jsonl(trace_path, trace_rows)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

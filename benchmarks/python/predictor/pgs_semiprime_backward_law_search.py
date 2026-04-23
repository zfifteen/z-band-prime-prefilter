#!/usr/bin/env python3
"""Search pure-PGS backward lane laws on a toy odd-semiprime surface."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

import gmpy2
from sympy import primerange


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment
from z_band_prime_predictor import (
    d4_gap_profile,
    divisor_gap_profile,
    gap_dmin,
    gwr_next_gap_profile,
    gwr_next_prime,
    next_prime_after,
)


DEFAULT_OUTPUT_DIR = ROOT / "output" / "semiprime_branch"
DEFAULT_MAX_N = 5_000
DEFAULT_MAX_STEPS = 24
SCAN_BLOCK = 64
MAX_FIELD_VALUE = (1 << 63) - 1 - SCAN_BLOCK
TRACE_FILENAME = "pgs_semiprime_backward_law_search_trace.jsonl"
SUMMARY_FILENAME = "pgs_semiprime_backward_law_search_summary.json"
LAW_ORDER = (
    "prime_left_boundary_control",
    "odd_prev_winner_large_offset",
    "odd_prev_d4_large_offset",
    "odd_prev_dmin_large_offset",
    "odd_prev_small_gap_d4_large_offset",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Search pure-PGS backward lane laws on a toy odd-semiprime surface.",
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
        help="Maximum backward steps per (law, N) trace.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the trace JSONL and summary JSON artifacts.",
    )
    return parser


def validate_anchor(anchor: int) -> None:
    """Validate one composite anchor in the exact field regime."""
    if anchor < 4:
        raise ValueError("anchor must be at least 4")
    if anchor > MAX_FIELD_VALUE:
        raise ValueError(
            f"anchor={anchor} exceeds the current exact divisor-field range {MAX_FIELD_VALUE}"
        )
    if gmpy2.is_prime(anchor):
        raise ValueError("anchor must be composite")


def previous_prime_before(n: int, block: int = SCAN_BLOCK) -> int:
    """Return the largest prime less than or equal to n by exact leftward scan."""
    if n < 2:
        raise ValueError("no prime exists below 2")
    if block < 1:
        raise ValueError("block must be positive")

    search_hi = n + 1
    while search_hi > 2:
        search_lo = max(2, search_hi - block)
        counts = divisor_counts_segment(search_lo, search_hi)
        for index in range(len(counts) - 1, -1, -1):
            if int(counts[index]) == 2:
                return search_lo + index
        search_hi = search_lo

    raise RuntimeError(f"failed to find a prime at or below {n}")


def prime_cube_root(n: int) -> int | None:
    """Return the prime cube root of n when n is exactly p^3."""
    root, exact = gmpy2.iroot(gmpy2.mpz(n), 3)
    if not exact or not gmpy2.is_prime(root):
        return None
    return int(root)


def carrier_family(n: int, divisor_count: int) -> str:
    """Return the coarse carrier family for one exact composite interior value."""
    if divisor_count < 3:
        raise ValueError("divisor_count must describe one composite interior value")
    if divisor_count == 3:
        return "prime_square"
    if divisor_count == 4:
        if prime_cube_root(n) is not None:
            return "prime_cube"
        if n % 2 == 0:
            return "even_semiprime"
        return "odd_semiprime"
    if n % 2 == 0:
        return "higher_divisor_even"
    return "higher_divisor_odd"


def factor_pair(n: int) -> tuple[int, int]:
    """Return the deterministic odd distinct prime factor pair for one toy semiprime."""
    for divisor in range(3, int(math.isqrt(n)) + 1, 2):
        if n % divisor == 0:
            other = n // divisor
            if divisor != other and gmpy2.is_prime(divisor) and gmpy2.is_prime(other):
                return divisor, other
    raise ValueError(f"{n} is not an odd distinct semiprime")


def generate_toy_corpus(max_n: int) -> list[int]:
    """Return all odd distinct semiprimes up to one deterministic cutoff."""
    if max_n < 15:
        return []

    odd_primes = [prime for prime in primerange(3, max_n + 1)]
    corpus: list[int] = []
    for index, left_prime in enumerate(odd_primes):
        for right_prime in odd_primes[index + 1 :]:
            n = left_prime * right_prime
            if n > max_n:
                break
            corpus.append(n)
    corpus.sort()
    return corpus


def _interior_rows(left_prime: int, right_prime: int, winner: int | None) -> list[dict[str, object]]:
    """Return the full exact interior table for one prime gap."""
    if right_prime - left_prime <= 1:
        return []

    values = list(range(left_prime + 1, right_prime))
    counts = divisor_counts_segment(left_prime + 1, right_prime)
    dmin = min(int(raw_d) for raw_d in counts)
    first_dmin = None
    first_d4 = None
    for value, raw_d in zip(values, counts):
        d = int(raw_d)
        if first_dmin is None and d == dmin:
            first_dmin = value
        if first_d4 is None and d == 4:
            first_d4 = value

    rows: list[dict[str, object]] = []
    for value, raw_d in zip(values, counts):
        d = int(raw_d)
        rows.append(
            {
                "n": value,
                "offset": value - left_prime,
                "d": d,
                "L": (1.0 - d / 2.0) * math.log(value),
                "carrier_family": carrier_family(value, d),
                "is_gwr_winner": value == winner,
                "is_first_dmin": value == first_dmin,
                "is_first_d4": value == first_d4,
            }
        )
    return rows


def build_gap_payload(role: str, left_prime: int, right_prime: int, anchor: int) -> dict[str, object]:
    """Return one exact gap payload for one parity-neutral anchor neighborhood."""
    profile = gwr_next_gap_profile(left_prime, block=SCAN_BLOCK)
    if int(profile["next_prime"]) != right_prime:
        raise AssertionError(
            f"gap mismatch for role={role}: expected right_prime={right_prime}, "
            f"got {profile['next_prime']}"
        )

    winner_offset = profile["winner_offset"]
    winner_d = profile["winner_d"]
    winner = None if winner_offset is None else left_prime + int(winner_offset)
    contains_anchor = bool(left_prime < anchor < right_prime)
    return {
        "role": role,
        "left_prime": left_prime,
        "right_prime": right_prime,
        "gap_width": right_prime - left_prime,
        "has_interior": right_prime - left_prime > 1,
        "contains_anchor": contains_anchor,
        "anchor_offset_from_left": (anchor - left_prime) if contains_anchor else None,
        "anchor_offset_from_right": (right_prime - anchor) if contains_anchor else None,
        "winner": winner,
        "winner_d": None if winner_d is None else int(winner_d),
        "winner_offset": None if winner_offset is None else int(winner_offset),
        "carrier_family": None if winner is None else carrier_family(int(winner), int(winner_d)),
        "dmin": gap_dmin(left_prime, right_prime),
        "d3_profile": divisor_gap_profile(left_prime, right_prime, 3),
        "d4_profile": d4_gap_profile(left_prime, right_prime),
        "interior_rows": _interior_rows(left_prime, right_prime, winner),
    }


def orient_anchor(anchor: int) -> dict[str, object]:
    """Return the exact three-gap neighborhood around one composite anchor."""
    validate_anchor(anchor)

    p_left = previous_prime_before(anchor - 1, block=SCAN_BLOCK)
    p_right = next_prime_after(anchor, block=SCAN_BLOCK)
    p_prev = previous_prime_before(p_left - 1, block=SCAN_BLOCK)
    p_next = gwr_next_prime(p_right, block=SCAN_BLOCK)
    gaps = [
        build_gap_payload("previous", p_prev, p_left, anchor),
        build_gap_payload("containing", p_left, p_right, anchor),
        build_gap_payload("following", p_right, p_next, anchor),
    ]
    return {
        "anchor": anchor,
        "scan_block": SCAN_BLOCK,
        "p_prev": p_prev,
        "p_left": p_left,
        "p_right": p_right,
        "p_next": p_next,
        "gaps": gaps,
    }


def role_priority(role: str) -> int:
    """Return the fixed role priority used in law ranking."""
    if role == "previous":
        return 0
    if role == "containing":
        return 1
    raise ValueError(f"unsupported role {role}")


def boundary_priority(boundary_kind: str | None) -> int:
    """Return the deterministic boundary order for terminal prime nominees."""
    if boundary_kind == "p_left":
        return 0
    if boundary_kind == "p_prev":
        return 1
    return 2


def compact_gap_snapshot(gap: dict[str, object]) -> dict[str, object]:
    """Return one compact gap record suitable for the trace JSONL."""
    return {
        "role": gap["role"],
        "left_prime": gap["left_prime"],
        "right_prime": gap["right_prime"],
        "gap_width": gap["gap_width"],
        "contains_anchor": gap["contains_anchor"],
        "winner": gap["winner"],
        "winner_d": gap["winner_d"],
        "winner_offset": gap["winner_offset"],
        "carrier_family": gap["carrier_family"],
        "dmin": gap["dmin"],
        "interior_count": len(gap["interior_rows"]),
    }


def build_candidate_pool(
    summary: dict[str, object],
    current_anchor: int,
    visited: set[int],
) -> list[dict[str, object]]:
    """Return the local prime-boundary and odd-semiprime carrier candidates."""
    candidates: list[dict[str, object]] = []
    for boundary_value, role, boundary_kind in (
        (int(summary["p_prev"]), "previous", "p_prev"),
        (int(summary["p_left"]), "containing", "p_left"),
    ):
        if boundary_value < 4 or boundary_value >= current_anchor or boundary_value in visited:
            continue
        source_gap = next(gap for gap in summary["gaps"] if str(gap["role"]) == role)
        candidates.append(
            {
                "n": boundary_value,
                "kind": "prime_boundary",
                "role": role,
                "boundary_kind": boundary_kind,
                "carrier_family": None,
                "is_gwr_winner": False,
                "is_first_dmin": False,
                "is_first_d4": False,
                "offset": None,
                "gap_width": int(source_gap["gap_width"]),
            }
        )

    for gap in summary["gaps"]:
        if gap["role"] not in ("previous", "containing"):
            continue
        for row in gap["interior_rows"]:
            candidate = int(row["n"])
            if candidate < 4 or candidate >= current_anchor or candidate in visited:
                continue
            if str(row["carrier_family"]) != "odd_semiprime":
                continue
            candidates.append(
                {
                    "n": candidate,
                    "kind": "odd_semiprime",
                    "role": str(gap["role"]),
                    "boundary_kind": None,
                    "carrier_family": "odd_semiprime",
                    "is_gwr_winner": bool(row["is_gwr_winner"]),
                    "is_first_dmin": bool(row["is_first_dmin"]),
                    "is_first_d4": bool(row["is_first_d4"]),
                    "offset": int(row["offset"]),
                    "gap_width": int(gap["gap_width"]),
                }
            )
    return candidates


def odd_candidate_lane_factors(candidate: dict[str, object], left_factor: int, right_factor: int) -> set[int]:
    """Return the factor-side intersection for one odd-semiprime candidate."""
    if str(candidate["kind"]) != "odd_semiprime":
        return set()

    value = int(candidate["n"])
    matches: set[int] = set()
    if value % left_factor == 0:
        matches.add(left_factor)
    if value % right_factor == 0:
        matches.add(right_factor)
    return matches


def candidate_sort_key(law_id: str, candidate: dict[str, object]) -> tuple[object, ...]:
    """Return the pure-PGS ranking key for one local candidate."""
    kind = str(candidate["kind"])
    role = str(candidate["role"])
    boundary_kind = candidate["boundary_kind"]
    offset = int(candidate["offset"]) if candidate["offset"] is not None else 0
    gap_width = int(candidate["gap_width"])
    n = int(candidate["n"])
    kind_rank = 0 if kind == "odd_semiprime" else 1
    prime_key = (boundary_priority(str(boundary_kind) if boundary_kind is not None else None), n)
    if law_id == "prime_left_boundary_control":
        return (
            0 if kind == "prime_boundary" else 1,
            boundary_priority(str(boundary_kind) if boundary_kind is not None else None),
            n,
        )
    if law_id == "odd_prev_winner_large_offset":
        return (
            kind_rank,
            role_priority(role),
            0 if bool(candidate["is_gwr_winner"]) else 1,
            -offset,
            n,
            prime_key,
        )
    if law_id == "odd_prev_d4_large_offset":
        return (
            kind_rank,
            role_priority(role),
            0 if bool(candidate["is_first_d4"]) else 1,
            -offset,
            n,
            prime_key,
        )
    if law_id == "odd_prev_dmin_large_offset":
        return (
            kind_rank,
            role_priority(role),
            0 if bool(candidate["is_first_dmin"]) else 1,
            -offset,
            n,
            prime_key,
        )
    if law_id == "odd_prev_small_gap_d4_large_offset":
        return (
            kind_rank,
            role_priority(role),
            gap_width,
            0 if bool(candidate["is_first_d4"]) else 1,
            -offset,
            n,
            prime_key,
        )
    raise ValueError(f"unsupported law {law_id}")


def select_next_candidate(
    law_id: str,
    current_anchor: int,
    candidates: list[dict[str, object]],
    visited: set[int],
) -> tuple[dict[str, object] | None, str | None]:
    """Return the selected candidate and an immediate failure reason, if any."""
    if not candidates:
        return None, "no_candidate"

    ranked = sorted(candidates, key=lambda candidate: candidate_sort_key(law_id, candidate))
    selected = dict(ranked[0])
    if int(selected["n"]) in visited:
        return None, "repeat_anchor"
    if int(selected["n"]) >= current_anchor:
        return None, "anchor_not_decreasing"
    return selected, None


def run_case(law_id: str, modulus: int, max_steps: int) -> list[dict[str, object]]:
    """Run one deterministic backward lane trace for one law and modulus."""
    if max_steps < 1:
        raise ValueError("max_steps must be at least 1")

    left_factor, right_factor = factor_pair(modulus)
    trace_rows: list[dict[str, object]] = []
    current_anchor = modulus
    visited = {modulus}
    lane_factor: int | None = None

    for step in range(1, max_steps + 1):
        summary = orient_anchor(current_anchor)
        candidates = build_candidate_pool(summary, current_anchor, visited)
        selected, failure_reason = select_next_candidate(
            law_id=law_id,
            current_anchor=current_anchor,
            candidates=candidates,
            visited=visited,
        )
        selected_lane_factors = (
            [] if selected is None else sorted(odd_candidate_lane_factors(selected, left_factor, right_factor))
        )
        selected_on_lane = bool(lane_factor is not None and lane_factor in selected_lane_factors)
        factor_reach = bool(
            selected is not None
            and str(selected["kind"]) == "prime_boundary"
            and int(selected["n"]) in (left_factor, right_factor)
        )
        stop_reason = None
        lane_success = False
        next_lane_factor = lane_factor

        if failure_reason is not None:
            stop_reason = "lane_success_terminal_no_candidate" if lane_factor is not None else failure_reason
            lane_success = lane_factor is not None
        elif str(selected["kind"]) == "prime_boundary":
            if factor_reach:
                stop_reason = "factor_reach"
                lane_success = True
            elif lane_factor is not None:
                stop_reason = "lane_success_terminal_prime"
                lane_success = True
            else:
                stop_reason = "terminal_prime_nominee"
        else:
            if lane_factor is None:
                if not selected_lane_factors:
                    stop_reason = "not_odd_semiprime_lane"
                else:
                    next_lane_factor = int(selected_lane_factors[0])
            elif lane_factor not in selected_lane_factors:
                stop_reason = "lane_broken"

        row = {
            "law_id": law_id,
            "n": modulus,
            "step": step,
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
            "lane_factor": next_lane_factor,
            "selected_on_lane": selected_on_lane,
            "lane_success": lane_success,
            "factor_reach": factor_reach,
            "stop_reason": stop_reason,
            "gaps": [compact_gap_snapshot(gap) for gap in summary["gaps"]],
        }
        trace_rows.append(row)

        if stop_reason is not None:
            return trace_rows

        lane_factor = next_lane_factor
        visited.add(int(selected["n"]))
        current_anchor = int(selected["n"])

    trace_rows[-1]["stop_reason"] = "lane_success_exhausted" if lane_factor is not None else "max_steps_exhausted"
    trace_rows[-1]["lane_success"] = lane_factor is not None
    trace_rows[-1]["lane_factor"] = lane_factor
    return trace_rows


def summarize_trace(trace_rows: list[dict[str, object]]) -> dict[str, object]:
    """Return the terminal payload for one trace."""
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
    """Run the pure-PGS law family over the pinned toy corpus."""
    corpus = generate_toy_corpus(max_n)
    trace_rows: list[dict[str, object]] = []
    traces_by_law: dict[str, list[dict[str, object]]] = {law_id: [] for law_id in LAW_ORDER}

    for law_id in LAW_ORDER:
        for modulus in corpus:
            trace = run_case(law_id, modulus, max_steps=max_steps)
            trace_rows.extend(trace)
            traces_by_law[law_id].append(summarize_trace(trace))

    law_summaries: dict[str, dict[str, object]] = {}
    best_law = LAW_ORDER[0]
    best_lane_success_count = -1
    best_factor_reach_count = -1
    for law_id in LAW_ORDER:
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
        summary = {
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
        law_summaries[law_id] = summary
        if (lane_success_count, factor_reach_count) > (best_lane_success_count, best_factor_reach_count):
            best_lane_success_count = lane_success_count
            best_factor_reach_count = factor_reach_count
            best_law = law_id

    best_lane_success_count = max(best_lane_success_count, 0)
    best_factor_reach_count = max(best_factor_reach_count, 0)
    summary = {
        "max_n": max_n,
        "case_count": len(corpus),
        "max_steps": max_steps,
        "law_summaries": law_summaries,
        "best_law": best_law,
        "best_lane_success_count": best_lane_success_count,
        "best_factor_reach_count": best_factor_reach_count,
        "searched_family_falsified": best_lane_success_count == 0,
    }
    return trace_rows, summary


def write_trace_jsonl(output_path: Path, trace_rows: list[dict[str, object]]) -> None:
    """Write the full per-step trace as JSONL."""
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        for row in trace_rows:
            handle.write(json.dumps(row, sort_keys=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run the backward lane search harness and emit artifacts."""
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

"""Probe semiprime-shadow chains as bounded rightward search objects."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from functools import lru_cache
from pathlib import Path
from statistics import median

from sympy import primerange


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_controller import (  # noqa: E402
    write_json,
    write_jsonl,
)
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    admissible_offsets,
    closure_reason,
)


LEFT_HORIZON_HIDDEN_IMPOSTOR = "LEFT_HORIZON_HIDDEN_IMPOSTOR"
LEFT_SEMIPRIME_SHADOW = "LEFT_SEMIPRIME_SHADOW"
AUDIT_PRIME = "AUDIT_PRIME"
AFTER_TRUE_AUDIT = "AFTER_TRUE_AUDIT"
HORIZON_HIDDEN_BEFORE_TRUE = "HORIZON_HIDDEN_BEFORE_TRUE"
RANKERS = ("ranker_b", "ranker_c", "ranker_d")
STOP_RULES = (
    "stop_rule_1_first_chain_node",
    "stop_rule_2_successor_gap_exceeds_prior_median",
    "stop_rule_3_low_exact_boundary_delta",
    "stop_rule_4_post_visible_open_density_drop",
    "stop_rule_5_next_chain_node_outside_R64",
    "stop_rule_6_best_ranker_b",
    "stop_rule_7_best_ranker_c",
    "stop_rule_8_after_final_semiprime_gt_horizon_audit_only",
    "chain_fallback_exact_first_prime_in_chain",
)


def rule_source(stop_rule: str) -> str:
    """Return the honest source label for one selector row."""
    if stop_rule == "chain_fallback_exact_first_prime_in_chain":
        return "chain_fallback"
    if stop_rule == "stop_rule_8_after_final_semiprime_gt_horizon_audit_only":
        return "audit_assisted_probe"
    return "PGS_probe"


@lru_cache(maxsize=None)
def visible_reason(p: int, offset: int, max_divisor_floor: int) -> str | None:
    """Return cached visible closure evidence for one offset."""
    return closure_reason(int(p), int(offset), int(max_divisor_floor))


def node_audit_class(
    candidate: int,
    true_q: int,
    _max_divisor_floor: int,
) -> str:
    """Classify one chain node for audit-only analysis."""
    if int(candidate) == int(true_q):
        return AUDIT_PRIME
    if int(candidate) > int(true_q):
        return AFTER_TRUE_AUDIT
    return HORIZON_HIDDEN_BEFORE_TRUE


def closure_window(
    p: int,
    previous_offset: int,
    node_offset: int,
    open_offsets: list[int],
    max_divisor_floor: int,
) -> tuple[list[str], int, int]:
    """Return closure reasons and skipped counts before one chain node."""
    reasons: list[str] = []
    open_skipped = 0
    closed_skipped = 0
    for offset in open_offsets:
        if offset <= int(previous_offset):
            continue
        if offset >= int(node_offset):
            break
        open_skipped += 1
        reason = visible_reason(int(p), offset, max_divisor_floor)
        if reason is not None:
            closed_skipped += 1
            reasons.append(f"{offset}:{reason}")
    return reasons, open_skipped, closed_skipped


def closure_counts(
    p: int,
    offset: int,
    shadow_offset: int,
    open_offsets: list[int],
    max_divisor_floor: int,
) -> tuple[int, int]:
    """Return closed and unclosed open offsets before one candidate."""
    closed = 0
    unclosed = 0
    for prior in open_offsets:
        if prior <= int(shadow_offset):
            continue
        if prior >= int(offset):
            break
        if visible_reason(int(p), prior, max_divisor_floor) is None:
            unclosed += 1
        else:
            closed += 1
    return closed, unclosed


def visible_boundary_score(
    p: int,
    offset: int,
    shadow_offset: int,
    open_offsets: list[int],
    max_divisor_floor: int,
) -> tuple[int, int, int, int]:
    """Return the existing label-free chamber-closure score."""
    closed, unclosed = closure_counts(
        p,
        offset,
        shadow_offset,
        open_offsets,
        max_divisor_floor,
    )
    self_open = visible_reason(int(p), int(offset), max_divisor_floor) is None
    return (
        1 if self_open else 0,
        closed - (2 * unclosed),
        closed,
        -abs(int(offset) - int(shadow_offset)),
    )


def ranked_offsets(
    ranker_name: str,
    offsets: list[int],
    p: int,
    shadow_offset: int,
    open_offsets: list[int],
    max_divisor_floor: int,
    predecessor_closure_count: int,
) -> list[int]:
    """Return right offsets ordered by one prior label-free ranker."""
    if ranker_name == "ranker_b":
        return sorted(
            offsets,
            key=lambda offset: (
                0
                if (
                    visible_reason(int(p), offset, max_divisor_floor) is None
                    and closure_counts(
                        p,
                        offset,
                        shadow_offset,
                        open_offsets,
                        max_divisor_floor,
                    )[1]
                    == 0
                )
                else 1,
                offset,
            ),
        )
    if ranker_name == "ranker_c":
        return sorted(
            offsets,
            key=lambda offset: visible_boundary_score(
                p,
                offset,
                shadow_offset,
                open_offsets,
                max_divisor_floor,
            ),
            reverse=True,
        )
    if ranker_name == "ranker_d":
        return sorted(
            offsets,
            key=lambda offset: (
                0
                if (
                    visible_reason(int(p), offset, max_divisor_floor) is None
                    and closure_counts(
                        p,
                        offset,
                        shadow_offset,
                        open_offsets,
                        max_divisor_floor,
                    )[0]
                    >= int(predecessor_closure_count)
                )
                else 1,
                closure_counts(
                    p,
                    offset,
                    shadow_offset,
                    open_offsets,
                    max_divisor_floor,
                )[1],
                offset,
            ),
        )
    raise ValueError(f"unknown ranker: {ranker_name}")


def visible_chain_offsets(
    p: int,
    shadow_offset: int,
    candidate_bound: int,
    chain_limit: int,
    max_divisor_floor: int,
) -> list[int]:
    """Return the first visible-open rightward chain offsets after a shadow."""
    chain: list[int] = []
    current_offset = int(shadow_offset)
    open_offsets = admissible_offsets(int(p), int(candidate_bound))
    while len(chain) < int(chain_limit):
        next_offsets = [
            offset
            for offset in open_offsets
            if offset > current_offset
            and visible_reason(int(p), offset, max_divisor_floor) is None
        ]
        if not next_offsets:
            break
        current_offset = min(next_offsets)
        chain.append(current_offset)
    return chain


def rank_maps(
    p: int,
    shadow_offset: int,
    candidate_bound: int,
    max_divisor_floor: int,
    predecessor_closure_count: int,
) -> dict[str, dict[int, int]]:
    """Return rank maps for chain-node reporting."""
    open_offsets = admissible_offsets(int(p), int(candidate_bound))
    right_offsets = [
        offset
        for offset in open_offsets
        if int(shadow_offset) < offset <= int(candidate_bound)
    ]
    maps: dict[str, dict[int, int]] = {}
    for ranker_name in RANKERS:
        ordered = ranked_offsets(
            ranker_name,
            right_offsets,
            p,
            shadow_offset,
            open_offsets,
            max_divisor_floor,
            predecessor_closure_count,
        )
        maps[ranker_name] = {
            int(offset): rank for rank, offset in enumerate(ordered, start=1)
        }
    return maps


def chain_node_rows(
    shadow_row: dict[str, object],
    chain_limit: int,
    candidate_bound: int,
    max_divisor_floor: int,
) -> list[dict[str, object]]:
    """Return per-node rows for one audit-marked shadow chain."""
    scale = int(shadow_row["scale"])
    p = int(shadow_row["anchor_p"])
    true_q = int(shadow_row["true_q_for_audit_only"])
    shadow_s0 = int(shadow_row["shadow_s"])
    shadow_offset = shadow_s0 - int(p)
    chain_offsets = visible_chain_offsets(
        p,
        shadow_offset,
        candidate_bound,
        chain_limit,
        max_divisor_floor,
    )
    open_offsets = admissible_offsets(int(p), int(candidate_bound))
    ranks = rank_maps(
        p,
        shadow_offset,
        candidate_bound,
        max_divisor_floor,
        int(shadow_row["predecessor_closure_count"]),
    )
    rows: list[dict[str, object]] = []
    previous_offset = shadow_offset
    for index, offset in enumerate(chain_offsets, start=1):
        next_offset = chain_offsets[index] if index < len(chain_offsets) else None
        reasons, open_skipped, closed_skipped = closure_window(
            p,
            previous_offset,
            offset,
            open_offsets,
            max_divisor_floor,
        )
        candidate = int(p) + int(offset)
        rows.append(
            {
                "scale": int(scale),
                "chain_limit": int(chain_limit),
                "anchor_p": int(p),
                "true_q_for_audit_only": true_q,
                "shadow_s0": shadow_s0,
                "shadow_class": str(shadow_row["impostor_class"]),
                "chain_index": int(index),
                "chain_candidate": candidate,
                "is_true_boundary_for_audit_only": candidate == true_q,
                "audit_node_class": node_audit_class(
                    candidate,
                    true_q,
                    max_divisor_floor,
                ),
                "candidate_offset_from_anchor": int(offset),
                "candidate_offset_from_shadow": int(offset) - int(shadow_offset),
                "delta_to_previous_chain_node": int(offset) - int(previous_offset),
                "delta_to_next_chain_node": (
                    None if next_offset is None else int(next_offset) - int(offset)
                ),
                "visible_closure_reason_before_node": reasons,
                "open_candidates_skipped_before_node": open_skipped,
                "closed_candidates_skipped_before_node": closed_skipped,
                "carrier_w": int(p),
                "carrier_d": 2,
                "carrier_to_node_delta": candidate - int(p),
                "node_mod_6": candidate % 6,
                "node_mod_30": candidate % 30,
                "offset_mod_6": int(offset) % 6,
                "offset_mod_30": int(offset) % 30,
                "ranker_b_rank": ranks["ranker_b"].get(int(offset)),
                "ranker_c_rank": ranks["ranker_c"].get(int(offset)),
                "ranker_d_rank": ranks["ranker_d"].get(int(offset)),
                "shadow_chain_signature": (
                    f"idx={index}|dprev={int(offset) - int(previous_offset)}|"
                    f"dnext={None if next_offset is None else int(next_offset) - int(offset)}|"
                    f"mod30={candidate % 30}|closed_skip={closed_skipped}"
                ),
            }
        )
        previous_offset = offset
    return rows


@lru_cache(maxsize=None)
def low_exact_boundary_deltas(candidate_bound: int) -> set[int]:
    """Return low-surface true boundary offsets for stop-rule probing."""
    primes = list(primerange(11, 1_000_000 + int(candidate_bound) + 1))
    deltas: set[int] = set()
    for left, right in zip(primes, primes[1:]):
        if left > 1_000_000:
            break
        delta = int(right) - int(left)
        if delta <= int(candidate_bound):
            deltas.add(delta)
    return deltas


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read LF-terminated JSONL rows."""
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def select_node(
    stop_rule: str,
    rows: list[dict[str, object]],
    low_deltas: set[int],
) -> dict[str, object] | None:
    """Select one chain node by a stop rule."""
    if not rows:
        return None
    if stop_rule == "stop_rule_1_first_chain_node":
        return rows[0]
    if stop_rule == "stop_rule_2_successor_gap_exceeds_prior_median":
        prior: list[int] = []
        for row in rows:
            prior.append(int(row["delta_to_previous_chain_node"]))
            next_delta = row["delta_to_next_chain_node"]
            if next_delta is not None and int(next_delta) > median(prior):
                return row
        return rows[0]
    if stop_rule == "stop_rule_3_low_exact_boundary_delta":
        for row in rows:
            if int(row["carrier_to_node_delta"]) in low_deltas:
                return row
        return rows[0]
    if stop_rule == "stop_rule_4_post_visible_open_density_drop":
        total_span = max(
            1,
            int(rows[-1]["candidate_offset_from_shadow"]),
        )
        for index, row in enumerate(rows, start=1):
            offset_span = max(1, int(row["candidate_offset_from_shadow"]))
            before_density = index / offset_span
            after_span = max(1, total_span - offset_span)
            after_density = (len(rows) - index) / after_span
            if after_density < before_density:
                return row
        return rows[0]
    if stop_rule == "stop_rule_5_next_chain_node_outside_R64":
        for row in rows:
            next_delta = row["delta_to_next_chain_node"]
            next_shadow_delta = (
                None
                if next_delta is None
                else int(row["candidate_offset_from_shadow"]) + int(next_delta)
            )
            if next_shadow_delta is None or next_shadow_delta > 64:
                return row
        return rows[0]
    if stop_rule == "stop_rule_6_best_ranker_b":
        return min(rows, key=lambda row: (row["ranker_b_rank"] or 10_000, row["chain_index"]))
    if stop_rule == "stop_rule_7_best_ranker_c":
        return min(rows, key=lambda row: (row["ranker_c_rank"] or 10_000, row["chain_index"]))
    if stop_rule == "stop_rule_8_after_final_semiprime_gt_horizon_audit_only":
        true_index = next(
            (
                int(row["chain_index"])
                for row in rows
                if bool(row["is_true_boundary_for_audit_only"])
            ),
            None,
        )
        if true_index is None:
            return rows[0]
        last_hidden = max(
            (
                int(row["chain_index"])
                for row in rows
                if int(row["chain_index"]) < true_index
                and row["audit_node_class"] == HORIZON_HIDDEN_BEFORE_TRUE
            ),
            default=0,
        )
        target_index = max(1, last_hidden + 1)
        return next(
            (row for row in rows if int(row["chain_index"]) == target_index),
            rows[0],
        )
    if stop_rule == "chain_fallback_exact_first_prime_in_chain":
        return next(
            (
                row
                for row in rows
                if bool(row["is_true_boundary_for_audit_only"])
            ),
            rows[0],
        )
    raise ValueError(f"unknown stop rule: {stop_rule}")


def build_rows(
    shadow_rows_path: Path,
    scales: list[int],
    sample_size: int,
    candidate_bound: int,
    chain_limits: list[int],
    max_divisor_floor: int,
) -> list[dict[str, object]]:
    """Return all per-node rows for all requested chain limits."""
    if not shadow_rows_path.exists():
        raise FileNotFoundError(f"missing shadow rows: {shadow_rows_path}")
    scale_set = {int(scale) for scale in scales}
    base_rows = [
        row
        for row in read_jsonl(shadow_rows_path)
        if int(row["scale"]) in scale_set
    ]
    if sample_size:
        limited_rows: list[dict[str, object]] = []
        for scale in scales:
            scale_rows = [
                row for row in base_rows if int(row["scale"]) == int(scale)
            ]
            limited_rows.extend(scale_rows[: int(sample_size)])
        base_rows = limited_rows
    rows: list[dict[str, object]] = []
    for shadow_row in base_rows:
        if str(shadow_row["impostor_class"]) not in {
            LEFT_SEMIPRIME_SHADOW,
            LEFT_HORIZON_HIDDEN_IMPOSTOR,
        }:
            continue
        if not bool(shadow_row["true_boundary_right_of_shadow"]):
            continue
        for chain_limit in chain_limits:
            rows.extend(
                chain_node_rows(
                    shadow_row,
                    chain_limit,
                    candidate_bound,
                    max_divisor_floor,
                )
            )
    return rows


def recall(count: int, total: int) -> float:
    """Return count / total."""
    return 0.0 if int(total) == 0 else int(count) / int(total)


def summary_rows(rows: list[dict[str, object]], candidate_bound: int) -> list[dict[str, object]]:
    """Return stop-rule summary rows."""
    summaries: list[dict[str, object]] = []
    low_deltas = low_exact_boundary_deltas(candidate_bound)
    keys = sorted(
        {
            (int(row["scale"]), int(row["chain_limit"]), int(row["anchor_p"]))
            for row in rows
        }
    )
    grouped = {
        key: [
            row
            for row in rows
            if (
                int(row["scale"]),
                int(row["chain_limit"]),
                int(row["anchor_p"]),
            )
            == key
        ]
        for key in keys
    }
    for scale in sorted({key[0] for key in keys}):
        for chain_limit in sorted({key[1] for key in keys}):
            chains = [
                chain
                for key, chain in grouped.items()
                if key[0] == scale and key[1] == chain_limit
            ]
            shadow_count = len(chains)
            true_positions = [
                int(row["chain_index"])
                for chain in chains
                for row in chain
                if bool(row["is_true_boundary_for_audit_only"])
            ]
            true_in_chain_count = len(true_positions)
            max_true_position = max(true_positions) if true_positions else None
            for stop_rule in STOP_RULES:
                selected = [select_node(stop_rule, chain, low_deltas) for chain in chains]
                selected = [row for row in selected if row is not None]
                top1 = sum(
                    1
                    for row in selected
                    if bool(row["is_true_boundary_for_audit_only"])
                )
                missed_true = shadow_count - true_in_chain_count
                wrong_selected = shadow_count - top1 - missed_true
                summaries.append(
                    {
                        "scale": int(scale),
                        "chain_limit": int(chain_limit),
                        "stop_rule": stop_rule,
                        "source": rule_source(stop_rule),
                        "shadow_count": shadow_count,
                        "true_in_chain_count": true_in_chain_count,
                        "max_true_chain_position": max_true_position,
                        "top1_correct": top1,
                        "top1_recall": recall(top1, shadow_count),
                        "audit_failed_after_stop_rule": shadow_count - top1,
                        "miss_true_not_in_chain": missed_true,
                        "miss_wrong_chain_node_selected": wrong_selected,
                    }
                )
    return summaries


def aggregate_rows(summaries: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return aggregate stop-rule rows across scales."""
    rows: list[dict[str, object]] = []
    for chain_limit in sorted({int(row["chain_limit"]) for row in summaries}):
        for stop_rule in STOP_RULES:
            matching = [
                row
                for row in summaries
                if int(row["chain_limit"]) == chain_limit
                and row["stop_rule"] == stop_rule
            ]
            shadow_count = sum(int(row["shadow_count"]) for row in matching)
            true_in_chain = sum(int(row["true_in_chain_count"]) for row in matching)
            top1 = sum(int(row["top1_correct"]) for row in matching)
            rows.append(
                {
                    "scale": "ALL",
                    "chain_limit": int(chain_limit),
                    "stop_rule": stop_rule,
                    "source": rule_source(stop_rule),
                    "shadow_count": shadow_count,
                    "true_in_chain_count": true_in_chain,
                    "max_true_chain_position": max(
                        int(row["max_true_chain_position"])
                        for row in matching
                        if row["max_true_chain_position"] is not None
                    ),
                    "top1_correct": top1,
                    "top1_recall": recall(top1, shadow_count),
                    "audit_failed_after_stop_rule": shadow_count - top1,
                    "miss_true_not_in_chain": shadow_count - true_in_chain,
                    "miss_wrong_chain_node_selected": true_in_chain - top1,
                }
            )
    return rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    """Write LF-terminated CSV rows."""
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    """Build the shadow-chain probe CLI."""
    parser = argparse.ArgumentParser(
        description="Probe visible-open semiprime-shadow chains."
    )
    parser.add_argument("--scales", type=int, nargs="+", required=True)
    parser.add_argument("--sample-size", type=int, default=256)
    parser.add_argument("--candidate-bound", type=int, default=128)
    parser.add_argument("--chain-limits", type=int, nargs="+", default=[4, 6, 8, 10, 12])
    parser.add_argument("--max-divisor-floor", type=int, default=10_000)
    parser.add_argument(
        "--shadow-rows",
        type=Path,
        default=Path("output/simple_pgs_semiprime_shadow_reorientation_probe/shadow_rows.jsonl"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the shadow-chain selector probe."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows(
        args.shadow_rows,
        [int(scale) for scale in args.scales],
        args.sample_size,
        args.candidate_bound,
        sorted({int(limit) for limit in args.chain_limits}),
        args.max_divisor_floor,
    )
    summaries = summary_rows(rows, args.candidate_bound)
    aggregates = aggregate_rows(summaries)
    write_jsonl(rows, args.output_dir / "chain_nodes.jsonl")
    write_json(
        {
            "summary": summaries,
            "aggregate": aggregates,
        },
        args.output_dir / "summary.json",
    )
    write_csv(summaries, args.output_dir / "summary.csv")
    write_csv(aggregates, args.output_dir / "aggregate_summary.csv")
    for row in aggregates:
        if int(row["chain_limit"]) == 8:
            print(
                "limit={chain_limit} rule={stop_rule} shadows={shadow_count} "
                "true_in_chain={true_in_chain_count} top1={top1_recall:.4f} "
                "failed={audit_failed_after_stop_rule}".format(**row)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

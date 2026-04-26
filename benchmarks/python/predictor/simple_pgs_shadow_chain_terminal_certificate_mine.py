"""Mine terminal-node certificates inside high-scale shadow chains."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from statistics import median

from sympy import factorint, isprime, prevprime, primerange


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_controller import (  # noqa: E402
    write_json,
    write_jsonl,
)
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    CHAIN_FALLBACK_SOURCE,
    DEFAULT_CHAIN_LIMIT,
    DEFAULT_VISIBLE_DIVISOR_BOUND,
    PGS_SOURCE,
    admissible_offsets,
    closure_reason,
    pgs_probe_certificate,
    visible_open_chain_offsets,
)


RULE_IDS = (
    "rule_a_first_chain_node",
    "rule_b_best_ranker_b",
    "rule_c_next_delta_larger_than_all_previous",
    "rule_d_post_visible_open_drop",
    "rule_e_low_delta_and_successor_not_low_delta",
    "rule_f_low_exact_terminal_signature",
    "rule_g_ranker_c_shortlist_best_ranker_b",
)


def sampled_anchors_near(scale: int, sample_size: int) -> list[int]:
    """Return deterministic prime anchors immediately below scale."""
    anchors: list[int] = []
    cursor = int(scale)
    while len(anchors) < int(sample_size):
        anchor = int(prevprime(cursor))
        anchors.append(anchor)
        cursor = anchor
    return anchors


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows."""
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def factorization_accepts_candidate(n: int) -> bool:
    """Return True when deterministic factorization finds no nontrivial factor."""
    factors = {int(prime): int(exp) for prime, exp in factorint(int(n)).items()}
    return len(factors) == 1 and factors.get(int(n)) == 1


def audit_confirms_next_prime(p: int, q: int) -> bool:
    """Return True when downstream audit confirms q is next after p."""
    if int(q) <= int(p) or not bool(isprime(int(q))):
        return False
    return not any(isprime(candidate) for candidate in range(int(p) + 1, int(q)))


def visible_reason(
    p: int,
    offset: int,
    visible_divisor_bound: int,
) -> str | None:
    """Return bounded visible closure evidence for one offset."""
    return closure_reason(int(p), int(offset), int(visible_divisor_bound))


def closure_vector_between(
    p: int,
    left_offset: int,
    right_offset: int,
    visible_divisor_bound: int,
) -> tuple[list[str], int, int]:
    """Return closure vector and open/closed counts in one offset interval."""
    reasons: list[str] = []
    open_count = 0
    closed_count = 0
    for offset in admissible_offsets(int(p), int(right_offset) - 1):
        if offset <= int(left_offset):
            continue
        reason = visible_reason(p, offset, visible_divisor_bound)
        if reason is None:
            open_count += 1
            reasons.append(f"{offset}:open")
        else:
            closed_count += 1
            reasons.append(f"{offset}:{reason}")
    return reasons, closed_count, open_count


def closure_counts_before(
    p: int,
    offset: int,
    seed_offset: int,
    open_offsets: list[int],
    visible_divisor_bound: int,
) -> tuple[int, int]:
    """Return visible closed/open counts between seed and one offset."""
    closed = 0
    open_count = 0
    for prior in open_offsets:
        if prior <= int(seed_offset):
            continue
        if prior >= int(offset):
            break
        if visible_reason(p, prior, visible_divisor_bound) is None:
            open_count += 1
        else:
            closed += 1
    return closed, open_count


def visible_boundary_score(
    p: int,
    offset: int,
    seed_offset: int,
    open_offsets: list[int],
    visible_divisor_bound: int,
) -> tuple[int, int, int, int]:
    """Return the chamber-closure boundary-likeness score."""
    closed, open_count = closure_counts_before(
        p,
        offset,
        seed_offset,
        open_offsets,
        visible_divisor_bound,
    )
    self_open = visible_reason(p, offset, visible_divisor_bound) is None
    return (
        1 if self_open else 0,
        closed - (2 * open_count),
        closed,
        -abs(int(offset) - int(seed_offset)),
    )


def rank_maps(
    p: int,
    seed_offset: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> dict[str, dict[int, int]]:
    """Return ranker maps over the right side of one chain seed."""
    open_offsets = admissible_offsets(int(p), int(candidate_bound))
    right_offsets = [
        offset for offset in open_offsets if int(seed_offset) < offset
    ]

    ranker_b = sorted(
        right_offsets,
        key=lambda offset: (
            0
            if visible_reason(p, offset, visible_divisor_bound) is None
            and closure_counts_before(
                p,
                offset,
                seed_offset,
                open_offsets,
                visible_divisor_bound,
            )[1]
            == 0
            else 1,
            offset,
        ),
    )
    ranker_c = sorted(
        right_offsets,
        key=lambda offset: visible_boundary_score(
            p,
            offset,
            seed_offset,
            open_offsets,
            visible_divisor_bound,
        ),
        reverse=True,
    )
    ranker_d = sorted(
        right_offsets,
        key=lambda offset: (
            closure_counts_before(
                p,
                offset,
                seed_offset,
                open_offsets,
                visible_divisor_bound,
            )[1],
            offset,
        ),
    )
    return {
        "ranker_b": {offset: rank for rank, offset in enumerate(ranker_b, start=1)},
        "ranker_c": {offset: rank for rank, offset in enumerate(ranker_c, start=1)},
        "ranker_d": {offset: rank for rank, offset in enumerate(ranker_d, start=1)},
    }


def local_signature(
    delta_prev: int,
    delta_next: int | None,
    node_offset: int,
    node_value: int,
    closed_prev: int,
    open_prev: int,
    closed_next: int,
    open_next: int,
) -> str:
    """Return one compact label-free chain-node signature."""
    return (
        f"dprev={delta_prev}|dnext={delta_next}|"
        f"node30={node_value % 30}|off30={node_offset % 30}|"
        f"prev={closed_prev}:{open_prev}|next={closed_next}:{open_next}"
    )


def low_exact_boundary_deltas(candidate_bound: int) -> set[int]:
    """Return low-surface true boundary offsets."""
    primes = list(primerange(11, 1_000_000 + int(candidate_bound) + 1))
    deltas: set[int] = set()
    for left, right in zip(primes, primes[1:]):
        if left > 1_000_000:
            break
        delta = int(right) - int(left)
        if delta <= int(candidate_bound):
            deltas.add(delta)
    return deltas


def low_exact_terminal_signatures(
    candidate_bound: int,
    visible_divisor_bound: int,
) -> set[str]:
    """Return local signatures seen on low exact PGS true boundaries."""
    signatures: set[str] = set()
    for anchor in primerange(11, 100_001):
        certificate = pgs_probe_certificate(
            int(anchor),
            int(candidate_bound),
            int(visible_divisor_bound),
        )
        if certificate is None:
            continue
        q = int(certificate["q"])
        if not factorization_accepts_candidate(q):
            continue
        offset = q - int(anchor)
        open_offsets = admissible_offsets(int(anchor), int(candidate_bound))
        previous_open = max(
            (prior for prior in open_offsets if prior < offset),
            default=0,
        )
        next_open = min(
            (right for right in open_offsets if right > offset),
            default=None,
        )
        _before_vec, closed_prev, open_prev = closure_vector_between(
            int(anchor),
            previous_open,
            offset,
            int(visible_divisor_bound),
        )
        if next_open is None:
            closed_next = 0
            open_next = 0
            delta_next = None
        else:
            _after_vec, closed_next, open_next = closure_vector_between(
                int(anchor),
                offset,
                next_open,
                int(visible_divisor_bound),
            )
            delta_next = next_open - offset
        signatures.add(
            local_signature(
                offset - previous_open,
                delta_next,
                offset,
                q,
                closed_prev,
                open_prev,
                closed_next,
                open_next,
            )
        )
    return signatures


def chain_node_rows_for_record(
    record: dict[str, object],
    candidate_bound: int,
    chain_limit: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Return one row per visible-open chain node for one chain_fallback record."""
    p = int(record["p"])
    seed = int(record["chain_seed"])
    true_q = int(record["q"])
    seed_offset = seed - p
    chain_offsets = visible_open_chain_offsets(
        p,
        seed_offset,
        int(candidate_bound),
        int(chain_limit),
        int(visible_divisor_bound),
    )
    chain_values = [p + offset for offset in chain_offsets]
    ranks = rank_maps(p, seed_offset, candidate_bound, visible_divisor_bound)
    rows: list[dict[str, object]] = []
    for index, offset in enumerate(chain_offsets, start=1):
        value = p + offset
        previous_offset = seed_offset if index == 1 else chain_offsets[index - 2]
        next_offset = chain_offsets[index] if index < len(chain_offsets) else None
        before_vec, closed_prev, open_prev = closure_vector_between(
            p,
            previous_offset,
            offset,
            visible_divisor_bound,
        )
        if next_offset is None:
            after_vec: list[str] = []
            closed_next = 0
            open_next = 0
            delta_next = None
        else:
            after_vec, closed_next, open_next = closure_vector_between(
                p,
                offset,
                next_offset,
                visible_divisor_bound,
            )
            delta_next = next_offset - offset
        prefix = [
            chain_offsets[i] - (seed_offset if i == 0 else chain_offsets[i - 1])
            for i in range(index)
        ]
        suffix = [
            chain_offsets[i + 1] - chain_offsets[i]
            for i in range(index - 1, len(chain_offsets) - 1)
        ]
        signature = local_signature(
            offset - previous_offset,
            delta_next,
            offset,
            value,
            closed_prev,
            open_prev,
            closed_next,
            open_next,
        )
        rows.append(
            {
                "scale": int(record["scale"]),
                "anchor_p": p,
                "chain_seed": seed,
                "true_q_for_audit_only": true_q,
                "chain_index": index,
                "chain_candidate": value,
                "is_terminal_for_audit_only": value == true_q,
                "delta_prev": offset - previous_offset,
                "delta_next": delta_next,
                "prefix_delta_sequence": prefix,
                "suffix_delta_sequence": suffix,
                "node_offset_from_anchor": offset,
                "node_offset_from_seed": offset - seed_offset,
                "node_mod_6": value % 6,
                "node_mod_30": value % 30,
                "offset_mod_6": offset % 6,
                "offset_mod_30": offset % 30,
                "visible_closed_between_prev_and_node": closed_prev,
                "visible_open_between_prev_and_node": open_prev,
                "visible_closed_between_node_and_next": closed_next,
                "visible_open_between_node_and_next": open_next,
                "closure_reason_vector_before_node": before_vec,
                "closure_reason_vector_after_node": after_vec,
                "carrier_w": p,
                "carrier_d": 2,
                "carrier_to_node_delta": value - p,
                "carrier_to_seed_delta": seed - p,
                "ranker_b_rank": ranks["ranker_b"].get(offset),
                "ranker_c_rank": ranks["ranker_c"].get(offset),
                "ranker_d_rank": ranks["ranker_d"].get(offset),
                "local_chain_signature": signature,
            }
        )
    return rows


def select_rule(
    rule_id: str,
    rows: list[dict[str, object]],
    low_deltas: set[int],
    low_signatures: set[str],
) -> dict[str, object] | None:
    """Select one chain node by one candidate rule."""
    if not rows:
        return None
    if rule_id == "rule_a_first_chain_node":
        return rows[0]
    if rule_id == "rule_b_best_ranker_b":
        return min(rows, key=lambda row: (row["ranker_b_rank"] or 10_000, row["chain_index"]))
    if rule_id == "rule_c_next_delta_larger_than_all_previous":
        previous: list[int] = []
        for row in rows:
            previous.append(int(row["delta_prev"]))
            delta_next = row["delta_next"]
            if delta_next is not None and int(delta_next) > max(previous):
                return row
        return rows[0]
    if rule_id == "rule_d_post_visible_open_drop":
        for row in rows:
            if int(row["visible_open_between_node_and_next"]) < int(
                row["visible_open_between_prev_and_node"]
            ):
                return row
        return rows[0]
    if rule_id == "rule_e_low_delta_and_successor_not_low_delta":
        for index, row in enumerate(rows):
            successor = rows[index + 1] if index + 1 < len(rows) else None
            if int(row["carrier_to_node_delta"]) in low_deltas and (
                successor is None or int(successor["carrier_to_node_delta"]) not in low_deltas
            ):
                return row
        return rows[0]
    if rule_id == "rule_f_low_exact_terminal_signature":
        for row in rows:
            if str(row["local_chain_signature"]) in low_signatures:
                return row
        return rows[0]
    if rule_id == "rule_g_ranker_c_shortlist_best_ranker_b":
        shortlist = [
            row for row in rows if int(row["ranker_c_rank"] or 10_000) <= 4
        ]
        if not shortlist:
            return rows[0]
        return min(
            shortlist,
            key=lambda row: (row["ranker_b_rank"] or 10_000, row["chain_index"]),
        )
    raise ValueError(f"unknown rule: {rule_id}")


def summarize_rules(
    rows: list[dict[str, object]],
    probe_rows: list[dict[str, object]],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Return terminal-rule mining summaries."""
    low_deltas = low_exact_boundary_deltas(candidate_bound)
    low_signatures = low_exact_terminal_signatures(candidate_bound, visible_divisor_bound)
    summaries: list[dict[str, object]] = []
    grouped: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((int(row["scale"]), int(row["anchor_p"])), []).append(row)
    base_by_scale: dict[int, dict[str, int]] = {}
    for row in probe_rows:
        scale = int(row["scale"])
        base = base_by_scale.setdefault(scale, {"emitted": 0, "pgs": 0, "chain": 0})
        if row["q"] is not None:
            base["emitted"] += 1
        if row["source"] == PGS_SOURCE:
            base["pgs"] += 1
        if row["source"] == CHAIN_FALLBACK_SOURCE:
            base["chain"] += 1

    for scale in sorted({key[0] for key in grouped}):
        chains = [chain for key, chain in grouped.items() if key[0] == scale]
        base = base_by_scale[scale]
        for rule_id in RULE_IDS:
            selected = [select_rule(rule_id, chain, low_deltas, low_signatures) for chain in chains]
            selected = [row for row in selected if row is not None]
            correct = sum(1 for row in selected if bool(row["is_terminal_for_audit_only"]))
            failures = len(selected) - correct
            projected_pgs = base["pgs"] + correct
            emitted = base["emitted"]
            summaries.append(
                {
                    "scale": scale,
                    "rule_id": rule_id,
                    "chain_rows": len(chains),
                    "top1_correct": correct,
                    "top1_recall": 0.0 if not chains else correct / len(chains),
                    "would_convert_chain_fallback_to_pgs": correct,
                    "would_create_audit_failures": failures,
                    "net_pgs_gain_points": (
                        0.0 if not emitted else (correct / emitted) * 100.0
                    ),
                    "projected_pgs_rate": (
                        0.0 if not emitted else projected_pgs / emitted
                    ),
                    "projected_pgs_percent": (
                        0.0 if not emitted else (projected_pgs / emitted) * 100.0
                    ),
                }
            )
    return summaries


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
    """Build the terminal-certificate miner CLI."""
    parser = argparse.ArgumentParser(
        description="Mine terminal certificates inside shadow-chain fallback rows."
    )
    parser.add_argument("--anchors", type=int, nargs="+", required=True)
    parser.add_argument("--sample-size", type=int, required=True)
    parser.add_argument("--candidate-bound", type=int, default=128)
    parser.add_argument("--chain-limit", type=int, default=DEFAULT_CHAIN_LIMIT)
    parser.add_argument(
        "--visible-divisor-bound",
        type=int,
        default=DEFAULT_VISIBLE_DIVISOR_BOUND,
    )
    parser.add_argument(
        "--probe-rows",
        type=Path,
        default=Path("output/simple_pgs_high_scale_chain_probe/rows.jsonl"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run terminal-certificate mining."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scale_set = {int(scale) for scale in args.anchors}
    probe_rows = [
        row
        for row in read_jsonl(args.probe_rows)
        if int(row["scale"]) in scale_set
    ]
    if args.sample_size:
        limited: list[dict[str, object]] = []
        for scale in args.anchors:
            scale_rows = [row for row in probe_rows if int(row["scale"]) == int(scale)]
            limited.extend(scale_rows[: int(args.sample_size)])
        probe_rows = limited
    chain_records = [
        row for row in probe_rows if row["source"] == CHAIN_FALLBACK_SOURCE
    ]
    node_rows: list[dict[str, object]] = []
    for record in chain_records:
        node_rows.extend(
            chain_node_rows_for_record(
                record,
                args.candidate_bound,
                args.chain_limit,
                args.visible_divisor_bound,
            )
        )
    summaries = summarize_rules(
        node_rows,
        probe_rows,
        args.candidate_bound,
        args.visible_divisor_bound,
    )
    write_jsonl(node_rows, args.output_dir / "chain_nodes.jsonl")
    write_csv(summaries, args.output_dir / "summary.csv")
    write_json({"summary": summaries}, args.output_dir / "summary.json")
    for row in summaries:
        print(
            "scale={scale} rule={rule_id} top1={top1_recall:.4f} "
            "failures={would_create_audit_failures} "
            "projected_pgs={projected_pgs_percent:.2f}%".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

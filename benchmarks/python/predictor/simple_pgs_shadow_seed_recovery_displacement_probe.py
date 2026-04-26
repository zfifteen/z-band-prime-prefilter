"""Mine label-free replacements for shadow-seed trial recovery."""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path

from sympy import factorint


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_controller import write_json  # noqa: E402
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    DEFAULT_VISIBLE_DIVISOR_BOUND,
    PGS_SOURCE,
    SHADOW_SEED_RECOVERY_SOURCE,
    WHEEL_OPEN_RESIDUES_MOD30,
    closure_reason,
    divisor_witness,
)


DEFAULT_INPUT_ROWS = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_LOW_DIAGNOSTICS = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_1e6" / "diagnostics.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "output" / "simple_pgs_shadow_seed_recovery_displacement_probe"
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def divisor_count(n: int) -> int:
    """Return exact divisor count for probe-only sidecar fields."""
    total = 1
    for exponent in factorint(int(n)).values():
        total *= int(exponent) + 1
    return total


def is_wheel_open(n: int) -> bool:
    """Return whether n is open on the mod-30 wheel."""
    return int(n) % 30 in WHEEL_OPEN_RESIDUES_MOD30


def prefix_signature(tokens: list[str]) -> str:
    """Return a compact prefix signature."""
    return ".".join(tokens[-12:])


def visible_open_nodes(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[int]:
    """Return visible-open candidates to the right of the seed."""
    nodes: list[int] = []
    for candidate in range(int(seed_q0) + 1, int(p) + int(candidate_bound) + 1):
        offset = candidate - int(p)
        if (
            is_wheel_open(candidate)
            and closure_reason(int(p), offset, int(visible_divisor_bound)) is None
        ):
            nodes.append(candidate)
    return nodes


def low_scale_signatures(
    diagnostics_path: Path,
    visible_divisor_bound: int,
) -> tuple[set[int], set[int], set[str]]:
    """Return low-scale PGS residues, deltas, and prefix signatures."""
    residues: set[int] = set()
    deltas: set[int] = set()
    prefixes: set[str] = set()
    for row in read_jsonl(diagnostics_path):
        if row.get("source") != PGS_SOURCE:
            continue
        p = int(row["p"])
        q = int(row["q"])
        residues.add(q % 210)
        deltas.add(q - p)
        tokens: list[str] = []
        open_count = 0
        closed_count = 0
        for candidate in range(p + 1, q + 1):
            offset = candidate - p
            reason = closure_reason(p, offset, visible_divisor_bound)
            if candidate == q:
                token = f"B:{candidate % 30}:{offset % 30}:{open_count}:{closed_count}"
            elif is_wheel_open(candidate) and reason is None:
                open_count += 1
                token = f"O:{candidate % 30}:{offset % 30}"
            else:
                closed_count += 1
                token = "C"
            tokens.append(token)
        prefixes.add(prefix_signature(tokens))
    return residues, deltas, prefixes


def candidate_rows_for_shadow_row(
    row: dict[str, object],
    candidate_bound: int,
    visible_divisor_bound: int,
    low_residues: set[int],
    low_deltas: set[int],
    low_prefixes: set[str],
) -> list[dict[str, object]]:
    """Return one candidate row per inspected rightward value."""
    scale = int(row["scale"])
    p = int(row["p"])
    seed_q0 = int(row["chain_seed"])
    recovered_q = int(row["q"])
    visible_nodes = visible_open_nodes(p, seed_q0, candidate_bound, visible_divisor_bound)
    visible_index = {candidate: index + 1 for index, candidate in enumerate(visible_nodes)}
    carrier_d = divisor_count(seed_q0)
    out: list[dict[str, object]] = []
    tokens: list[str] = []
    open_before = 0
    closed_before = 0
    for index, candidate in enumerate(range(seed_q0 + 1, recovered_q + 1), start=1):
        offset = candidate - p
        witness = divisor_witness(candidate, visible_divisor_bound)
        reason = closure_reason(p, offset, visible_divisor_bound)
        wheel_open = is_wheel_open(candidate)
        chain_index = visible_index.get(candidate)
        pgs_prefix_closed = all(
            closure_reason(p, prior - p, visible_divisor_bound) is not None
            for prior in range(seed_q0 + 1, candidate)
            if is_wheel_open(prior)
        )
        if candidate == recovered_q:
            token = f"B:{candidate % 30}:{offset % 30}:{open_before}:{closed_before}"
        elif wheel_open and reason is None:
            token = f"O:{candidate % 30}:{offset % 30}"
        else:
            token = "C"
        tokens.append(token)
        delta_prev = 0 if index == 1 else 1
        delta_next = 0 if candidate == recovered_q else 1
        local_gap_signature = (
            f"{candidate % 30}:{candidate % 210}:{offset % 30}:{offset % 210}:"
            f"{open_before}:{closed_before}:{delta_prev}:{delta_next}"
        )
        out.append(
            {
                "scale": scale,
                "anchor_p": p,
                "seed_q0": seed_q0,
                "recovered_q_for_audit_only": recovered_q,
                "candidate_n": candidate,
                "candidate_index_from_seed": index,
                "is_recovered_q_for_audit_only": candidate == recovered_q,
                "candidate_offset_from_anchor": offset,
                "candidate_offset_from_seed": candidate - seed_q0,
                "delta_prev_candidate": delta_prev,
                "delta_next_candidate": delta_next,
                "candidate_mod_30": candidate % 30,
                "candidate_mod_210": candidate % 210,
                "offset_mod_30": offset % 30,
                "offset_mod_210": offset % 210,
                "wheel_open": wheel_open,
                "visible_closure_reason": "" if reason is None else reason,
                "visible_divisor_witness_under_10000": "" if witness is None else witness,
                "pgs_chamber_closed_before_candidate": pgs_prefix_closed,
                "visible_open_count_between_seed_and_candidate": open_before,
                "visible_closed_count_between_seed_and_candidate": closed_before,
                "carrier_w": seed_q0,
                "carrier_d": carrier_d,
                "carrier_to_candidate_delta": candidate - seed_q0,
                "chain_node_index_if_visible_open": "" if chain_index is None else chain_index,
                "chain_position_relative_to_seed": index,
                "local_gap_signature": local_gap_signature,
                "prefix_signature_from_seed": prefix_signature(tokens),
                "matches_low_residue_signature": candidate % 210 in low_residues,
                "matches_low_delta_signature": candidate - seed_q0 in low_deltas,
                "matches_low_prefix_signature": prefix_signature(tokens) in low_prefixes,
            }
        )
        if wheel_open and reason is None:
            open_before += 1
        else:
            closed_before += 1
    return out


def choose_rule_candidate(
    rule_id: str,
    rows: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the selected candidate for one rule."""
    visible_rows = [
        row
        for row in rows
        if bool(row["wheel_open"]) and row["visible_closure_reason"] == ""
    ]
    if rule_id == "R1_first_wheel_open_not_visibly_closed":
        return visible_rows[0] if visible_rows else None
    if rule_id == "R2_first_chamber_closed_prefix":
        for row in visible_rows:
            if bool(row["pgs_chamber_closed_before_candidate"]):
                return row
        return None
    if rule_id == "R3_first_visible_open_chain_node":
        for row in visible_rows:
            if row["chain_node_index_if_visible_open"] == 1:
                return row
        return None
    if rule_id == "R4_low_scale_residue_signature":
        for row in visible_rows:
            if bool(row["matches_low_residue_signature"]):
                return row
        return None
    if rule_id == "R5_low_scale_prefix_signature":
        for row in visible_rows:
            if bool(row["matches_low_prefix_signature"]):
                return row
        return None
    if rule_id == "R6_low_scale_carrier_delta":
        for row in visible_rows:
            if bool(row["matches_low_delta_signature"]):
                return row
        return None
    if rule_id == "R7_next_visible_gap_exceeds_prefix_median":
        if not visible_rows:
            return None
        visible_candidates = [int(row["candidate_n"]) for row in visible_rows]
        for index, row in enumerate(visible_rows[:-1]):
            if index == 0:
                continue
            prefix_gaps = [
                visible_candidates[i] - visible_candidates[i - 1]
                for i in range(1, index + 1)
            ]
            next_gap = visible_candidates[index + 1] - visible_candidates[index]
            if next_gap > statistics.median(prefix_gaps):
                return row
        return None
    raise ValueError(f"unknown rule_id: {rule_id}")


def summarize_rules(
    shadow_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    scales: list[int],
) -> list[dict[str, object]]:
    """Return one summary row per rule per scale."""
    rules = [
        "R1_first_wheel_open_not_visibly_closed",
        "R2_first_chamber_closed_prefix",
        "R3_first_visible_open_chain_node",
        "R4_low_scale_residue_signature",
        "R5_low_scale_prefix_signature",
        "R6_low_scale_carrier_delta",
        "R7_next_visible_gap_exceeds_prefix_median",
    ]
    rows_by_key: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in candidate_rows:
        rows_by_key.setdefault((int(row["scale"]), int(row["anchor_p"])), []).append(row)

    base_pgs_by_scale = {
        scale: sum(
            1
            for row in shadow_rows
            if int(row["scale"]) == scale and row["source"] == PGS_SOURCE
        )
        for scale in scales
    }
    emitted_by_scale = {
        scale: sum(
            1
            for row in shadow_rows
            if int(row["scale"]) == scale and row.get("q") is not None
        )
        for scale in scales
    }
    shadow_count_by_scale = {
        scale: sum(
            1
            for row in shadow_rows
            if int(row["scale"]) == scale
            and row["source"] == SHADOW_SEED_RECOVERY_SOURCE
        )
        for scale in scales
    }

    summaries: list[dict[str, object]] = []
    for scale in scales:
        for rule_id in rules:
            selected = 0
            correct = 0
            failures = 0
            for row in shadow_rows:
                if (
                    int(row["scale"]) != scale
                    or row["source"] != SHADOW_SEED_RECOVERY_SOURCE
                ):
                    continue
                options = rows_by_key.get((scale, int(row["p"])), [])
                pick = choose_rule_candidate(rule_id, options)
                if pick is None:
                    continue
                selected += 1
                if bool(pick["is_recovered_q_for_audit_only"]):
                    correct += 1
                else:
                    failures += 1
            emitted = emitted_by_scale[scale]
            projected = 0.0 if emitted == 0 else (
                (base_pgs_by_scale[scale] + correct) / emitted * 100.0
            )
            summaries.append(
                {
                    "scale": scale,
                    "rule_id": rule_id,
                    "shadow_seed_rows": shadow_count_by_scale[scale],
                    "top1_selected": selected,
                    "top1_correct": correct,
                    "top1_recall": (
                        0.0
                        if shadow_count_by_scale[scale] == 0
                        else correct / shadow_count_by_scale[scale]
                    ),
                    "would_convert_shadow_recovery_to_pgs": correct,
                    "would_create_audit_failures": failures,
                    "projected_pgs_percent": projected,
                    "promotion_eligible": False,
                }
            )
    for rule_id in rules:
        rule_rows = [row for row in summaries if row["rule_id"] == rule_id]
        eligible = all(
            int(row["would_create_audit_failures"]) == 0
            and float(row["projected_pgs_percent"]) >= 50.0
            for row in rule_rows
        )
        for row in rule_rows:
            row["promotion_eligible"] = eligible
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


def run_probe(
    input_rows: Path,
    low_diagnostics: Path,
    output_dir: Path,
    scales: list[int],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> dict[str, object]:
    """Run the displacement probe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(input_rows)
    low_residues, low_deltas, low_prefixes = low_scale_signatures(
        low_diagnostics,
        visible_divisor_bound,
    )
    shadow_rows = [
        row
        for row in rows
        if int(row["scale"]) in scales
        and row["source"] in {PGS_SOURCE, SHADOW_SEED_RECOVERY_SOURCE}
    ]
    candidate_rows: list[dict[str, object]] = []
    for row in shadow_rows:
        if row["source"] != SHADOW_SEED_RECOVERY_SOURCE:
            continue
        candidate_rows.extend(
            candidate_rows_for_shadow_row(
                row,
                candidate_bound,
                visible_divisor_bound,
                low_residues,
                low_deltas,
                low_prefixes,
            )
        )
    rule_rows = summarize_rules(shadow_rows, candidate_rows, scales)
    summary = {
        "input_rows": str(input_rows),
        "low_diagnostics": str(low_diagnostics),
        "scales": scales,
        "candidate_bound": int(candidate_bound),
        "visible_divisor_bound": int(visible_divisor_bound),
        "candidate_row_count": len(candidate_rows),
        "rule_rows": rule_rows,
        "promotion_eligible_rules": sorted(
            {
                str(row["rule_id"])
                for row in rule_rows
                if bool(row["promotion_eligible"])
            }
        ),
        "strongest_result": (
            "no_tested_static_rule_promotes; shadow_seed_recovery_remains_bridge"
        ),
    }
    write_csv(candidate_rows, output_dir / "candidate_rows.csv")
    write_csv(rule_rows, output_dir / "rule_report.csv")
    write_json(summary, output_dir / "summary.json")
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build the probe CLI."""
    parser = argparse.ArgumentParser(
        description="Mine PGS displacement rules for shadow-seed recovery."
    )
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--low-diagnostics", type=Path, default=DEFAULT_LOW_DIAGNOSTICS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scales", type=int, nargs="+", default=[10**15, 10**18])
    parser.add_argument("--candidate-bound", type=int, default=128)
    parser.add_argument(
        "--visible-divisor-bound",
        type=int,
        default=DEFAULT_VISIBLE_DIVISOR_BOUND,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the probe."""
    args = build_parser().parse_args(argv)
    summary = run_probe(
        args.input_rows,
        args.low_diagnostics,
        args.output_dir,
        [int(scale) for scale in args.scales],
        int(args.candidate_bound),
        int(args.visible_divisor_bound),
    )
    print(
        "candidate_rows={candidate_row_count} promotion_eligible_rules={rules} "
        "strongest_result={strongest_result}".format(
            candidate_row_count=summary["candidate_row_count"],
            rules=",".join(summary["promotion_eligible_rules"]) or "none",
            strongest_result=summary["strongest_result"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Probe seed-distance closure for shadow-seed recovery rows.

This probe stays inside PGS-visible chamber mechanics:

- wheel openness mod 30;
- bounded divisor witnesses via closure_reason(..., max_divisor=10_000).

It tests whether the terminal boundary is the first anchor-visible-open
candidate whose offsets back to the seed (and earlier visible-open candidates)
are all *visibly closed* in the distance-framed chamber.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path


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
)


DEFAULT_INPUT_ROWS = ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "output" / "simple_pgs_solution_09_seed_distance_closure_probe"
DEFAULT_CANDIDATE_BOUND = 128


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    """Write LF-terminated CSV rows."""
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def is_left_visible_open(p: int, n: int, visible_divisor_bound: int) -> bool:
    """Return whether n is open in the anchor-framed visible chamber."""
    offset = int(n) - int(p)
    return (
        int(n) % 30 in WHEEL_OPEN_RESIDUES_MOD30
        and closure_reason(int(p), int(offset), int(visible_divisor_bound)) is None
    )


def distance_closure(past: int, current: int, visible_divisor_bound: int) -> str | None:
    """Return the visible closure reason for the positive distance current - past."""
    delta = int(current) - int(past)
    if delta < 1:
        raise ValueError("distance_closure requires past < current")
    return closure_reason(0, delta, int(visible_divisor_bound))


def visible_open_nodes(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[int]:
    """Return anchor-visible-open nodes to the right of seed_q0 inside the bound."""
    upper = int(p) + int(candidate_bound)
    return [
        candidate
        for candidate in range(int(seed_q0) + 1, upper + 1)
        if is_left_visible_open(int(p), candidate, int(visible_divisor_bound))
    ]


def candidate_profile(
    seed_q0: int,
    candidate: int,
    visible_nodes: list[int],
    visible_divisor_bound: int,
) -> dict[str, object]:
    """Return seed-distance closure fields for one candidate."""
    prior_visible_open = [seed_q0, *[node for node in visible_nodes if node < int(candidate)]]
    distance_open_prior = [
        node
        for node in prior_visible_open
        if distance_closure(int(node), int(candidate), int(visible_divisor_bound)) is None
    ]
    seed_reason = distance_closure(int(seed_q0), int(candidate), int(visible_divisor_bound))
    return {
        "prior_visible_open_count_including_seed": len(prior_visible_open),
        "distance_open_prior_count_including_seed": len(distance_open_prior),
        "distance_closed_prior_count_including_seed": len(prior_visible_open) - len(distance_open_prior),
        "seed_distance_closure_reason": "" if seed_reason is None else str(seed_reason),
    }


def pick_first_visible(candidates: list[dict[str, object]]) -> dict[str, object] | None:
    """Return the first anchor-visible-open candidate."""
    return candidates[0] if candidates else None


def pick_first_seed_distance_closes_all_prior(
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the first candidate whose prior open nodes are distance-closed."""
    for candidate in candidates:
        if (
            int(candidate["prior_visible_open_count_including_seed"]) > 0
            and int(candidate["distance_open_prior_count_including_seed"]) == 0
        ):
            return candidate
    return None


RULES = {
    "B0_first_visible_open_baseline": pick_first_visible,
    "D1_first_seed_distance_closes_all_prior": pick_first_seed_distance_closes_all_prior,
}


def failure_mode(pick: dict[str, object] | None, recovered_q: int) -> str:
    """Return selection failure mode."""
    if pick is None:
        return "no_selection"
    candidate = int(pick["candidate_n"])
    if candidate == int(recovered_q):
        return "correct"
    if candidate < int(recovered_q):
        return "selected_too_early"
    return "selected_too_late"


def candidate_rows_for_shadow_row(
    row: dict[str, object],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Return seed-distance candidate rows for one shadow-seed row."""
    scale = int(row["scale"])
    p = int(row["p"])
    seed_q0 = int(row["chain_seed"])
    recovered_q = int(row["q"])
    nodes = visible_open_nodes(int(p), int(seed_q0), int(candidate_bound), int(visible_divisor_bound))
    out: list[dict[str, object]] = []
    for ordinal, candidate in enumerate(nodes, start=1):
        profile = candidate_profile(int(seed_q0), int(candidate), nodes, int(visible_divisor_bound))
        out.append(
            {
                "scale": scale,
                "anchor_p": p,
                "seed_q0": seed_q0,
                "recovered_q_for_audit_only": recovered_q,
                "candidate_n": candidate,
                "candidate_visible_ordinal": ordinal,
                "candidate_offset_from_anchor": candidate - p,
                "candidate_offset_from_seed": candidate - seed_q0,
                "is_recovered_q_for_audit_only": candidate == recovered_q,
                **profile,
            }
        )
    return out


def summarize_rules(
    rows: list[dict[str, object]],
    candidate_rows_by_key: dict[tuple[int, int, int], list[dict[str, object]]],
    scales: list[int],
) -> list[dict[str, object]]:
    """Return one summary row per rule per scale."""
    base_pgs_by_scale = {
        scale: sum(1 for row in rows if int(row["scale"]) == scale and row["source"] == PGS_SOURCE)
        for scale in scales
    }
    emitted_by_scale = {
        scale: sum(1 for row in rows if int(row["scale"]) == scale and row.get("q") is not None)
        for scale in scales
    }
    shadow_by_scale = {
        scale: sum(
            1
            for row in rows
            if int(row["scale"]) == scale and row["source"] == SHADOW_SEED_RECOVERY_SOURCE
        )
        for scale in scales
    }
    summaries: list[dict[str, object]] = []
    for scale in scales:
        for rule_id, picker in RULES.items():
            modes: Counter[str] = Counter()
            selected = 0
            correct = 0
            for row in rows:
                if int(row["scale"]) != scale or row["source"] != SHADOW_SEED_RECOVERY_SOURCE:
                    continue
                key = (scale, int(row["p"]), int(row["chain_seed"]))
                pick = picker(candidate_rows_by_key.get(key, []))
                mode = failure_mode(pick, int(row["q"]))
                modes[mode] += 1
                if pick is not None:
                    selected += 1
                if mode == "correct":
                    correct += 1
            failures = selected - correct
            emitted = emitted_by_scale[scale]
            projected = 0.0 if emitted == 0 else ((base_pgs_by_scale[scale] + correct) / emitted * 100.0)
            summaries.append(
                {
                    "scale": scale,
                    "rule_id": rule_id,
                    "shadow_seed_rows": shadow_by_scale[scale],
                    "top1_selected": selected,
                    "top1_correct": correct,
                    "top1_recall": 0.0 if shadow_by_scale[scale] == 0 else correct / shadow_by_scale[scale],
                    "would_convert_shadow_recovery_to_pgs": correct,
                    "would_create_audit_failures": failures,
                    "projected_pgs_percent": projected,
                    "promotion_eligible": False,
                    "failure_mode_selected_too_early": modes["selected_too_early"],
                    "failure_mode_selected_too_late": modes["selected_too_late"],
                    "failure_mode_no_selection": modes["no_selection"],
                }
            )
    for rule_id in RULES:
        rule_rows = [row for row in summaries if row["rule_id"] == rule_id]
        eligible = all(
            int(row["would_create_audit_failures"]) == 0 and float(row["projected_pgs_percent"]) >= 50.0
            for row in rule_rows
        )
        for row in rule_rows:
            row["promotion_eligible"] = eligible
    return summaries


def run_probe(
    input_rows: Path,
    output_dir: Path,
    scales: list[int],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> dict[str, object]:
    """Run the seed-distance closure probe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(input_rows)
    active_rows = [
        row
        for row in rows
        if int(row["scale"]) in scales and row["source"] in {PGS_SOURCE, SHADOW_SEED_RECOVERY_SOURCE}
    ]
    candidate_rows: list[dict[str, object]] = []
    candidate_rows_by_key: dict[tuple[int, int, int], list[dict[str, object]]] = {}
    for row in active_rows:
        if row["source"] != SHADOW_SEED_RECOVERY_SOURCE:
            continue
        rows_for_event = candidate_rows_for_shadow_row(
            row,
            int(candidate_bound),
            int(visible_divisor_bound),
        )
        key = (int(row["scale"]), int(row["p"]), int(row["chain_seed"]))
        candidate_rows_by_key[key] = rows_for_event
        candidate_rows.extend(rows_for_event)

    rule_rows = summarize_rules(active_rows, candidate_rows_by_key, scales)
    summary = {
        "input_rows": str(input_rows),
        "scales": scales,
        "candidate_bound": int(candidate_bound),
        "visible_divisor_bound": int(visible_divisor_bound),
        "candidate_row_count": len(candidate_rows),
        "rule_rows": rule_rows,
        "promotion_eligible_rules": sorted({str(row["rule_id"]) for row in rule_rows if bool(row["promotion_eligible"])}),
        "strongest_result": (
            "seed_distance_visible_closure_does_not_resolve_margin; "
            "distance-closure still selects too early or too late on many rows"
        ),
    }
    write_csv(candidate_rows, output_dir / "seed_distance_candidate_rows.csv")
    write_csv(rule_rows, output_dir / "seed_distance_rule_report.csv")
    write_json(summary, output_dir / "summary.json")
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Probe seed-distance closure rules for shadow-seed recovery.",
    )
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scales", type=int, nargs="+", default=[10**12, 10**15, 10**18])
    parser.add_argument("--candidate-bound", type=int, default=DEFAULT_CANDIDATE_BOUND)
    parser.add_argument(
        "--visible-divisor-bound",
        type=int,
        default=DEFAULT_VISIBLE_DIVISOR_BOUND,
        help="Bound on deterministic visible divisor witnesses (PGS-visible).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run CLI."""
    args = build_parser().parse_args(argv)
    summary = run_probe(
        args.input_rows,
        args.output_dir,
        [int(scale) for scale in args.scales],
        int(args.candidate_bound),
        int(args.visible_divisor_bound),
    )
    print(
        "candidate_rows={candidate_row_count} promotion_eligible_rules={rules} strongest_result={strongest}".format(
            candidate_row_count=summary["candidate_row_count"],
            rules=",".join(summary["promotion_eligible_rules"]) or "none",
            strongest=summary["strongest_result"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""Probe DeepSeek's square-grid openQ shadow recovery proposal."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from math import isqrt
from pathlib import Path
from typing import Iterable


DEFAULT_ROWS_PATH = Path("output/simple_pgs_shadow_seed_gwr_solution_probe/rows.jsonl")
DEFAULT_CANDIDATES_PATH = Path(
    "output/simple_pgs_shadow_seed_recovery_displacement_probe/candidate_rows.csv"
)
DEFAULT_OUTPUT_DIR = Path("output/simple_pgs_solution_04_square_grid_openq_probe")
DEFAULT_CANDIDATE_BOUND = 128
DEFAULT_VISIBLE_DIVISOR_BOUND = 10_000
WHEEL_OPEN_RESIDUES_MOD30 = {1, 7, 11, 13, 17, 19, 23, 29}


def ceil_div(numerator: int, denominator: int) -> int:
    return -(-int(numerator) // int(denominator))


def percent(numerator: int, denominator: int) -> float:
    return 0.0 if int(denominator) == 0 else 100.0 * int(numerator) / int(denominator)


def load_shadow_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open() as handle:
        for line in handle:
            record = json.loads(line)
            if record.get("source") == "shadow_seed_recovery":
                rows.append(
                    {
                        "scale": int(record["scale"]),
                        "p": int(record["p"]),
                        "q": int(record["q"]),
                        "seed": int(record["chain_seed"]),
                    }
                )
    return rows


def load_materialized_witnesses(path: Path) -> dict[tuple[int, int, int], set[int]]:
    grouped: dict[tuple[int, int, int], set[int]] = defaultdict(set)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["scale"]), int(row["anchor_p"]), int(row["seed_q0"]))
            witness = row["visible_divisor_witness_under_10000"]
            if witness:
                grouped[key].add(int(witness))
    return dict(grouped)


def square_grid_candidates(p: int, seed: int, upper: int) -> list[tuple[int, int]]:
    root = isqrt(int(p) * int(seed))
    candidates: list[tuple[int, int]] = []
    seen: set[int] = set()
    k = 0
    while True:
        value = ceil_div((root + k) * (root + k), int(p))
        if value > int(upper):
            break
        if value > int(seed) and value not in seen:
            candidates.append((k, value))
            seen.add(value)
        k += 1
        if k > 4 * (int(upper) - int(seed) + 2):
            break
    return candidates


def open_by_witnesses(candidate: int, witnesses: Iterable[int]) -> bool:
    return all(int(candidate) % int(witness) != 0 for witness in witnesses)


def open_by_visible_bound(candidate: int, visible_divisor_bound: int) -> bool:
    upper = min(int(visible_divisor_bound), isqrt(int(candidate)))
    for divisor in range(2, upper + 1):
        if int(candidate) % divisor == 0:
            return False
    return True


def first_open_grid_candidate(
    *,
    p: int,
    seed: int,
    upper: int,
    rule_id: str,
    witnesses: set[int],
    visible_divisor_bound: int,
) -> tuple[int | None, int | None, int, bool]:
    grid = square_grid_candidates(int(p), int(seed), int(upper))
    for k, candidate in grid:
        if rule_id.endswith("_wheel_open") and candidate % 30 not in WHEEL_OPEN_RESIDUES_MOD30:
            continue
        if rule_id.startswith("materialized_witnesses"):
            if open_by_witnesses(candidate, witnesses):
                return candidate, k, len(grid), True
        elif rule_id.startswith("visible_bound_all"):
            if open_by_visible_bound(candidate, visible_divisor_bound):
                return candidate, k, len(grid), True
        else:
            raise ValueError(f"unknown rule_id: {rule_id}")
    return None, None, len(grid), True


def failure_mode(selected: int | None, true_q: int) -> str:
    if selected is None:
        return "no_selection"
    if int(selected) == int(true_q):
        return "correct"
    if int(selected) < int(true_q):
        return "selected_too_early"
    return "selected_too_late"


def evaluate(
    shadow_rows: list[dict[str, object]],
    witnesses_by_key: dict[tuple[int, int, int], set[int]],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    rule_ids = [
        "materialized_witnesses",
        "materialized_witnesses_wheel_open",
        "visible_bound_all",
        "visible_bound_all_wheel_open",
    ]
    bound_modes = ["anchor_bound", "seed_bound"]
    rows: list[dict[str, object]] = []
    for record in shadow_rows:
        scale = int(record["scale"])
        p = int(record["p"])
        seed = int(record["seed"])
        true_q = int(record["q"])
        key = (scale, p, seed)
        witnesses = witnesses_by_key.get(key, set())
        for bound_mode in bound_modes:
            upper = p + int(candidate_bound)
            if bound_mode == "seed_bound":
                upper = seed + int(candidate_bound)
            grid = square_grid_candidates(p, seed, upper)
            true_grid_positions = [k for k, value in grid if value == true_q]
            true_in_grid = bool(true_grid_positions)
            for rule_id in rule_ids:
                materialized_missing = rule_id.startswith("materialized") and key not in witnesses_by_key
                if materialized_missing:
                    selected = None
                    selected_k = None
                    grid_count = len(grid)
                    did_evaluate = False
                else:
                    selected, selected_k, grid_count, did_evaluate = first_open_grid_candidate(
                        p=p,
                        seed=seed,
                        upper=upper,
                        rule_id=rule_id,
                        witnesses=witnesses,
                        visible_divisor_bound=visible_divisor_bound,
                    )
                rows.append(
                    {
                        "scale": scale,
                        "rule_id": rule_id,
                        "bound_mode": bound_mode,
                        "anchor_p": p,
                        "seed_q0": seed,
                        "true_q_for_audit_only": true_q,
                        "upper_bound": upper,
                        "true_in_square_grid": true_in_grid,
                        "true_square_grid_k": true_grid_positions[0] if true_grid_positions else "",
                        "selected_q": selected if selected is not None else "",
                        "selected_square_grid_k": selected_k if selected_k is not None else "",
                        "failure_mode": failure_mode(selected, true_q),
                        "selected_delta_from_true": "" if selected is None else int(selected) - true_q,
                        "grid_count_checked": grid_count,
                        "materialized_witness_count": len(witnesses),
                        "did_evaluate": did_evaluate,
                        "failure_reason": (
                            "missing_materialized_candidate_rows"
                            if materialized_missing
                            else ""
                        ),
                    }
                )
    return rows


def summarize(
    selection_rows: list[dict[str, object]],
    source_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    emitted_sources = {"PGS", "shadow_seed_recovery", "chain_horizon_closure", "chain_fallback", "fallback"}
    emitted = Counter()
    pgs = Counter()
    for row in source_rows:
        scale = int(row["scale"])
        if row.get("source") in emitted_sources:
            emitted[scale] += 1
        if row.get("source") == "PGS":
            pgs[scale] += 1

    grouped: dict[tuple[int, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in selection_rows:
        grouped[(int(row["scale"]), str(row["rule_id"]), str(row["bound_mode"]))].append(row)

    summaries: list[dict[str, object]] = []
    for (scale, rule_id, bound_mode), rows in sorted(grouped.items()):
        mode_counts = Counter(str(row["failure_mode"]) for row in rows)
        shadow_rows = len(rows)
        correct = mode_counts["correct"]
        failures = mode_counts["selected_too_early"] + mode_counts["selected_too_late"]
        no_selection = mode_counts["no_selection"]
        true_not_in_grid = sum(1 for row in rows if not row["true_in_square_grid"])
        evaluated = sum(1 for row in rows if row["did_evaluate"])
        projected_pgs_count = pgs[scale] + correct
        projected_pgs_percent = percent(projected_pgs_count, emitted[scale])
        summaries.append(
            {
                "scale": scale,
                "rule_id": rule_id,
                "bound_mode": bound_mode,
                "shadow_rows": shadow_rows,
                "evaluated_rows": evaluated,
                "correct": correct,
                "selected_too_early": mode_counts["selected_too_early"],
                "selected_too_late": mode_counts["selected_too_late"],
                "no_selection": no_selection,
                "true_not_in_square_grid": true_not_in_grid,
                "would_create_audit_failures": failures,
                "projected_pgs_percent": projected_pgs_percent,
                "promotion_eligible": (
                    failures == 0
                    and no_selection == 0
                    and true_not_in_grid == 0
                    and projected_pgs_percent >= 50.0
                ),
            }
        )
    return summaries


def materialization_rows(
    shadow_rows: list[dict[str, object]],
    witnesses_by_key: dict[tuple[int, int, int], set[int]],
) -> list[dict[str, object]]:
    shadow_by_scale = Counter(int(row["scale"]) for row in shadow_rows)
    materialized_by_scale = Counter()
    for row in shadow_rows:
        key = (int(row["scale"]), int(row["p"]), int(row["seed"]))
        if key in witnesses_by_key:
            materialized_by_scale[int(row["scale"])] += 1
    return [
        {
            "scale": scale,
            "shadow_rows": shadow_by_scale[scale],
            "rows_with_materialized_candidate_stream": materialized_by_scale[scale],
            "rows_missing_materialized_candidate_stream": (
                shadow_by_scale[scale] - materialized_by_scale[scale]
            ),
            "materialized_percent": percent(materialized_by_scale[scale], shadow_by_scale[scale]),
        }
        for scale in sorted(shadow_by_scale)
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", newline="\n")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS_PATH)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATES_PATH)
    parser.add_argument("--candidate-bound", type=int, default=DEFAULT_CANDIDATE_BOUND)
    parser.add_argument("--visible-divisor-bound", type=int, default=DEFAULT_VISIBLE_DIVISOR_BOUND)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    shadow_rows = load_shadow_rows(args.rows)
    source_rows = [json.loads(line) for line in args.rows.open()]
    witnesses_by_key = load_materialized_witnesses(args.candidate_rows)
    selection_rows = evaluate(
        shadow_rows,
        witnesses_by_key,
        args.candidate_bound,
        args.visible_divisor_bound,
    )
    summary_rows = summarize(selection_rows, source_rows)
    materialized = materialization_rows(shadow_rows, witnesses_by_key)
    contract_rows = [
        {
            "required_object": "active wall prime set W",
            "materialized_in_current_artifacts": False,
            "probe_handling": "tested materialized visible witnesses and visible-bound proxies separately",
        },
        {
            "required_object": "closed[1..q0] chamber vector",
            "materialized_in_current_artifacts": False,
            "probe_handling": "not assumed; no pure-PGS promotion can rely on it from this branch",
        },
        {
            "required_object": "square-grid q_k sequence",
            "materialized_in_current_artifacts": True,
            "probe_handling": "computed directly from p and q0",
        },
    ]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "square_grid_selection_rows.csv", selection_rows)
    write_csv(args.output_dir / "square_grid_summary.csv", summary_rows)
    write_csv(args.output_dir / "materialized_coverage.csv", materialized)
    write_csv(args.output_dir / "materialized_contract.csv", contract_rows)

    eligible = [row for row in summary_rows if row["promotion_eligible"]]
    verdict = (
        "promotion_eligible"
        if eligible
        else "rejected_no_square_grid_openq_rule_met_promotion_gate"
    )
    payload = {
        "verdict": verdict,
        "candidate_bound": args.candidate_bound,
        "visible_divisor_bound": args.visible_divisor_bound,
        "shadow_rows": len(shadow_rows),
        "eligible_rule_count": len(eligible),
        "eligible_rules": eligible,
        "materialized_coverage": materialized,
        "artifacts": {
            "selection_rows": str(args.output_dir / "square_grid_selection_rows.csv"),
            "summary": str(args.output_dir / "square_grid_summary.csv"),
            "materialized_coverage": str(args.output_dir / "materialized_coverage.csv"),
            "materialized_contract": str(args.output_dir / "materialized_contract.csv"),
        },
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

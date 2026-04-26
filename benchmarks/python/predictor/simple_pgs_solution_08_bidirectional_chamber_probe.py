"""Probe bidirectional chamber closure for shadow-seed rows."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_controller import write_json  # noqa: E402
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    PGS_SOURCE,
    SHADOW_SEED_RECOVERY_SOURCE,
    WHEEL_OPEN_RESIDUES_MOD30,
    closure_reason,
)


DEFAULT_INPUT_ROWS = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "output" / "simple_pgs_solution_08_bidirectional_chamber_probe"
)
DEFAULT_CANDIDATE_BOUND = 128
DEFAULT_VISIBLE_DIVISOR_BOUND = 10_000
OPEN_RESIDUES_MOD210 = frozenset(
    residue for residue in range(210) if math.gcd(residue, 210) == 1
)


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
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def is_left_visible_open(
    p: int,
    n: int,
    visible_divisor_bound: int,
) -> bool:
    """Return whether n is open in the anchor-framed chamber."""
    offset = int(n) - int(p)
    return (
        int(n) % 30 in WHEEL_OPEN_RESIDUES_MOD30
        and closure_reason(int(p), offset, int(visible_divisor_bound)) is None
    )


def is_right_phase_open(candidate: int, interior: int, modulus: int) -> bool:
    """Return whether an interior point is open from the proposed boundary."""
    residue = (int(candidate) - int(interior)) % int(modulus)
    if int(modulus) == 30:
        return residue in WHEEL_OPEN_RESIDUES_MOD30
    if int(modulus) == 210:
        return residue in OPEN_RESIDUES_MOD210
    raise ValueError(f"unsupported modulus: {modulus}")


def visible_open_nodes(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[int]:
    """Return anchor-visible open nodes to the right of q0."""
    upper = int(p) + int(candidate_bound)
    return [
        candidate
        for candidate in range(int(seed_q0) + 1, upper + 1)
        if is_left_visible_open(int(p), candidate, int(visible_divisor_bound))
    ]


def candidate_profile(
    p: int,
    seed_q0: int,
    candidate: int,
    visible_nodes: list[int],
    visible_divisor_bound: int,
    right_modulus: int,
) -> dict[str, object]:
    """Return bidirectional profile fields for one candidate."""
    prior_visible = [node for node in visible_nodes if node < int(candidate)]
    right_open_prior = [
        node
        for node in prior_visible
        if is_right_phase_open(int(candidate), node, int(right_modulus))
    ]
    interior_left_open = [
        node
        for node in range(int(seed_q0) + 1, int(candidate))
        if is_left_visible_open(int(p), node, int(visible_divisor_bound))
    ]
    two_sided_defects = [
        node
        for node in interior_left_open
        if is_right_phase_open(int(candidate), node, int(right_modulus))
    ]
    return {
        "prior_visible_open_count": len(prior_visible),
        "right_open_prior_count": len(right_open_prior),
        "right_closed_prior_count": len(prior_visible) - len(right_open_prior),
        "two_sided_defect_count": len(two_sided_defects),
        "right_modulus": int(right_modulus),
    }


def pick_first_visible(
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the first anchor-visible open candidate."""
    return candidates[0] if candidates else None


def pick_first_prior_right_closed(
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return first candidate whose earlier visible nodes close from the right."""
    for candidate in candidates:
        if (
            int(candidate["prior_visible_open_count"]) > 0
            and int(candidate["right_open_prior_count"]) == 0
        ):
            return candidate
    return None


def pick_min_right_defect(
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the leftmost minimum right-defect candidate after one prior node."""
    scored = [
        candidate
        for candidate in candidates
        if int(candidate["prior_visible_open_count"]) > 0
    ]
    if not scored:
        return None
    return min(
        scored,
        key=lambda candidate: (
            int(candidate["right_open_prior_count"]),
            int(candidate["candidate_n"]),
        ),
    )


def pick_first_two_sided_closed(
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return first candidate whose left-open interior closes from the right."""
    for candidate in candidates:
        if (
            int(candidate["prior_visible_open_count"]) > 0
            and int(candidate["two_sided_defect_count"]) == 0
        ):
            return candidate
    return None


RULES = {
    "B0_first_visible_open_baseline": pick_first_visible,
    "B1_first_prior_right_closed_mod30": pick_first_prior_right_closed,
    "B2_min_right_defect_mod30": pick_min_right_defect,
    "B3_first_two_sided_closed_mod30": pick_first_two_sided_closed,
    "B4_first_prior_right_closed_mod210": pick_first_prior_right_closed,
    "B5_min_right_defect_mod210": pick_min_right_defect,
    "B6_first_two_sided_closed_mod210": pick_first_two_sided_closed,
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
    right_modulus: int,
) -> list[dict[str, object]]:
    """Return bidirectional candidate rows for one shadow-seed row."""
    scale = int(row["scale"])
    p = int(row["p"])
    seed_q0 = int(row["chain_seed"])
    recovered_q = int(row["q"])
    nodes = visible_open_nodes(
        p,
        seed_q0,
        int(candidate_bound),
        int(visible_divisor_bound),
    )
    out: list[dict[str, object]] = []
    for ordinal, candidate in enumerate(nodes, start=1):
        profile = candidate_profile(
            p,
            seed_q0,
            candidate,
            nodes,
            int(visible_divisor_bound),
            int(right_modulus),
        )
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
    shadow_rows: list[dict[str, object]],
    candidate_rows_by_key: dict[tuple[int, int, int, int], list[dict[str, object]]],
    scales: list[int],
) -> list[dict[str, object]]:
    """Return one summary row per rule per scale."""
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
        for rule_id, picker in RULES.items():
            right_modulus = 210 if rule_id.endswith("mod210") else 30
            modes: Counter[str] = Counter()
            selected = 0
            correct = 0
            for row in shadow_rows:
                if (
                    int(row["scale"]) != scale
                    or row["source"] != SHADOW_SEED_RECOVERY_SOURCE
                ):
                    continue
                key = (scale, int(row["p"]), int(row["chain_seed"]), right_modulus)
                pick = picker(candidate_rows_by_key.get(key, []))
                mode = failure_mode(pick, int(row["q"]))
                modes[mode] += 1
                if pick is not None:
                    selected += 1
                if mode == "correct":
                    correct += 1
            failures = selected - correct
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
                    "failure_mode_selected_too_early": modes["selected_too_early"],
                    "failure_mode_selected_too_late": modes["selected_too_late"],
                    "failure_mode_no_selection": modes["no_selection"],
                }
            )
    for rule_id in RULES:
        rule_rows = [row for row in summaries if row["rule_id"] == rule_id]
        eligible = all(
            int(row["would_create_audit_failures"]) == 0
            and float(row["projected_pgs_percent"]) >= 50.0
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
    """Run the bidirectional chamber probe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(input_rows)
    shadow_rows = [
        row
        for row in rows
        if int(row["scale"]) in scales
        and row["source"] in {PGS_SOURCE, SHADOW_SEED_RECOVERY_SOURCE}
    ]
    candidate_rows: list[dict[str, object]] = []
    candidate_rows_by_key: dict[
        tuple[int, int, int, int],
        list[dict[str, object]],
    ] = {}
    for row in shadow_rows:
        if row["source"] != SHADOW_SEED_RECOVERY_SOURCE:
            continue
        for right_modulus in (30, 210):
            rows_for_event = candidate_rows_for_shadow_row(
                row,
                int(candidate_bound),
                int(visible_divisor_bound),
                right_modulus,
            )
            key = (
                int(row["scale"]),
                int(row["p"]),
                int(row["chain_seed"]),
                right_modulus,
            )
            candidate_rows_by_key[key] = rows_for_event
            candidate_rows.extend(rows_for_event)
    rule_rows = summarize_rules(shadow_rows, candidate_rows_by_key, scales)
    summary = {
        "input_rows": str(input_rows),
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
            "bidirectional_right_phase_closure_does_not_promote; "
            "current_right_phase_adds_no_safe_boundary_margin"
        ),
    }
    write_csv(candidate_rows, output_dir / "bidirectional_candidate_rows.csv")
    write_csv(rule_rows, output_dir / "bidirectional_rule_report.csv")
    write_json(summary, output_dir / "summary.json")
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Probe bidirectional chamber rules for shadow-seed recovery."
    )
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scales", type=int, nargs="+", default=[10**12, 10**15, 10**18])
    parser.add_argument("--candidate-bound", type=int, default=DEFAULT_CANDIDATE_BOUND)
    parser.add_argument(
        "--visible-divisor-bound",
        type=int,
        default=DEFAULT_VISIBLE_DIVISOR_BOUND,
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

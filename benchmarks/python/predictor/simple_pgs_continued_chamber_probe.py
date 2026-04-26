"""Test continued-chamber correction ladders on shadow-seed rows."""

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
    SHADOW_SEED_RECOVERY_SOURCE,
    WHEEL_OPEN_RESIDUES_MOD30,
    closure_reason,
)


DEFAULT_INPUT_ROWS = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "output" / "simple_pgs_continued_chamber_probe"


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read LF-terminated JSONL rows."""
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def is_lambert_step(distance: int) -> bool:
    """Return whether distance is on the 2, 6, 10, 14, ... ladder."""
    return int(distance) >= 2 and (int(distance) - 2) % 4 == 0


def is_wheel_open(n: int) -> bool:
    """Return whether n is open on the mod-30 wheel."""
    return int(n) % 30 in WHEEL_OPEN_RESIDUES_MOD30


def visible_open_candidates(
    p: int,
    seed: int,
    q_audit: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Return candidates to the right of the seed with visible chamber state."""
    rows: list[dict[str, object]] = []
    visible_open_index = 0
    visible_closed_count = 0
    for candidate in range(int(seed) + 1, int(q_audit) + 1):
        offset = candidate - int(p)
        reason = closure_reason(int(p), offset, int(visible_divisor_bound))
        wheel_open = is_wheel_open(candidate)
        visibly_open = wheel_open and reason is None
        if visibly_open:
            visible_open_index += 1
            rows.append(
                {
                    "candidate": candidate,
                    "distance_from_seed": candidate - int(seed),
                    "visible_open_index": visible_open_index,
                    "visible_closed_before": visible_closed_count,
                    "distance_on_lambert_ladder": is_lambert_step(
                        candidate - int(seed)
                    ),
                    "closed_prefix_on_lambert_ladder": is_lambert_step(
                        visible_closed_count
                    ),
                }
            )
        else:
            visible_closed_count += 1
    return rows


def choose_candidate(
    rule_id: str,
    candidates: list[dict[str, object]],
) -> dict[str, object] | None:
    """Select one candidate by a predeclared continued-chamber rule."""
    if rule_id == "first_visible_open":
        return candidates[0] if candidates else None
    if rule_id == "first_distance_on_4m_plus_2":
        for candidate in candidates:
            if bool(candidate["distance_on_lambert_ladder"]):
                return candidate
        return None
    if rule_id == "first_closed_prefix_on_4m_plus_2":
        for candidate in candidates:
            if bool(candidate["closed_prefix_on_lambert_ladder"]):
                return candidate
        return None
    if rule_id == "first_both_ladders":
        for candidate in candidates:
            if bool(candidate["distance_on_lambert_ladder"]) and bool(
                candidate["closed_prefix_on_lambert_ladder"]
            ):
                return candidate
        return None
    raise ValueError(f"unknown rule_id: {rule_id}")


def candidate_rows_for_shadow_row(
    row: dict[str, object],
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Return continued-chamber candidate rows for one shadow-seed row."""
    scale = int(row["scale"])
    p = int(row["p"])
    seed = int(row["chain_seed"])
    q_audit = int(row["q"])
    candidates = visible_open_candidates(p, seed, q_audit, visible_divisor_bound)
    out: list[dict[str, object]] = []
    for candidate in candidates:
        n = int(candidate["candidate"])
        out.append(
            {
                "scale": scale,
                "anchor_p": p,
                "seed": seed,
                "q_for_audit_only": q_audit,
                "candidate": n,
                "is_q_for_audit_only": n == q_audit,
                "distance_from_seed": candidate["distance_from_seed"],
                "visible_open_index": candidate["visible_open_index"],
                "visible_closed_before": candidate["visible_closed_before"],
                "distance_on_lambert_ladder": candidate["distance_on_lambert_ladder"],
                "closed_prefix_on_lambert_ladder": candidate[
                    "closed_prefix_on_lambert_ladder"
                ],
            }
        )
    return out


def summarize_rules(
    shadow_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, object]],
    scales: list[int],
) -> list[dict[str, object]]:
    """Return one summary row per rule and scale."""
    rules = [
        "first_visible_open",
        "first_distance_on_4m_plus_2",
        "first_closed_prefix_on_4m_plus_2",
        "first_both_ladders",
    ]
    rows_by_key: dict[tuple[int, int], list[dict[str, object]]] = {}
    for row in candidate_rows:
        rows_by_key.setdefault((int(row["scale"]), int(row["anchor_p"])), []).append(
            row
        )

    summaries: list[dict[str, object]] = []
    for scale in scales:
        scale_shadow_rows = [row for row in shadow_rows if int(row["scale"]) == scale]
        for rule_id in rules:
            selected = 0
            correct = 0
            failures = 0
            for row in scale_shadow_rows:
                options = rows_by_key.get((scale, int(row["p"])), [])
                pick = choose_candidate(rule_id, options)
                if pick is None:
                    continue
                selected += 1
                if bool(pick["is_q_for_audit_only"]):
                    correct += 1
                else:
                    failures += 1
            summaries.append(
                {
                    "scale": scale,
                    "rule_id": rule_id,
                    "shadow_seed_rows": len(scale_shadow_rows),
                    "top1_selected": selected,
                    "top1_correct": correct,
                    "top1_failures": failures,
                    "top1_recall": (
                        0.0 if not scale_shadow_rows else correct / len(scale_shadow_rows)
                    ),
                    "audit_clean": failures == 0,
                }
            )
    return summaries


def q_ladder_summary(candidate_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return observed ladder membership for the true q rows."""
    counts: Counter[tuple[int, bool, bool]] = Counter()
    for row in candidate_rows:
        if not bool(row["is_q_for_audit_only"]):
            continue
        counts[
            (
                int(row["scale"]),
                bool(row["distance_on_lambert_ladder"]),
                bool(row["closed_prefix_on_lambert_ladder"]),
            )
        ] += 1
    return [
        {
            "scale": scale,
            "q_distance_on_lambert_ladder": distance_hit,
            "q_closed_prefix_on_lambert_ladder": closed_hit,
            "rows": count,
        }
        for (scale, distance_hit, closed_hit), count in sorted(counts.items())
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


def write_plot(rule_rows: list[dict[str, object]], path: Path) -> None:
    """Write a compact recall/failure plot."""
    import matplotlib.pyplot as plt

    rules = list(dict.fromkeys(str(row["rule_id"]) for row in rule_rows))
    scales = list(dict.fromkeys(int(row["scale"]) for row in rule_rows))
    fig, axes = plt.subplots(1, len(scales), figsize=(12, 4), sharey=True)
    if len(scales) == 1:
        axes = [axes]
    for axis, scale in zip(axes, scales):
        scale_rows = [row for row in rule_rows if int(row["scale"]) == scale]
        recall = [float(row["top1_recall"]) for row in scale_rows]
        failures = [int(row["top1_failures"]) for row in scale_rows]
        x = range(len(rules))
        axis.bar(x, recall, color="#3c7d8a")
        axis.set_title(f"scale {scale:g}")
        axis.set_xticks(list(x), [rule.replace("_", "\n") for rule in rules])
        axis.set_ylim(0, 1)
        axis.tick_params(axis="x", labelsize=7)
        for index, failure_count in enumerate(failures):
            axis.text(index, recall[index] + 0.02, str(failure_count), ha="center")
    axes[0].set_ylabel("top-1 recall, failure count above bar")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def run_probe(
    input_rows: Path,
    output_dir: Path,
    scales: list[int],
    visible_divisor_bound: int,
) -> dict[str, object]:
    """Run the continued-chamber falsification probe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    input_data = read_jsonl(input_rows)
    shadow_rows = [
        row
        for row in input_data
        if row.get("source") == SHADOW_SEED_RECOVERY_SOURCE
        and int(row["scale"]) in scales
    ]
    candidate_rows: list[dict[str, object]] = []
    for row in shadow_rows:
        candidate_rows.extend(candidate_rows_for_shadow_row(row, visible_divisor_bound))

    rule_rows = summarize_rules(shadow_rows, candidate_rows, scales)
    q_rows = q_ladder_summary(candidate_rows)
    audit_clean_rules = sorted(
        {
            str(row["rule_id"])
            for row in rule_rows
            if bool(row["audit_clean"]) and int(row["top1_correct"]) > 0
        }
    )
    summary = {
        "input_rows": str(input_rows),
        "scales": scales,
        "visible_divisor_bound": int(visible_divisor_bound),
        "shadow_seed_rows": len(shadow_rows),
        "candidate_rows": len(candidate_rows),
        "rule_rows": rule_rows,
        "q_ladder_rows": q_rows,
        "audit_clean_rules_with_hits": audit_clean_rules,
        "strongest_result": (
            "continued_chamber_ladder_falsified"
            if not audit_clean_rules
            else "continued_chamber_ladder_partial_signal"
        ),
    }
    write_csv(candidate_rows, output_dir / "candidate_rows.csv")
    write_csv(rule_rows, output_dir / "rule_report.csv")
    write_csv(q_rows, output_dir / "q_ladder_report.csv")
    write_json(summary, output_dir / "summary.json")
    write_plot(rule_rows, output_dir / "continued_chamber_rule_recall.png")
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build the probe CLI."""
    parser = argparse.ArgumentParser(
        description="Test continued-chamber correction ladders on shadow rows."
    )
    parser.add_argument("--input-rows", type=Path, default=DEFAULT_INPUT_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scales", type=int, nargs="+", default=[10**12, 10**15, 10**18])
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
        args.output_dir,
        [int(scale) for scale in args.scales],
        int(args.visible_divisor_bound),
    )
    print(
        "shadow_seed_rows={shadow_seed_rows} candidate_rows={candidate_rows} "
        "audit_clean_rules_with_hits={rules} strongest_result={strongest_result}".format(
            shadow_seed_rows=summary["shadow_seed_rows"],
            candidate_rows=summary["candidate_rows"],
            rules=",".join(summary["audit_clean_rules_with_hits"]) or "none",
            strongest_result=summary["strongest_result"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

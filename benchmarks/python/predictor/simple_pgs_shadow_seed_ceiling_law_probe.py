"""Probe proof-level shadow-seed ceiling laws."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from math import isqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    DEFAULT_CANDIDATE_BOUND,
    DEFAULT_VISIBLE_DIVISOR_BOUND,
    WHEEL_OPEN_RESIDUES_MOD30,
    closure_reason,
)

DEFAULT_INPUT = (
    ROOT
    / "output"
    / "simple_pgs_shadow_seed_recovery_displacement_probe"
    / "candidate_rows.csv"
)
DEFAULT_OUTPUT_DIR = ROOT / "output" / "simple_pgs_shadow_seed_ceiling_law_probe"


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read CSV rows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def write_json(record: dict[str, object], path: Path) -> None:
    """Write LF-terminated JSON."""
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def grouped_rows(
    rows: list[dict[str, str]],
    scales: set[int],
) -> dict[tuple[int, int, int], list[dict[str, str]]]:
    """Group candidate rows by shadow seed."""
    groups: dict[tuple[int, int, int], list[dict[str, str]]] = {}
    for row in rows:
        scale = int(row["scale"])
        if scale not in scales:
            continue
        key = (scale, int(row["anchor_p"]), int(row["seed_q0"]))
        groups.setdefault(key, []).append(row)
    for group in groups.values():
        group.sort(key=lambda row: int(row["candidate_n"]))
    return groups


def next_square_after(n: int) -> int:
    """Return the first integer square strictly greater than n."""
    root = isqrt(int(n)) + 1
    return root * root


def next_odd_square_after(n: int) -> int:
    """Return the first odd integer square strictly greater than n."""
    root = isqrt(int(n)) + 1
    if root % 2 == 0:
        root += 1
    return root * root


def next_open_square_after(n: int) -> int:
    """Return the first square with an open mod-30 residue."""
    root = isqrt(int(n)) + 1
    while True:
        square = root * root
        if square % 30 in {1, 7, 11, 13, 17, 19, 23, 29}:
            return square
        root += 1


def visible_open_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return visible-open candidate rows."""
    return [
        row
        for row in rows
        if row["wheel_open"] == "True" and row["visible_closure_reason"] == ""
    ]


def visible_open_candidates(
    p: int,
    seed_q0: int,
    upper: int,
    visible_divisor_bound: int,
) -> list[int]:
    """Return visible-open candidates from seed through upper."""
    out: list[int] = []
    for candidate in range(int(seed_q0) + 1, int(upper) + 1):
        offset = candidate - int(p)
        if (
            candidate % 30 in WHEEL_OPEN_RESIDUES_MOD30
            and closure_reason(int(p), offset, int(visible_divisor_bound)) is None
        ):
            out.append(candidate)
    return out


def select_candidate(
    rule_id: str,
    rows: list[dict[str, str]],
    ceiling: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> dict[str, str] | None:
    """Select a candidate using one ceiling rule."""
    p = int(rows[0]["anchor_p"])
    seed_q0 = int(rows[0]["seed_q0"])
    upper = min(int(ceiling), p + int(candidate_bound))
    visible = visible_open_candidates(p, seed_q0, upper, visible_divisor_bound)
    if not visible:
        return None
    if rule_id == "S1_first_visible_before_ceiling":
        for candidate in visible:
            if candidate < int(ceiling):
                return {"candidate_n": str(candidate)}
        return None
    if rule_id == "S2_last_visible_before_ceiling":
        before = [candidate for candidate in visible if candidate < int(ceiling)]
        return {"candidate_n": str(before[-1])} if before else None
    if rule_id == "S3_first_visible_after_ceiling":
        for candidate in visible:
            if candidate >= int(ceiling):
                return {"candidate_n": str(candidate)}
        return None
    if rule_id == "S4_visible_whose_successor_crosses_ceiling":
        for index, candidate in enumerate(visible):
            next_n = visible[index + 1] if index + 1 < len(visible) else None
            if candidate < int(ceiling) and (
                next_n is None or next_n >= int(ceiling)
            ):
                return {"candidate_n": str(candidate)}
        return None
    raise ValueError(f"unknown rule_id: {rule_id}")


def failure_mode(pick: dict[str, str] | None, recovered_q: int) -> str:
    """Return failure-mode label for one selection."""
    if pick is None:
        return "no_selection"
    candidate = int(pick["candidate_n"])
    if candidate == int(recovered_q):
        return "correct"
    if candidate < int(recovered_q):
        return "selected_too_early"
    return "selected_too_late"


def summarize(
    groups: dict[tuple[int, int, int], list[dict[str, str]]],
    scales: list[int],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    """Return ceiling rows and law summaries."""
    ceiling_fns = {
        "C_integer_square": next_square_after,
        "C_odd_square": next_odd_square_after,
        "C_open_square": next_open_square_after,
    }
    selector_rules = [
        "S1_first_visible_before_ceiling",
        "S2_last_visible_before_ceiling",
        "S3_first_visible_after_ceiling",
        "S4_visible_whose_successor_crosses_ceiling",
    ]
    base_pgs_counts = {10**15: 108, 10**18: 105}
    emitted_counts = {10**15: 249, 10**18: 250}
    ceiling_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for (scale, anchor_p, seed_q0), rows in groups.items():
        recovered_q = int(rows[0]["recovered_q_for_audit_only"])
        for ceiling_id, ceiling_fn in ceiling_fns.items():
            ceiling = ceiling_fn(seed_q0)
            upper = min(ceiling, anchor_p + int(candidate_bound))
            visible_before = visible_open_candidates(
                anchor_p,
                seed_q0,
                upper,
                visible_divisor_bound,
            )
            ceiling_rows.append(
                {
                    "scale": scale,
                    "anchor_p": anchor_p,
                    "seed_q0": seed_q0,
                    "recovered_q_for_audit_only": recovered_q,
                    "ceiling_id": ceiling_id,
                    "ceiling_value": ceiling,
                    "ceiling_delta_from_seed": ceiling - seed_q0,
                    "recovered_q_before_ceiling": recovered_q < ceiling,
                    "visible_open_before_ceiling_or_bound": len(visible_before),
                    "ceiling_exceeds_candidate_bound": ceiling > anchor_p + int(candidate_bound),
                    "terminal_is_last_visible_before_ceiling": bool(
                        visible_before and visible_before[-1] == recovered_q
                    ),
                }
            )
    for scale in scales:
        scale_groups = {
            key: rows
            for key, rows in groups.items()
            if key[0] == scale
        }
        for ceiling_id, ceiling_fn in ceiling_fns.items():
            covered = 0
            terminal_last = 0
            for (_scale, _anchor_p, seed_q0), rows in scale_groups.items():
                recovered_q = int(rows[0]["recovered_q_for_audit_only"])
                ceiling = ceiling_fn(seed_q0)
                if recovered_q < ceiling:
                    covered += 1
                upper = min(ceiling, _anchor_p + int(candidate_bound))
                before = visible_open_candidates(
                    _anchor_p,
                    seed_q0,
                    upper,
                    visible_divisor_bound,
                )
                if before and before[-1] == recovered_q:
                    terminal_last += 1
            for rule_id in selector_rules:
                selected = 0
                correct = 0
                early = 0
                late = 0
                none = 0
                for (_scale, _anchor_p, seed_q0), rows in scale_groups.items():
                    recovered_q = int(rows[0]["recovered_q_for_audit_only"])
                    pick = select_candidate(
                        rule_id,
                        rows,
                        ceiling_fn(seed_q0),
                        candidate_bound,
                        visible_divisor_bound,
                    )
                    mode = failure_mode(pick, recovered_q)
                    if pick is not None:
                        selected += 1
                    if mode == "correct":
                        correct += 1
                    elif mode == "selected_too_early":
                        early += 1
                    elif mode == "selected_too_late":
                        late += 1
                    else:
                        none += 1
                emitted = emitted_counts[scale]
                projected = 0.0 if emitted == 0 else (
                    (base_pgs_counts[scale] + correct) / emitted * 100.0
                )
                summary_rows.append(
                    {
                        "scale": scale,
                        "ceiling_id": ceiling_id,
                        "selector_rule": rule_id,
                        "shadow_seed_rows": len(scale_groups),
                        "recovered_q_before_ceiling_count": covered,
                        "terminal_is_last_visible_before_ceiling_count": terminal_last,
                        "top1_selected": selected,
                        "top1_correct": correct,
                        "would_create_audit_failures": early + late,
                        "failure_mode_selected_too_early": early,
                        "failure_mode_selected_too_late": late,
                        "failure_mode_no_selection": none,
                        "projected_pgs_percent": projected,
                        "promotion_eligible": (early + late) == 0 and projected >= 50.0,
                    }
                )
    return ceiling_rows, summary_rows


def run_probe(
    input_path: Path,
    output_dir: Path,
    scales: list[int],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> dict[str, object]:
    """Run the ceiling-law probe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    groups = grouped_rows(read_csv(input_path), set(scales))
    ceiling_rows, summary_rows = summarize(
        groups,
        scales,
        candidate_bound,
        visible_divisor_bound,
    )
    promotion_rules = sorted(
        {
            f"{row['ceiling_id']}:{row['selector_rule']}"
            for row in summary_rows
            if bool(row["promotion_eligible"])
        }
    )
    summary = {
        "input": str(input_path),
        "scales": scales,
        "candidate_bound": int(candidate_bound),
        "visible_divisor_bound": int(visible_divisor_bound),
        "shadow_seed_rows": len(groups),
        "ceiling_row_count": len(ceiling_rows),
        "law_row_count": len(summary_rows),
        "promotion_eligible_rules": promotion_rules,
        "strongest_result": (
            "square_pressure_ceilings_do_not_select_terminal_boundary_safely"
        ),
    }
    write_csv(ceiling_rows, output_dir / "ceiling_rows.csv")
    write_csv(summary_rows, output_dir / "ceiling_law_report.csv")
    write_json(summary, output_dir / "summary.json")
    return summary


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        description="Probe shadow-seed no-later-simpler ceiling laws."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--scales", type=int, nargs="+", default=[10**15, 10**18])
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
        args.input,
        args.output_dir,
        [int(scale) for scale in args.scales],
        int(args.candidate_bound),
        int(args.visible_divisor_bound),
    )
    print(
        "shadow_seed_rows={shadow_seed_rows} law_rows={law_row_count} "
        "promotion_eligible_rules={rules} strongest_result={strongest_result}".format(
            shadow_seed_rows=summary["shadow_seed_rows"],
            law_row_count=summary["law_row_count"],
            rules=",".join(summary["promotion_eligible_rules"]) or "none",
            strongest_result=summary["strongest_result"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

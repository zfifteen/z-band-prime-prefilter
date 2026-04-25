"""Autopsy high-scale PGS boundary-validity failures."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from math import isqrt
from pathlib import Path
from statistics import median

from sympy import nextprime, prevprime


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_controller import (  # noqa: E402
    write_json,
    write_jsonl,
)
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    WHEEL_OPEN_RESIDUES_MOD30,
    admissible_offsets,
    closure_reason,
    pgs_probe_certificate,
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


def previous_open_offset(open_offsets: list[int], gap_offset: int) -> int | None:
    """Return the previous wheel-open chamber offset."""
    prior = [offset for offset in open_offsets if offset < int(gap_offset)]
    return prior[-1] if prior else None


def next_open_offset(open_offsets: list[int], gap_offset: int) -> int | None:
    """Return the next wheel-open chamber offset."""
    for offset in open_offsets:
        if offset > int(gap_offset):
            return offset
    return None


def autopsy_row(
    scale: int,
    p: int,
    certificate: dict[str, object],
    candidate_bound: int,
    max_divisor_floor: int,
) -> dict[str, object]:
    """Return one audit-labeled row for boundary-validity comparison."""
    emitted_q = int(certificate["q"])
    true_q = int(nextprime(int(p)))
    gap_offset = int(certificate["gap_offset"])
    true_gap_offset = true_q - int(p)
    open_offsets = admissible_offsets(int(p), int(candidate_bound))
    right_open_offsets = [
        offset for offset in open_offsets if offset > gap_offset
    ]
    right_unclosed_offsets = [
        offset
        for offset in right_open_offsets
        if closure_reason(int(p), offset, max_divisor_floor) is None
    ]
    prior_open = previous_open_offset(open_offsets, gap_offset)
    following_open = next_open_offset(open_offsets, gap_offset)
    first_right_unclosed = (
        right_unclosed_offsets[0] if right_unclosed_offsets else None
    )
    q_closure_reason = closure_reason(int(p), gap_offset, max_divisor_floor)
    carrier_w = int(certificate["carrier_w"])
    carrier_d = int(certificate["carrier_d"])
    carrier_offset = carrier_w - int(p)
    carrier_to_q_delta = emitted_q - carrier_w
    right_first_unclosed_delta = (
        None if first_right_unclosed is None else first_right_unclosed - gap_offset
    )
    next_open_delta = None if following_open is None else following_open - gap_offset
    prev_open_delta = None if prior_open is None else gap_offset - prior_open

    return {
        "scale": int(scale),
        "rule_id": str(certificate["rule_id"]),
        "anchor_p": int(p),
        "emitted_q": emitted_q,
        "true_q_for_audit_only": true_q,
        "audit_passed": emitted_q == true_q,
        "delta_to_true_q": true_q - emitted_q,
        "gap_offset": gap_offset,
        "true_gap_offset": true_gap_offset,
        "closed_offsets_before_q_count": len(
            certificate["closed_offsets_before_q"]
        ),
        "unclosed_offsets_before_q_count": len(
            certificate["unclosed_offsets_before_q"]
        ),
        "carrier_w": carrier_w,
        "carrier_d": carrier_d,
        "carrier_offset": carrier_offset,
        "carrier_to_q_delta": carrier_to_q_delta,
        "q_offset_mod_6": gap_offset % 6,
        "q_offset_mod_30": gap_offset % 30,
        "q_value_mod_6": emitted_q % 6,
        "q_value_mod_30": emitted_q % 30,
        "next_open_offset_after_q": following_open,
        "prev_open_offset_before_q": prior_open,
        "right_chamber_open_count": len(right_open_offsets),
        "right_chamber_unclosed_count": len(right_unclosed_offsets),
        "right_chamber_first_unclosed_offset": first_right_unclosed,
        "right_chamber_first_unclosed_delta": right_first_unclosed_delta,
        "boundary_score_components": {
            "left_closed_count": len(certificate["closed_offsets_before_q"]),
            "right_open_count": len(right_open_offsets),
            "right_unclosed_count": len(right_unclosed_offsets),
            "right_first_unclosed_delta": right_first_unclosed_delta,
            "next_open_delta": next_open_delta,
            "prev_open_delta": prev_open_delta,
        },
        "self_certificate_components": {
            "q_wheel_open": emitted_q % 30 in WHEEL_OPEN_RESIDUES_MOD30,
            "q_visible_closure_reason": q_closure_reason,
            "predecessor_closure_complete": (
                len(certificate["unclosed_offsets_before_q"]) == 0
            ),
            "used_forbidden_tool": bool(certificate["used_forbidden_tool"]),
        },
    }


def autopsy_scale(
    scale: int,
    sample_size: int,
    candidate_bound: int,
    max_divisor_floor: int,
) -> list[dict[str, object]]:
    """Return autopsy rows for one high-scale probe surface."""
    rows: list[dict[str, object]] = []
    for anchor in sampled_anchors_near(scale, sample_size):
        certificate = pgs_probe_certificate(
            anchor,
            candidate_bound,
            max_divisor_floor,
        )
        if certificate is None:
            continue
        rows.append(
            autopsy_row(
                scale,
                anchor,
                certificate,
                candidate_bound,
                max_divisor_floor,
            )
        )
    return rows


def value_distribution(values: list[object]) -> dict[str, object]:
    """Return a compact distribution for table cells."""
    present = [value for value in values if value is not None]
    if not present:
        return {"count": len(values), "missing": len(values)}
    if all(isinstance(value, (int, float, bool)) for value in present):
        numeric = [float(value) for value in present]
        return {
            "count": len(values),
            "missing": len(values) - len(present),
            "min": min(numeric),
            "median": median(numeric),
            "max": max(numeric),
        }
    counts = Counter(str(value) for value in present)
    return {
        "count": len(values),
        "missing": len(values) - len(present),
        "top_values": counts.most_common(8),
    }


def table_row(
    feature: str,
    rows: list[dict[str, object]],
    predicate,
    candidate_rule: str,
) -> dict[str, object]:
    """Return one pass/fail separation row."""
    passed = [row for row in rows if bool(row["audit_passed"])]
    failed = [row for row in rows if not bool(row["audit_passed"])]
    return {
        "feature": feature,
        "passed_distribution": value_distribution([row.get(feature) for row in passed]),
        "failed_distribution": value_distribution([row.get(feature) for row in failed]),
        "safe_rejection_count": sum(1 for row in failed if predicate(row)),
        "unsafe_rejection_count": sum(1 for row in passed if predicate(row)),
        "candidate_rule": candidate_rule,
    }


def separation_table(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return failed-versus-passed candidate rejection table."""
    table: list[dict[str, object]] = []
    table.append(
        table_row(
            "q_value_mod_30",
            rows,
            lambda row: not row["self_certificate_components"]["q_wheel_open"],
            "reject if q is not wheel-open relative to p",
        )
    )
    for band in (6, 12, 18, 30):
        table.append(
            table_row(
                "right_chamber_first_unclosed_offset",
                rows,
                lambda row, band=band: (
                    row["right_chamber_first_unclosed_offset"] is not None
                    and int(row["right_chamber_first_unclosed_offset"])
                    - int(row["gap_offset"])
                    <= band
                ),
                f"reject if q has an unresolved right-neighborhood competitor within {band}",
            )
        )
    passed_carrier_deltas = {
        int(row["carrier_to_q_delta"])
        for row in rows
        if bool(row["audit_passed"])
    }
    table.append(
        table_row(
            "carrier_to_q_delta",
            rows,
            lambda row: int(row["carrier_to_q_delta"]) not in passed_carrier_deltas,
            "reject if carrier_to_q_delta was not seen among passing rows",
        )
    )
    table.append(
        table_row(
            "right_chamber_first_unclosed_delta",
            rows,
            lambda row: row["right_chamber_first_unclosed_delta"] is None,
            "reject if there is no visible right-side unresolved boundary candidate",
        )
    )
    for residue, _count in Counter(
        int(row["q_value_mod_30"])
        for row in rows
        if not bool(row["audit_passed"])
    ).most_common(8):
        table.append(
            table_row(
                "q_value_mod_30",
                rows,
                lambda row, residue=residue: int(row["q_value_mod_30"]) == residue,
                f"reject if q_value_mod_30 == {residue}",
            )
        )
    for offset, _count in Counter(
        int(row["gap_offset"])
        for row in rows
        if not bool(row["audit_passed"])
    ).most_common(8):
        table.append(
            table_row(
                "gap_offset",
                rows,
                lambda row, offset=offset: int(row["gap_offset"]) == offset,
                f"reject if gap_offset == {offset}",
            )
        )
    return table


def scale_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return one summary row per scale."""
    summaries = []
    for scale in sorted({int(row["scale"]) for row in rows}):
        scale_rows = [row for row in rows if int(row["scale"]) == scale]
        audit_failed = sum(1 for row in scale_rows if not bool(row["audit_passed"]))
        count = len(scale_rows)
        summaries.append(
            {
                "scale": scale,
                "pgs_certified_count": count,
                "audit_passed": count - audit_failed,
                "audit_failed": audit_failed,
                "audit_failed_percent": 0.0 if count == 0 else audit_failed * 100.0 / count,
                "max_required_divisor_floor": max(
                    isqrt(int(row["anchor_p"]) + 1) for row in scale_rows
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
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value) if isinstance(value, (dict, list)) else value
                    for key, value in row.items()
                }
            )


def build_parser() -> argparse.ArgumentParser:
    """Build the autopsy CLI."""
    parser = argparse.ArgumentParser(
        description="Autopsy PGS chamber-closure boundary-validity failures."
    )
    parser.add_argument("--scales", type=int, nargs="+", required=True)
    parser.add_argument("--sample-size", type=int, default=256)
    parser.add_argument("--candidate-bound", type=int, default=128)
    parser.add_argument("--max-divisor-floor", type=int, default=10_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run boundary-validity autopsy and write artifacts."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        row
        for scale in args.scales
        for row in autopsy_scale(
            scale,
            args.sample_size,
            args.candidate_bound,
            args.max_divisor_floor,
        )
    ]
    table = separation_table(rows)
    summaries = scale_summaries(rows)
    write_jsonl(rows, args.output_dir / "autopsy_rows.jsonl")
    write_json({"scales": summaries}, args.output_dir / "summary.json")
    write_json({"rows": table}, args.output_dir / "separation_table.json")
    write_csv(table, args.output_dir / "separation_table.csv")
    for summary in summaries:
        print(
            "scale={scale} pgs_certified={pgs_certified_count} "
            "audit_failed={audit_failed} "
            "audit_failed_percent={audit_failed_percent:.2f}%".format(**summary)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

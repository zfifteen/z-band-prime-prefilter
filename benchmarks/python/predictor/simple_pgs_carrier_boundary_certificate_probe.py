"""Probe carrier-regime signatures for PGS self-boundary certificates."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from math import isqrt
from pathlib import Path

from sympy import nextprime, prevprime, primerange


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
    divisor_witness,
    pgs_probe_certificate,
)


def full_surface_anchors(stop: int) -> list[int]:
    """Return all prime anchors from 11 through stop."""
    return [int(p) for p in primerange(11, int(stop) + 1)]


def sampled_anchors_near(scale: int, sample_size: int) -> list[int]:
    """Return deterministic prime anchors immediately below scale."""
    anchors: list[int] = []
    cursor = int(scale)
    while len(anchors) < int(sample_size):
        anchor = int(prevprime(cursor))
        anchors.append(anchor)
        cursor = anchor
    return anchors


def visible_divisor_class(n: int, max_divisor_floor: int) -> int:
    """Return a bounded divisor-class value visible to the probe."""
    witness = divisor_witness(int(n), int(max_divisor_floor))
    if witness is None:
        return 2
    cofactor = int(n) // int(witness)
    if witness == cofactor:
        return 3
    return 4


def is_visible_semiprime_lane(n: int, max_divisor_floor: int) -> bool:
    """Return True when bounded arithmetic sees a semiprime-like lane."""
    witness = divisor_witness(int(n), int(max_divisor_floor))
    if witness is None:
        return False
    cofactor = int(n) // int(witness)
    if witness == cofactor:
        return False
    return divisor_witness(cofactor, int(max_divisor_floor)) is None


def is_square_pressure(n: int) -> bool:
    """Return True when n is an exact square landmark."""
    root = isqrt(int(n))
    return root * root == int(n)


def density(count: int, total: int) -> float:
    """Return count / total with an empty denominator convention."""
    return 0.0 if int(total) == 0 else int(count) / int(total)


def min_or_none(values: list[int]) -> int | None:
    """Return the minimum value or None."""
    return min(values) if values else None


def signature_for_row(
    gap_offset: int,
    carrier_to_q_delta: int,
    before_density: float,
    after_density: float,
    minimal_d_before_q: int | None,
    minimal_d_after_q: int | None,
    semiprime_before: int,
    semiprime_after: int,
    square_before: int,
    square_after: int,
) -> str:
    """Return a compact local carrier-regime signature."""
    density_shift = "down" if after_density < before_density else "not_down"
    d_shift = (
        "unknown"
        if minimal_d_before_q is None or minimal_d_after_q is None
        else ("up" if minimal_d_after_q > minimal_d_before_q else "not_up")
    )
    semi_shift = "down" if semiprime_after < semiprime_before else "not_down"
    square_shift = "clear" if square_before == 0 and square_after == 0 else "pressure"
    return (
        f"gap={int(gap_offset)}|delta={int(carrier_to_q_delta)}|"
        f"density={density_shift}|d={d_shift}|semi={semi_shift}|"
        f"square={square_shift}"
    )


def profile_row(
    surface: str,
    p: int,
    candidate_bound: int,
    max_divisor_floor: int,
) -> dict[str, object] | None:
    """Return one carrier-regime profile for a PGS-certified candidate."""
    certificate = pgs_probe_certificate(int(p), int(candidate_bound), max_divisor_floor)
    if certificate is None:
        return None

    q = int(certificate["q"])
    true_q = int(nextprime(int(p)))
    gap_offset = int(certificate["gap_offset"])
    true_gap_offset = true_q - int(p)
    carrier_w = int(certificate["carrier_w"])
    carrier_d = int(certificate["carrier_d"])
    carrier_offset = carrier_w - int(p)
    carrier_to_q_delta = q - carrier_w
    open_offsets = admissible_offsets(int(p), int(candidate_bound))
    before_offsets = [offset for offset in open_offsets if offset < gap_offset]
    after_offsets = [offset for offset in open_offsets if offset > gap_offset]
    before_values = [int(p) + offset for offset in before_offsets]
    after_values = [int(p) + offset for offset in after_offsets]
    before_classes = [
        visible_divisor_class(value, max_divisor_floor) for value in before_values
    ]
    after_classes = [
        visible_divisor_class(value, max_divisor_floor) for value in after_values
    ]
    left_carrier_count = before_classes.count(carrier_d)
    right_carrier_count = after_classes.count(carrier_d)
    semiprime_before = sum(
        1 for value in before_values if is_visible_semiprime_lane(value, max_divisor_floor)
    )
    semiprime_after = sum(
        1 for value in after_values if is_visible_semiprime_lane(value, max_divisor_floor)
    )
    square_before = sum(1 for value in before_values if is_square_pressure(value))
    square_after = sum(1 for value in after_values if is_square_pressure(value))
    minimal_d_before_q = min_or_none(before_classes)
    minimal_d_after_q = min_or_none(after_classes)
    minimal_d_at_carrier = visible_divisor_class(carrier_w, max_divisor_floor)
    before_density = density(left_carrier_count, len(before_offsets))
    after_density = density(right_carrier_count, len(after_offsets))
    signature = signature_for_row(
        gap_offset,
        carrier_to_q_delta,
        before_density,
        after_density,
        minimal_d_before_q,
        minimal_d_after_q,
        semiprime_before,
        semiprime_after,
        square_before,
        square_after,
    )

    return {
        "surface": surface,
        "p": int(p),
        "q": q,
        "true_q_for_audit_only": true_q,
        "audit_passed": q == true_q,
        "gap_offset": gap_offset,
        "true_gap_offset": true_gap_offset,
        "carrier_w": carrier_w,
        "carrier_d": carrier_d,
        "carrier_offset": carrier_offset,
        "carrier_to_q_delta": carrier_to_q_delta,
        "left_carrier_count": left_carrier_count,
        "right_carrier_count": right_carrier_count,
        "carrier_density_before_q": before_density,
        "carrier_density_after_q": after_density,
        "minimal_d_before_q": minimal_d_before_q,
        "minimal_d_at_carrier": minimal_d_at_carrier,
        "minimal_d_after_q": minimal_d_after_q,
        "semiprime_lane_count_before_q": semiprime_before,
        "semiprime_lane_count_after_q": semiprime_after,
        "square_pressure_before_q": square_before,
        "square_pressure_after_q": square_after,
        "open_offset_count_before_q": len(before_offsets),
        "open_offset_count_after_q": len(after_offsets),
        "closure_certificate_complete": (
            len(certificate["unclosed_offsets_before_q"]) == 0
        ),
        "self_boundary_candidate_signature": signature,
    }


def build_rows(
    sample_size: int,
    candidate_bound: int,
    max_divisor_floor: int,
) -> list[dict[str, object]]:
    """Build all requested carrier-regime profile rows."""
    surfaces = [
        ("10^5_exact_full", full_surface_anchors(100_000)),
        ("10^6_exact_full", full_surface_anchors(1_000_000)),
        ("10^12_sampled_256", sampled_anchors_near(10**12, sample_size)),
        ("10^15_sampled_256", sampled_anchors_near(10**15, sample_size)),
        ("10^18_sampled_256", sampled_anchors_near(10**18, sample_size)),
    ]
    rows: list[dict[str, object]] = []
    for surface, anchors in surfaces:
        for anchor in anchors:
            row = profile_row(surface, anchor, candidate_bound, max_divisor_floor)
            if row is not None:
                rows.append(row)
    return rows


def surface_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return one summary row per surface."""
    summaries = []
    for surface in sorted({str(row["surface"]) for row in rows}):
        surface_rows = [row for row in rows if row["surface"] == surface]
        audit_failed = sum(1 for row in surface_rows if not bool(row["audit_passed"]))
        count = len(surface_rows)
        summaries.append(
            {
                "surface": surface,
                "pgs_profiled_count": count,
                "audit_passed": count - audit_failed,
                "audit_failed": audit_failed,
                "audit_failed_percent": 0.0 if count == 0 else audit_failed * 100.0 / count,
            }
        )
    return summaries


def certificate_predicates(rows: list[dict[str, object]]):
    """Return named candidate positive certificate predicates."""
    low_rows = [
        row
        for row in rows
        if str(row["surface"]) in {"10^5_exact_full", "10^6_exact_full"}
    ]
    low_signatures = {
        str(row["self_boundary_candidate_signature"]) for row in low_rows
    }
    low_deltas = {int(row["carrier_to_q_delta"]) for row in low_rows}
    low_gap_residues = {int(row["gap_offset"]) % 30 for row in low_rows}
    return [
        (
            "carrier_delta_seen_on_low_exact",
            lambda row: int(row["carrier_to_q_delta"]) in low_deltas,
        ),
        (
            "signature_seen_on_low_exact",
            lambda row: str(row["self_boundary_candidate_signature"]) in low_signatures,
        ),
        (
            "gap_residue_seen_on_low_exact",
            lambda row: int(row["gap_offset"]) % 30 in low_gap_residues,
        ),
        (
            "post_boundary_carrier_density_drop",
            lambda row: float(row["carrier_density_after_q"])
            < float(row["carrier_density_before_q"]),
        ),
        (
            "post_boundary_carrier_density_nonincrease",
            lambda row: float(row["carrier_density_after_q"])
            <= float(row["carrier_density_before_q"]),
        ),
        (
            "minimal_d_after_exceeds_before",
            lambda row: row["minimal_d_before_q"] is not None
            and row["minimal_d_after_q"] is not None
            and int(row["minimal_d_after_q"]) > int(row["minimal_d_before_q"]),
        ),
        (
            "semiprime_lane_exhaustion",
            lambda row: int(row["semiprime_lane_count_before_q"]) > 0
            and int(row["semiprime_lane_count_after_q"]) == 0,
        ),
        (
            "square_pressure_exclusion",
            lambda row: int(row["square_pressure_before_q"]) == 0
            and int(row["square_pressure_after_q"]) == 0,
        ),
        (
            "gap_offset_at_most_30",
            lambda row: int(row["gap_offset"]) <= 30,
        ),
        (
            "gap_offset_at_most_60",
            lambda row: int(row["gap_offset"]) <= 60,
        ),
    ]


def coverage(rows: list[dict[str, object]], predicate) -> float:
    """Return predicate coverage on rows."""
    return 0.0 if not rows else sum(1 for row in rows if predicate(row)) / len(rows)


def certificate_report(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return candidate positive certificate coverage metrics."""
    low_1e5 = [row for row in rows if row["surface"] == "10^5_exact_full"]
    low_1e6 = [row for row in rows if row["surface"] == "10^6_exact_full"]
    high_rows = [
        row
        for row in rows
        if str(row["surface"]) not in {"10^5_exact_full", "10^6_exact_full"}
    ]
    high_pass = [row for row in high_rows if bool(row["audit_passed"])]
    high_fail = [row for row in high_rows if not bool(row["audit_passed"])]
    report = []
    for name, predicate in certificate_predicates(rows):
        safe_certified = sum(1 for row in high_pass if predicate(row))
        unsafe_certified = sum(1 for row in high_fail if predicate(row))
        high_certified = safe_certified + unsafe_certified
        precision = 0.0 if high_certified == 0 else safe_certified / high_certified
        report.append(
            {
                "certificate_name": name,
                "low_10^5_coverage": coverage(low_1e5, predicate),
                "low_10^6_coverage": coverage(low_1e6, predicate),
                "high_pass_coverage": coverage(high_pass, predicate),
                "high_fail_coverage": coverage(high_fail, predicate),
                "safe_certified_count": safe_certified,
                "unsafe_certified_count": unsafe_certified,
                "precision_on_high_probe": precision,
                "pgs_certified_rate_if_required": coverage(high_rows, predicate),
            }
        )
    return report


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
    """Build the carrier-boundary certificate probe CLI."""
    parser = argparse.ArgumentParser(
        description="Probe carrier-regime self-boundary certificates."
    )
    parser.add_argument("--sample-size", type=int, default=256)
    parser.add_argument("--candidate-bound", type=int, default=128)
    parser.add_argument("--max-divisor-floor", type=int, default=10_000)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the carrier-regime certificate probe."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_rows(
        args.sample_size,
        args.candidate_bound,
        args.max_divisor_floor,
    )
    summaries = surface_summary(rows)
    report = certificate_report(rows)
    write_jsonl(rows, args.output_dir / "profile_rows.jsonl")
    write_json({"surfaces": summaries}, args.output_dir / "summary.json")
    write_json({"certificates": report}, args.output_dir / "certificate_report.json")
    write_csv(report, args.output_dir / "certificate_report.csv")
    for summary in summaries:
        print(
            "surface={surface} profiled={pgs_profiled_count} "
            "audit_failed={audit_failed} "
            "audit_failed_percent={audit_failed_percent:.2f}%".format(**summary)
        )
    for row in report:
        print(
            "certificate={certificate_name} high_precision={precision_on_high_probe:.4f} "
            "high_certified_rate={pgs_certified_rate_if_required:.4f} "
            "unsafe={unsafe_certified_count}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

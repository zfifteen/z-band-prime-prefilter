#!/usr/bin/env python3
"""Generate insight-probe artifacts for gap-ridge findings."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/z-band-prime-prefilter-mpl")

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
SCRIPT_DIR = Path(__file__).resolve().parent
for entry in (SOURCE_DIR, SCRIPT_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from z_band_prime_composite_field import divisor_counts_segment
from z_band_prime_gap_ridge.runs import (
    DEFAULT_FULL_LIMITS,
    DEFAULT_WINDOW_SCALES,
    build_even_window_starts,
)


DEFAULT_OUTPUT_DIR = Path("benchmarks/output/python/gap_ridge/insight_probes")
DEFAULT_VALIDATION_JSON = Path(
    "benchmarks/output/python/gap_ridge/lexicographic_peak_validation/lexicographic_peak_validation.json"
)
DEFAULT_WINDOW_SIZE = 2_000_000
DEFAULT_WINDOW_COUNT = 4
RESIDUE_ORDER = [1, 7, 11, 13, 17, 19, 23, 29]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Generate insight-probe artifacts for gap-ridge findings.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and SVG probe artifacts.",
    )
    parser.add_argument(
        "--validation-json",
        type=Path,
        default=DEFAULT_VALIDATION_JSON,
        help="Existing lexicographic validation JSON used to derive summary probes.",
    )
    parser.add_argument(
        "--full-limits",
        type=int,
        nargs="+",
        default=list(DEFAULT_FULL_LIMITS),
        help="Exact full natural-number ceilings to analyze.",
    )
    parser.add_argument(
        "--window-scales",
        type=int,
        nargs="+",
        default=list(DEFAULT_WINDOW_SCALES),
        help="Larger scales analyzed through evenly spaced windows.",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=DEFAULT_WINDOW_SIZE,
        help="Width of each exact sampled window.",
    )
    parser.add_argument(
        "--window-count",
        type=int,
        default=DEFAULT_WINDOW_COUNT,
        help="Number of evenly spaced windows per sampled scale.",
    )
    return parser


def raw_log_scores(divisor_count: np.ndarray, values: np.ndarray) -> np.ndarray:
    """Return raw-Z log scores for one interval."""
    return (1.0 - divisor_count.astype(np.float64) / 2.0) * np.log(
        values.astype(np.float64)
    )


def is_odd_prime_square(n: int, divisor_count: int) -> bool:
    """Return whether n is an odd prime square."""
    if divisor_count != 3 or n % 2 == 0:
        return False
    root = math.isqrt(n)
    return root * root == n


def analyze_d4_interval(lo: int, hi: int) -> dict[str, int]:
    """Analyze one interval for d(n)=4 availability and peak-carrier rates."""
    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]
    scores = raw_log_scores(divisor_count, values)

    gap_count = 0
    has_d4 = 0
    peak_d4 = 0
    violations = 0
    square_exceptions = 0

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]
        gap_scores = scores[left_index:right_index]

        best_index = int(np.argmax(gap_scores))
        best_n = int(gap_values[best_index])
        best_divisors = int(gap_divisors[best_index])
        has_d4_gap = bool(np.any(gap_divisors == 4))

        gap_count += 1
        has_d4 += int(has_d4_gap)
        peak_d4 += int(best_divisors == 4)
        if has_d4_gap and best_divisors != 4:
            violations += 1
            square_exceptions += int(is_odd_prime_square(best_n, best_divisors))

    return {
        "gap_count": gap_count,
        "has_d4": has_d4,
        "peak_d4": peak_d4,
        "violations": violations,
        "square_exceptions": square_exceptions,
    }


def analyze_residue_interval(lo: int, hi: int) -> dict[str, object]:
    """Analyze one interval for left-prime residue orientation."""
    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]
    scores = raw_log_scores(divisor_count, values)

    stats = {
        residue: {"gaps": 0, "left": 0, "right": 0, "center": 0, "edge2": 0}
        for residue in RESIDUE_ORDER
    }
    global_stats = {"gaps": 0, "left": 0, "right": 0, "center": 0, "edge2": 0}

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        residue = int(left_prime % 30)
        if residue not in stats:
            continue

        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_scores = scores[left_index:right_index]
        best_offset = int(np.argmax(gap_scores)) + 1
        edge_distance = min(best_offset, gap - best_offset)

        bucket = stats[residue]
        bucket["gaps"] += 1
        global_stats["gaps"] += 1

        if best_offset < gap / 2:
            bucket["left"] += 1
            global_stats["left"] += 1
        elif best_offset > gap / 2:
            bucket["right"] += 1
            global_stats["right"] += 1
        else:
            bucket["center"] += 1
            global_stats["center"] += 1

        if edge_distance == 2:
            bucket["edge2"] += 1
            global_stats["edge2"] += 1

    return {"stats": stats, "global": global_stats}


def summarize_d4_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Convert raw d4 counts into JSON-ready rows."""
    summary: list[dict[str, object]] = []
    for row in rows:
        gap_count = int(row["gap_count"])
        has_d4 = int(row["has_d4"])
        peak_d4 = int(row["peak_d4"])
        violations = int(row["violations"])
        square_exceptions = int(row["square_exceptions"])
        summary.append(
            {
                "scale": int(row["scale"]),
                "mode": str(row["mode"]),
                "gap_count": gap_count,
                "has_d4_share": has_d4 / gap_count,
                "peak_d4_share": peak_d4 / gap_count,
                "violation_rate": violations / gap_count,
                "square_exception_rate": square_exceptions / gap_count,
                "violations": violations,
                "square_exceptions": square_exceptions,
            }
        )
    return summary


def summarize_residue_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    """Convert residue counts into JSON-ready summaries."""
    summary: list[dict[str, object]] = []
    for row in rows:
        global_stats = row["global"]
        global_right_share = global_stats["right"] / global_stats["gaps"]
        for residue in RESIDUE_ORDER:
            stats = row["stats"][str(residue)] if isinstance(next(iter(row["stats"].keys())), str) else row["stats"][residue]
            gaps = int(stats["gaps"])
            right_share = stats["right"] / gaps if gaps else 0.0
            left_share = stats["left"] / gaps if gaps else 0.0
            center_share = stats["center"] / gaps if gaps else 0.0
            edge2_share = stats["edge2"] / gaps if gaps else 0.0
            summary.append(
                {
                    "scale": int(row["scale"]),
                    "mode": str(row["mode"]),
                    "residue": residue,
                    "gaps": gaps,
                    "right_share": right_share,
                    "left_share": left_share,
                    "center_share": center_share,
                    "edge2_share": edge2_share,
                    "right_lift": right_share / global_right_share if global_right_share else 0.0,
                }
            )
    return {"rows": rows, "summary": summary}


def render_d4_availability(rows: list[dict[str, object]], output_path: Path) -> None:
    """Render the d4 availability probe figure."""
    scales = [int(row["scale"]) for row in rows]
    has_d4 = [float(row["has_d4_share"]) for row in rows]
    peak_d4 = [float(row["peak_d4_share"]) for row in rows]
    violation = [float(row["violation_rate"]) for row in rows]

    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9.2, 6.8), sharex=True)
    top.plot(scales, has_d4, marker="o", linewidth=2.2, color="#1f4e79", label="has interior d(n)=4")
    top.plot(scales, peak_d4, marker="s", linewidth=2.2, color="#c05621", label="peak carried by d(n)=4")
    top.set_xscale("log")
    top.set_ylim(0.80, 0.86)
    top.set_ylabel("Share")
    top.set_title("d(n)=4 availability versus peak-carrier share", pad=12)
    top.grid(True, alpha=0.25)
    top.legend(frameon=False, loc="lower left")

    bottom.plot(scales, violation, marker="o", linewidth=2.2, color="#8b1e3f")
    bottom.set_xscale("log")
    bottom.set_ylabel("Violation rate")
    bottom.set_xlabel("Scale")
    bottom.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value * 100.0:.3f}%"))
    bottom.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: rf"$10^{{{int(np.log10(value))}}}$")
    )
    bottom.grid(True, alpha=0.25)

    fig.tight_layout()
    fig.savefig(output_path, format="svg")
    plt.close(fig)


def render_residue_orientation(payload: dict[str, object], output_path: Path) -> None:
    """Render the residue-orientation probe figure for exact 10^7 and sampled 10^18."""
    summary = payload["summary"]

    def pick(scale: int) -> list[dict[str, object]]:
        return [row for row in summary if int(row["scale"]) == scale]

    available_scales = sorted({int(row["scale"]) for row in summary})
    exact_scales = sorted({int(row["scale"]) for row in summary if str(row["mode"]) == "exact"})
    sampled_scales = sorted(
        {int(row["scale"]) for row in summary if str(row["mode"]) != "exact"}
    )
    selected = [
        (
            exact_scales[-1] if exact_scales else available_scales[0],
            "highest exact regime",
        ),
        (
            sampled_scales[-1] if sampled_scales else available_scales[-1],
            "highest sampled regime",
        ),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 6.8), sharex="col")
    residue_labels = [str(residue) for residue in RESIDUE_ORDER]

    for column, (scale, label) in enumerate(selected):
        rows = pick(scale)
        right_share = [float(row["right_share"]) for row in rows]
        right_lift = [float(row["right_lift"]) for row in rows]
        global_right_share = sum(float(row["right_share"]) * int(row["gaps"]) for row in rows) / sum(
            int(row["gaps"]) for row in rows
        )

        top = axes[0, column]
        bottom = axes[1, column]

        top.bar(residue_labels, right_share, color="#1f4e79")
        top.axhline(global_right_share, color="#c05621", linestyle="--", linewidth=1.6)
        top.set_title(label)
        top.set_ylabel("Right-edge share")
        top.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value * 100.0:.1f}%"))

        bottom.bar(residue_labels, right_lift, color="#245c3b")
        bottom.axhline(1.0, color="#5a5a5a", linestyle="--", linewidth=1.4)
        bottom.set_ylabel("Right-edge lift")
        bottom.set_xlabel("Left prime mod 30")

    fig.suptitle("Residue-modulated right-edge ridge orientation", y=0.98)
    fig.tight_layout()
    fig.savefig(output_path, format="svg")
    plt.close(fig)


def render_match_by_scale(rows: list[dict[str, object]], output_path: Path) -> None:
    """Render lexicographic match rate by scale."""
    scales = [int(row["scale"]) for row in rows]
    rates = [float(row["match_rate"]) for row in rows]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.plot(scales, rates, marker="o", linewidth=2.2, color="#1f4e79")
    ax.set_xscale("log")
    ax.set_ylim(0.95, 1.005)
    ax.set_title("Lexicographic match rate by tested regime", pad=12)
    ax.set_xlabel("Scale")
    ax.set_ylabel("Match rate")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value * 100.0:.1f}%"))
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: rf"$10^{{{int(np.log10(value))}}}$")
    )
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, format="svg")
    plt.close(fig)


def render_match_margin(rows: list[dict[str, object]], output_path: Path) -> None:
    """Render minimum log-score margin by tested regime."""
    scales = [int(row["scale"]) for row in rows]
    margins = [float(row["min_log_score_margin"]) for row in rows]
    fig, ax = plt.subplots(figsize=(9.2, 4.8))
    ax.plot(scales, margins, marker="o", linewidth=2.2, color="#8b1e3f")
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=1e-16)
    ax.set_title("Minimum winning log-score margin by tested regime", pad=12)
    ax.set_xlabel("Scale")
    ax.set_ylabel("Minimum log-score margin")
    ax.xaxis.set_major_formatter(
        FuncFormatter(lambda value, _: rf"$10^{{{int(np.log10(value))}}}$")
    )
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path, format="svg")
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    """Generate insight-probe artifacts."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    d4_rows: list[dict[str, object]] = []
    residue_rows: list[dict[str, object]] = []

    for limit in args.full_limits:
        d4_stats = analyze_d4_interval(2, limit + 1)
        d4_stats["scale"] = limit
        d4_stats["mode"] = "exact"
        d4_rows.append(d4_stats)

        residue_stats = analyze_residue_interval(2, limit + 1)
        residue_rows.append(
            {
                "scale": limit,
                "mode": "exact",
                "stats": residue_stats["stats"],
                "global": residue_stats["global"],
            }
        )

    for scale in args.window_scales:
        starts = build_even_window_starts(scale, args.window_size, args.window_count)

        merged_d4 = {"gap_count": 0, "has_d4": 0, "peak_d4": 0, "violations": 0, "square_exceptions": 0}
        merged_residue = {
            residue: {"gaps": 0, "left": 0, "right": 0, "center": 0, "edge2": 0}
            for residue in RESIDUE_ORDER
        }
        merged_global = {"gaps": 0, "left": 0, "right": 0, "center": 0, "edge2": 0}

        for start in starts:
            d4_stats = analyze_d4_interval(start, start + args.window_size)
            for key in merged_d4:
                merged_d4[key] += int(d4_stats[key])

            residue_stats = analyze_residue_interval(start, start + args.window_size)
            for residue in RESIDUE_ORDER:
                for key in merged_residue[residue]:
                    merged_residue[residue][key] += int(residue_stats["stats"][residue][key])
            for key in merged_global:
                merged_global[key] += int(residue_stats["global"][key])

        merged_d4["scale"] = scale
        merged_d4["mode"] = "even-window"
        d4_rows.append(merged_d4)

        residue_rows.append(
            {
                "scale": scale,
                "mode": "even-window",
                "stats": merged_residue,
                "global": merged_global,
            }
        )

    d4_summary = summarize_d4_rows(d4_rows)
    residue_payload = summarize_residue_rows(residue_rows)

    validation_payload = json.loads(args.validation_json.read_text(encoding="utf-8"))
    validation_rows = [
        {
            "scale": int(row["scale"]),
            "mode": str(row["mode"]),
            "gap_count": int(row["gap_count"]),
            "match_rate": float(row["match_rate"]),
            "min_log_score_margin": float(row["min_log_score_margin"]),
        }
        for row in validation_payload["rows"]
    ]
    aggregate_gap_count = sum(int(row["gap_count"]) for row in validation_payload["rows"])
    aggregate_match_count = sum(int(row["match_count"]) for row in validation_payload["rows"])
    aggregate_mismatch_count = sum(int(row["counterexample_count"]) for row in validation_payload["rows"])

    render_d4_availability(
        d4_summary,
        args.output_dir / "d4_availability_vs_peak_share.svg",
    )
    render_residue_orientation(
        residue_payload,
        args.output_dir / "residue_mod30_right_edge_share.svg",
    )
    render_match_by_scale(
        validation_rows,
        args.output_dir / "lexicographic_rule_match_by_scale.svg",
    )
    render_match_margin(
        validation_rows,
        args.output_dir / "lexicographic_rule_match_rate.svg",
    )

    (args.output_dir / "d4_availability_vs_peak_share.json").write_text(
        json.dumps(d4_summary, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "residue_mod30_right_edge_share.json").write_text(
        json.dumps(residue_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "lexicographic_rule_match_by_scale.json").write_text(
        json.dumps(validation_rows, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "lexicographic_rule_match_rate.json").write_text(
        json.dumps(
            {
                "stats": {
                    "gap_count": aggregate_gap_count,
                    "lex_match": aggregate_match_count,
                    "lex_mismatch": aggregate_mismatch_count,
                    "match_rate": aggregate_match_count / aggregate_gap_count,
                },
                "rows": validation_rows,
                "svg": str(args.output_dir / "lexicographic_rule_match_rate.svg"),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

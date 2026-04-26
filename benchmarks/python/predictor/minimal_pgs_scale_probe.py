"""Run scale probes for the minimal PGS generator."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from math import isqrt
from pathlib import Path

import matplotlib.pyplot as plt
from sympy import prevprime, primerange


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_audit import audit_report  # noqa: E402
from z_band_prime_predictor.simple_pgs_controller import (  # noqa: E402
    diagnostic_records,
    write_json,
    write_jsonl,
)
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    emit_records,
)


DEFAULT_OUTPUT_DIR = Path("output/minimal_pgs_scale_probe_1e5_to_1e18")


def full_surface_anchors(limit: int) -> list[int]:
    """Return all prime anchors from 11 through limit."""
    return [int(p) for p in primerange(11, limit + 1)]


def sampled_anchors_near(scale: int, count: int) -> list[int]:
    """Return deterministic prime anchors immediately below a scale."""
    anchors: list[int] = []
    cursor = int(scale)
    while len(anchors) < count and cursor > 11:
        anchor = int(prevprime(cursor))
        anchors.append(anchor)
        cursor = anchor
    return anchors


def max_required_divisor_floor(anchors: list[int]) -> int:
    """Return the largest divisor floor implied by the fallback candidates."""
    return max(isqrt(anchor + 1) for anchor in anchors) if anchors else 0


def run_scale(
    exponent: int,
    sample_count: int,
    full_surface_limit: int,
    max_divisor_floor: int,
    candidate_bound: int,
) -> dict[str, object]:
    """Run one exact scale probe or record why it was skipped."""
    scale = 10**exponent
    if scale <= full_surface_limit:
        anchors = full_surface_anchors(scale)
        mode = "full_surface"
    else:
        anchors = sampled_anchors_near(scale, sample_count)
        mode = "near_scale_sample"

    divisor_floor = max_required_divisor_floor(anchors)
    base: dict[str, object] = {
        "scale_exponent": exponent,
        "scale": scale,
        "mode": mode,
        "anchors_requested": len(anchors),
        "max_required_divisor_floor": divisor_floor,
    }
    if divisor_floor > max_divisor_floor:
        return {
            **base,
            "status": "skipped",
            "skip_reason": "fallback_divisor_floor_exceeds_budget",
            "anchors_scanned": 0,
            "emitted_count": 0,
            "audit_confirmed": 0,
            "audit_failed": 0,
            "pgs_count": 0,
            "fallback_count": 0,
            "pgs_rate": None,
            "fallback_rate": None,
            "pgs_percent": None,
            "fallback_percent": None,
            "first_failure": None,
            "runtime_seconds": 0.0,
        }

    started = time.perf_counter()
    records = emit_records(anchors, candidate_bound=candidate_bound)
    diagnostics = diagnostic_records(anchors, candidate_bound=candidate_bound)
    report = audit_report(records, diagnostics)
    runtime_seconds = time.perf_counter() - started
    return {
        **base,
        "status": "completed",
        "skip_reason": None,
        **report,
        "runtime_seconds": runtime_seconds,
    }


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


def plot_rates(rows: list[dict[str, object]], path: Path) -> None:
    """Plot PGS and fallback rates by scale."""
    completed = [row for row in rows if row["status"] == "completed"]
    skipped = [row for row in rows if row["status"] == "skipped"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = [int(row["scale_exponent"]) for row in completed]
    ax.plot(
        x,
        [float(row["pgs_rate"]) for row in completed],
        marker="o",
        label="PGS rate",
    )
    ax.plot(
        x,
        [float(row["fallback_rate"]) for row in completed],
        marker="o",
        label="Fallback rate",
    )
    for row in skipped:
        ax.axvline(int(row["scale_exponent"]), color="0.85", linewidth=1)
    ax.set_xlabel("Scale exponent k in 10^k")
    ax.set_ylabel("Portion of emitted primes")
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("Minimal PGS Generator Source Portion by Scale")
    ax.legend()
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_counts(rows: list[dict[str, object]], path: Path) -> None:
    """Plot source counts by scale."""
    completed = [row for row in rows if row["status"] == "completed"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = [int(row["scale_exponent"]) for row in completed]
    pgs = [int(row["pgs_count"]) for row in completed]
    fallback = [int(row["fallback_count"]) for row in completed]
    ax.bar(x, pgs, label="PGS")
    ax.bar(x, fallback, bottom=pgs, label="Fallback")
    ax.set_xlabel("Scale exponent k in 10^k")
    ax.set_ylabel("Emitted records")
    ax.set_title("PGS vs Fallback Counts on Completed Scale Probes")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_cost(rows: list[dict[str, object]], path: Path) -> None:
    """Plot divisor-floor budget pressure by scale."""
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = [int(row["scale_exponent"]) for row in rows]
    floors = [int(row["max_required_divisor_floor"]) for row in rows]
    ax.plot(x, floors, marker="o", label="required divisor floor")
    ax.set_yscale("log")
    ax.set_xlabel("Scale exponent k in 10^k")
    ax.set_ylabel("max floor(sqrt(candidate))")
    ax.set_title("Fallback Divisor-Exhaustion Cost by Scale")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def plot_audit(rows: list[dict[str, object]], path: Path) -> None:
    """Plot audit confirmations and failures."""
    completed = [row for row in rows if row["status"] == "completed"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    x = [int(row["scale_exponent"]) for row in completed]
    confirmed = [int(row["audit_confirmed"]) for row in completed]
    failed = [int(row["audit_failed"]) for row in completed]
    ax.bar(x, confirmed, label="confirmed")
    ax.bar(x, failed, bottom=confirmed, label="failed")
    ax.set_xlabel("Scale exponent k in 10^k")
    ax.set_ylabel("Audited records")
    ax.set_title("Audit Results on Completed Scale Probes")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    """Build the scale probe CLI."""
    parser = argparse.ArgumentParser(description="Probe minimal PGS generator scales.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-exponent", type=int, default=5)
    parser.add_argument("--max-exponent", type=int, default=18)
    parser.add_argument("--sample-count", type=int, default=16)
    parser.add_argument("--full-surface-limit", type=int, default=1_000_000)
    parser.add_argument("--max-divisor-floor", type=int, default=2_000_000)
    parser.add_argument("--candidate-bound", type=int, default=128)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run all configured scale probes and write plots."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plots_dir = args.output_dir / "plots"
    plots_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        run_scale(
            exponent,
            args.sample_count,
            args.full_surface_limit,
            args.max_divisor_floor,
            args.candidate_bound,
        )
        for exponent in range(args.min_exponent, args.max_exponent + 1)
    ]

    write_json({"rows": rows}, args.output_dir / "scale_probe_summary.json")
    write_jsonl(rows, args.output_dir / "scale_probe_rows.jsonl")
    write_csv(rows, args.output_dir / "scale_probe_rows.csv")
    plot_rates(rows, plots_dir / "fallback_rate_by_scale.png")
    plot_counts(rows, plots_dir / "source_counts_by_scale.png")
    plot_cost(rows, plots_dir / "fallback_cost_by_scale.png")
    plot_audit(rows, plots_dir / "audit_status_by_scale.png")
    for row in rows:
        if row["status"] == "completed":
            print(
                "scale=10^{scale_exponent} fallback_percent={fallback_percent:.2f}% "
                "pgs_percent={pgs_percent:.2f}% audit_failed={audit_failed}".format(
                    **row
                )
            )
        else:
            print(
                "scale=10^{scale_exponent} fallback_percent=SKIPPED "
                "reason={skip_reason}".format(**row)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

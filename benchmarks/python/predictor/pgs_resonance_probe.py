#!/usr/bin/env python3
"""Measure phase-conditioned resonance around record prime gaps."""

from __future__ import annotations

import argparse
import json
import math
from bisect import bisect_right
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sympy import primerange


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "output" / "python" / "predictor" / "pgs_resonance"
DEFAULT_MAX_N = 20_000_000
DEFAULT_WINDOW_RADIUS = 8
DEFAULT_RING_INNER = 9
DEFAULT_RING_OUTER = 64
DEFAULT_LATE_CUTOFF = 100_000
DEFAULT_PHASE_MODULUS = 210
DEFAULT_COMPARISON_FLOOR = 5_000_000


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Measure phase-conditioned record-gap echo structure on an exact prime surface.",
    )
    parser.add_argument(
        "--max-n",
        type=int,
        default=DEFAULT_MAX_N,
        help="Largest integer included in the exact prime surface.",
    )
    parser.add_argument(
        "--window-radius",
        type=int,
        default=DEFAULT_WINDOW_RADIUS,
        help="Number of neighboring gaps kept on each side of the record gap.",
    )
    parser.add_argument(
        "--ring-inner",
        type=int,
        default=DEFAULT_RING_INNER,
        help="Inner exclusion radius for the uncontaminated local baseline ring.",
    )
    parser.add_argument(
        "--ring-outer",
        type=int,
        default=DEFAULT_RING_OUTER,
        help="Outer radius for the uncontaminated local baseline ring.",
    )
    parser.add_argument(
        "--late-cutoff",
        type=int,
        default=DEFAULT_LATE_CUTOFF,
        help="Smallest record-gap start included in the late-record subset.",
    )
    parser.add_argument(
        "--phase-modulus",
        type=int,
        default=DEFAULT_PHASE_MODULUS,
        help="Residue modulus used for entry-phase conditioning.",
    )
    parser.add_argument(
        "--comparison-floor",
        type=int,
        default=DEFAULT_COMPARISON_FLOOR,
        help="Secondary exact surface used in the default cross-scale comparison.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and plot artifacts.",
    )
    return parser


def record_gap_indices(gaps: list[int]) -> list[int]:
    """Return the indices of new record gaps."""
    indices: list[int] = []
    largest_gap = -1
    for index, gap in enumerate(gaps):
        if gap > largest_gap:
            indices.append(index)
            largest_gap = gap
    return indices


def comparison_scales(max_n: int, comparison_floor: int) -> list[int]:
    """Return the deterministic scale list used for cross-scale comparison."""
    if max_n <= comparison_floor:
        return [max_n]
    return sorted({comparison_floor, max_n})


def ring_baseline(
    gaps: list[int],
    index: int,
    ring_inner: int,
    ring_outer: int,
) -> float:
    """Return the uncontaminated local baseline around one gap."""
    left_ring = gaps[index - ring_outer:index - ring_inner + 1]
    right_ring = gaps[index + ring_inner:index + ring_outer + 1]
    ring = left_ring + right_ring
    return sum(ring) / len(ring)


def normalized_profile(
    gaps: list[int],
    index: int,
    window_radius: int,
    ring_inner: int,
    ring_outer: int,
) -> list[float]:
    """Return the normalized local gap profile around one index."""
    baseline = ring_baseline(gaps, index, ring_inner, ring_outer)
    return [gaps[index + offset] / baseline for offset in range(-window_radius, window_radius + 1)]


def mean_profile(rows: list[list[float]]) -> list[float]:
    """Return the columnwise mean of aligned profile rows."""
    return [sum(column) / len(column) for column in zip(*rows)]


def phase_profile_rows(
    primes: list[int],
    gaps: list[int],
    indices: list[int],
    window_radius: int,
    ring_inner: int,
    ring_outer: int,
    phase_modulus: int,
) -> dict[int, list[list[float]]]:
    """Return normalized profiles grouped by the phase of the gap start."""
    grouped: dict[int, list[list[float]]] = {}
    for index in indices:
        phase = primes[index] % phase_modulus
        grouped.setdefault(phase, []).append(
            normalized_profile(gaps, index, window_radius, ring_inner, ring_outer)
        )
    return grouped


def profile_summary(profile: list[float], window_radius: int) -> dict[str, float]:
    """Return compact summary ratios for one neighborhood profile."""
    center = window_radius
    adjacent_mean = (profile[center - 1] + profile[center + 1]) / 2.0
    four_step_mean = (profile[center - 4] + profile[center + 4]) / 2.0
    return {
        "adjacent_mean": adjacent_mean,
        "four_step_mean": four_step_mean,
        "four_step_to_adjacent_ratio": four_step_mean / adjacent_mean,
        "pre_five_mean": sum(profile[center - 5:center]) / 5.0,
        "post_five_mean": sum(profile[center + 1:center + 6]) / 5.0,
    }


def anomaly_profile(profile: list[float]) -> list[float]:
    """Return the signed anomaly profile relative to the local baseline."""
    return [value - 1.0 for value in profile]


def symmetric_harmonics(profile: list[float], window_radius: int) -> list[float]:
    """Return the symmetric harmonic amplitudes for k = 1..window_radius."""
    anomaly = anomaly_profile(profile)
    center = window_radius
    return [
        (anomaly[center - k] + anomaly[center + k]) / 2.0
        for k in range(1, window_radius + 1)
    ]


def phase_summaries(
    phase_profiles: dict[int, list[float]],
    phase_counts: dict[int, int],
    window_radius: int,
) -> dict[str, dict[str, float | int]]:
    """Return per-phase harmonic summaries."""
    summaries: dict[str, dict[str, float | int]] = {}
    for phase in sorted(phase_profiles):
        profile = phase_profiles[phase]
        harmonics = symmetric_harmonics(profile, window_radius)
        dominant_index, dominant_value = max(
            enumerate(harmonics, start=1),
            key=lambda item: (item[1], -item[0]),
        )
        summaries[str(phase)] = {
            "count": phase_counts[phase],
            "dominant_harmonic_k": dominant_index,
            "dominant_harmonic_amplitude": dominant_value,
            **profile_summary(profile, window_radius),
        }
    return summaries


def event_rows(
    primes: list[int],
    gaps: list[int],
    indices: list[int],
    window_radius: int,
    ring_inner: int,
    ring_outer: int,
    phase_modulus: int,
) -> list[dict[str, float | int | list[float]]]:
    """Return per-record event measurements."""
    rows: list[dict[str, float | int | list[float]]] = []
    for index in indices:
        profile = normalized_profile(gaps, index, window_radius, ring_inner, ring_outer)
        rows.append(
            {
                "gap_start": primes[index],
                "gap_end": primes[index + 1],
                "phase": primes[index] % phase_modulus,
                "record_gap": gaps[index],
                "profile": profile,
                "anomaly_profile": anomaly_profile(profile),
                "harmonics": symmetric_harmonics(profile, window_radius),
                **profile_summary(profile, window_radius),
            }
        )
    return rows


def analyze_scale(
    primes_full: list[int],
    scale_max_n: int,
    window_radius: int,
    ring_inner: int,
    ring_outer: int,
    late_cutoff: int,
    phase_modulus: int,
) -> dict[str, object]:
    """Return one full phase-conditioned resonance summary."""
    prime_count = bisect_right(primes_full, scale_max_n)
    primes = primes_full[:prime_count]
    gaps = [right - left for left, right in zip(primes, primes[1:])]

    record_indices_all = record_gap_indices(gaps)
    eligible_record_indices = [
        index
        for index in record_indices_all
        if index >= ring_outer and index + ring_outer < len(gaps)
    ]
    late_record_indices = [
        index for index in eligible_record_indices if primes[index] >= late_cutoff
    ]
    record_index_set = set(record_indices_all)
    control_indices = [
        index
        for index in range(ring_outer, len(gaps) - ring_outer)
        if index not in record_index_set
    ]

    control_rows = [
        normalized_profile(gaps, index, window_radius, ring_inner, ring_outer)
        for index in control_indices
    ]
    all_record_rows = [
        normalized_profile(gaps, index, window_radius, ring_inner, ring_outer)
        for index in eligible_record_indices
    ]
    late_record_rows = [
        normalized_profile(gaps, index, window_radius, ring_inner, ring_outer)
        for index in late_record_indices
    ]

    phase_rows = phase_profile_rows(
        primes,
        gaps,
        eligible_record_indices,
        window_radius,
        ring_inner,
        ring_outer,
        phase_modulus,
    )
    phase_profiles = {
        phase: mean_profile(rows)
        for phase, rows in phase_rows.items()
    }
    phase_counts = {
        phase: len(rows)
        for phase, rows in phase_rows.items()
    }

    return {
        "max_n": scale_max_n,
        "prime_count": len(primes),
        "gap_count": len(gaps),
        "record_count_total": len(record_indices_all),
        "record_count_used": len(eligible_record_indices),
        "late_record_count_used": len(late_record_indices),
        "profiles": {
            "control": mean_profile(control_rows),
            "all_records": mean_profile(all_record_rows),
            "late_records": mean_profile(late_record_rows),
        },
        "profile_summary": {
            "control": profile_summary(mean_profile(control_rows), window_radius),
            "all_records": profile_summary(mean_profile(all_record_rows), window_radius),
            "late_records": profile_summary(mean_profile(late_record_rows), window_radius),
        },
        "phase_modulus": phase_modulus,
        "observed_phases": sorted(phase_profiles),
        "phase_counts": {str(phase): count for phase, count in sorted(phase_counts.items())},
        "phase_profiles": {
            str(phase): profile
            for phase, profile in sorted(phase_profiles.items())
        },
        "phase_anomaly_profiles": {
            str(phase): anomaly_profile(profile)
            for phase, profile in sorted(phase_profiles.items())
        },
        "phase_harmonics": {
            str(phase): {
                str(k): value
                for k, value in enumerate(symmetric_harmonics(profile, window_radius), start=1)
            }
            for phase, profile in sorted(phase_profiles.items())
        },
        "phase_summary": phase_summaries(phase_profiles, phase_counts, window_radius),
        "record_events": event_rows(
            primes,
            gaps,
            eligible_record_indices,
            window_radius,
            ring_inner,
            ring_outer,
            phase_modulus,
        ),
    }


def plot_profiles(
    control_profile: list[float],
    all_record_profile: list[float],
    late_record_profile: list[float],
    output_path: Path,
    max_n: int,
) -> None:
    """Render the normalized neighborhood comparison plot."""
    window_radius = (len(control_profile) - 1) // 2
    offsets = list(range(-window_radius, window_radius + 1))
    figure, axis = plt.subplots(figsize=(10.5, 6.0))
    axis.plot(
        offsets,
        control_profile,
        color="#1d4ed8",
        linewidth=1.8,
        alpha=0.85,
        label="All non-record windows",
    )
    axis.plot(
        offsets,
        all_record_profile,
        color="#c2410c",
        linewidth=2.2,
        marker="o",
        label="All record gaps",
    )
    axis.plot(
        offsets,
        late_record_profile,
        color="#047857",
        linewidth=2.4,
        marker="o",
        label="Late record gaps",
    )
    axis.axhline(1.0, color="#334155", linewidth=1.0, linestyle="--")
    axis.axvline(0, color="#7c2d12", linewidth=1.0, linestyle=":")
    axis.set_xlabel("Gap offset relative to the record gap")
    axis.set_ylabel("Gap size / surrounding-ring baseline")
    axis.set_title(f"Record-gap neighborhood profiles on the exact surface to {max_n:,}")
    axis.grid(alpha=0.18)
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(output_path, dpi=170)


def heatmap_limit(matrix: np.ndarray) -> float:
    """Return the symmetric color limit for a signed heatmap."""
    finite = matrix[np.isfinite(matrix)]
    if finite.size == 0:
        return 1.0
    limit = float(np.max(np.abs(finite)))
    return limit if limit > 0.0 else 1.0


def plot_phase_offset_heatmap(
    scale_summary: dict[str, object],
    window_radius: int,
    output_path: Path,
) -> None:
    """Render the phase-conditioned signed anomaly matrix R(k, phi)."""
    phases = [int(value) for value in scale_summary["observed_phases"]]
    matrix = np.array(
        [scale_summary["phase_anomaly_profiles"][str(phase)] for phase in phases],
        dtype=float,
    )
    offsets = list(range(-window_radius, window_radius + 1))
    figure_height = max(4.5, 0.42 * len(phases) + 2.0)
    figure, axis = plt.subplots(figsize=(11.0, figure_height))
    image = axis.imshow(
        matrix,
        aspect="auto",
        cmap="coolwarm",
        vmin=-heatmap_limit(matrix),
        vmax=heatmap_limit(matrix),
    )
    axis.set_xticks(range(len(offsets)))
    axis.set_xticklabels(offsets)
    axis.set_yticks(range(len(phases)))
    axis.set_yticklabels(
        [f"{phase} (n={scale_summary['phase_counts'][str(phase)]})" for phase in phases]
    )
    axis.set_xlabel("Gap offset k")
    axis.set_ylabel("Entry phase q mod 210")
    axis.set_title("Signed anomaly kernel R(k, phi) on the primary exact surface")
    figure.colorbar(image, ax=axis, label="Normalized gap anomaly")
    figure.tight_layout()
    figure.savefig(output_path, dpi=170)


def plot_phase_harmonic_heatmap(
    scale_summary: dict[str, object],
    window_radius: int,
    output_path: Path,
) -> None:
    """Render the phase-conditioned symmetric harmonic amplitudes."""
    phases = [int(value) for value in scale_summary["observed_phases"]]
    matrix = np.array(
        [
            [
                scale_summary["phase_harmonics"][str(phase)][str(k)]
                for k in range(1, window_radius + 1)
            ]
            for phase in phases
        ],
        dtype=float,
    )
    figure_height = max(4.5, 0.42 * len(phases) + 2.0)
    figure, axis = plt.subplots(figsize=(9.4, figure_height))
    image = axis.imshow(
        matrix,
        aspect="auto",
        cmap="coolwarm",
        vmin=-heatmap_limit(matrix),
        vmax=heatmap_limit(matrix),
    )
    axis.set_xticks(range(window_radius))
    axis.set_xticklabels(list(range(1, window_radius + 1)))
    axis.set_yticks(range(len(phases)))
    axis.set_yticklabels(
        [f"{phase} (n={scale_summary['phase_counts'][str(phase)]})" for phase in phases]
    )
    axis.set_xlabel("Symmetric harmonic index k")
    axis.set_ylabel("Entry phase q mod 210")
    axis.set_title("Phase-conditioned harmonic amplitudes A(k, phi)")
    figure.colorbar(image, ax=axis, label="Symmetric anomaly amplitude")
    figure.tight_layout()
    figure.savefig(output_path, dpi=170)


def plot_cross_scale_dominant_harmonic(
    scales: list[int],
    scale_summaries: dict[str, dict[str, object]],
    output_path: Path,
) -> None:
    """Render the dominant harmonic index by phase across scales."""
    phase_union = sorted(
        {
            int(phase)
            for summary in scale_summaries.values()
            for phase in summary["observed_phases"]
        }
    )
    matrix = np.full((len(phase_union), len(scales)), np.nan, dtype=float)
    counts = np.full((len(phase_union), len(scales)), "", dtype=object)

    for column, scale in enumerate(scales):
        summary = scale_summaries[str(scale)]
        for row, phase in enumerate(phase_union):
            phase_key = str(phase)
            if phase_key not in summary["phase_summary"]:
                continue
            matrix[row, column] = summary["phase_summary"][phase_key]["dominant_harmonic_k"]
            counts[row, column] = str(summary["phase_summary"][phase_key]["count"])

    masked = np.ma.masked_invalid(matrix)
    figure_height = max(4.8, 0.42 * len(phase_union) + 2.0)
    figure, axis = plt.subplots(figsize=(7.6, figure_height))
    image = axis.imshow(
        masked,
        aspect="auto",
        cmap="viridis",
        vmin=1,
        vmax=max(1, int(np.nanmax(matrix))),
    )
    axis.set_xticks(range(len(scales)))
    axis.set_xticklabels([f"{scale:,}" for scale in scales])
    axis.set_yticks(range(len(phase_union)))
    axis.set_yticklabels([str(phase) for phase in phase_union])
    axis.set_xlabel("Exact surface upper bound")
    axis.set_ylabel("Entry phase q mod 210")
    axis.set_title("Dominant harmonic index by phase across exact scales")
    figure.colorbar(image, ax=axis, label="Dominant k")

    for row in range(len(phase_union)):
        for column in range(len(scales)):
            if math.isnan(matrix[row, column]):
                continue
            axis.text(
                column,
                row,
                f"{int(matrix[row, column])}\n(n={counts[row, column]})",
                ha="center",
                va="center",
                color="white" if matrix[row, column] >= 5 else "black",
                fontsize=8,
            )

    figure.tight_layout()
    figure.savefig(output_path, dpi=170)


def main(argv: list[str] | None = None) -> int:
    """Run the probe and write the artifact set."""
    args = build_parser().parse_args(argv)
    if args.window_radius < 5:
        raise ValueError("window_radius must be at least 5")
    if args.ring_inner <= args.window_radius:
        raise ValueError("ring_inner must exceed window_radius")
    if args.ring_outer < args.ring_inner:
        raise ValueError("ring_outer must be at least ring_inner")
    if args.phase_modulus <= 1:
        raise ValueError("phase_modulus must exceed 1")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    scales = comparison_scales(args.max_n, args.comparison_floor)
    primes_full = list(primerange(2, args.max_n + 1))
    scale_summaries = {
        str(scale): analyze_scale(
            primes_full,
            scale,
            args.window_radius,
            args.ring_inner,
            args.ring_outer,
            args.late_cutoff,
            args.phase_modulus,
        )
        for scale in scales
    }
    primary_summary = scale_summaries[str(args.max_n)]

    summary = {
        "primary_max_n": args.max_n,
        "comparison_scales": scales,
        "window_radius": args.window_radius,
        "ring_inner": args.ring_inner,
        "ring_outer": args.ring_outer,
        "late_cutoff": args.late_cutoff,
        "phase_modulus": args.phase_modulus,
        "scale_summaries": scale_summaries,
    }

    summary_path = args.output_dir / "pgs_resonance_summary.json"
    profile_path = args.output_dir / "pgs_resonance_profile.png"
    phase_offset_path = args.output_dir / "pgs_resonance_phase_offset_heatmap.png"
    phase_harmonic_path = args.output_dir / "pgs_resonance_phase_harmonic_heatmap.png"
    cross_scale_path = args.output_dir / "pgs_resonance_cross_scale_dominant_harmonic.png"

    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    plot_profiles(
        primary_summary["profiles"]["control"],
        primary_summary["profiles"]["all_records"],
        primary_summary["profiles"]["late_records"],
        profile_path,
        args.max_n,
    )
    plot_phase_offset_heatmap(primary_summary, args.window_radius, phase_offset_path)
    plot_phase_harmonic_heatmap(primary_summary, args.window_radius, phase_harmonic_path)
    plot_cross_scale_dominant_harmonic(scales, scale_summaries, cross_scale_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

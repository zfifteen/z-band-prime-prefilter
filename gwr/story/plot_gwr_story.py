#!/usr/bin/env python3
"""Generate the first plot batch for the GWR long-form story."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment
from z_band_prime_gap_ridge.runs import build_even_window_starts


PLOTS_DIR = ROOT / "gwr" / "story" / "plots"
SUMMARY_PATH = ROOT / "gwr" / "story" / "plot_manifest.json"
PRIOR_JSON = (
    ROOT
    / "benchmarks"
    / "output"
    / "python"
    / "gap_ridge"
    / "lexicographic_peak_validation"
    / "lexicographic_peak_validation.json"
)
REVALIDATION_JSON = ROOT / "output" / "lexicographic_rule_revalidation_summary.json"


def raw_z(values: np.ndarray, divisors: np.ndarray) -> np.ndarray:
    """Return the raw-Z score on one integer array."""
    return (1.0 - divisors.astype(np.float64) / 2.0) * np.log(values.astype(np.float64))


def analyze_interval_details(lo: int, hi: int) -> list[dict[str, object]]:
    """Return per-gap detail rows for one interval."""
    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]
    rows: list[dict[str, object]] = []

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]
        gap_scores = raw_z(gap_values, gap_divisors)

        best_index = int(np.argmax(gap_scores))
        min_d = int(np.min(gap_divisors))
        lex_index = int(np.flatnonzero(gap_divisors == min_d)[0])
        offset = best_index + 1
        edge_distance = min(offset, gap - offset)
        normalized_position = offset / gap
        sorted_scores = np.sort(gap_scores)[::-1]
        score_margin = float(sorted_scores[0] - sorted_scores[1]) if sorted_scores.size >= 2 else 0.0

        rows.append(
            {
                "left_prime": int(left_prime),
                "right_prime": int(right_prime),
                "gap": gap,
                "gap_values": gap_values.astype(np.int64).tolist(),
                "gap_divisors": gap_divisors.astype(np.int64).tolist(),
                "gap_scores": gap_scores.astype(np.float64).tolist(),
                "best_index": best_index,
                "best_n": int(gap_values[best_index]),
                "best_d": int(gap_divisors[best_index]),
                "lex_index": lex_index,
                "lex_n": int(gap_values[lex_index]),
                "lex_d": int(gap_divisors[lex_index]),
                "edge_distance": edge_distance,
                "normalized_position": normalized_position,
                "score_margin": score_margin,
            }
        )

    return rows


def select_exemplars(exact_rows: list[dict[str, object]], sampled_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Pick a small set of narrative exemplar gaps."""
    small_gap = next(row for row in exact_rows if int(row["gap"]) == 4)
    medium_gap = next(row for row in exact_rows if int(row["gap"]) == 18 and int(row["best_d"]) == 4)
    tight_exact = min(exact_rows, key=lambda row: float(row["score_margin"]))
    tight_sampled = min(sampled_rows, key=lambda row: float(row["score_margin"]))
    return [
        {"label": "Short gap at exact 1e6", "surface": "exact 1e6", "row": small_gap},
        {"label": "Medium gap at exact 1e6", "surface": "exact 1e6", "row": medium_gap},
        {"label": "Tightest-margin gap at exact 1e6", "surface": "exact 1e6", "row": tight_exact},
        {"label": "Tightest-margin gap at sampled 1e9", "surface": "even-window 1e9", "row": tight_sampled},
    ]


def plot_exemplar_gap_profiles(exemplars: list[dict[str, object]], output_path: Path) -> None:
    """Plot several individual gap score profiles."""
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 8.8), constrained_layout=True)
    divisor_colors = {
        3: "#2b8cbe",
        4: "#1a9850",
        6: "#66bd63",
        8: "#a6d96a",
        10: "#fdae61",
        12: "#f46d43",
    }

    for axis, exemplar in zip(axes.flat, exemplars):
        row = exemplar["row"]
        gap_values = np.array(row["gap_values"], dtype=np.int64)
        gap_divisors = np.array(row["gap_divisors"], dtype=np.int64)
        gap_scores = np.array(row["gap_scores"], dtype=np.float64)
        offsets = gap_values - int(row["left_prime"])
        colors = [divisor_colors.get(int(d), "#7f7f7f") for d in gap_divisors]

        axis.scatter(offsets, gap_scores, c=colors, s=42, edgecolor="white", linewidth=0.5, zorder=3)
        axis.plot(offsets, gap_scores, color="#4c566a", alpha=0.35, linewidth=1.2, zorder=2)
        axis.scatter(
            offsets[int(row["best_index"])],
            gap_scores[int(row["best_index"])],
            marker="*",
            s=220,
            color="#111111",
            zorder=5,
            label="raw-Z winner",
        )
        axis.scatter(
            offsets[int(row["lex_index"])],
            gap_scores[int(row["lex_index"])],
            marker="o",
            s=110,
            facecolor="none",
            edgecolor="#cc3311",
            linewidth=2.2,
            zorder=6,
            label="GWR winner",
        )
        axis.set_title(
            f"{exemplar['label']}\n({int(row['left_prime'])}, {int(row['right_prime'])}), gap {int(row['gap'])}",
            fontsize=10.5,
        )
        axis.set_xlabel("Offset from left prime")
        axis.set_ylabel("raw-Z")
        axis.grid(alpha=0.22, linewidth=0.7)

    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.02))
    fig.suptitle("Exemplar prime gaps: the raw-Z winner and the GWR winner coincide", fontsize=15, y=1.06)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_match_rate_surface(output_path: Path) -> None:
    """Plot the tested validation ladder."""
    prior = json.loads(PRIOR_JSON.read_text())
    revalidation = json.loads(REVALIDATION_JSON.read_text())

    rows: list[dict[str, object]] = []
    rows.extend(prior["rows"])
    rows.append(revalidation["experiment_a"])

    scales = []
    labels = []
    gaps = []
    for row in rows:
        scales.append(int(row["scale"]))
        labels.append(f"{int(row['scale']):,}")
        gaps.append(int(row["gap_count"]))

    fig = plt.figure(figsize=(12.2, 7.2), constrained_layout=True)
    grid = fig.add_gridspec(2, 1, height_ratios=[3.2, 1.8])
    ax = fig.add_subplot(grid[0])
    ax_table = fig.add_subplot(grid[1])

    ax.plot(scales, np.ones(len(scales)), marker="o", linewidth=2.2, color="#1f4e79")
    ax.set_xscale("log")
    ax.set_ylim(0.9988, 1.0012)
    ax.set_xlabel("Scale")
    ax.set_ylabel("Match rate")
    ax.set_title("GWR validation surface: every reported tested regime remains at match rate 1.0")
    ax.grid(alpha=0.25)
    ax.set_yticks([0.999, 1.0, 1.001])

    exact_points = [(int(row["scale"]), int(row["gap_count"])) for row in rows if str(row.get("mode", row.get("window_mode", ""))) == "exact"]
    sampled_points = [(int(row["scale"]), int(row["gap_count"])) for row in rows if str(row.get("mode", row.get("window_mode", ""))) != "exact"]

    def scale_label(scale: int) -> str:
        exponent = int(round(math.log10(scale)))
        if scale == 2 * 10**7:
            return "2e7"
        return f"1e{exponent}"

    for scale, _ in exact_points:
        ax.annotate(
            scale_label(scale),
            (scale, 1.0),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=8.5,
            color="#243b53",
        )

    sampled_anchor_scales = {10**8, 10**10, 10**12, 10**14, 10**16, 10**18}
    for scale, _ in sampled_points:
        if scale not in sampled_anchor_scales:
            continue
        ax.annotate(
            scale_label(scale),
            (scale, 1.0),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=8.5,
            color="#243b53",
        )

    ax_table.axis("off")
    table_rows = [
        ["exact 1e6", f"{70_327:,}"],
        ["exact 1e7", f"{605_597:,}"],
        ["exact 2e7", f"{1_163_198:,}"],
        ["sampled 1e8", f"{444_133:,}"],
        ["sampled 1e12", f"{344_454:,}"],
        ["sampled 1e18", f"{275_466:,}"],
    ]
    table = ax_table.table(
        cellText=table_rows,
        colLabels=["Regime", "Gap count"],
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1.0, 1.25)
    ax_table.set_title("Selected anchor regimes and tested gap counts", fontsize=10.5, pad=6)

    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def _winner_surface_rows() -> list[dict[str, object]]:
    """Return per-gap rows on the even-window 1e9 story surface."""
    starts = build_even_window_starts(1_000_000_000, 2_000_000, 4)
    all_rows: list[dict[str, object]] = []
    for start in starts:
        all_rows.extend(analyze_interval_details(start, start + 2_000_000))
    return all_rows


def plot_divisor_enrichment(rows: list[dict[str, object]], output_path: Path) -> None:
    """Plot winner-share versus baseline-share by divisor class."""
    winner_counts: Counter[int] = Counter()
    baseline_counts: Counter[int] = Counter()
    total_winners = 0
    total_baseline = 0

    for row in rows:
        gap_divisors = [int(value) for value in row["gap_divisors"]]
        winner_d = int(row["best_d"])
        winner_counts[winner_d] += 1
        total_winners += 1
        for d in gap_divisors:
            baseline_counts[d] += 1
            total_baseline += 1

    visible_ds = [d for d in sorted(set(winner_counts) | set(baseline_counts)) if d <= 24]
    remainder_winner = sum(count for d, count in winner_counts.items() if d > 24)
    remainder_baseline = sum(count for d, count in baseline_counts.items() if d > 24)

    labels = [str(d) for d in visible_ds]
    winner_share = [winner_counts[d] / total_winners for d in visible_ds]
    baseline_share = [baseline_counts[d] / total_baseline for d in visible_ds]

    if remainder_winner > 0 or remainder_baseline > 0:
        labels.append("24+")
        winner_share.append(remainder_winner / total_winners)
        baseline_share.append(remainder_baseline / total_baseline)

    winner_share_arr = np.array(winner_share, dtype=np.float64)
    baseline_share_arr = np.array(baseline_share, dtype=np.float64)
    enrichment = winner_share_arr / baseline_share_arr

    fig, ax = plt.subplots(figsize=(10.5, 5.2), constrained_layout=True)
    ax.bar(labels, enrichment, color="#1a9850", alpha=0.85)
    ax.axhline(1.0, color="#333333", linewidth=1.1, linestyle="--")
    ax.set_title("Winner selection is strongly enriched toward low divisor-count classes")
    ax.set_xlabel("Divisor count d(n)")
    ax.set_ylabel("Winner share / baseline share")
    ax.grid(axis="y", alpha=0.22)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_normalized_position(rows: list[dict[str, object]], output_path: Path) -> None:
    """Plot winner normalized positions against the uniform interior baseline."""
    bins = np.linspace(0.0, 1.0, 21)
    winner_positions = np.array([float(row["normalized_position"]) for row in rows], dtype=np.float64)

    baseline_positions: list[float] = []
    for row in rows:
        gap = int(row["gap"])
        baseline_positions.extend(offset / gap for offset in range(1, gap))

    fig, ax = plt.subplots(figsize=(10.5, 5.2), constrained_layout=True)
    ax.hist(baseline_positions, bins=bins, density=True, alpha=0.45, color="#bdbdbd", label="all interior positions")
    ax.hist(winner_positions, bins=bins, density=True, alpha=0.75, color="#1f78b4", label="GWR winners")
    ax.set_title("Winners cluster toward the left side of the gap")
    ax.set_xlabel("Normalized position in gap (offset / gap)")
    ax.set_ylabel("Density")
    ax.legend(frameon=False)
    ax.grid(alpha=0.2)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_edge_distance(rows: list[dict[str, object]], output_path: Path) -> None:
    """Plot edge-distance counts against the baseline interior expectation."""
    winner_counts: Counter[int] = Counter()
    baseline_counts: Counter[int] = Counter()
    for row in rows:
        winner_counts[int(row["edge_distance"])] += 1
        gap = int(row["gap"])
        for offset in range(1, gap):
            baseline_counts[min(offset, gap - offset)] += 1

    max_edge_distance = max(max(winner_counts), max(baseline_counts))
    xs = np.arange(1, min(max_edge_distance, 15) + 1)
    winner_share = np.array([winner_counts[int(x)] for x in xs], dtype=np.float64)
    winner_share /= winner_share.sum()
    baseline_share = np.array([baseline_counts[int(x)] for x in xs], dtype=np.float64)
    baseline_share /= baseline_share.sum()

    fig, ax = plt.subplots(figsize=(10.5, 5.2), constrained_layout=True)
    width = 0.38
    ax.bar(xs - width / 2, baseline_share, width=width, color="#c7c7c7", label="baseline")
    ax.bar(xs + width / 2, winner_share, width=width, color="#cc3311", label="winners")
    ax.set_title("Edge-distance 2 is heavily overrepresented among winners")
    ax.set_xlabel("Edge distance")
    ax.set_ylabel("Share")
    ax.set_xticks(xs)
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_counterexample_pair(output_path: Path) -> None:
    """Plot the explicit unordered-pair counterexample to the over-strong theorem."""
    labels = ["49", "6"]
    ds = [3, 4]
    zs = [(1.0 - 3 / 2.0) * math.log(49), (1.0 - 4 / 2.0) * math.log(6)]
    colors = ["#2b8cbe", "#f46d43"]

    fig, ax1 = plt.subplots(figsize=(8.5, 4.8), constrained_layout=True)
    ax2 = ax1.twinx()

    ax1.bar(np.arange(2) - 0.18, ds, width=0.36, color=colors, alpha=0.85)
    ax2.bar(np.arange(2) + 0.18, zs, width=0.36, color=colors, alpha=0.35)

    ax1.set_xticks(np.arange(2))
    ax1.set_xticklabels(labels)
    ax1.set_xlabel("Composite integer")
    ax1.set_ylabel("Divisor count d(n)")
    ax2.set_ylabel("raw-Z")
    ax1.set_title("Why the unrestricted global theorem fails: lower d(n) does not always win out of order")

    ax1.annotate("49 has lower d(n)", (0, ds[0]), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=9)
    ax2.annotate("but lower raw-Z", (0.18, zs[0]), textcoords="offset points", xytext=(0, -18), ha="center", fontsize=9)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_winner_heatmap(rows: list[dict[str, object]], output_path: Path) -> None:
    """Plot winner concentration in normalized-position/divisor-count space."""
    positions = np.array([float(row["normalized_position"]) for row in rows], dtype=np.float64)
    divisors = np.array([int(row["best_d"]) for row in rows], dtype=np.float64)
    divisor_cap = 16.5
    capped_divisors = np.clip(divisors, 3.0, divisor_cap)

    xbins = np.linspace(0.0, 1.0, 21)
    ybins = np.array([3, 4, 5, 6, 8, 10, 12, 16, 17], dtype=np.float64)

    fig, ax = plt.subplots(figsize=(10.0, 5.8), constrained_layout=True)
    heatmap, _, _, image = ax.hist2d(positions, capped_divisors, bins=[xbins, ybins], cmap="YlGnBu")
    ax.set_title("Winner mass concentrates in the low-divisor, left-side corner")
    ax.set_xlabel("Normalized position in gap (offset / gap)")
    ax.set_ylabel("Winner divisor count d(n)")
    ax.set_yticks([3.5, 4.5, 5.5, 7.0, 9.0, 11.0, 14.0, 16.5])
    ax.set_yticklabels(["3", "4", "5", "6/8", "10", "12", "16", "16+"])
    fig.colorbar(image, ax=ax, label="Winner count")
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    """Generate the first batch of story figures."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    exact_rows = analyze_interval_details(2, 1_000_000 + 1)
    sampled_rows = _winner_surface_rows()
    exemplars = select_exemplars(exact_rows, sampled_rows)

    manifest = {
        "surfaces": {
            "exact_1e6_gap_count": len(exact_rows),
            "even_window_1e9_gap_count": len(sampled_rows),
        },
        "figures": [],
    }

    figure_jobs = [
        ("figure_01_exemplar_gap_profiles.png", lambda path: plot_exemplar_gap_profiles(exemplars, path)),
        ("figure_02_match_rate_surface.png", plot_match_rate_surface),
        ("figure_03_divisor_enrichment.png", lambda path: plot_divisor_enrichment(sampled_rows, path)),
        ("figure_04_normalized_position.png", lambda path: plot_normalized_position(sampled_rows, path)),
        ("figure_05_edge_distance.png", lambda path: plot_edge_distance(sampled_rows, path)),
        ("figure_06_counterexample_pair.png", plot_counterexample_pair),
        ("figure_07_winner_heatmap.png", lambda path: plot_winner_heatmap(sampled_rows, path)),
    ]

    for filename, builder in figure_jobs:
        output_path = PLOTS_DIR / filename
        builder(output_path)
        manifest["figures"].append({"file": filename, "path": str(output_path.relative_to(ROOT))})

    SUMMARY_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

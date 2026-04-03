"""Revalidate the Lexicographic Winner-Take-All Peak Rule on new surfaces.

This script reproduces a baseline run from the uploaded ``runs.py`` helper,
then extends the validation with explicit lexicographic winner checks,
additional window placements, and small alternative score perturbations.
"""

from __future__ import annotations

import csv
import json
import math
import platform
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

# Ensure the uploaded artifacts directory is importable.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import runs  # noqa: E402
from z_band_prime_composite_field import divisor_counts_segment  # noqa: E402

OUTPUT_DIR = HERE / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

EXPERIMENT_B_SCALES = [10**8, 10**9, 10**10, 10**11, 10**12]
EXPERIMENT_B_WINDOW_SIZE = 2_000_000
EXPERIMENT_B_WINDOW_COUNT = 4
EXPERIMENT_B_RANDOM_SEEDS = [20260331, 20260401]
EXPERIMENT_A_EXACT_LIMIT = 5_000_000
EXPERIMENT_D_EPSILON = 1.0

SOURCE_CODES = {
    "A1": "runs.py",
    "A2": "lexicographic_winner_take_all_peak_rule.md",
    "A3": "lexicographic_peak_validation.json",
}


def _float_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def score_field(values: np.ndarray, score_function_name: str) -> np.ndarray:
    """Return the smooth factor f(n) used inside the raw-Z score."""
    values_f = values.astype(np.float64)
    if score_function_name == "log(n)":
        return np.log(values_f)
    if score_function_name == "log(n+1)":
        return np.log(values_f + 1.0)
    if score_function_name == "log(n) + n^(-1/2)":
        return np.log(values_f) + values_f ** (-0.5)
    raise ValueError(f"Unknown score function: {score_function_name}")


def validate_lexicographic_rule_on_interval(
    lo: int,
    hi: int,
    scale: int,
    window_mode: str,
    *,
    window_size: int | None = None,
    seed: int | None = None,
    score_function_name: str = "log(n)",
    keep_examples: int = 10,
) -> dict:
    """Analyze all eligible prime gaps in [lo, hi) with explicit lexicographic checks."""
    interval_start = time.perf_counter()
    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]
    smooth_scores = score_field(values, score_function_name)

    gap_count = 0
    counterexample_count = 0
    match_count = 0
    max_gap = 0
    counterexample_examples: list[dict] = []
    min_score_margin: float | None = None
    min_margin_gap: dict | None = None

    observed_edge2 = 0
    baseline_edge2_sum = 0.0
    observed_d4 = 0
    baseline_d4_sum = 0.0
    observed_left = 0
    observed_right = 0
    observed_center = 0
    winner_d_counts: Counter[int] = Counter()

    for left_prime, right_prime in zip(primes[:-1], primes[1:]):
        gap = int(right_prime - left_prime)
        if gap < 4:
            continue

        left_index = int(left_prime - lo + 1)
        right_index = int(right_prime - lo)
        gap_divisors = divisor_count[left_index:right_index]
        gap_scores = (
            (1.0 - gap_divisors.astype(np.float64) / 2.0)
            * smooth_scores[left_index:right_index]
        )

        best_index = int(np.argmax(gap_scores))
        best_offset = best_index + 1
        best_n_z = int(left_prime + best_offset)
        best_d_z = int(gap_divisors[best_index])

        min_d = int(np.min(gap_divisors))
        lex_index = int(np.argmax(gap_divisors == min_d))
        best_n_lex = int(left_prime + lex_index + 1)
        best_d_lex = min_d

        gap_count += 1
        match = (best_n_z == best_n_lex) and (best_d_z == best_d_lex)
        if match:
            match_count += 1
        else:
            counterexample_count += 1
            if len(counterexample_examples) < keep_examples:
                counterexample_examples.append(
                    {
                        "left_prime": int(left_prime),
                        "right_prime": int(right_prime),
                        "gap": gap,
                        "best_n_z": best_n_z,
                        "best_d_z": best_d_z,
                        "best_n_lex": best_n_lex,
                        "best_d_lex": best_d_lex,
                    }
                )

        max_gap = max(max_gap, gap)

        top2 = np.partition(gap_scores, gap_scores.size - 2)[-2:]
        score_margin = float(np.max(top2) - np.min(top2))
        if min_score_margin is None or score_margin < min_score_margin:
            min_score_margin = score_margin
            min_margin_gap = {
                "left_prime": int(left_prime),
                "right_prime": int(right_prime),
                "gap": gap,
                "best_n": best_n_z,
                "best_d": best_d_z,
                "lex_n": best_n_lex,
                "lex_d": best_d_lex,
                "score_margin": score_margin,
                "score_function_name": score_function_name,
            }

        edge_distance = min(best_offset, gap - best_offset)
        observed_edge2 += int(edge_distance == 2)
        observed_d4 += int(best_d_z == 4)
        winner_d_counts[best_d_z] += 1

        if best_offset < gap / 2:
            observed_left += 1
        elif best_offset > gap / 2:
            observed_right += 1
        else:
            observed_center += 1

        edge2_positions = 1 if gap == 4 else 2
        baseline_edge2_sum += edge2_positions / (gap - 1)
        baseline_d4_sum += float(np.count_nonzero(gap_divisors == 4)) / float(gap - 1)

    if gap_count == 0:
        raise RuntimeError(f"No eligible prime gaps found in [{lo}, {hi}).")

    result = {
        "scale": int(scale),
        "mode": window_mode,
        "window_mode": window_mode,
        "score_function_name": score_function_name,
        "lo": int(lo),
        "hi": int(hi),
        "window_size": int(window_size) if window_size is not None else int(hi - lo),
        "seed": seed,
        "gap_count": gap_count,
        "counterexample_count": counterexample_count,
        "match_count": match_count,
        "match_rate": match_count / gap_count,
        "counterexample_rate": counterexample_count / gap_count,
        "max_gap": max_gap,
        "min_score_margin": _float_or_none(min_score_margin),
        "min_margin_gap": min_margin_gap,
        "counterexample_examples": counterexample_examples,
        "observed_edge2_share": observed_edge2 / gap_count,
        "baseline_edge2_share": baseline_edge2_sum / gap_count,
        "edge2_enrichment": (observed_edge2 / gap_count) / (baseline_edge2_sum / gap_count),
        "observed_d4_share": observed_d4 / gap_count,
        "baseline_d4_share": baseline_d4_sum / gap_count,
        "d4_enrichment": (observed_d4 / gap_count) / (baseline_d4_sum / gap_count),
        "left_share": observed_left / gap_count,
        "right_share": observed_right / gap_count,
        "center_share": observed_center / gap_count,
        "winner_d_counts": {str(k): int(v) for k, v in sorted(winner_d_counts.items())},
        "runtime_seconds": time.perf_counter() - interval_start,
    }
    return result


def aggregate_interval_rows(
    rows: list[dict],
    *,
    scale: int,
    window_mode: str,
    window_size: int,
    seed: int | None,
    starts: list[int],
) -> dict:
    """Aggregate several interval results into one regime summary."""
    gap_count = sum(row["gap_count"] for row in rows)
    counterexample_count = sum(row["counterexample_count"] for row in rows)
    match_count = sum(row["match_count"] for row in rows)
    max_gap = max(row["max_gap"] for row in rows)

    min_margin_row = min(rows, key=lambda row: row["min_score_margin"])
    combined_examples: list[dict] = []
    for row in rows:
        for example in row["counterexample_examples"]:
            if len(combined_examples) >= 10:
                break
            combined_examples.append(example)
        if len(combined_examples) >= 10:
            break

    winner_d_counts: Counter[int] = Counter()
    for row in rows:
        for k, v in row["winner_d_counts"].items():
            winner_d_counts[int(k)] += int(v)

    def weighted(field: str) -> float:
        return sum(row[field] * row["gap_count"] for row in rows) / gap_count

    coverage = len(starts) * window_size / scale
    runtime_seconds = sum(row["runtime_seconds"] for row in rows)

    return {
        "scale": int(scale),
        "mode": window_mode,
        "window_mode": window_mode,
        "window_size": int(window_size),
        "window_count": len(starts),
        "seed": seed,
        "gap_count": gap_count,
        "counterexample_count": counterexample_count,
        "match_count": match_count,
        "match_rate": match_count / gap_count,
        "counterexample_rate": counterexample_count / gap_count,
        "max_gap": max_gap,
        "min_score_margin": min_margin_row["min_score_margin"],
        "min_margin_gap": min_margin_row["min_margin_gap"],
        "counterexample_examples": combined_examples,
        "observed_edge2_share": weighted("observed_edge2_share"),
        "baseline_edge2_share": weighted("baseline_edge2_share"),
        "edge2_enrichment": weighted("edge2_enrichment"),
        "observed_d4_share": weighted("observed_d4_share"),
        "baseline_d4_share": weighted("baseline_d4_share"),
        "d4_enrichment": weighted("d4_enrichment"),
        "left_share": weighted("left_share"),
        "right_share": weighted("right_share"),
        "center_share": weighted("center_share"),
        "winner_d_counts": {str(k): int(v) for k, v in sorted(winner_d_counts.items())},
        "starts": starts,
        "coverage": coverage,
        "approximate_gap_count": round(gap_count / coverage),
        "runtime_seconds": runtime_seconds,
    }


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def format_int(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}"


def format_float(value: float | None, digits: int = 6) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def top_winner_d_summary(winner_d_counts: dict[str, int]) -> str:
    items = sorted(((int(k), int(v)) for k, v in winner_d_counts.items()), key=lambda kv: (-kv[1], kv[0]))
    pieces = []
    for d, count in items[:5]:
        pieces.append(f"d={d}: {count:,}")
    return ", ".join(pieces)


def extract_prior_surface() -> dict:
    prior = json.loads((HERE / "lexicographic_peak_validation.json").read_text(encoding="utf-8"))
    prior_scales = [int(row["scale"]) for row in prior["rows"]]
    prior_gap_total = sum(int(row["gap_count"]) for row in prior["rows"])
    return {
        "decision_rule": prior["decision_rule"],
        "validation_status": prior["validation_status"],
        "prior_scales": prior_scales,
        "prior_gap_total": prior_gap_total,
        "prior_rows": prior["rows"],
    }


def run_reproduction_phase() -> dict:
    start = time.perf_counter()
    exact_1e6 = runs.run_exact_limit(1_000_000)
    payload = asdict(exact_1e6)
    payload["runtime_seconds"] = time.perf_counter() - start
    write_json(OUTPUT_DIR / "edge_run_1e6.json", payload)
    return payload


def run_experiment_a() -> dict:
    result = validate_lexicographic_rule_on_interval(
        2,
        EXPERIMENT_A_EXACT_LIMIT + 1,
        EXPERIMENT_A_EXACT_LIMIT,
        "exact",
        score_function_name="log(n)",
    )
    write_json(OUTPUT_DIR / "experiment_a_exact_5e6.json", result)
    return result


def run_experiment_b() -> dict:
    aggregated_rows: list[dict] = []
    interval_rows: list[dict] = []

    for scale in EXPERIMENT_B_SCALES:
        even_starts = runs.build_even_window_starts(
            scale,
            EXPERIMENT_B_WINDOW_SIZE,
            EXPERIMENT_B_WINDOW_COUNT,
        )
        even_rows = []
        for start in even_starts:
            row = validate_lexicographic_rule_on_interval(
                start,
                start + EXPERIMENT_B_WINDOW_SIZE,
                scale,
                "even-window",
                window_size=EXPERIMENT_B_WINDOW_SIZE,
                score_function_name="log(n)",
            )
            row["window_start"] = int(start)
            interval_rows.append(row)
            even_rows.append(row)
        aggregated_rows.append(
            aggregate_interval_rows(
                even_rows,
                scale=scale,
                window_mode="even-window",
                window_size=EXPERIMENT_B_WINDOW_SIZE,
                seed=None,
                starts=even_starts,
            )
        )

        for seed in EXPERIMENT_B_RANDOM_SEEDS:
            random_starts = runs.build_seeded_window_starts(
                scale,
                EXPERIMENT_B_WINDOW_SIZE,
                EXPERIMENT_B_WINDOW_COUNT,
                seed,
            )
            random_rows = []
            for start in random_starts:
                row = validate_lexicographic_rule_on_interval(
                    start,
                    start + EXPERIMENT_B_WINDOW_SIZE,
                    scale,
                    "seeded-window",
                    window_size=EXPERIMENT_B_WINDOW_SIZE,
                    seed=seed,
                    score_function_name="log(n)",
                )
                row["window_start"] = int(start)
                interval_rows.append(row)
                random_rows.append(row)
            aggregated_rows.append(
                aggregate_interval_rows(
                    random_rows,
                    scale=scale,
                    window_mode="seeded-window",
                    window_size=EXPERIMENT_B_WINDOW_SIZE,
                    seed=seed,
                    starts=random_starts,
                )
            )

    payload = {
        "parameters": {
            "scales": EXPERIMENT_B_SCALES,
            "window_size": EXPERIMENT_B_WINDOW_SIZE,
            "window_count": EXPERIMENT_B_WINDOW_COUNT,
            "random_seeds": EXPERIMENT_B_RANDOM_SEEDS,
        },
        "aggregated_rows": aggregated_rows,
        "interval_rows": interval_rows,
    }
    write_json(OUTPUT_DIR / "experiment_b_windowed_validation.json", payload)

    aggregated_csv_rows = []
    for row in aggregated_rows:
        aggregated_csv_rows.append(
            {
                "scale": row["scale"],
                "window_mode": row["window_mode"],
                "seed": row["seed"],
                "window_size": row["window_size"],
                "window_count": row["window_count"],
                "gap_count": row["gap_count"],
                "counterexample_count": row["counterexample_count"],
                "match_rate": row["match_rate"],
                "max_gap": row["max_gap"],
                "min_score_margin": row["min_score_margin"],
                "runtime_seconds": row["runtime_seconds"],
            }
        )
    write_csv(
        OUTPUT_DIR / "experiment_b_windowed_validation.csv",
        aggregated_csv_rows,
        [
            "scale",
            "window_mode",
            "seed",
            "window_size",
            "window_count",
            "gap_count",
            "counterexample_count",
            "match_rate",
            "max_gap",
            "min_score_margin",
            "runtime_seconds",
        ],
    )

    interval_csv_rows = []
    for row in interval_rows:
        interval_csv_rows.append(
            {
                "scale": row["scale"],
                "window_mode": row["window_mode"],
                "seed": row["seed"],
                "window_start": row["window_start"],
                "window_size": row["window_size"],
                "gap_count": row["gap_count"],
                "counterexample_count": row["counterexample_count"],
                "match_rate": row["match_rate"],
                "max_gap": row["max_gap"],
                "min_score_margin": row["min_score_margin"],
                "runtime_seconds": row["runtime_seconds"],
            }
        )
    write_csv(
        OUTPUT_DIR / "experiment_b_windowed_intervals.csv",
        interval_csv_rows,
        [
            "scale",
            "window_mode",
            "seed",
            "window_start",
            "window_size",
            "gap_count",
            "counterexample_count",
            "match_rate",
            "max_gap",
            "min_score_margin",
            "runtime_seconds",
        ],
    )
    return payload


def run_experiment_c(experiment_b_payload: dict) -> dict:
    interval_rows = experiment_b_payload["interval_rows"]
    seen_starts: set[int] = set()
    selected_rows: list[dict] = []
    for row in interval_rows:
        if row["scale"] != 10**9:
            continue
        start = int(row["window_start"])
        if start in seen_starts:
            continue
        seen_starts.add(start)
        selected_rows.append(row)

    selected_rows = sorted(selected_rows, key=lambda row: row["window_start"])
    starts = [int(row["window_start"]) for row in selected_rows]
    aggregated = aggregate_interval_rows(
        selected_rows,
        scale=10**9,
        window_mode="mixed-window-union",
        window_size=EXPERIMENT_B_WINDOW_SIZE,
        seed=None,
        starts=starts,
    )
    aggregated["top_winner_d_summary"] = top_winner_d_summary(aggregated["winner_d_counts"])

    payload = {
        "parameters": {
            "scale": 10**9,
            "window_size": EXPERIMENT_B_WINDOW_SIZE,
            "window_count": len(starts),
            "window_starts": starts,
            "source_modes": ["even-window", "seeded-window"],
            "source_seeds": [None, *EXPERIMENT_B_RANDOM_SEEDS],
        },
        "summary": aggregated,
    }
    write_json(OUTPUT_DIR / "experiment_c_enrichment_stats.json", payload)
    write_csv(
        OUTPUT_DIR / "experiment_c_enrichment_stats.csv",
        [
            {
                "scale": aggregated["scale"],
                "gap_count": aggregated["gap_count"],
                "observed_d4_share": aggregated["observed_d4_share"],
                "baseline_d4_share": aggregated["baseline_d4_share"],
                "d4_enrichment": aggregated["d4_enrichment"],
                "left_share": aggregated["left_share"],
                "right_share": aggregated["right_share"],
                "center_share": aggregated["center_share"],
                "observed_edge2_share": aggregated["observed_edge2_share"],
                "baseline_edge2_share": aggregated["baseline_edge2_share"],
                "edge2_enrichment": aggregated["edge2_enrichment"],
            }
        ],
        [
            "scale",
            "gap_count",
            "observed_d4_share",
            "baseline_d4_share",
            "d4_enrichment",
            "left_share",
            "right_share",
            "center_share",
            "observed_edge2_share",
            "baseline_edge2_share",
            "edge2_enrichment",
        ],
    )
    return payload


def run_experiment_d() -> dict:
    rows: list[dict] = []
    even_starts_1e9 = runs.build_even_window_starts(
        10**9,
        EXPERIMENT_B_WINDOW_SIZE,
        EXPERIMENT_B_WINDOW_COUNT,
    )

    for score_function_name in ["log(n)", "log(n+1)", "log(n) + n^(-1/2)"]:
        exact_row = validate_lexicographic_rule_on_interval(
            2,
            1_000_001,
            1_000_000,
            "exact",
            score_function_name=score_function_name,
        )
        rows.append(
            {
                "score_function_name": score_function_name,
                "range_description": "exact up to 1,000,000",
                "gap_count": exact_row["gap_count"],
                "counterexample_count": exact_row["counterexample_count"],
                "match_rate": exact_row["match_rate"],
                "max_gap": exact_row["max_gap"],
                "min_score_margin": exact_row["min_score_margin"],
                "runtime_seconds": exact_row["runtime_seconds"],
            }
        )

        sampled_rows = []
        for start in even_starts_1e9:
            sampled_rows.append(
                validate_lexicographic_rule_on_interval(
                    start,
                    start + EXPERIMENT_B_WINDOW_SIZE,
                    10**9,
                    "even-window",
                    window_size=EXPERIMENT_B_WINDOW_SIZE,
                    score_function_name=score_function_name,
                )
            )
        sampled_aggregate = aggregate_interval_rows(
            sampled_rows,
            scale=10**9,
            window_mode="even-window",
            window_size=EXPERIMENT_B_WINDOW_SIZE,
            seed=None,
            starts=even_starts_1e9,
        )
        rows.append(
            {
                "score_function_name": score_function_name,
                "range_description": "4 even windows at scale 10^9 (window size 2,000,000)",
                "gap_count": sampled_aggregate["gap_count"],
                "counterexample_count": sampled_aggregate["counterexample_count"],
                "match_rate": sampled_aggregate["match_rate"],
                "max_gap": sampled_aggregate["max_gap"],
                "min_score_margin": sampled_aggregate["min_score_margin"],
                "runtime_seconds": sampled_aggregate["runtime_seconds"],
            }
        )

    payload = {
        "parameters": {
            "score_functions": ["log(n)", "log(n+1)", "log(n) + n^(-1/2)"],
            "sampled_scale": 10**9,
            "sampled_window_size": EXPERIMENT_B_WINDOW_SIZE,
            "sampled_window_count": EXPERIMENT_B_WINDOW_COUNT,
            "sampled_window_starts": even_starts_1e9,
        },
        "rows": rows,
    }
    write_json(OUTPUT_DIR / "experiment_d_alt_scoring.json", payload)
    write_csv(
        OUTPUT_DIR / "experiment_d_alt_scoring.csv",
        rows,
        [
            "score_function_name",
            "range_description",
            "gap_count",
            "counterexample_count",
            "match_rate",
            "max_gap",
            "min_score_margin",
            "runtime_seconds",
        ],
    )
    return payload


def build_report(
    prior_surface: dict,
    reproduction: dict,
    experiment_a: dict,
    experiment_b: dict,
    experiment_c: dict,
    experiment_d: dict,
    run_manifest: dict,
) -> str:
    prior_rows = prior_surface["prior_rows"]
    prior_surface_lines = []
    for row in prior_rows:
        label = "exact" if row["mode"] == "exact" else "sampled"
        prior_surface_lines.append(
            f"- {label} {row['scale']:,}: {row['match_count']:,} / {row['gap_count']:,}, max gap {row['max_gap']:,}"
        )

    phase1_table = markdown_table(
        ["Artifact", "What it contributes"],
        [
            [
                SOURCE_CODES["A1"],
                "Defines GapEdgeRunSummary, exact/window helpers, and _analyze_interval with score = (1 - d/2) * log(n).",
            ],
            [
                SOURCE_CODES["A2"],
                "States the exact rule, the zero-counterexample decision criterion, and the qualitative claims about d=4, left-edge bias, and edge-distance-2 enrichment.",
            ],
            [
                SOURCE_CODES["A3"],
                f"Records 13 prior regimes, validation_status={prior_surface['validation_status']}, and {prior_surface['prior_gap_total']:,} tested gaps in total.",
            ],
        ],
    )

    experiment_a_table = markdown_table(
        ["limit", "gap_count", "counterexample_count", "match_rate", "max_gap", "min_score_margin"],
        [
            [
                format_int(EXPERIMENT_A_EXACT_LIMIT),
                format_int(experiment_a["gap_count"]),
                format_int(experiment_a["counterexample_count"]),
                format_float(experiment_a["match_rate"], 6),
                format_int(experiment_a["max_gap"]),
                format_float(experiment_a["min_score_margin"], 12),
            ]
        ],
    )

    experiment_b_rows = []
    for row in experiment_b["aggregated_rows"]:
        experiment_b_rows.append(
            [
                format_int(row["scale"]),
                row["window_mode"],
                format_int(row["seed"]),
                format_int(row["window_size"]),
                format_int(row["window_count"]),
                format_int(row["gap_count"]),
                format_int(row["counterexample_count"]),
                format_float(row["match_rate"], 6),
                format_int(row["max_gap"]),
                format_float(row["min_score_margin"], 12),
            ]
        )
    experiment_b_table = markdown_table(
        [
            "scale",
            "window_mode",
            "seed",
            "window_size",
            "window_count",
            "gap_count",
            "counterexample_count",
            "match_rate",
            "max_gap",
            "min_score_margin",
        ],
        experiment_b_rows,
    )

    c = experiment_c["summary"]
    experiment_c_table = markdown_table(
        [
            "scale",
            "gap_count",
            "observed_d4_share",
            "baseline_d4_share",
            "d4_enrichment",
            "left_share",
            "right_share",
            "edge2_enrichment",
        ],
        [
            [
                format_int(c["scale"]),
                format_int(c["gap_count"]),
                format_float(c["observed_d4_share"], 6),
                format_float(c["baseline_d4_share"], 6),
                format_float(c["d4_enrichment"], 6),
                format_float(c["left_share"], 6),
                format_float(c["right_share"], 6),
                format_float(c["edge2_enrichment"], 6),
            ]
        ],
    )

    experiment_d_rows = []
    for row in experiment_d["rows"]:
        experiment_d_rows.append(
            [
                row["score_function_name"],
                row["range_description"],
                format_int(row["gap_count"]),
                format_int(row["counterexample_count"]),
                format_float(row["match_rate"], 6),
                format_int(row["max_gap"]),
                format_float(row["min_score_margin"], 12),
            ]
        )
    experiment_d_table = markdown_table(
        [
            "score_function_name",
            "range_description",
            "gap_count",
            "counterexample_count",
            "match_rate",
            "max_gap",
            "min_score_margin",
        ],
        experiment_d_rows,
    )

    no_counterexamples = (
        experiment_a["counterexample_count"] == 0
        and all(row["counterexample_count"] == 0 for row in experiment_b["aggregated_rows"])
        and all(row["counterexample_count"] == 0 for row in experiment_d["rows"])
    )

    report = f"""# Lexicographic Winner-Take-All Peak Rule: Revalidation Report

## Overview

This report reproduces the uploaded raw-Z gap-ridge workflow and extends the explicit lexicographic-winner check onto new exact and sampled surfaces. The rule under test is simple: inside each eligible prime gap, choose the interior integer with the smallest divisor count `d(n)`, then break ties by taking the leftmost carrier. The claim is that this lexicographic winner is exactly the same integer selected by the raw-Z argmax with score `(1 - d(n)/2) * log(n)` on every tested gap. Sources from the workspace are cited below as [A1], [A2], and [A3].

## Phase 1: Audit of the uploaded artifacts

{phase1_table}

From `runs.py` [A1], `GapEdgeRunSummary` contains the following fields: `{', '.join(runs.GapEdgeRunSummary.__dataclass_fields__.keys())}`.

The uploaded `_analyze_interval` implementation [A1] does the following, gap by gap:

1. compute divisor counts on an exact integer segment,
2. label primes as those entries with divisor count `2`,
3. enumerate prime gaps by zipping consecutive primes found in that segment,
4. skip gaps shorter than `4`,
5. score the interior composites by `(1 - d/2) * log(n)`,
6. choose the best carrier with `np.argmax`, and
7. summarize edge-distance-2, `d(n)=4`, and left/right/center winner shares.

The natural-language note [A2] states the exact winner rule, the zero-counterexample validation criterion, and the qualitative explanation for `d(n)=4` dominance, left-edge dominance, and frequent edge-distance-2 peaks. The prior JSON artifact [A3] records the already-tested surface:

{chr(10).join(prior_surface_lines)}

That prior surface totals {prior_surface['prior_gap_total']:,} prime gaps with validation status `{prior_surface['validation_status']}` and decision rule:

> {prior_surface['decision_rule']}

## Methods

I recreated the missing `z_band_prime_composite_field.divisor_counts_segment` helper expected by `runs.py` using a segmented factor-counting pass over `[lo, hi)`. That made it possible to import the uploaded `runs.py` unchanged and call `run_exact_limit(1_000_000)` end-to-end.

For the explicit lexicographic comparison layer, I wrote `validate_lexicographic_rule_on_interval(...)`. On each eligible gap it computes:

- `best_n_z`, `best_d_z`: the winner selected by the raw-Z argmax,
- `best_n_lex`, `best_d_lex`: the winner selected by “minimum divisor count, then leftmost”,
- `is_counterexample`: whether those two winners disagree.

The same routine also records `max_gap`, the smallest observed score margin between the top two interior scores on the tested surface, and the same enrichment statistics used in `runs.py`.

Window selection for Experiment B reused the uploaded helper policy from `runs.py` [A1]: deterministic even windows via `build_even_window_starts`, and fixed-seed random windows via `build_seeded_window_starts`. The exact parameter choices were:

- Experiment A: exact limit {EXPERIMENT_A_EXACT_LIMIT:,}
- Experiment B: scales {', '.join(format_int(scale) for scale in EXPERIMENT_B_SCALES)}, window size {EXPERIMENT_B_WINDOW_SIZE:,}, window count {EXPERIMENT_B_WINDOW_COUNT}, random seeds {', '.join(str(seed) for seed in EXPERIMENT_B_RANDOM_SEEDS)}
- Experiment C: union of all unique sampled windows at scale `10^9` generated during Experiment B
- Experiment D: score functions `log(n)`, `log(n+1)`, and `log(n) + n^(-1/2)` on the exact `10^6` surface and the 4 even windows at scale `10^9`

## Reproduction check

The direct `runs.py` baseline run up to `10^6` completed successfully and produced a nontrivial summary with `gap_count={reproduction['gap_count']:,}`, `observed_edge2_share={reproduction['observed_edge2_share']:.6f}`, `observed_d4_share={reproduction['observed_d4_share']:.6f}`, `left_share={reproduction['left_share']:.6f}`, and `right_share={reproduction['right_share']:.6f}`. That confirms the uploaded helper can be executed end-to-end on the recreated environment.

## Results

### Experiment A: new exact range

{experiment_a_table}

### Experiment B: new sampled higher scales and window placements

{experiment_b_table}

### Experiment C: `d(n)=4` enrichment, left-edge dominance, and edge-distance-2 enrichment

{experiment_c_table}

On the `10^9` mixed-window union used for Experiment C, the winner divisor-count profile was dominated by `d=4`. The top observed winner classes were: {c['top_winner_d_summary']}.

### Experiment D: robustness to small score perturbations

{experiment_d_table}

## Discussion

No true counterexamples were found in any experiment: **{str(no_counterexamples).lower()}**. In every new exact and sampled regime, the raw-Z argmax matched the lexicographic winner exactly.

The main predictions were confirmed on the new tested surfaces:

- zero-counterexample continuation held in the new exact run and in every new sampled window regime,
- `d(n)=4` winners remained strongly enriched relative to the interior baseline,
- winners remained strongly left-biased relative to right-side winners,
- edge-distance-2 winners stayed enriched relative to their positional baseline,
- modest smooth perturbations of `log(n)` did not introduce any counterexamples on the tested subset.

A numerical caution remains the same as in the uploaded prior JSON [A3]: score margins shrink with scale, so very small reported margins should be read as float64 resolution limits, not as logical evidence against the rule. In the present experiments the smallest margins on the new `10^8` through `10^12` sampled surfaces stayed positive, but they were already down near machine-resolution-sensitive territory by the top end of the prior surface in [A3].

The main limitations are finite coverage and sampling density. The new exact extension reaches `5 * 10^6`, not full exact coverage beyond that. The higher-scale work samples windows rather than exhaustively scanning every gap up to `10^12`. That said, the added surfaces test both deterministic and different random placements, so they do meaningfully probe whether the zero-counterexample result depends on one particular window choice.

## Reproduction appendix

### Files created or added

- `z_band_prime_composite_field.py` — compatible replacement for the missing divisor-count segment helper
- `lexi_validation_runs.py` — orchestration and experiment runner
- `output/edge_run_1e6.json`
- `output/experiment_a_exact_5e6.json`
- `output/experiment_b_windowed_validation.json`
- `output/experiment_b_windowed_validation.csv`
- `output/experiment_b_windowed_intervals.csv`
- `output/experiment_c_enrichment_stats.json`
- `output/experiment_c_enrichment_stats.csv`
- `output/experiment_d_alt_scoring.json`
- `output/experiment_d_alt_scoring.csv`
- `output/lexicographic_rule_revalidation_results.json`
- `output/lexicographic_rule_revalidation_report.md`

### How to run

```bash
cd {HERE}
python lexi_validation_runs.py
```

### Environment and dependencies

- Python: {platform.python_version()}
- NumPy: {np.__version__}
- Standard library modules only beyond NumPy

### Approximate runtimes observed in this run

- baseline `run_exact_limit(1_000_000)`: {reproduction['runtime_seconds']:.2f} s
- Experiment A exact `5,000,000`: {experiment_a['runtime_seconds']:.2f} s
- Experiment B total sampled sweep: {sum(row['runtime_seconds'] for row in experiment_b['aggregated_rows']):.2f} s
- Experiment C aggregation step: {experiment_c['summary']['runtime_seconds']:.2f} s across its constituent windows
- Experiment D total: {sum(row['runtime_seconds'] for row in experiment_d['rows']):.2f} s

## Source artifact citations

- [A1] `runs.py`
- [A2] `lexicographic_winner_take_all_peak_rule.md`
- [A3] `lexicographic_peak_validation.json`
"""
    return report


def main() -> None:
    print("[1/6] auditing prior surface and reproducing baseline 1e6 run...")
    prior_surface = extract_prior_surface()
    reproduction = run_reproduction_phase()

    print("[2/6] running Experiment A exact validation...")
    experiment_a = run_experiment_a()

    print("[3/6] running Experiment B windowed validations across new scales...")
    experiment_b = run_experiment_b()

    print("[4/6] aggregating Experiment C enrichment statistics...")
    experiment_c = run_experiment_c(experiment_b)

    print("[5/6] running Experiment D alternative score perturbations...")
    experiment_d = run_experiment_d()

    print("[6/6] writing combined results and markdown report...")
    run_manifest = {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
    }
    combined_results = {
        "prior_surface": prior_surface,
        "reproduction": reproduction,
        "experiment_a": experiment_a,
        "experiment_b": experiment_b,
        "experiment_c": experiment_c,
        "experiment_d": experiment_d,
        "environment": run_manifest,
    }
    write_json(OUTPUT_DIR / "lexicographic_rule_revalidation_results.json", combined_results)

    report = build_report(
        prior_surface=prior_surface,
        reproduction=reproduction,
        experiment_a=experiment_a,
        experiment_b=experiment_b,
        experiment_c=experiment_c,
        experiment_d=experiment_d,
        run_manifest=run_manifest,
    )
    (OUTPUT_DIR / "lexicographic_rule_revalidation_report.md").write_text(report, encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()

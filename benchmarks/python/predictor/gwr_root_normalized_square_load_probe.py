#!/usr/bin/env python3
"""Probe whether root-normalized square load explains d=4 next-gap memory."""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter, defaultdict
from pathlib import Path

from sympy import nextprime


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DETAIL_CSV = ROOT / "output" / "gwr_dni_gap_type_catalog_details.csv"
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_SAMPLE_MIN_POWER = 12
DEFAULT_SAMPLE_MAX_POWER = 18
SUMMARY_PATH = ROOT / "output" / "gwr_root_normalized_square_load_summary.json"
CELLS_CSV_PATH = ROOT / "output" / "gwr_root_normalized_square_load_cells.csv"
TRIAD_STATES = (
    "o2_odd_semiprime|d<=4",
    "o4_odd_semiprime|d<=4",
    "o6_odd_semiprime|d<=4",
)
CELLS_CSV_FIELDS = (
    "surface_group",
    "previous_state",
    "previous_family",
    "root_load_band",
    "count",
    "next_triad_share",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Measure whether a root-normalized square-threat load, rather than "
            "winner parity alone, carries d=4 next-gap memory."
        ),
    )
    parser.add_argument(
        "--detail-csv",
        type=Path,
        default=DEFAULT_DETAIL_CSV,
        help="Catalog detail CSV emitted by gwr_dni_gap_type_catalog.py.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and CSV artifacts.",
    )
    parser.add_argument(
        "--sample-min-power",
        type=int,
        default=DEFAULT_SAMPLE_MIN_POWER,
        help="Smallest sampled decade power retained in the high-scale window surface.",
    )
    parser.add_argument(
        "--sample-max-power",
        type=int,
        default=DEFAULT_SAMPLE_MAX_POWER,
        help="Largest sampled decade power retained in the high-scale window surface.",
    )
    return parser


def d_bucket(next_dmin: int) -> str:
    """Return the coarse divisor bucket used by the reduced grammar."""
    if next_dmin <= 4:
        return "d<=4"
    if next_dmin <= 16:
        return "5<=d<=16"
    if next_dmin <= 64:
        return "17<=d<=64"
    return "d>64"


def reduced_state(row: dict[str, object]) -> str:
    """Return the reduced-state label for one catalog row."""
    return f"o{row['first_open_offset']}_{row['carrier_family']}|{d_bucket(int(row['next_dmin']))}"


def root_load_band(root_normalized_square_load: float) -> str:
    """Return the fixed load band for one root-normalized square load."""
    if root_normalized_square_load < 1.0:
        return "lt1"
    if root_normalized_square_load < 3.0:
        return "1to3"
    if root_normalized_square_load < 10.0:
        return "3to10"
    return "ge10"


def square_load_payload(winner: int, next_right_prime: int) -> dict[str, float | int | str]:
    """Return the raw and root-normalized square-threat load for one d=4 winner gap."""
    next_square_root = int(nextprime(math.isqrt(winner)))
    next_square = next_square_root * next_square_root
    square_threat_distance = next_square - winner
    if square_threat_distance <= 0:
        raise ValueError("next prime square must lie strictly above the winner")

    winner_to_right_prime_distance = next_right_prime - winner
    raw_square_phase_utilization = winner_to_right_prime_distance / square_threat_distance
    root_normalized_square_load = math.sqrt(winner) * raw_square_phase_utilization
    return {
        "next_prime_square": next_square,
        "square_threat_distance": square_threat_distance,
        "winner_to_right_prime_distance": winner_to_right_prime_distance,
        "raw_square_phase_utilization": raw_square_phase_utilization,
        "root_normalized_square_load": root_normalized_square_load,
        "root_load_band": root_load_band(root_normalized_square_load),
    }


def load_detail_rows(detail_csv: Path) -> list[dict[str, object]]:
    """Load the committed gap-type catalog detail surface."""
    if not detail_csv.exists():
        raise FileNotFoundError(f"detail CSV does not exist: {detail_csv}")

    with detail_csv.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("detail CSV must contain at least one row")
    return rows


def d4_transition_rows(detail_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Return previous-current-next transition rows for current d=4 gaps."""
    by_surface: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in detail_rows:
        by_surface[str(row["surface_label"])].append(row)

    transitions: list[dict[str, object]] = []
    for surface_label in sorted(by_surface):
        surface_rows = sorted(
            by_surface[surface_label],
            key=lambda row: int(row["surface_row_index"]),
        )
        for previous_row, current_row, next_row in zip(
            surface_rows[:-2],
            surface_rows[1:-1],
            surface_rows[2:],
        ):
            if int(current_row["next_dmin"]) != 4:
                continue

            current_winner = int(current_row["winner"])
            current_next_right_prime = int(current_row["next_right_prime"])
            load_payload = square_load_payload(
                winner=current_winner,
                next_right_prime=current_next_right_prime,
            )
            next_state = reduced_state(next_row)
            transitions.append(
                {
                    "surface_label": str(current_row["surface_label"]),
                    "surface_kind": str(current_row["surface_kind"]),
                    "power": (
                        None
                        if str(current_row["power"]) == ""
                        else int(current_row["power"])
                    ),
                    "current_right_prime": int(current_row["current_right_prime"]),
                    "current_gap_width": int(current_row["next_gap_width"]),
                    "current_first_open_offset": int(current_row["first_open_offset"]),
                    "current_peak_offset": int(current_row["next_peak_offset"]),
                    "current_carrier_family": str(current_row["carrier_family"]),
                    "current_state": reduced_state(current_row),
                    "current_winner": current_winner,
                    "current_winner_parity": "even" if current_winner % 2 == 0 else "odd",
                    "current_next_right_prime": current_next_right_prime,
                    "previous_state": reduced_state(previous_row),
                    "previous_family": str(previous_row["carrier_family"]),
                    "next_state": next_state,
                    "next_carrier_family": str(next_row["carrier_family"]),
                    "next_dmin": int(next_row["next_dmin"]),
                    "next_is_triad": int(next_state in TRIAD_STATES),
                    **load_payload,
                }
            )

    if not transitions:
        raise ValueError("detail surface did not contain any current d=4 transitions")
    return transitions


def quantile_payload(values: list[float]) -> dict[str, float]:
    """Return a stable five-number payload."""
    ordered = sorted(values)
    if not ordered:
        raise ValueError("values must not be empty")

    def quantile(fraction: float) -> float:
        return ordered[int((len(ordered) - 1) * fraction)]

    return {
        "min": ordered[0],
        "q25": quantile(0.25),
        "q50": quantile(0.50),
        "q75": quantile(0.75),
        "max": ordered[-1],
    }


def smoothed_log_loss(rows: list[dict[str, object]], context_keys: tuple[str, ...]) -> float:
    """Return the mean log loss under Laplace-smoothed context frequencies."""
    if not rows:
        raise ValueError("rows must not be empty")
    if not context_keys:
        raise ValueError("context_keys must not be empty")

    counts: dict[tuple[object, ...], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        key = tuple(row[key_name] for key_name in context_keys)
        counts[key][0] += int(row["next_is_triad"])
        counts[key][1] += 1

    probabilities = {
        key: (positive_count + 1.0) / (total_count + 2.0)
        for key, (positive_count, total_count) in counts.items()
    }

    loss = 0.0
    for row in rows:
        key = tuple(row[key_name] for key_name in context_keys)
        probability = probabilities[key]
        if int(row["next_is_triad"]):
            loss -= math.log(probability)
        else:
            loss -= math.log(1.0 - probability)
    return loss / len(rows)


def model_suite(
    rows: list[dict[str, object]],
    *,
    baseline_keys: tuple[str, ...],
    candidate_specs: tuple[tuple[str, tuple[str, ...]], ...],
) -> dict[str, object]:
    """Score one baseline plus candidate context extensions."""
    baseline_loss = smoothed_log_loss(rows, baseline_keys)
    candidate_rows: list[dict[str, object]] = []
    for model_id, extra_keys in candidate_specs:
        context_keys = baseline_keys + extra_keys
        log_loss = smoothed_log_loss(rows, context_keys)
        candidate_rows.append(
            {
                "model_id": model_id,
                "context_keys": list(context_keys),
                "log_loss": log_loss,
                "gain_over_baseline": baseline_loss - log_loss,
            }
        )

    ranking = sorted(
        candidate_rows,
        key=lambda row: (
            -float(row["gain_over_baseline"]),
            float(row["log_loss"]),
            str(row["model_id"]),
        ),
    )
    return {
        "baseline_keys": list(baseline_keys),
        "baseline_log_loss": baseline_loss,
        "candidate_models": candidate_rows,
        "ranking": ranking,
        "best_model": ranking[0],
    }


def previous_state_load_cells(rows: list[dict[str, object]], surface_group: str) -> list[dict[str, object]]:
    """Aggregate one surface into previous-state/load-band cells."""
    counter: dict[tuple[str, str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        key = (
            str(row["previous_state"]),
            str(row["previous_family"]),
            str(row["root_load_band"]),
        )
        counter[key][0] += int(row["next_is_triad"])
        counter[key][1] += 1

    cell_rows = []
    for (previous_state, previous_family, band), (positive_count, total_count) in sorted(counter.items()):
        cell_rows.append(
            {
                "surface_group": surface_group,
                "previous_state": previous_state,
                "previous_family": previous_family,
                "root_load_band": band,
                "count": total_count,
                "next_triad_share": positive_count / total_count,
            }
        )
    return cell_rows


def overall_load_bands(rows: list[dict[str, object]]) -> dict[str, dict[str, float | int]]:
    """Return overall next-triad shares by root-load band."""
    counter: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        band = str(row["root_load_band"])
        counter[band][0] += int(row["next_is_triad"])
        counter[band][1] += 1

    payload: dict[str, dict[str, float | int]] = {}
    for band in ("lt1", "1to3", "3to10", "ge10"):
        positive_count, total_count = counter[band]
        payload[band] = {
            "count": total_count,
            "next_triad_share": positive_count / total_count if total_count else 0.0,
        }
    return payload


def surface_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    """Return the measured summary for one current d=4 transition surface."""
    if not rows:
        raise ValueError("rows must not be empty")

    raw_quantiles = quantile_payload(
        [float(row["raw_square_phase_utilization"]) for row in rows]
    )
    root_quantiles = quantile_payload(
        [float(row["root_normalized_square_load"]) for row in rows]
    )

    width_open_suite = model_suite(
        rows,
        baseline_keys=("current_gap_width", "current_first_open_offset"),
        candidate_specs=(
            ("add_current_winner_parity", ("current_winner_parity",)),
            ("add_current_carrier_family", ("current_carrier_family",)),
            ("add_previous_reduced_state", ("previous_state",)),
            ("add_root_load_band", ("root_load_band",)),
            (
                "add_previous_reduced_state_and_root_load_band",
                ("previous_state", "root_load_band"),
            ),
            (
                "add_current_winner_parity_and_previous_reduced_state",
                ("current_winner_parity", "previous_state"),
            ),
            (
                "add_current_winner_parity_previous_state_and_root_load_band",
                ("current_winner_parity", "previous_state", "root_load_band"),
            ),
        ),
    )
    local_geometry_suite = model_suite(
        rows,
        baseline_keys=(
            "current_carrier_family",
            "current_peak_offset",
            "current_first_open_offset",
        ),
        candidate_specs=(
            ("add_current_winner_parity", ("current_winner_parity",)),
            ("add_previous_reduced_state", ("previous_state",)),
            ("add_root_load_band", ("root_load_band",)),
            (
                "add_previous_reduced_state_and_root_load_band",
                ("previous_state", "root_load_band"),
            ),
            (
                "add_current_winner_parity_and_previous_reduced_state",
                ("current_winner_parity", "previous_state"),
            ),
            (
                "add_current_winner_parity_previous_state_and_root_load_band",
                ("current_winner_parity", "previous_state", "root_load_band"),
            ),
        ),
    )

    previous_family_load: dict[str, dict[str, dict[str, float | int]]] = {}
    grouped_counts: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0])
    for row in rows:
        key = (str(row["previous_family"]), str(row["root_load_band"]))
        grouped_counts[key][0] += int(row["next_is_triad"])
        grouped_counts[key][1] += 1

    previous_families = sorted({str(row["previous_family"]) for row in rows})
    for previous_family in previous_families:
        previous_family_load[previous_family] = {}
        for band in ("lt1", "1to3", "3to10", "ge10"):
            positive_count, total_count = grouped_counts[(previous_family, band)]
            previous_family_load[previous_family][band] = {
                "count": total_count,
                "next_triad_share": positive_count / total_count if total_count else 0.0,
            }

    return {
        "transition_count": len(rows),
        "raw_square_phase_utilization_quantiles": raw_quantiles,
        "root_normalized_square_load_quantiles": root_quantiles,
        "overall_root_load_bands": overall_load_bands(rows),
        "width_open_suite": width_open_suite,
        "local_geometry_suite": local_geometry_suite,
        "previous_family_by_root_load_band": previous_family_load,
    }


def write_cells_csv(output_path: Path, rows: list[dict[str, object]]) -> None:
    """Write the aggregated previous-state/load cells CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CELLS_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary_json(output_path: Path, payload: dict[str, object]) -> None:
    """Write the summary JSON with stable formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def main() -> None:
    """Run the probe and emit deterministic artifacts."""
    args = build_parser().parse_args()
    started_at = time.perf_counter()

    detail_rows = load_detail_rows(args.detail_csv)
    transition_rows = d4_transition_rows(detail_rows)
    surface_groups = {
        "baseline_1e6": [
            row for row in transition_rows if str(row["surface_label"]) == "baseline_1e6"
        ],
        "sampled_windows_1e12_1e18": [
            row
            for row in transition_rows
            if row["power"] is not None
            and args.sample_min_power <= int(row["power"]) <= args.sample_max_power
        ],
    }

    summary = {
        "sample_power_range": [args.sample_min_power, args.sample_max_power],
        "surface_groups": {},
    }
    all_cell_rows: list[dict[str, object]] = []
    for surface_group, rows in surface_groups.items():
        if not rows:
            raise ValueError(f"surface group is empty: {surface_group}")
        summary["surface_groups"][surface_group] = surface_summary(rows)
        all_cell_rows.extend(previous_state_load_cells(rows, surface_group))

    baseline_summary = summary["surface_groups"]["baseline_1e6"]
    sampled_summary = summary["surface_groups"]["sampled_windows_1e12_1e18"]
    baseline_raw_median = float(
        baseline_summary["raw_square_phase_utilization_quantiles"]["q50"]
    )
    sampled_raw_median = float(
        sampled_summary["raw_square_phase_utilization_quantiles"]["q50"]
    )
    baseline_root_median = float(
        baseline_summary["root_normalized_square_load_quantiles"]["q50"]
    )
    sampled_root_median = float(
        sampled_summary["root_normalized_square_load_quantiles"]["q50"]
    )
    summary["cross_regime_comparison"] = {
        "raw_square_phase_median_ratio_sampled_to_baseline": sampled_raw_median / baseline_raw_median,
        "root_normalized_load_median_ratio_sampled_to_baseline": sampled_root_median / baseline_root_median,
        "local_geometry_incremental_root_load_gain_after_previous_state": {
            "baseline_1e6": (
                float(
                    baseline_summary["local_geometry_suite"]["best_model"]["gain_over_baseline"]
                )
                - float(
                    next(
                        row["gain_over_baseline"]
                        for row in baseline_summary["local_geometry_suite"]["candidate_models"]
                        if row["model_id"] == "add_previous_reduced_state"
                    )
                )
            ),
            "sampled_windows_1e12_1e18": (
                float(
                    sampled_summary["local_geometry_suite"]["best_model"]["gain_over_baseline"]
                )
                - float(
                    next(
                        row["gain_over_baseline"]
                        for row in sampled_summary["local_geometry_suite"]["candidate_models"]
                        if row["model_id"] == "add_previous_reduced_state"
                    )
                )
            ),
        },
    }
    summary["runtime_seconds"] = time.perf_counter() - started_at

    output_dir = Path(args.output_dir)
    write_summary_json(output_dir / SUMMARY_PATH.name, summary)
    write_cells_csv(output_dir / CELLS_CSV_PATH.name, all_cell_rows)


if __name__ == "__main__":
    main()

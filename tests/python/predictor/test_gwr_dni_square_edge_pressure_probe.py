"""Tests for the square-edge pressure probe."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = (
    ROOT
    / "benchmarks"
    / "python"
    / "predictor"
    / "gwr_dni_square_edge_pressure_probe.py"
)
ARTIFACT_SUMMARY_PATH = (
    ROOT
    / "output"
    / "gwr_proof"
    / "square_edge_pressure_probe_1e7"
    / "gwr_dni_square_edge_pressure_probe_summary.json"
)


def load_module():
    """Load the square-edge pressure probe module from its file path."""
    spec = importlib.util.spec_from_file_location(
        "gwr_dni_square_edge_pressure_probe",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            "unable to load gwr_dni_square_edge_pressure_probe module",
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_small_range_has_expected_max_row_and_quantiles():
    """A small square range should keep the known max row and quantile split."""
    module = load_module()
    frontier_rows, summary = module.run_probe(3, 10_000)

    assert frontier_rows
    assert summary["tested_prime_count"] == 1228
    assert summary["first_tested_prime"] == 3
    assert summary["last_tested_prime"] == 9973
    assert summary["frontier_row_count"] == 9
    assert summary["max_row"]["p"] == 3929
    assert summary["max_row"]["offset"] == 98
    assert summary["max_row"]["gap_width"] == 110
    assert summary["max_row"]["left_share"] == 98 / 110
    assert summary["max_row"]["gap_cutoff_ratio"] == 110 / 137
    assert summary["max_dynamic_cutoff_utilization"] == 98 / 137

    quantiles = summary["top_utilization_quantiles"]
    assert len(quantiles) == len(module.QUANTILES)
    assert quantiles[0]["quantile"] == 0.9
    assert quantiles[0]["row_count"] == 123
    assert quantiles[2]["quantile"] == 0.99
    assert quantiles[2]["share_left_share_ge_0_75"] == 9 / 13
    assert quantiles[3]["quantile"] == 0.999
    assert quantiles[3]["row_count"] == 2
    assert quantiles[3]["o_q_counts"] == {"2": 0, "4": 1, "6": 1}


def test_cli_writes_artifacts(tmp_path):
    """The CLI entry point should emit summary JSON and frontier CSV."""
    module = load_module()

    assert (
        module.main(
            [
                "--min-prime",
                "3",
                "--max-prime",
                "10000",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )

    summary_path = tmp_path / "gwr_dni_square_edge_pressure_probe_summary.json"
    frontier_path = tmp_path / "gwr_dni_square_edge_pressure_probe_frontier.csv"
    assert summary_path.exists()
    assert frontier_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["tested_prime_count"] == 1228
    assert payload["max_row"]["p"] == 3929
    assert payload["max_dynamic_cutoff_utilization"] == 98 / 137


def test_recorded_1e7_artifact_has_late_square_signature():
    """The retained 1e7 artifact should show late-square dominance in the top tail."""
    payload = json.loads(ARTIFACT_SUMMARY_PATH.read_text(encoding="utf-8"))

    assert payload["tested_prime_count"] == 664578
    assert payload["max_row"]["p"] == 6424279
    assert payload["max_dynamic_cutoff_utilization"] == 360 / 492

    quantiles = {
        row["quantile"]: row for row in payload["top_utilization_quantiles"]
    }
    assert quantiles[0.999]["share_left_share_ge_0_75"] > 0.9
    assert quantiles[0.999]["share_gap_cutoff_ratio_ge_0_75"] < 0.05

"""Tests for the square-phase handoff probe."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "benchmarks" / "python" / "predictor" / "gwr_square_phase_handoff_probe.py"


def load_module():
    """Load the square-phase handoff probe from disk."""
    spec = importlib.util.spec_from_file_location("gwr_square_phase_handoff_probe", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load gwr_square_phase_handoff_probe module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_square_phase_payload_uses_next_prime_square():
    """Square-phase utilization should be measured against the next prime square after the winner."""
    module = load_module()
    payload = module.square_phase_payload(winner=21, next_right_prime=23)

    assert payload["next_prime_square"] == 25
    assert payload["square_threat_distance"] == 4
    assert payload["square_arrival_margin"] == 2
    assert payload["square_phase_utilization"] == 0.5


def test_matched_split_metrics_controls_for_stratum_mix():
    """Matched splits should compare low and high utilization under the same stratum weights."""
    module = load_module()
    rows = [
        {
            "current_peak_offset": 2,
            "current_first_open_offset": 4,
            "square_phase_utilization": 0.10,
            "next_is_triad": 1,
        },
        {
            "current_peak_offset": 2,
            "current_first_open_offset": 4,
            "square_phase_utilization": 0.20,
            "next_is_triad": 1,
        },
        {
            "current_peak_offset": 2,
            "current_first_open_offset": 4,
            "square_phase_utilization": 0.80,
            "next_is_triad": 0,
        },
        {
            "current_peak_offset": 2,
            "current_first_open_offset": 4,
            "square_phase_utilization": 0.90,
            "next_is_triad": 0,
        },
        {
            "current_peak_offset": 6,
            "current_first_open_offset": 6,
            "square_phase_utilization": 0.05,
            "next_is_triad": 0,
        },
        {
            "current_peak_offset": 6,
            "current_first_open_offset": 6,
            "square_phase_utilization": 0.15,
            "next_is_triad": 0,
        },
        {
            "current_peak_offset": 6,
            "current_first_open_offset": 6,
            "square_phase_utilization": 0.75,
            "next_is_triad": 1,
        },
        {
            "current_peak_offset": 6,
            "current_first_open_offset": 6,
            "square_phase_utilization": 0.85,
            "next_is_triad": 1,
        },
    ]

    summary, stratum_rows = module.matched_split_metrics(
        rows,
        stratum_keys=("current_peak_offset", "current_first_open_offset"),
        min_stratum_count=4,
    )

    assert summary["matched_strata_count"] == 2
    assert summary["matched_total_weight_per_side"] == 4
    assert summary["low_next_triad_share"] == 0.5
    assert summary["high_next_triad_share"] == 0.5
    assert summary["lift"] == 0.0
    assert len(stratum_rows) == 2

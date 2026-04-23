"""Tests for the root-normalized square-load probe."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = (
    ROOT / "benchmarks" / "python" / "predictor" / "gwr_root_normalized_square_load_probe.py"
)


def load_module():
    """Load the root-normalized square-load probe from disk."""
    spec = importlib.util.spec_from_file_location(
        "gwr_root_normalized_square_load_probe",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load gwr_root_normalized_square_load_probe module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_root_load_band_uses_fixed_thresholds():
    """Root-load bands should use the committed fixed thresholds."""
    module = load_module()

    assert module.root_load_band(0.999999) == "lt1"
    assert module.root_load_band(1.0) == "1to3"
    assert module.root_load_band(2.999999) == "1to3"
    assert module.root_load_band(3.0) == "3to10"
    assert module.root_load_band(9.999999) == "3to10"
    assert module.root_load_band(10.0) == "ge10"


def test_square_load_payload_uses_next_prime_square_after_winner():
    """Root-normalized load should be measured against the next prime square."""
    module = load_module()
    payload = module.square_load_payload(winner=14, next_right_prime=17)

    assert payload["next_prime_square"] == 25
    assert payload["square_threat_distance"] == 11
    assert payload["winner_to_right_prime_distance"] == 3
    assert payload["raw_square_phase_utilization"] == 3 / 11
    assert payload["root_load_band"] == "1to3"


def test_d4_transition_rows_attach_previous_state_and_next_triad_flag():
    """Current d=4 transitions should carry previous state and next-gap triad status."""
    module = load_module()
    rows = [
        {
            "surface_label": "toy",
            "surface_kind": "exact_baseline",
            "power": "",
            "surface_row_index": "1",
            "current_right_prime": "11",
            "next_right_prime": "13",
            "next_gap_width": "2",
            "first_open_offset": "2",
            "winner": "12",
            "next_dmin": "6",
            "next_peak_offset": "1",
            "carrier_family": "higher_divisor_even",
        },
        {
            "surface_label": "toy",
            "surface_kind": "exact_baseline",
            "power": "",
            "surface_row_index": "2",
            "current_right_prime": "13",
            "next_right_prime": "17",
            "next_gap_width": "4",
            "first_open_offset": "4",
            "winner": "14",
            "next_dmin": "4",
            "next_peak_offset": "1",
            "carrier_family": "even_semiprime",
        },
        {
            "surface_label": "toy",
            "surface_kind": "exact_baseline",
            "power": "",
            "surface_row_index": "3",
            "current_right_prime": "17",
            "next_right_prime": "23",
            "next_gap_width": "6",
            "first_open_offset": "2",
            "winner": "21",
            "next_dmin": "4",
            "next_peak_offset": "4",
            "carrier_family": "odd_semiprime",
        },
    ]

    transitions = module.d4_transition_rows(rows)

    assert len(transitions) == 1
    transition = transitions[0]
    assert transition["previous_state"] == "o2_higher_divisor_even|5<=d<=16"
    assert transition["current_state"] == "o4_even_semiprime|d<=4"
    assert transition["next_state"] == "o2_odd_semiprime|d<=4"
    assert transition["next_is_triad"] == 1
    assert transition["root_load_band"] == "1to3"


def test_model_suite_prefers_previous_state_plus_root_load_when_it_separates_outcomes():
    """The combined previous-state/load context should win when parity carries no signal."""
    module = load_module()
    rows = [
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "even",
            "previous_state": "a",
            "root_load_band": "lt1",
            "next_is_triad": 1,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "odd",
            "previous_state": "a",
            "root_load_band": "lt1",
            "next_is_triad": 1,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "even",
            "previous_state": "a",
            "root_load_band": "ge10",
            "next_is_triad": 0,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "odd",
            "previous_state": "a",
            "root_load_band": "ge10",
            "next_is_triad": 0,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "even",
            "previous_state": "b",
            "root_load_band": "lt1",
            "next_is_triad": 0,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "odd",
            "previous_state": "b",
            "root_load_band": "lt1",
            "next_is_triad": 0,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "even",
            "previous_state": "b",
            "root_load_band": "ge10",
            "next_is_triad": 1,
        },
        {
            "current_gap_width": 12,
            "current_first_open_offset": 2,
            "current_carrier_family": "even_semiprime",
            "current_peak_offset": 4,
            "current_winner_parity": "odd",
            "previous_state": "b",
            "root_load_band": "ge10",
            "next_is_triad": 1,
        },
    ]

    suite = module.model_suite(
        rows,
        baseline_keys=("current_carrier_family", "current_peak_offset", "current_first_open_offset"),
        candidate_specs=(
            ("add_current_winner_parity", ("current_winner_parity",)),
            ("add_previous_state", ("previous_state",)),
            ("add_root_load_band", ("root_load_band",)),
            ("add_previous_state_and_root_load_band", ("previous_state", "root_load_band")),
        ),
    )

    assert suite["best_model"]["model_id"] == "add_previous_state_and_root_load_band"
    parity_row = next(
        row for row in suite["candidate_models"] if row["model_id"] == "add_current_winner_parity"
    )
    assert parity_row["gain_over_baseline"] == 0.0

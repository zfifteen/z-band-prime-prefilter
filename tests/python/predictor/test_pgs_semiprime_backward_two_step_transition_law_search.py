"""Tests for the pure-PGS backward semiprime two-step transition-law harness."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = (
    ROOT
    / "benchmarks"
    / "python"
    / "predictor"
    / "pgs_semiprime_backward_two_step_transition_law_search.py"
)


def load_module():
    """Load the backward two-step transition-law harness as a module."""
    spec = importlib.util.spec_from_file_location(
        "pgs_semiprime_backward_two_step_transition_law_search",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pgs_semiprime_backward_two_step_transition_law_search module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pgs_semiprime_backward_two_step_transition_law_search"] = module
    spec.loader.exec_module(module)
    return module


def test_two_step_law_family_shape_is_pinned():
    """The two-step law family should keep its fixed deterministic size."""
    module = load_module()

    assert len(module.ENTRY_LAWS) == 2
    assert len(module.CONTINUATION_LAWS) == 5
    assert len(module.CLOSURE_LAWS) == 5
    assert len(module.TWO_STEP_LAW_ORDER) == 50


def test_two_step_trace_for_39_records_second_order_state():
    """The sentinel 39 trace should expose the requested second-order memory fields."""
    module = load_module()
    law_id = "winner_large_offset__same_gap_change_repeat_offset__same_role_p_left"
    trace = module.run_case(law_id, 39, max_steps=24)

    assert trace[0]["phase"] == "entry"
    assert trace[0]["selected_anchor"] == 33
    assert trace[0]["lane_factor"] == 3
    assert trace[1]["phase"] == "closure"
    assert trace[1]["prev_role_1"] == "previous"
    assert trace[1]["prev_role_2"] is None
    assert trace[1]["prev_offset_class_1"] == "tight"
    assert trace[1]["prev_gap_width_1"] == 6
    assert trace[1]["prev_gap_change_1"] == "start"
    assert trace[1]["stop_reason"] == "lane_success_terminal_prime"
    assert trace[1]["lane_success"] is True


def test_two_step_run_search_is_deterministic_on_reduced_surface():
    """The reduced two-step summary should be deterministic."""
    module = load_module()
    trace_a, summary_a = module.run_search(max_n=500, max_steps=24)
    trace_b, summary_b = module.run_search(max_n=500, max_steps=24)

    assert trace_a == trace_b
    assert summary_a == summary_b


def test_reduced_surface_pins_two_step_best_law():
    """The reduced two-step surface should pin the measured best-law tuple."""
    module = load_module()
    _trace, summary = module.run_search(max_n=500, max_steps=24)

    assert summary["best_law"] == "winner_large_offset__repeat_role_repeat_offset__same_role_p_left"
    assert summary["best_lane_success_count"] == 8
    assert summary["best_factor_reach_count"] == 0
    assert summary["baseline_best_lane_success_count"] == 70
    assert summary["improvement_over_baseline"] == -62
    assert summary["searched_family_falsified"] is False


def test_full_surface_ties_but_does_not_beat_one_step_baseline():
    """The first two-step family should tie the 70/980 one-step baseline, not beat it."""
    module = load_module()
    _trace, summary = module.run_search(max_n=5000, max_steps=24)

    assert summary["best_law"] == "small_gap_d4_large_offset__repeat_role_repeat_offset__same_role_p_left"
    assert summary["best_lane_success_count"] == 70
    assert summary["best_factor_reach_count"] == 0
    assert summary["baseline_best_lane_success_count"] == 70
    assert summary["improvement_over_baseline"] == 0
    assert summary["searched_family_falsified"] is False


def test_cli_writes_lf_terminated_summary(tmp_path: Path):
    """The CLI should emit one LF-terminated summary JSON only."""
    module = load_module()
    exit_code = module.main(["--max-n", "500", "--max-steps", "24", "--output-dir", str(tmp_path)])

    assert exit_code == 0

    summary_path = tmp_path / module.SUMMARY_FILENAME
    assert summary_path.exists()

    summary_raw = summary_path.read_bytes()
    assert summary_raw.endswith(b"\n")
    assert b"\r\n" not in summary_raw

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["best_law"] == "winner_large_offset__repeat_role_repeat_offset__same_role_p_left"
    assert summary["best_lane_success_count"] == 8
    assert summary["searched_family_falsified"] is False

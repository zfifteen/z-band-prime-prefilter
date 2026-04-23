"""Tests for the pure-PGS backward semiprime transition-law harness."""

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
    / "pgs_semiprime_backward_transition_law_search.py"
)


def load_module():
    """Load the backward transition-law harness as a module."""
    spec = importlib.util.spec_from_file_location(
        "pgs_semiprime_backward_transition_law_search",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pgs_semiprime_backward_transition_law_search module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pgs_semiprime_backward_transition_law_search"] = module
    spec.loader.exec_module(module)
    return module


def test_law_family_shape_is_pinned():
    """The transition-law family should keep its fixed deterministic size."""
    module = load_module()

    assert len(module.ENTRY_LAWS) == 4
    assert len(module.CONTINUATION_LAWS) == 6
    assert len(module.CLOSURE_LAWS) == 4
    assert len(module.TRANSITION_LAW_ORDER) == 96


def test_transition_trace_for_39_records_one_step_memory():
    """The sentinel 39 trace should expose the requested memory fields."""
    module = load_module()
    law_id = "small_gap_d4_large_offset__same_role_same_offset_winner__same_role_p_left"
    trace = module.run_case(law_id, 39, max_steps=24)

    assert trace[0]["phase"] == "entry"
    assert trace[0]["selected_anchor"] == 33
    assert trace[0]["lane_factor"] == 3
    assert trace[1]["phase"] == "closure"
    assert trace[1]["previous_role"] == "previous"
    assert trace[1]["previous_d"] == 4
    assert trace[1]["previous_gap_width"] == 6
    assert trace[1]["previous_offset_class"] == "tight"
    assert trace[1]["stop_reason"] == "lane_success_terminal_prime"
    assert trace[1]["lane_success"] is True


def test_run_search_is_deterministic_on_reduced_surface():
    """The reduced transition summary and trace should be deterministic."""
    module = load_module()
    trace_a, summary_a = module.run_search(max_n=500, max_steps=24)
    trace_b, summary_b = module.run_search(max_n=500, max_steps=24)

    assert trace_a == trace_b
    assert summary_a == summary_b


def test_reduced_surface_pins_transition_best_law():
    """The reduced transition surface should pin the measured best-law tuple."""
    module = load_module()
    _trace, summary = module.run_search(max_n=500, max_steps=24)

    assert summary["best_law"] == "winner_large_offset__same_role_same_offset_winner__same_role_p_left"
    assert summary["best_lane_success_count"] == 8
    assert summary["best_factor_reach_count"] == 0
    assert summary["baseline_best_lane_success_count"] == 32
    assert summary["improvement_over_baseline"] == -24
    assert summary["searched_family_falsified"] is False


def test_full_surface_beats_the_lane_baseline():
    """The full toy surface should now beat the earlier 32/980 lane baseline."""
    module = load_module()
    _trace, summary = module.run_search(max_n=5000, max_steps=24)

    assert summary["best_law"] == "small_gap_d4_large_offset__same_role_same_offset_winner__same_role_p_left"
    assert summary["best_lane_success_count"] == 70
    assert summary["best_factor_reach_count"] == 0
    assert summary["baseline_best_lane_success_count"] == 32
    assert summary["improvement_over_baseline"] == 38
    assert summary["searched_family_falsified"] is False


def test_cli_writes_lf_terminated_trace_and_summary(tmp_path: Path):
    """The CLI should emit LF-terminated JSONL and JSON artifacts only."""
    module = load_module()
    exit_code = module.main(["--max-n", "500", "--max-steps", "24", "--output-dir", str(tmp_path)])

    assert exit_code == 0

    trace_path = tmp_path / module.TRACE_FILENAME
    summary_path = tmp_path / module.SUMMARY_FILENAME
    assert trace_path.exists()
    assert summary_path.exists()

    trace_raw = trace_path.read_bytes()
    summary_raw = summary_path.read_bytes()
    assert trace_raw.endswith(b"\n")
    assert summary_raw.endswith(b"\n")
    assert b"\r\n" not in trace_raw
    assert b"\r\n" not in summary_raw

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["best_law"] == "winner_large_offset__same_role_same_offset_winner__same_role_p_left"
    assert summary["best_lane_success_count"] == 8
    assert summary["searched_family_falsified"] is False

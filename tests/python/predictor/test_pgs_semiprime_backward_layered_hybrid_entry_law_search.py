"""Tests for the layered residual miner and layered hybrid entry law search."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MINER_PATH = (
    ROOT
    / "benchmarks"
    / "python"
    / "predictor"
    / "pgs_semiprime_backward_layered_entry_pattern_miner.py"
)
LAYERED_PATH = (
    ROOT
    / "benchmarks"
    / "python"
    / "predictor"
    / "pgs_semiprime_backward_layered_hybrid_entry_law_search.py"
)


def load_module(name: str, path: Path):
    """Load one local benchmark module by path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_layered_miner_pins_current_layered_bottleneck():
    """The layered miner should pin the hybrid-law residual miss surface."""
    module = load_module("pgs_semiprime_backward_layered_entry_pattern_miner", MINER_PATH)
    summary = module.mine_layered_patterns(max_n=5000)

    assert summary["immediate_good_entry_count"] == 153
    assert summary["missed_good_entry_count"] == 65
    assert summary["top_switch_rows"][0]["selected_shape"] == ["previous", True, True, 12, 2]
    assert summary["top_switch_rows"][0]["alternative_shape"] == ["previous", False, False, 12, 6]
    assert summary["top_switch_rows"][0]["alt_lane_success_count"] == 4


def test_layered_harness_is_deterministic_on_reduced_surface():
    """The layered hybrid reduced summary should be deterministic."""
    module = load_module("pgs_semiprime_backward_layered_hybrid_entry_law_search", LAYERED_PATH)
    trace_a, summary_a = module.run_search(max_n=500, max_steps=24)
    trace_b, summary_b = module.run_search(max_n=500, max_steps=24)

    assert trace_a == trace_b
    assert summary_a == summary_b


def test_layered_harness_beats_hybrid_baseline_on_full_surface():
    """The layered hybrid family should improve over the pushed 88/980 hybrid baseline."""
    module = load_module("pgs_semiprime_backward_layered_hybrid_entry_law_search", LAYERED_PATH)
    _trace, summary = module.run_search(max_n=5000, max_steps=24)

    assert summary["best_law"] == "layered_hybrid_exact_shape_entry_switch"
    assert summary["best_lane_success_count"] == 89
    assert summary["best_factor_reach_count"] == 0
    assert summary["baseline_best_lane_success_count"] == 88
    assert summary["improvement_over_baseline"] == 1
    assert summary["searched_family_falsified"] is False


def test_cli_writes_lf_terminated_layered_summary(tmp_path: Path):
    """The layered hybrid CLI should emit LF-terminated summary JSON only."""
    module = load_module("pgs_semiprime_backward_layered_hybrid_entry_law_search", LAYERED_PATH)
    exit_code = module.main(["--max-n", "500", "--max-steps", "24", "--output-dir", str(tmp_path)])

    assert exit_code == 0

    summary_path = tmp_path / module.SUMMARY_FILENAME
    assert summary_path.exists()
    raw = summary_path.read_bytes()
    assert raw.endswith(b"\n")
    assert b"\r\n" not in raw

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["best_law"] == "baseline_hybrid_exact_shape_entry_switch"
    assert summary["best_lane_success_count"] == 10
    assert summary["baseline_best_lane_success_count"] == 88
    assert summary["searched_family_falsified"] is False

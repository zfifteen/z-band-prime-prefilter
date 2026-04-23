"""Tests for the pure-PGS backward semiprime lane-search harness."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "benchmarks" / "python" / "predictor" / "pgs_semiprime_backward_law_search.py"


def load_module():
    """Load the backward lane-search harness as a module."""
    spec = importlib.util.spec_from_file_location("pgs_semiprime_backward_law_search", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pgs_semiprime_backward_law_search module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pgs_semiprime_backward_law_search"] = module
    spec.loader.exec_module(module)
    return module


def test_toy_corpus_generator_matches_reduced_surface():
    """The reduced toy corpus should match the pinned odd-semiprime surface."""
    module = load_module()
    corpus = module.generate_toy_corpus(500)

    assert len(corpus) == 93
    assert corpus[:10] == [15, 21, 33, 35, 39, 51, 55, 57, 65, 69]


def test_parity_neutral_orientation_accepts_even_composite_anchors():
    """Even composite anchors reached during walking should orient exactly."""
    module = load_module()
    summary = module.orient_anchor(12)

    assert summary["anchor"] == 12
    assert summary["p_left"] == 11
    assert summary["p_right"] == 13
    assert [gap["role"] for gap in summary["gaps"]] == ["previous", "containing", "following"]
    assert summary["gaps"][1]["contains_anchor"] is True


def test_candidate_pool_includes_prime_boundaries_and_odd_semiprimes_only():
    """The local lane pool should expose prime boundaries and lower odd semiprimes only."""
    module = load_module()
    summary = module.orient_anchor(39)
    candidates = module.build_candidate_pool(summary, 39, {39})

    assert [(candidate["n"], candidate["kind"]) for candidate in candidates] == [
        (31, "prime_boundary"),
        (37, "prime_boundary"),
        (33, "odd_semiprime"),
        (35, "odd_semiprime"),
    ]


def test_odd_prev_d4_large_offset_enters_the_3_lane_for_39():
    """The sentinel 39 should enter the 3-lane through the previous odd semiprime 33."""
    module = load_module()
    trace = module.run_case("odd_prev_d4_large_offset", 39, max_steps=24)

    assert trace[0]["current_anchor"] == 39
    assert trace[0]["selected_anchor"] == 33
    assert trace[0]["selected_kind"] == "odd_semiprime"
    assert trace[0]["selected_role"] == "previous"
    assert trace[0]["selected_lane_factors"] == [3]
    assert trace[0]["lane_factor"] == 3
    assert trace[1]["selected_kind"] == "prime_boundary"
    assert trace[1]["stop_reason"] == "lane_success_terminal_prime"
    assert trace[1]["lane_success"] is True


def test_run_search_is_deterministic_on_reduced_surface():
    """The reduced lane summary and trace should be deterministic."""
    module = load_module()
    trace_a, summary_a = module.run_search(max_n=500, max_steps=24)
    trace_b, summary_b = module.run_search(max_n=500, max_steps=24)

    assert trace_a == trace_b
    assert summary_a == summary_b


def test_reduced_surface_has_positive_lane_signal_and_zero_prime_control():
    """The rebuilt reduced surface should show lane signal under pure PGS laws."""
    module = load_module()
    _trace, summary = module.run_search(max_n=500, max_steps=24)

    assert summary["law_summaries"]["prime_left_boundary_control"]["lane_success_count"] == 0
    assert summary["law_summaries"]["odd_prev_winner_large_offset"]["lane_success_count"] == 8
    assert summary["law_summaries"]["odd_prev_d4_large_offset"]["lane_success_count"] == 8
    assert summary["best_law"] == "odd_prev_winner_large_offset"
    assert summary["best_lane_success_count"] == 8
    assert summary["best_factor_reach_count"] == 0
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
    assert summary["max_n"] == 500
    assert summary["case_count"] == 93
    assert summary["best_law"] == "odd_prev_winner_large_offset"
    assert summary["best_lane_success_count"] == 8
    assert summary["searched_family_falsified"] is False

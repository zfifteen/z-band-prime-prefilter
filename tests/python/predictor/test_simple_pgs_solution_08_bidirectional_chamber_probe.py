"""Tests for the Solution 08 bidirectional chamber probe."""

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
    / "simple_pgs_solution_08_bidirectional_chamber_probe.py"
)


def load_module():
    """Load the bidirectional chamber probe module."""
    spec = importlib.util.spec_from_file_location(
        "simple_pgs_solution_08_bidirectional_chamber_probe",
        MODULE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load bidirectional chamber probe")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bidirectional_probe_rejects_promotion_on_committed_surface(tmp_path):
    """The tested right-phase rules must not be reported as promotable."""
    module = load_module()

    assert module.main(["--output-dir", str(tmp_path)]) == 0

    summary_path = tmp_path / "summary.json"
    candidate_rows_path = tmp_path / "bidirectional_candidate_rows.csv"
    rule_report_path = tmp_path / "bidirectional_rule_report.csv"
    assert summary_path.exists()
    assert candidate_rows_path.exists()
    assert rule_report_path.exists()
    assert b"\r\n" not in candidate_rows_path.read_bytes()
    assert b"\r\n" not in rule_report_path.read_bytes()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["candidate_row_count"] == 5166
    assert summary["promotion_eligible_rules"] == []
    assert summary["strongest_result"] == (
        "bidirectional_right_phase_closure_does_not_promote; "
        "current_right_phase_adds_no_safe_boundary_margin"
    )

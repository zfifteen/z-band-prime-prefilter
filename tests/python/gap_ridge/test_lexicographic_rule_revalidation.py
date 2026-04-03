"""Smoke tests for the lexicographic rule revalidation runner."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
BENCHMARKS_DIR = ROOT / "benchmarks" / "python" / "gap_ridge"


def load_module(name: str):
    """Load one benchmark module directly from its file path."""
    path = BENCHMARKS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_validate_interval_matches_small_exact_surface():
    """The interval validator should return exact agreement on a small range."""
    module = load_module("lexicographic_rule_revalidation")
    row = module.validate_lexicographic_rule_on_interval(2, 10_001, 10_000, "exact")

    assert row["gap_count"] > 0
    assert row["counterexample_count"] == 0
    assert row["match_rate"] == 1.0
    assert row["observed_d4_share"] > row["baseline_d4_share"]


def test_revalidation_entry_point_emits_requested_artifacts(tmp_path):
    """The revalidation runner should emit the report and summary artifacts."""
    module = load_module("lexicographic_rule_revalidation")

    assert (
        module.main(
            [
                "--output-dir",
                str(tmp_path),
                "--exact-limit",
                "100000",
                "--sampled-scales",
                "1000000",
                "--window-size",
                "10000",
                "--window-count",
                "2",
                "--seeds",
                "7",
                "11",
                "--alt-score-sample-scale",
                "1000000",
                "--alt-score-sample-limit",
                "10000",
            ]
        )
        == 0
    )

    assert (tmp_path / "edge_run_1e6.json").exists()
    assert (tmp_path / "lexicographic_rule_experiment_a.json").exists()
    assert (tmp_path / "lexicographic_rule_experiment_b.json").exists()
    assert (tmp_path / "lexicographic_rule_experiment_b.csv").exists()
    assert (tmp_path / "lexicographic_rule_experiment_c.json").exists()
    assert (tmp_path / "lexicographic_rule_experiment_d.json").exists()
    assert (tmp_path / "lexicographic_rule_revalidation_summary.json").exists()
    assert (tmp_path / "lexicographic_rule_revalidation_report.md").exists()

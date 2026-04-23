"""Smoke tests for the d=4 square-threat frontier scan."""

from __future__ import annotations

import importlib.util
import json
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


def test_analyze_interval_returns_positive_margin_frontier():
    """Small exact surfaces should return only positive-margin d=4 rows."""
    module = load_module("d4_square_threat_frontier")
    summary, frontier = module.analyze_interval(
        lo=2,
        hi=100_001,
        scale=100_000,
        window_mode="exact",
        frontier_size=10,
        prime_buffer=1_000,
    )

    assert summary["d4_gap_count"] > 0
    assert summary["min_margin"] is not None
    assert frontier
    assert all(int(row["winner_d"]) == 4 for row in frontier)
    assert all(int(row["margin"]) > 0 for row in frontier)
    assert all(float(row["closure_utilization"]) < 1.0 for row in frontier)


def test_entry_point_emits_frontier_artifacts(tmp_path):
    """The CLI entry point should emit summary and frontier artifacts."""
    module = load_module("d4_square_threat_frontier")

    assert (
        module.main(
            [
                "--output-dir",
                str(tmp_path),
                "--exact-limit",
                "100000",
                "--scales",
                "1000000",
                "--window-size",
                "10000",
                "--window-count",
                "2",
                "--frontier-size",
                "5",
                "--prime-buffer",
                "1000",
            ]
        )
        == 0
    )

    summary_path = tmp_path / "d4_square_threat_frontier_summary.json"
    frontier_path = tmp_path / "d4_square_threat_frontier.csv"
    assert summary_path.exists()
    assert frontier_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert int(payload["global_min_margin"]) > 0
    assert len(payload["frontier"]) == 5

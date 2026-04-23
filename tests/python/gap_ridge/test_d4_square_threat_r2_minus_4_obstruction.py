"""Smoke tests for the d=4 r^2-4 obstruction scan."""

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


def test_obstruction_scan_reports_no_margin_four_on_small_surface():
    """The small exact surface should show zero observed margin-4 closures."""
    module = load_module("d4_square_threat_r2_minus_4_obstruction")
    summary, frontier = module.scan_r2_minus_4_obstruction(
        max_n=1_000_000,
        chunk_size=200_000,
        buffer=10_000,
        frontier_size=10,
        prime_buffer=1_000,
    )

    assert summary["scanned_gap_count"] > 0
    assert summary["composite_r2_minus_2_count"] > 0
    assert summary["observed_margin_4_count"] == 0
    assert int(summary["global_min_margin"]) > 4
    assert frontier
    assert all(int(row["margin"]) > 4 for row in frontier)


def test_entry_point_emits_obstruction_artifacts(tmp_path):
    """The CLI entry point should emit summary and frontier artifacts."""
    module = load_module("d4_square_threat_r2_minus_4_obstruction")

    assert (
        module.main(
            [
                "--output-dir",
                str(tmp_path),
                "--max-n",
                "1000000",
                "--chunk-size",
                "200000",
                "--buffer",
                "10000",
                "--frontier-size",
                "5",
                "--prime-buffer",
                "1000",
            ]
        )
        == 0
    )

    summary_path = tmp_path / "d4_square_threat_r2_minus_4_obstruction_summary.json"
    frontier_path = tmp_path / "d4_square_threat_r2_minus_4_obstruction.csv"
    assert summary_path.exists()
    assert frontier_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["observed_margin_4_count"] == 0
    assert len(payload["frontier"]) == 5

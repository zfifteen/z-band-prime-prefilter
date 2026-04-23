"""Smoke tests for the d=4 square-residue dead-zone probe."""

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


def test_dead_zone_scan_reports_the_residue_split():
    """The small exact surface should show the residue-locked first non-floor margins."""
    module = load_module("d4_square_residue_dead_zone_probe")
    summary, frontier = module.scan_residue_dead_zone(
        max_n=1_000_000,
        chunk_size=200_000,
        buffer=10_000,
        frontier_size=8,
        prime_buffer=1_000,
    )

    assert summary["nonfloor_count"] > 0
    assert summary["checks"]["nonfloor_residue_classes_mod30"] == [1, 19]
    assert summary["checks"]["all_margin_6_rows_live_in_residue_19"] is True
    assert summary["residue_summary"]["1"]["min_margin"] == 8
    assert summary["residue_summary"]["19"]["min_margin"] == 6
    assert summary["checks"]["residue_checks"]["1"]["margin_6_count"] == 0
    assert summary["checks"]["residue_checks"]["19"]["margin_6_count"] > 0
    assert frontier


def test_dead_zone_entry_point_emits_artifacts(tmp_path):
    """The CLI entry point should emit summary and frontier artifacts."""
    module = load_module("d4_square_residue_dead_zone_probe")

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
                "6",
                "--prime-buffer",
                "1000",
            ]
        )
        == 0
    )

    summary_path = tmp_path / "d4_square_residue_dead_zone_summary.json"
    frontier_path = tmp_path / "d4_square_residue_dead_zone.csv"
    assert summary_path.exists()
    assert frontier_path.exists()

    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["residue_summary"]["1"]["min_margin"] == 8
    assert payload["residue_summary"]["19"]["min_margin"] == 6

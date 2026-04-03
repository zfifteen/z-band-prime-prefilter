"""Smoke tests for the lexicographic peak validation script."""

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


def test_lexicographic_peak_validation_emits_expected_artifacts(tmp_path):
    """The validation entry point should emit JSON and SVG artifacts."""
    module = load_module("lexicographic_peak_validation")
    output_dir = tmp_path / "validation"

    assert (
        module.main(
            [
                "--output-dir",
                str(output_dir),
                "--full-limits",
                "10000",
                "20000",
                "--window-scales",
                "100000",
                "--window-size",
                "10000",
                "--window-count",
                "2",
            ]
        )
        == 0
    )

    assert (output_dir / "lexicographic_peak_validation.json").exists()
    assert (output_dir / "lexicographic_peak_validation_summary.svg").exists()


def test_lexicographic_peak_validation_defaults_extend_through_10e18():
    """The validation script should expose the full configured sampled-scale ladder."""
    module = load_module("lexicographic_peak_validation")
    args = module.build_parser().parse_args([])

    assert args.full_limits == [1_000_000, 10_000_000]
    assert args.window_scales == [
        100_000_000,
        1_000_000_000,
        10_000_000_000,
        100_000_000_000,
        1_000_000_000_000,
        10_000_000_000_000,
        100_000_000_000_000,
        1_000_000_000_000_000,
        10_000_000_000_000_000,
        100_000_000_000_000_000,
        1_000_000_000_000_000_000,
    ]

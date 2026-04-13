"""Tests for the residual-class window-theorem exact scan."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "window_theorem_scan.py"


def load_module():
    """Load the window-theorem scan module directly from its file path."""
    spec = importlib.util.spec_from_file_location("window_theorem_scan", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load window_theorem_scan.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["window_theorem_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_small_exact_scan_reproduces_known_early_violations():
    """A small exact scan should reproduce the first violations for early classes."""
    module = load_module()
    residual_classes = [
        module.ResidualClassWindow(D=30, winner_divisor_bound=28, delta=1),
        module.ResidualClassWindow(D=42, winner_divisor_bound=40, delta=1),
        module.ResidualClassWindow(D=60, winner_divisor_bound=56, delta=1),
    ]

    payload = module.scan_window_violations(2, 30_001, residual_classes)
    rows = {row["D"]: row for row in payload["results"]}

    assert payload["all_classes_resolved"] is True
    assert payload["open_classes"] == []
    assert rows[30]["status"] == "VIOLATION_FOUND"
    assert rows[30]["violation"] == {
        "p": 4463,
        "q": 4481,
        "k": 4464,
        "w": 4467,
        "delta_actual": 3,
    }
    assert rows[42]["status"] == "VIOLATION_FOUND"
    assert rows[42]["violation"] == {
        "p": 16703,
        "q": 16729,
        "k": 16704,
        "w": 16706,
        "delta_actual": 2,
    }
    assert rows[60]["status"] == "VIOLATION_FOUND"
    assert rows[60]["violation"] == {
        "p": 20879,
        "q": 20887,
        "k": 20880,
        "w": 20883,
        "delta_actual": 3,
    }


def test_cli_emits_output_file(tmp_path):
    """The CLI should write the requested JSON artifact."""
    module = load_module()
    output_path = tmp_path / "window.json"

    assert (
        module.main(
            [
                "--hi",
                "30001",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["search_interval"] == {"lo": 2, "hi": 30001}
    assert payload["results"][0]["D"] == 10

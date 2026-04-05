"""Tests for the exact asymptotic-bridge load scan."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "asymptotic_bridge_load_scan.py"


def load_module():
    """Load the proof-pursuit script directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "asymptotic_bridge_load_scan",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load asymptotic_bridge_load_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["asymptotic_bridge_load_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_asymptotic_bridge_load_scan_emits_normalized_surface(tmp_path, capsys):
    """The bridge-load scan should emit a normalized no-early-spoiler surface."""
    module = load_module()
    output_path = tmp_path / "proof" / "asymptotic_bridge_load_scan.json"

    assert (
        module.main(
            [
                "--lo",
                "2",
                "--hi",
                "10001",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["interval"] == {"lo": 2, "hi": 10001}
    assert payload["earlier_candidate_count"] > 0
    assert payload["bridge_failure_count"] == 0
    assert payload["max_bridge_load"] < 1.0
    assert payload["top_bridge_load_cases"]
    assert payload["pair_summary"]
    assert payload["gap_size_frontier"]

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["interval"] == {"lo": 2, "hi": 10001}

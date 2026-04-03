"""Tests for the low-divisor hard-regime scan."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "low_divisor_hard_regime_scan.py"


def load_module():
    """Load the proof-pursuit script directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "low_divisor_hard_regime_scan",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load low_divisor_hard_regime_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["low_divisor_hard_regime_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_low_divisor_hard_regime_scan_emits_json(tmp_path, capsys):
    """The hard-regime scan should emit a JSON artifact on a small exact interval."""
    module = load_module()
    output_path = tmp_path / "proof" / "low_divisor_hard_regime_scan.json"

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
    assert payload["unresolved_candidate_count"] == 0
    assert payload["hard_classes"] == [4, 6, 8, 12, 16]

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["interval"] == {"lo": 2, "hi": 10001}

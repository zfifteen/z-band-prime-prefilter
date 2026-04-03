"""Tests for the low-divisor extremal-example extractor."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "low_divisor_extremal_examples.py"


def load_module():
    """Load the proof-pursuit script directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "low_divisor_extremal_examples",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load low_divisor_extremal_examples")
    module = importlib.util.module_from_spec(spec)
    sys.modules["low_divisor_extremal_examples"] = module
    spec.loader.exec_module(module)
    return module


def test_low_divisor_extremal_examples_emits_json(tmp_path, capsys):
    """The extremal-example extractor should emit a JSON artifact."""
    module = load_module()
    output_path = tmp_path / "proof" / "low_divisor_extremal_examples.json"

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
    assert payload["target_classes"] == [4, 6, 8, 12, 16]
    assert payload["interval"] == {"lo": 2, "hi": 10001}

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["target_classes"] == [4, 6, 8, 12, 16]

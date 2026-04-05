"""Tests for the exact no-early-spoiler margin scan."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "no_early_spoiler_margin_scan.py"


def load_module():
    """Load the proof-pursuit script directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "no_early_spoiler_margin_scan",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load no_early_spoiler_margin_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["no_early_spoiler_margin_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_no_early_spoiler_margin_scan_emits_positive_margins(tmp_path, capsys):
    """The exact scan should emit only positive margins on a small interval."""
    module = load_module()
    output_path = tmp_path / "proof" / "no_early_spoiler_margin_scan.json"

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
    assert payload["exact_spoiler_count"] == 0
    assert payload["min_log_score_margin"] > 0.0
    assert payload["min_critical_ratio_margin"] > 0.0
    assert payload["top_tight_ratio_margin_cases"]
    assert payload["top_tight_log_margin_cases"]

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["interval"] == {"lo": 2, "hi": 10001}

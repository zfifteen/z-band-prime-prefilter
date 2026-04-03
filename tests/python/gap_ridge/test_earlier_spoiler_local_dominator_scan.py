"""Tests for the exact earlier-candidate local-dominator scan."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = (
    ROOT / "gwr" / "experiments" / "proof" / "earlier_spoiler_local_dominator_scan.py"
)


def load_module():
    """Load the scan script directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "earlier_spoiler_local_dominator_scan",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load earlier_spoiler_local_dominator_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["earlier_spoiler_local_dominator_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_local_dominator_scan_exact_1e6_surface(tmp_path, capsys):
    """The exact 10^6 surface should resolve every true earlier candidate."""
    module = load_module()
    output_path = tmp_path / "proof" / "local_dominator_scan_1e6.json"

    assert (
        module.main(
            [
                "--lo",
                "2",
                "--hi",
                "1000001",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["gap_count"] == 70327
    assert payload["earlier_candidate_count"] == 169021
    assert payload["unresolved_count"] == 0
    assert payload["median_offset"] == 1
    assert payload["99th_percentile_offset"] == 7
    assert payload["worst_offset"] == 47

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload == payload

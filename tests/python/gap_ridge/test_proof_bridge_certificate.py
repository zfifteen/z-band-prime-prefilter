"""Tests for the proof-bridge certificate helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "proof_bridge_certificate.py"


def load_module():
    """Load the certificate helper directly from its file path."""
    spec = importlib.util.spec_from_file_location(
        "proof_bridge_certificate",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load proof_bridge_certificate")
    module = importlib.util.module_from_spec(spec)
    sys.modules["proof_bridge_certificate"] = module
    spec.loader.exec_module(module)
    return module


def test_certificate_uses_actual_artifact_schema():
    """The helper should load the committed bridge-load artifact correctly."""
    module = load_module()
    payload = module.build_report(
        theta=0.525,
        c=1.5379,
        gap_constant=1.0,
        verified_hi=20_000_001,
        artifact_path=module.DEFAULT_ARTIFACT,
    )
    assert payload["explicit_n0"] >= 16
    assert payload["finite_base"]["earlier_candidate_count"] == 3349874
    assert payload["finite_base"]["bridge_failure_count"] == 0
    assert payload["finite_base"]["max_bridge_load"] < 1.0
    dusart = payload["dusart_bounded_case"]
    assert dusart["coverage_lo_inclusive"] == 396738
    assert dusart["coverage_hi_inclusive"] == 5571362243795
    assert dusart["envelope_increasing_from_dusart_start"] is True
    assert dusart["finite_base_within_coverage"] is True

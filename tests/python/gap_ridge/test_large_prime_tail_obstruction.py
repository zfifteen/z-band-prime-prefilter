"""Tests for the fixed large-prime class-tail obstruction script."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "large_prime_tail_obstruction.py"


def load_module():
    """Load the proof-pursuit script directly from its file path."""
    spec = importlib.util.spec_from_file_location("large_prime_tail_obstruction", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load large_prime_tail_obstruction")
    module = importlib.util.module_from_spec(spec)
    sys.modules["large_prime_tail_obstruction"] = module
    spec.loader.exec_module(module)
    return module


def test_primorial_family_has_the_expected_first_exact_and_eventual_cutoffs():
    """The D = 2^k family should cross the current reducer exactly where expected."""
    module = load_module()
    payload = module.analyze_tail_obstruction(prime_threshold=396_739, max_k=32)

    assert payload["exact_first_witness_k"] == 18
    assert payload["eventual_cutoff_k"] == 20


def test_large_prime_tail_obstruction_emits_json(tmp_path, capsys):
    """The script should emit a JSON artifact for the current large-prime threshold."""
    module = load_module()
    output_path = tmp_path / "proof" / "large_prime_tail_obstruction.json"

    assert (
        module.main(
            [
                "--prime-threshold",
                "396739",
                "--max-k",
                "24",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["fixed_large_prime_factor"] > 1.0
    assert payload["family"]["parameter"] == "k >= 2"
    assert payload["exact_first_witness_k"] == 18
    assert payload["eventual_cutoff_k"] == 20

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload["proof_note_target"] == "universal tail obstruction for the fixed large-prime class reducer"

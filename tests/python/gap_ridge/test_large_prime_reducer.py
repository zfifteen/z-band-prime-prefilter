"""Tests for the combined GWR proof-pursuit large-prime reducer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "large_prime_reducer.py"


def load_module():
    """Load the proof-pursuit script directly from its file path."""
    spec = importlib.util.spec_from_file_location("large_prime_reducer", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load large_prime_reducer")
    module = importlib.util.module_from_spec(spec)
    sys.modules["large_prime_reducer"] = module
    spec.loader.exec_module(module)
    return module


def test_fixed_large_prime_table_eliminates_small_divisor_classes():
    """The fixed-factor table should eliminate the first tested divisor classes."""
    module = load_module()
    table = module.analyze_large_prime_divisor_classes(
        prime_threshold=396_739,
        max_divisor_class=64,
    )

    assert table["all_rows_eliminated"] is True
    assert table["unresolved_row_count"] == 0


def test_large_prime_reducer_emits_json(tmp_path, capsys):
    """The combined reducer should emit a JSON artifact on a small proof run."""
    module = load_module()
    output_path = tmp_path / "proof" / "large_prime_reducer.json"

    assert (
        module.main(
            [
                "--prime-threshold",
                "1000",
                "--max-divisor-class",
                "32",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["small_prime_surface"]["exact_spoiler_count"] == 0
    assert payload["large_prime_table"]["row_count"] == 29

    stdout_payload = json.loads(capsys.readouterr().out)
    assert (
        stdout_payload["proof_note_target"]
        == "former finite-reduction route: exact base surface plus fixed large-prime reducer"
    )

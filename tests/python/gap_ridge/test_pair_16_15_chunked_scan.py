from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "pair_16_15_chunked_scan.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location(
        "pair_16_15_chunked_scan",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load pair_16_15_chunked_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pair_16_15_chunked_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_pair_16_15_chunked_scan_emits_json(tmp_path, capsys):
    module = load_script_module()
    output_path = tmp_path / "proof" / "pair_16_15_chunked_scan.json"

    exit_code = module.main(
        [
            "--lo",
            "2",
            "--hi",
            "100001",
            "--chunk-size",
            "20000",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["interval"] == {"lo": 2, "hi": 100001}
    assert payload["pair"] == {
        "earlier_divisor_count": 16,
        "first_descent_divisor_count": 15,
    }
    assert payload["exact_failure_count"] == 0

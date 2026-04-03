from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = ROOT / "gwr" / "experiments" / "proof" / "low_divisor_first_descent_scan.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location(
        "low_divisor_first_descent_scan",
        SCRIPT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load low_divisor_first_descent_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["low_divisor_first_descent_scan"] = module
    spec.loader.exec_module(module)
    return module


def test_low_divisor_first_descent_scan_emits_json(tmp_path, capsys):
    module = load_script_module()
    output_path = tmp_path / "proof" / "low_divisor_first_descent_scan.json"

    exit_code = module.main(
        [
            "--lo",
            "2",
            "--hi",
            "10001",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["interval"] == {"lo": 2, "hi": 10001}
    assert payload["target_classes"] == [4, 6, 8, 12, 16]
    assert payload["unresolved_by_first_descent_count"] == 0

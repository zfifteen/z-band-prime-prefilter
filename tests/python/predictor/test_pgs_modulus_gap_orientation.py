"""Tests for the PGS modulus gap orientation milestone runner."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "benchmarks" / "python" / "predictor" / "pgs_modulus_gap_orientation.py"


def load_module():
    """Load the modulus orientation runner as a module."""
    spec = importlib.util.spec_from_file_location("pgs_modulus_gap_orientation", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load pgs_modulus_gap_orientation module")
    module = importlib.util.module_from_spec(spec)
    sys.modules["pgs_modulus_gap_orientation"] = module
    spec.loader.exec_module(module)
    return module


def test_decimal_and_hex_parsing_agree_for_121():
    """Decimal and hexadecimal input should parse to the same modulus."""
    module = load_module()
    assert module.parse_modulus("121") == 121
    assert module.parse_modulus("0x79") == 121


def test_orient_modulus_121_returns_expected_neighborhood_and_gap_order():
    """The 121 sentinel should produce the pinned three-gap neighborhood."""
    module = load_module()
    summary = module.orient_modulus(121)

    assert summary["p_prev"] == 109
    assert summary["p_left"] == 113
    assert summary["p_right"] == 127
    assert summary["p_next"] == 131
    assert summary["containing_gap_width"] == 14
    assert summary["n_offset_from_left"] == 8
    assert summary["n_offset_from_right"] == 6

    gaps = summary["gaps"]
    assert [gap["role"] for gap in gaps] == ["previous", "containing", "following"]

    previous, containing, following = gaps
    assert previous["winner"] == 111
    assert previous["carrier_family"] == "odd_semiprime"
    assert containing["winner"] == 121
    assert containing["carrier_family"] == "prime_square"
    assert following["winner"] == 129
    assert following["carrier_family"] == "odd_semiprime"


def test_containing_gap_for_121_has_expected_offsets():
    """The containing gap should pin N between 113 and 127 with offsets 8 and 6."""
    module = load_module()
    summary = module.orient_modulus(121)
    containing = summary["gaps"][1]

    assert containing["left_prime"] == 113
    assert containing["right_prime"] == 127
    assert containing["contains_n"] is True
    assert containing["n_offset_from_left"] == 8
    assert containing["n_offset_from_right"] == 6


def test_gap_with_no_interior_is_represented_honestly():
    """A gap with no interior should emit null winner fields and empty rows."""
    module = load_module()
    payload = module.build_gap_payload("empty", 2, 3, 9)

    assert payload["has_interior"] is False
    assert payload["winner"] is None
    assert payload["winner_d"] is None
    assert payload["winner_offset"] is None
    assert payload["carrier_family"] is None
    assert payload["dmin"] is None
    assert payload["interior_rows"] == []


def test_cli_writes_json_and_markdown_with_lf_endings(tmp_path: Path):
    """The CLI should emit both artifacts with LF termination only."""
    module = load_module()
    exit_code = module.main(["--n", "121", "--output-dir", str(tmp_path)])

    assert exit_code == 0

    stem = module.artifact_stem(121)
    summary_path = tmp_path / f"{stem}_summary.json"
    report_path = tmp_path / f"{stem}_report.md"
    assert summary_path.exists()
    assert report_path.exists()

    summary_raw = summary_path.read_bytes()
    report_raw = report_path.read_bytes()
    assert summary_raw.endswith(b"\n")
    assert report_raw.endswith(b"\n")
    assert b"\r\n" not in summary_raw
    assert b"\r\n" not in report_raw

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["n"] == 121

    report = report_path.read_text(encoding="utf-8")
    assert "`109 < 113 < 121 < 127 < 131`" in report

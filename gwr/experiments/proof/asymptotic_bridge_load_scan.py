#!/usr/bin/env python3
"""Measure the exact asymptotic-bridge load for the no-early-spoiler condition."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


MARGIN_SCAN_PATH = ROOT / "gwr" / "experiments" / "proof" / "no_early_spoiler_margin_scan.py"
TOP_CASE_LIMIT = 20


def load_margin_scan_module():
    """Load the exact margin-scan helpers directly from file."""
    module_name = "no_early_spoiler_margin_scan_runtime_bridge_load"
    spec = importlib.util.spec_from_file_location(module_name, MARGIN_SCAN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load no_early_spoiler_margin_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


MARGIN_SCAN = load_margin_scan_module()


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan exact prime gaps and measure the normalized bridge load "
            "actual_excess / critical_excess for the no-early-spoiler inequality."
        ),
    )
    parser.add_argument(
        "--lo",
        type=int,
        default=2,
        help="Inclusive lower bound of the natural-number interval.",
    )
    parser.add_argument(
        "--hi",
        type=int,
        default=20_000_001,
        help="Exclusive upper bound of the natural-number interval.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def _round_float(value: float) -> float:
    """Return a stable JSON float."""
    return float(f"{value:.18g}")


def analyze_interval(lo: int, hi: int) -> dict[str, object]:
    """Return the exact bridge-load surface on one interval."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    gap_count = 0
    earlier_candidate_count = 0
    bridge_failure_count = 0
    max_load_case: dict[str, int | float] | None = None
    top_load_cases: list[dict[str, int | float]] = []
    pair_summary: dict[tuple[int, int], dict[str, int | float]] = {}
    gap_size_frontier: dict[int, dict[str, int | float]] = {}

    for left_prime_raw, right_prime_raw in zip(primes[:-1], primes[1:]):
        left_prime = int(left_prime_raw)
        right_prime = int(right_prime_raw)
        gap = right_prime - left_prime
        if gap < 4:
            continue

        gap_count += 1
        left_index = left_prime - lo + 1
        right_index = right_prime - lo
        gap_values = values[left_index:right_index]
        gap_divisors = divisor_count[left_index:right_index]

        winner_divisor_count = int(np.min(gap_divisors))
        winner_index = int(np.flatnonzero(gap_divisors == winner_divisor_count)[0])
        winner_value = int(gap_values[winner_index])

        for earlier_value_raw, earlier_divisor_raw in zip(
            gap_values[:winner_index],
            gap_divisors[:winner_index],
        ):
            earlier_value = int(earlier_value_raw)
            earlier_divisor_count = int(earlier_divisor_raw)
            if earlier_divisor_count <= winner_divisor_count:
                raise RuntimeError(
                    "winner is not the leftmost carrier of the minimal divisor class"
                )

            earlier_candidate_count += 1
            delta = earlier_divisor_count - winner_divisor_count
            critical_ratio, actual_ratio, ratio_margin = MARGIN_SCAN.critical_ratio_margin(
                earlier_value,
                earlier_divisor_count,
                winner_value,
                winner_divisor_count,
            )
            log_margin = MARGIN_SCAN.log_score_margin(
                earlier_value,
                earlier_divisor_count,
                winner_value,
                winner_divisor_count,
            )
            critical_excess = critical_ratio - 1.0
            actual_excess = actual_ratio - 1.0
            bridge_load = actual_excess / critical_excess

            case = {
                "left_prime": left_prime,
                "right_prime": right_prime,
                "gap": gap,
                "winner_value": winner_value,
                "winner_divisor_count": winner_divisor_count,
                "winner_offset": winner_value - left_prime,
                "earlier_value": earlier_value,
                "earlier_divisor_count": earlier_divisor_count,
                "earlier_offset": earlier_value - left_prime,
                "delta": delta,
                "critical_ratio": _round_float(critical_ratio),
                "actual_log_ratio": _round_float(actual_ratio),
                "critical_ratio_margin": _round_float(ratio_margin),
                "critical_excess": _round_float(critical_excess),
                "actual_excess": _round_float(actual_excess),
                "bridge_load": _round_float(bridge_load),
                "log_score_margin": _round_float(log_margin),
            }

            if bridge_load >= 1.0:
                bridge_failure_count += 1

            if max_load_case is None or float(case["bridge_load"]) > float(max_load_case["bridge_load"]):
                max_load_case = case

            top_load_cases.append(case)
            top_load_cases.sort(key=lambda row: (-float(row["bridge_load"]), int(row["winner_value"])))
            del top_load_cases[TOP_CASE_LIMIT:]

            pair_key = (winner_divisor_count, earlier_divisor_count)
            pair_best = pair_summary.get(pair_key)
            if pair_best is None or float(case["bridge_load"]) > float(pair_best["max_bridge_load"]):
                pair_summary[pair_key] = {
                    "winner_divisor_count": winner_divisor_count,
                    "earlier_divisor_count": earlier_divisor_count,
                    "candidate_count": 1 if pair_best is None else int(pair_best["candidate_count"]) + 1,
                    "max_bridge_load": case["bridge_load"],
                    "min_critical_ratio_margin": case["critical_ratio_margin"],
                }
            else:
                pair_best["candidate_count"] = int(pair_best["candidate_count"]) + 1

            gap_best = gap_size_frontier.get(gap)
            if gap_best is None or float(case["bridge_load"]) > float(gap_best["bridge_load"]):
                gap_size_frontier[gap] = case

    if earlier_candidate_count == 0:
        raise RuntimeError("interval contains no earlier candidates")
    if max_load_case is None:
        raise RuntimeError("interval contains no bridge-load cases")

    pair_rows = sorted(
        pair_summary.values(),
        key=lambda row: (-float(row["max_bridge_load"]), int(row["winner_divisor_count"]), int(row["earlier_divisor_count"])),
    )
    gap_rows = [gap_size_frontier[gap] for gap in sorted(gap_size_frontier)]

    return {
        "interval": {"lo": lo, "hi": hi},
        "decision_surface": (
            "Exact normalized bridge load actual_excess / critical_excess for "
            "the no-early-spoiler inequality against the true GWR carrier."
        ),
        "gap_count": gap_count,
        "earlier_candidate_count": earlier_candidate_count,
        "bridge_failure_count": bridge_failure_count,
        "max_bridge_load": max_load_case["bridge_load"],
        "max_bridge_load_case": max_load_case,
        "top_bridge_load_cases": top_load_cases,
        "pair_summary": pair_rows,
        "gap_size_frontier": gap_rows,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the exact bridge-load scan."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_interval(args.lo, args.hi)
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

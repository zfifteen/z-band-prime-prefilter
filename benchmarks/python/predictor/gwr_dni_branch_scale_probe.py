#!/usr/bin/env python3
"""Measure branch-wise scale separation in the bounded DNI walker.

The current bounded compression uses one dynamic cutoff C(q) = max(64, ceil(0.5
* log(q)^2)). This probe tests a sharper structural question:

1. Do square-branch winners (exact next d_min = 3) set their pressure on a
   log-squared scale?
2. Do non-square continuation winners (exact next d_min in {4, 6}) stay on a
   lower, approximately log-scale envelope?

The script uses two deterministic surfaces:

- right-prime windows: exact next-gap comparisons over consecutive primes q;
- square windows: direct prime-square offsets p^2 - prevprime(p^2).

It emits one JSON summary and one CSV table of normalized branch maxima.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import gmpy2
from sympy import primerange


ROOT = Path(__file__).resolve().parents[3]
BENCHMARK_DIR = ROOT / "benchmarks" / "python" / "predictor"
if str(BENCHMARK_DIR) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_DIR))

import gwr_dni_recursive_walk as walk


DEFAULT_OUTPUT_DIR = ROOT / "output" / "gwr_proof" / "branch_scale_probe"
DEFAULT_RIGHT_PRIME_WINDOWS = [
    "1000000:20000",
    "10000000:20000",
    "100000000:20000",
    "1000000000:20000",
    "10000000000:20000",
    "100000000000:20000",
    "1000000000000:20000",
    "10000000000000:20000",
    "100000000000000:20000",
]
DEFAULT_SQUARE_PRIME_WINDOWS = [
    "100:20000",
    "1000:20000",
    "10000:20000",
    "100000:20000",
    "1000000:20000",
    "10000000:20000",
]
CSV_FIELDS = [
    "surface",
    "window_start",
    "window_width",
    "branch",
    "tested_count",
    "max_peak_offset",
    "normalized_peak",
    "normalization",
    "argmax_anchor",
    "argmax_first_open_offset",
    "argmax_gap_boundary_offset",
    "argmax_cutoff",
    "argmax_cutoff_utilization",
]


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Probe branch-wise scale separation in the bounded DNI walker.",
    )
    parser.add_argument(
        "--right-prime-window",
        action="append",
        default=None,
        help="Window in start:width form for consecutive-right-prime probing.",
    )
    parser.add_argument(
        "--square-prime-window",
        action="append",
        default=None,
        help="Window in start:width form for direct prime-square probing.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and CSV artifacts.",
    )
    return parser


def _parse_window(spec: str) -> tuple[int, int]:
    """Parse one start:width window specification."""
    parts = spec.split(":")
    if len(parts) != 2:
        raise ValueError(f"invalid window specification {spec!r}")
    start = int(parts[0])
    width = int(parts[1])
    if start < 3:
        raise ValueError("window start must be at least 3")
    if width < 1:
        raise ValueError("window width must be positive")
    return start, width


def _windows_or_default(raw_windows: list[str] | None, defaults: list[str]) -> list[tuple[int, int]]:
    """Return the parsed window list or the deterministic default list."""
    if raw_windows is None:
        raw_windows = defaults
    return [_parse_window(spec) for spec in raw_windows]


def _empty_branch_summary() -> dict[str, dict[str, object]]:
    """Return the initialized branch summary table."""
    return {
        "3": {
            "tested_count": 0,
            "max_peak_offset": 0,
            "normalized_peak": 0.0,
            "normalization": "peak/log(q)^2",
            "argmax": None,
        },
        "4": {
            "tested_count": 0,
            "max_peak_offset": 0,
            "normalized_peak": 0.0,
            "normalization": "peak/log(q)",
            "argmax": None,
        },
        "6": {
            "tested_count": 0,
            "max_peak_offset": 0,
            "normalized_peak": 0.0,
            "normalization": "peak/log(q)",
            "argmax": None,
        },
    }


def _update_branch_max(
    branch_summary: dict[str, dict[str, object]],
    branch: int,
    peak_offset: int,
    anchor: int,
    first_open_offset: int | None,
    gap_boundary_offset: int | None,
    cutoff: int | None,
) -> None:
    """Update the retained branch maximum and normalized peak."""
    if branch not in (3, 4, 6):
        return

    key = str(branch)
    entry = branch_summary[key]
    entry["tested_count"] = int(entry["tested_count"]) + 1

    log_anchor = math.log(anchor)
    if branch == 3:
        normalized_peak = float(peak_offset) / float(log_anchor * log_anchor)
    else:
        normalized_peak = float(peak_offset) / float(log_anchor)

    current_max_peak = int(entry["max_peak_offset"])
    current_normalized_peak = float(entry["normalized_peak"])
    if peak_offset > current_max_peak or (
        peak_offset == current_max_peak and normalized_peak > current_normalized_peak
    ):
        entry["max_peak_offset"] = int(peak_offset)
        entry["normalized_peak"] = normalized_peak
        entry["argmax"] = {
            "anchor": int(anchor),
            "first_open_offset": None if first_open_offset is None else int(first_open_offset),
            "gap_boundary_offset": None if gap_boundary_offset is None else int(gap_boundary_offset),
            "cutoff": None if cutoff is None else int(cutoff),
            "cutoff_utilization": None
            if cutoff is None
            else float(peak_offset) / float(cutoff),
        }


def _previous_prime_before_square(square: int) -> int:
    """Return the prime immediately below one odd prime square."""
    candidate = square - 2
    while not gmpy2.is_prime(candidate):
        candidate -= 2
    return int(candidate)


def probe_right_prime_windows(windows: list[tuple[int, int]]) -> list[dict[str, object]]:
    """Return one retained summary row per right-prime window and branch."""
    rows: list[dict[str, object]] = []

    for start, width in windows:
        branch_summary = _empty_branch_summary()
        for q in primerange(start, start + width):
            comparison = walk.compare_transition_rules(int(q))
            branch = int(comparison["exact_next_dmin"])
            peak_offset = int(comparison["exact_next_peak_offset"])
            _update_branch_max(
                branch_summary=branch_summary,
                branch=branch,
                peak_offset=peak_offset,
                anchor=int(comparison["current_right_prime"]),
                first_open_offset=int(comparison["first_open_offset"]),
                gap_boundary_offset=int(comparison["exact_gap_boundary_offset"]),
                cutoff=int(comparison["cutoff"]),
            )

        for branch_key, entry in branch_summary.items():
            argmax = entry["argmax"]
            rows.append(
                {
                    "surface": "right_prime",
                    "window_start": int(start),
                    "window_width": int(width),
                    "branch": int(branch_key),
                    "tested_count": int(entry["tested_count"]),
                    "max_peak_offset": int(entry["max_peak_offset"]),
                    "normalized_peak": float(entry["normalized_peak"]),
                    "normalization": str(entry["normalization"]),
                    "argmax_anchor": None if argmax is None else int(argmax["anchor"]),
                    "argmax_first_open_offset": None
                    if argmax is None or argmax["first_open_offset"] is None
                    else int(argmax["first_open_offset"]),
                    "argmax_gap_boundary_offset": None
                    if argmax is None or argmax["gap_boundary_offset"] is None
                    else int(argmax["gap_boundary_offset"]),
                    "argmax_cutoff": None
                    if argmax is None or argmax["cutoff"] is None
                    else int(argmax["cutoff"]),
                    "argmax_cutoff_utilization": None
                    if argmax is None or argmax["cutoff_utilization"] is None
                    else float(argmax["cutoff_utilization"]),
                }
            )

    return rows


def probe_square_prime_windows(windows: list[tuple[int, int]]) -> list[dict[str, object]]:
    """Return one retained summary row per square-prime window."""
    rows: list[dict[str, object]] = []

    for start, width in windows:
        branch_summary = _empty_branch_summary()
        for p in primerange(start, start + width):
            prime_value = int(p)
            square = prime_value * prime_value
            previous_prime = _previous_prime_before_square(square)
            peak_offset = square - previous_prime
            _update_branch_max(
                branch_summary=branch_summary,
                branch=3,
                peak_offset=peak_offset,
                anchor=previous_prime,
                first_open_offset=int(walk.first_open_offset(previous_prime % 30)),
                gap_boundary_offset=peak_offset,
                cutoff=int(walk.dynamic_cutoff(previous_prime)),
            )

        entry = branch_summary["3"]
        argmax = entry["argmax"]
        rows.append(
            {
                "surface": "square_prime",
                "window_start": int(start),
                "window_width": int(width),
                "branch": 3,
                "tested_count": int(entry["tested_count"]),
                "max_peak_offset": int(entry["max_peak_offset"]),
                "normalized_peak": float(entry["normalized_peak"]),
                "normalization": str(entry["normalization"]),
                "argmax_anchor": None if argmax is None else int(argmax["anchor"]),
                "argmax_first_open_offset": None
                if argmax is None or argmax["first_open_offset"] is None
                else int(argmax["first_open_offset"]),
                "argmax_gap_boundary_offset": None
                if argmax is None or argmax["gap_boundary_offset"] is None
                else int(argmax["gap_boundary_offset"]),
                "argmax_cutoff": None
                if argmax is None or argmax["cutoff"] is None
                else int(argmax["cutoff"]),
                "argmax_cutoff_utilization": None
                if argmax is None or argmax["cutoff_utilization"] is None
                else float(argmax["cutoff_utilization"]),
            }
        )

    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write one LF-terminated CSV file."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    """Run the branch scale probe and write the artifact set."""
    args = build_parser().parse_args(argv)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    started_at = time.time()
    right_prime_windows = _windows_or_default(
        args.right_prime_window,
        DEFAULT_RIGHT_PRIME_WINDOWS,
    )
    square_prime_windows = _windows_or_default(
        args.square_prime_window,
        DEFAULT_SQUARE_PRIME_WINDOWS,
    )

    right_prime_rows = probe_right_prime_windows(right_prime_windows)
    square_prime_rows = probe_square_prime_windows(square_prime_windows)
    rows = right_prime_rows + square_prime_rows

    summary = {
        "right_prime_windows": [
            {"start": int(start), "width": int(width)}
            for start, width in right_prime_windows
        ],
        "square_prime_windows": [
            {"start": int(start), "width": int(width)}
            for start, width in square_prime_windows
        ],
        "rows": rows,
        "elapsed_seconds": time.time() - started_at,
    }

    summary_path = args.output_dir / "gwr_dni_branch_scale_probe_summary.json"
    csv_path = args.output_dir / "gwr_dni_branch_scale_probe_rows.csv"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    _write_csv(csv_path, rows)

    print(
        "gwr-dni-branch-scale-probe:"
        f" right_prime_windows={len(right_prime_windows)}"
        f" square_prime_windows={len(square_prime_windows)}"
        f" elapsed_seconds={summary['elapsed_seconds']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

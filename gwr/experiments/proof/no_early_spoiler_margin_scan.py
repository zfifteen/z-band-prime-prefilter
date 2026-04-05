#!/usr/bin/env python3
"""Measure exact no-early-spoiler margins against the actual GWR carrier."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


TOP_CASE_LIMIT = 20


@dataclass(frozen=True)
class PairMarginStats:
    """Aggregate one winner-class / earlier-class margin pair."""

    winner_divisor_count: int
    earlier_divisor_count: int
    candidate_count: int = 0
    min_log_score_margin: float | None = None
    min_critical_ratio_margin: float | None = None

    def to_dict(self) -> dict[str, int | float | None]:
        """Return a JSON-ready mapping."""
        return asdict(self)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Scan exact prime gaps on an interval and measure the no-early-"
            "spoiler margins against the actual GWR carrier."
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


def score_strictly_greater(
    left_n: int,
    left_divisor_count: int,
    right_n: int,
    right_divisor_count: int,
) -> bool:
    """Return whether the score at the left value is strictly greater."""
    if left_divisor_count < 3 or right_divisor_count < 3:
        raise ValueError("exact score comparison requires composite inputs")

    return pow(left_n, left_divisor_count - 2) < pow(right_n, right_divisor_count - 2)


def log_score_margin(
    earlier_value: int,
    earlier_divisor_count: int,
    winner_value: int,
    winner_divisor_count: int,
) -> float:
    """Return the positive winner-minus-earlier log-score margin."""
    earlier_score = (1.0 - earlier_divisor_count / 2.0) * math.log(earlier_value)
    winner_score = (1.0 - winner_divisor_count / 2.0) * math.log(winner_value)
    return winner_score - earlier_score


def critical_ratio_margin(
    earlier_value: int,
    earlier_divisor_count: int,
    winner_value: int,
    winner_divisor_count: int,
) -> tuple[float, float, float]:
    """Return the critical ratio, actual log ratio, and their positive margin."""
    critical_ratio = (earlier_divisor_count - 2) / (winner_divisor_count - 2)
    actual_ratio = math.log(winner_value) / math.log(earlier_value)
    return critical_ratio, actual_ratio, critical_ratio - actual_ratio


def _round_float(value: float) -> float:
    """Return a stable JSON float."""
    return float(f"{value:.18g}")


def _case_record(
    left_prime: int,
    right_prime: int,
    winner_value: int,
    winner_divisor_count: int,
    earlier_value: int,
    earlier_divisor_count: int,
    log_margin: float,
    critical_ratio: float,
    actual_ratio: float,
    ratio_margin: float,
) -> dict[str, int | float]:
    """Return one JSON-ready tight-case record."""
    return {
        "left_prime": left_prime,
        "right_prime": right_prime,
        "gap": right_prime - left_prime,
        "winner_value": winner_value,
        "winner_divisor_count": winner_divisor_count,
        "winner_offset": winner_value - left_prime,
        "earlier_value": earlier_value,
        "earlier_divisor_count": earlier_divisor_count,
        "earlier_offset": earlier_value - left_prime,
        "delta": earlier_divisor_count - winner_divisor_count,
        "log_score_margin": _round_float(log_margin),
        "critical_ratio": _round_float(critical_ratio),
        "actual_log_ratio": _round_float(actual_ratio),
        "critical_ratio_margin": _round_float(ratio_margin),
    }


def _update_top_cases(
    top_cases: list[dict[str, int | float]],
    case: dict[str, int | float],
    margin_key: str,
) -> None:
    """Keep only the smallest-margin cases for one metric."""
    top_cases.append(case)
    top_cases.sort(key=lambda row: (float(row[margin_key]), int(row["winner_value"])))
    del top_cases[TOP_CASE_LIMIT:]


def analyze_interval(lo: int, hi: int) -> dict[str, object]:
    """Return exact no-early-spoiler margins on one interval."""
    if lo < 2:
        raise ValueError("lo must be at least 2")
    if hi <= lo:
        raise ValueError("hi must be greater than lo")

    divisor_count = divisor_counts_segment(lo, hi)
    values = np.arange(lo, hi, dtype=np.int64)
    primes = values[divisor_count == 2]

    gap_count = 0
    earlier_candidate_count = 0
    exact_spoiler_count = 0
    pair_stats: dict[tuple[int, int], PairMarginStats] = {}
    top_ratio_cases: list[dict[str, int | float]] = []
    top_log_margin_cases: list[dict[str, int | float]] = []
    exact_spoiler_examples: list[dict[str, int | float]] = []

    min_ratio_case: dict[str, int | float] | None = None
    min_log_margin_case: dict[str, int | float] | None = None

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
            winner_beats_earlier = score_strictly_greater(
                winner_value,
                winner_divisor_count,
                earlier_value,
                earlier_divisor_count,
            )
            if not winner_beats_earlier:
                exact_spoiler_count += 1

            current_log_margin = log_score_margin(
                earlier_value,
                earlier_divisor_count,
                winner_value,
                winner_divisor_count,
            )
            critical_ratio, actual_ratio, ratio_margin = critical_ratio_margin(
                earlier_value,
                earlier_divisor_count,
                winner_value,
                winner_divisor_count,
            )
            case = _case_record(
                left_prime=left_prime,
                right_prime=right_prime,
                winner_value=winner_value,
                winner_divisor_count=winner_divisor_count,
                earlier_value=earlier_value,
                earlier_divisor_count=earlier_divisor_count,
                log_margin=current_log_margin,
                critical_ratio=critical_ratio,
                actual_ratio=actual_ratio,
                ratio_margin=ratio_margin,
            )

            if min_ratio_case is None or float(case["critical_ratio_margin"]) < float(
                min_ratio_case["critical_ratio_margin"]
            ):
                min_ratio_case = case
            if min_log_margin_case is None or float(case["log_score_margin"]) < float(
                min_log_margin_case["log_score_margin"]
            ):
                min_log_margin_case = case

            _update_top_cases(top_ratio_cases, case, "critical_ratio_margin")
            _update_top_cases(top_log_margin_cases, case, "log_score_margin")

            key = (winner_divisor_count, earlier_divisor_count)
            stats = pair_stats.get(key)
            if stats is None:
                pair_stats[key] = PairMarginStats(
                    winner_divisor_count=winner_divisor_count,
                    earlier_divisor_count=earlier_divisor_count,
                    candidate_count=1,
                    min_log_score_margin=current_log_margin,
                    min_critical_ratio_margin=ratio_margin,
                )
            else:
                pair_stats[key] = PairMarginStats(
                    winner_divisor_count=winner_divisor_count,
                    earlier_divisor_count=earlier_divisor_count,
                    candidate_count=stats.candidate_count + 1,
                    min_log_score_margin=min(
                        stats.min_log_score_margin
                        if stats.min_log_score_margin is not None
                        else current_log_margin,
                        current_log_margin,
                    ),
                    min_critical_ratio_margin=min(
                        stats.min_critical_ratio_margin
                        if stats.min_critical_ratio_margin is not None
                        else ratio_margin,
                        ratio_margin,
                    ),
                )

            if not winner_beats_earlier and len(exact_spoiler_examples) < TOP_CASE_LIMIT:
                exact_spoiler_examples.append(case)

    if earlier_candidate_count == 0:
        raise RuntimeError("interval contains no earlier candidates")
    if min_ratio_case is None or min_log_margin_case is None:
        raise RuntimeError("interval contains no tight cases")

    pair_summary = [
        {
            "winner_divisor_count": stats.winner_divisor_count,
            "earlier_divisor_count": stats.earlier_divisor_count,
            "candidate_count": stats.candidate_count,
            "min_log_score_margin": _round_float(
                stats.min_log_score_margin if stats.min_log_score_margin is not None else 0.0
            ),
            "min_critical_ratio_margin": _round_float(
                stats.min_critical_ratio_margin
                if stats.min_critical_ratio_margin is not None
                else 0.0
            ),
        }
        for _, stats in sorted(pair_stats.items())
    ]

    return {
        "interval": {"lo": lo, "hi": hi},
        "decision_surface": (
            "Exact no-early-spoiler margins against the actual GWR carrier. "
            "Later candidates are already eliminated by the ordered-dominance theorem."
        ),
        "gap_count": gap_count,
        "earlier_candidate_count": earlier_candidate_count,
        "exact_spoiler_count": exact_spoiler_count,
        "min_log_score_margin": min_log_margin_case["log_score_margin"],
        "min_log_score_margin_case": min_log_margin_case,
        "min_critical_ratio_margin": min_ratio_case["critical_ratio_margin"],
        "min_critical_ratio_margin_case": min_ratio_case,
        "top_tight_log_margin_cases": top_log_margin_cases,
        "top_tight_ratio_margin_cases": top_ratio_cases,
        "pair_summary": pair_summary,
        "exact_spoiler_examples": exact_spoiler_examples,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the exact no-early-spoiler margin scan."""
    args = build_parser().parse_args(argv)
    payload = analyze_interval(args.lo, args.hi)
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

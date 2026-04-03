#!/usr/bin/env python3
"""Combine exact small-range scan with a fixed large-prime spoiler reducer."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))


SCAN_PATH = ROOT / "gwr" / "experiments" / "proof" / "earlier_spoiler_scan.py"
INF = 10**1000


def load_earlier_spoiler_scan_module():
    """Load the exact spoiler scan module from its file path."""
    spec = importlib.util.spec_from_file_location("earlier_spoiler_scan_runtime", SCAN_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load earlier_spoiler_scan")
    module = importlib.util.module_from_spec(spec)
    sys.modules["earlier_spoiler_scan_runtime"] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class DivisorClassRow:
    """One divisor-class elimination row under the fixed large-prime factor."""

    earlier_divisor_count: int
    minimal_earlier_value: int
    worst_case_threshold: float
    eliminated: bool

    def to_dict(self) -> dict[str, int | float | bool]:
        """Return a JSON-ready mapping."""
        return asdict(self)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Combine exact earlier-spoiler exhaustion below the explicit "
            "large-prime threshold with a fixed-factor large-prime reducer."
        ),
    )
    parser.add_argument(
        "--prime-threshold",
        type=int,
        default=396_739,
        help=(
            "Large-prime threshold P0 for the explicit next-prime factor "
            "q/p < 1 + 1/(25 log^2 P0)."
        ),
    )
    parser.add_argument(
        "--max-divisor-class",
        type=int,
        default=2_000,
        help="Largest earlier divisor class D to test in the large-prime table.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def primorial_prefix(prime_count: int) -> int:
    """Return the product of the first `prime_count` primes."""
    if prime_count < 0:
        raise ValueError("prime_count must be non-negative")
    product = 1
    candidate = 2
    count = 0
    while count < prime_count:
        is_prime = True
        trial = 2
        while trial * trial <= candidate:
            if candidate % trial == 0:
                is_prime = False
                break
            trial += 1
        if is_prime:
            product *= candidate
            count += 1
        candidate += 1
    return product


def generate_primes(limit: int) -> list[int]:
    """Return the first `limit` primes."""
    if limit <= 0:
        return []
    primes: list[int] = []
    candidate = 2
    while len(primes) < limit:
        is_prime = True
        trial = 2
        while trial * trial <= candidate:
            if candidate % trial == 0:
                is_prime = False
                break
            trial += 1
        if is_prime:
            primes.append(candidate)
        candidate += 1
    return primes


@lru_cache(maxsize=None)
def min_n_with_tau(target: int, prime_index: int = 0, max_exp: int = 2048) -> int:
    """Return the minimal integer with exactly `target` divisors."""
    if target == 1:
        return 1

    primes = generate_primes(32)
    if prime_index >= len(primes):
        return INF

    best = INF
    prime = primes[prime_index]
    value = 1
    limit = min(max_exp, target - 1)

    for exp in range(1, limit + 1):
        factor = exp + 1
        value *= prime
        if target % factor:
            if value >= best:
                break
            continue
        rest = min_n_with_tau(target // factor, prime_index + 1, exp)
        if rest >= INF:
            if value >= best:
                break
            continue
        candidate = value * rest
        if candidate < best:
            best = candidate
        if value >= best:
            break

    return int(best)


def large_prime_factor(prime_threshold: int) -> float:
    """Return the fixed multiplicative prime-gap factor at `prime_threshold`."""
    if prime_threshold <= 1:
        raise ValueError("prime_threshold must be greater than 1")
    return 1.0 + (1.0 / (25.0 * (math.log(prime_threshold) ** 2)))


def analyze_large_prime_divisor_classes(
    prime_threshold: int,
    max_divisor_class: int,
) -> dict[str, object]:
    """Return the fixed-factor large-prime divisor-class elimination table."""
    if max_divisor_class < 4:
        raise ValueError("max_divisor_class must be at least 4")

    factor = large_prime_factor(prime_threshold)
    rows: list[DivisorClassRow] = []
    unresolved_rows: list[dict[str, int | float | bool]] = []

    for earlier_divisor_count in range(4, max_divisor_class + 1):
        minimal_earlier_value = min_n_with_tau(earlier_divisor_count)
        worst_case_threshold = factor ** (earlier_divisor_count - 3)
        eliminated = minimal_earlier_value >= worst_case_threshold
        row = DivisorClassRow(
            earlier_divisor_count=earlier_divisor_count,
            minimal_earlier_value=minimal_earlier_value,
            worst_case_threshold=worst_case_threshold,
            eliminated=eliminated,
        )
        rows.append(row)
        if not eliminated:
            unresolved_rows.append(row.to_dict())

    return {
        "prime_threshold": prime_threshold,
        "fixed_large_prime_factor": factor,
        "max_divisor_class": max_divisor_class,
        "row_count": len(rows),
        "unresolved_row_count": len(unresolved_rows),
        "all_rows_eliminated": len(unresolved_rows) == 0,
        "rows": [row.to_dict() for row in rows],
        "unresolved_rows": unresolved_rows,
    }


def analyze_reducer(prime_threshold: int, max_divisor_class: int) -> dict[str, object]:
    """Run the exact small-range scan and the fixed-factor large-prime table."""
    scan_module = load_earlier_spoiler_scan_module()
    exact_surface = scan_module.analyze_interval(2, prime_threshold + 1)
    large_prime_table = analyze_large_prime_divisor_classes(
        prime_threshold=prime_threshold,
        max_divisor_class=max_divisor_class,
    )

    return {
        "proof_note_target": "former finite-reduction route: exact base surface plus fixed large-prime reducer",
        "small_prime_surface": {
            "interval": exact_surface["interval"],
            "gap_count": exact_surface["gap_count"],
            "exact_spoiler_count": exact_surface["exact_spoiler_count"],
            "unresolved_candidate_count": exact_surface["unresolved_candidate_count"],
            "counterexample_gap_count": exact_surface["counterexample_gap_count"],
            "unresolved_gap_count": exact_surface["unresolved_gap_count"],
        },
        "large_prime_table": large_prime_table,
        "current_status": (
            "This artifact exhausts the exact small-prime surface and then "
            "tests the fixed-factor large-prime divisor-class table through "
            "the chosen maximum divisor class."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the combined reducer and emit a JSON artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_reducer(
        prime_threshold=args.prime_threshold,
        max_divisor_class=args.max_divisor_class,
    )
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Exhaust the live odd winner branches for the residual GWR closure problem."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import gmpy2

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
import sys

if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


EXACT_SCAN_CEILING_P = 5_000_000_000
OPEN_BRANCHES: tuple[tuple[int, int], ...] = (
    (36, 35),
    (40, 39),
    (50, 49),
    (52, 51),
    (56, 55),
)
ODD_WINNER_PATTERNS: dict[int, tuple[tuple[int, ...], ...]] = {
    35: ((34,), (6, 4), (4, 6)),
    39: ((38,), (12, 2), (2, 12)),
    49: ((48,), (6, 6)),
    51: ((50,), (16, 2), (2, 16)),
    55: ((54,), (10, 4), (4, 10)),
}


@dataclass(frozen=True)
class BranchCase:
    """One realized earlier-versus-winner branch instance."""

    left_prime: int
    right_prime: int
    winner_value: int
    winner_offset: int
    earlier_value: int
    earlier_offset: int
    earlier_divisor_count: int
    winner_divisor_count: int
    log_margin: float

    def to_dict(self) -> dict[str, int | float]:
        """Return a JSON-ready mapping."""
        return asdict(self)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Exhaust the live odd winner branches by enumerating every odd-divisor "
            "winner carrier below the Bertrand threshold and checking its actual "
            "prime gap exactly."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def primes_up_to(limit: int) -> list[int]:
    """Return every prime up to the inclusive limit."""
    if limit < 2:
        return []
    sieve = bytearray(b"\x01") * (limit + 1)
    sieve[:2] = b"\x00\x00"
    root = int(limit**0.5)
    for prime in range(2, root + 1):
        if sieve[prime]:
            start = prime * prime
            sieve[start : limit + 1 : prime] = b"\x00" * (((limit - start) // prime) + 1)
    return [value for value, is_prime in enumerate(sieve) if is_prime]


def prev_prime(value: int) -> int:
    """Return the largest prime strictly below one integer."""
    candidate = value - 1
    if candidate % 2 == 0:
        candidate -= 1
    while candidate >= 2:
        if gmpy2.is_prime(candidate):
            return int(candidate)
        candidate -= 2
    raise ValueError("no previous prime below value")


def next_prime(value: int) -> int:
    """Return the least prime strictly above one integer."""
    candidate = value + 1
    if candidate <= 2:
        return 2
    if candidate % 2 == 0:
        candidate += 1
    while True:
        if gmpy2.is_prime(candidate):
            return int(candidate)
        candidate += 2


def log_margin(earlier_value: int, earlier_divisor_count: int, winner_value: int, winner_divisor_count: int) -> float:
    """Return winner-minus-earlier log-score margin."""
    return (
        (1.0 - winner_divisor_count / 2.0) * math.log(winner_value)
        - (1.0 - earlier_divisor_count / 2.0) * math.log(earlier_value)
    )


def enumerate_winner_values(winner_divisor_count: int, winner_limit: int) -> list[int]:
    """Return every odd-divisor winner value below the given limit."""
    patterns = ODD_WINNER_PATTERNS[winner_divisor_count]
    values: set[int] = set()
    prime_lists: dict[int, list[int]] = {}

    def prime_list_for_exponent(exponent: int) -> list[int]:
        limit = int(round(winner_limit ** (1.0 / exponent))) + 2
        primes = prime_lists.get(limit)
        if primes is None:
            primes = primes_up_to(limit)
            prime_lists[limit] = primes
        return primes

    for pattern in patterns:
        if len(pattern) == 1:
            exponent = pattern[0]
            for prime in prime_list_for_exponent(exponent):
                value = prime**exponent
                if value <= winner_limit:
                    values.add(value)
            continue

        first_exponent, second_exponent = pattern
        first_primes = prime_list_for_exponent(first_exponent)
        second_primes = prime_list_for_exponent(second_exponent)
        for first_prime in first_primes:
            first_factor = first_prime**first_exponent
            if first_factor > winner_limit:
                break
            for second_prime in second_primes:
                if second_prime == first_prime:
                    continue
                value = first_factor * (second_prime**second_exponent)
                if value <= winner_limit:
                    values.add(value)

    return sorted(values)


def analyze_branch(earlier_divisor_count: int, winner_divisor_count: int) -> dict[str, object]:
    """Return the exact status of one live odd winner branch."""
    if earlier_divisor_count != winner_divisor_count + 1:
        raise ValueError("this scanner only covers the live D = d + 1 odd branches")

    unresolved_hi = 1 << (winner_divisor_count - 2)
    winner_limit = 1 << (winner_divisor_count - 1)
    window_lo = EXACT_SCAN_CEILING_P + 1
    winner_values = enumerate_winner_values(winner_divisor_count, winner_limit)

    values_in_window = 0
    realized_winner_count = 0
    realized_pair_count = 0
    max_realized_winner_left_prime: int | None = None
    max_realized_pair_left_prime: int | None = None
    worst_pair: BranchCase | None = None
    counterexample: BranchCase | None = None

    for winner_value in winner_values:
        left_prime = prev_prime(winner_value)
        if left_prime < window_lo or left_prime > unresolved_hi:
            continue
        values_in_window += 1
        right_prime = next_prime(winner_value)

        gap_lo = left_prime + 1
        gap_hi = right_prime
        gap_divisors = divisor_counts_segment(gap_lo, gap_hi)
        winner_offset = winner_value - left_prime
        winner_index = winner_offset - 1
        winner_gap_divisor = int(gap_divisors[winner_index])
        gap_min_divisor = int(gap_divisors.min())
        first_min_index = int((gap_divisors == gap_min_divisor).nonzero()[0][0])

        if winner_gap_divisor != winner_divisor_count or gap_min_divisor != winner_divisor_count:
            continue
        if first_min_index != winner_index:
            continue

        realized_winner_count += 1
        max_realized_winner_left_prime = (
            left_prime
            if max_realized_winner_left_prime is None
            else max(max_realized_winner_left_prime, left_prime)
        )
        earlier_slice = gap_divisors[:winner_index]
        for earlier_index in (earlier_slice == earlier_divisor_count).nonzero()[0]:
            earlier_value = gap_lo + int(earlier_index)
            margin = log_margin(
                earlier_value=earlier_value,
                earlier_divisor_count=earlier_divisor_count,
                winner_value=winner_value,
                winner_divisor_count=winner_divisor_count,
            )
            case = BranchCase(
                left_prime=left_prime,
                right_prime=right_prime,
                winner_value=winner_value,
                winner_offset=winner_offset,
                earlier_value=earlier_value,
                earlier_offset=earlier_value - left_prime,
                earlier_divisor_count=earlier_divisor_count,
                winner_divisor_count=winner_divisor_count,
                log_margin=float(f"{margin:.18g}"),
            )
            realized_pair_count += 1
            max_realized_pair_left_prime = (
                left_prime
                if max_realized_pair_left_prime is None
                else max(max_realized_pair_left_prime, left_prime)
            )
            if worst_pair is None or case.log_margin < worst_pair.log_margin:
                worst_pair = case
            if case.log_margin <= 0.0:
                counterexample = case
                break
        if counterexample is not None:
            break

    return {
        "earlier_divisor_count": earlier_divisor_count,
        "winner_divisor_count": winner_divisor_count,
        "exact_scan_ceiling_p": EXACT_SCAN_CEILING_P,
        "unresolved_window": {
            "lo": window_lo,
            "hi": unresolved_hi,
        },
        "winner_limit": winner_limit,
        "enumerated_winner_value_count": len(winner_values),
        "winner_values_in_unresolved_window": values_in_window,
        "realized_winner_count": realized_winner_count,
        "max_realized_winner_left_prime": max_realized_winner_left_prime,
        "realized_pair_count": realized_pair_count,
        "max_realized_pair_left_prime": max_realized_pair_left_prime,
        "worst_pair": None if worst_pair is None else worst_pair.to_dict(),
        "counterexample": None if counterexample is None else counterexample.to_dict(),
    }


def analyze_all_branches() -> dict[str, object]:
    """Return the exact odd-branch scan for every currently open requested class."""
    branches = [analyze_branch(earlier_divisor_count=D, winner_divisor_count=d) for D, d in OPEN_BRANCHES]
    return {
        "exact_scan_ceiling_p": EXACT_SCAN_CEILING_P,
        "open_branches": [list(branch) for branch in OPEN_BRANCHES],
        "branch_reports": branches,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the live odd winner branch scan and emit JSON."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_all_branches()
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

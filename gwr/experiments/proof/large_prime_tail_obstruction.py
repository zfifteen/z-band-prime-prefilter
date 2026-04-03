#!/usr/bin/env python3
"""Prove that the fixed large-prime class reducer cannot close the universal tail."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class WitnessRow:
    """One primorial witness row for the divisor-count family D = 2^k."""

    k: int
    divisor_count: int
    primorial: int
    log_primorial: float
    log_threshold: float
    exact_witness_resolves_against_reducer: bool
    bound_log_upper: float
    bound_witness_resolves_against_reducer: bool

    def to_dict(self) -> dict[str, int | float | bool]:
        """Return a JSON-ready mapping."""
        return asdict(self)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Construct the exact D = 2^k primorial witness family showing that "
            "the fixed large-prime class reducer cannot close the universal tail."
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
        "--max-k",
        type=int,
        default=32,
        help="Largest family index k to emit.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def fixed_large_prime_factor(prime_threshold: int) -> float:
    """Return the fixed multiplicative prime-gap factor at `prime_threshold`."""
    if prime_threshold <= 1:
        raise ValueError("prime_threshold must be greater than 1")
    return 1.0 + (1.0 / (25.0 * (math.log(prime_threshold) ** 2)))


def first_n_primes(count: int) -> list[int]:
    """Return the first `count` primes."""
    if count < 0:
        raise ValueError("count must be non-negative")

    primes: list[int] = []
    candidate = 2
    while len(primes) < count:
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


def primorial_prefixes(max_k: int) -> tuple[list[int], list[float]]:
    """Return exact primorials and their logs through `max_k`."""
    if max_k < 2:
        raise ValueError("max_k must be at least 2")

    primes = first_n_primes(max_k)
    primorials: list[int] = []
    log_primorials: list[float] = []

    running_value = 1
    running_log = 0.0
    for prime in primes:
        running_value *= prime
        running_log += math.log(prime)
        primorials.append(running_value)
        log_primorials.append(running_log)

    return primorials, log_primorials


def exact_log_threshold(log_factor: float, k: int) -> float:
    """Return the exact log-threshold for the class D = 2^k."""
    return ((2**k) - 3) * log_factor


def elementary_bound_log(k: int) -> float:
    """Return the elementary Bertrand-based log upper bound for primorial(k)."""
    return ((k * (k + 1)) / 2.0) * math.log(2.0)


def monotone_increment(log_factor: float, k: int) -> float:
    """Return the increment in the elementary bound gap from k to k + 1."""
    return ((2**k) * log_factor) - ((k + 1) * math.log(2.0))


def analyze_tail_obstruction(prime_threshold: int, max_k: int) -> dict[str, object]:
    """Return the exact and eventual obstruction data for the D = 2^k family."""
    if max_k < 2:
        raise ValueError("max_k must be at least 2")

    factor = fixed_large_prime_factor(prime_threshold)
    log_factor = math.log(factor)
    primorials, log_primorials = primorial_prefixes(max_k)

    witness_rows: list[WitnessRow] = []
    exact_first_witness_k: int | None = None

    for k in range(2, max_k + 1):
        divisor_count = 2**k
        log_threshold = exact_log_threshold(log_factor, k)
        log_primorial = log_primorials[k - 1]
        bound_log_upper = elementary_bound_log(k)

        exact_resolves = log_primorial < log_threshold
        bound_resolves = bound_log_upper < log_threshold
        if exact_resolves and exact_first_witness_k is None:
            exact_first_witness_k = k

        witness_rows.append(
            WitnessRow(
                k=k,
                divisor_count=divisor_count,
                primorial=primorials[k - 1],
                log_primorial=log_primorial,
                log_threshold=log_threshold,
                exact_witness_resolves_against_reducer=exact_resolves,
                bound_log_upper=bound_log_upper,
                bound_witness_resolves_against_reducer=bound_resolves,
            )
        )

    eventual_cutoff_k: int | None = None
    for k in range(2, max_k + 1):
        bound_gap = exact_log_threshold(log_factor, k) - elementary_bound_log(k)
        increment = monotone_increment(log_factor, k)
        if bound_gap > 0.0 and increment > 0.0:
            eventual_cutoff_k = k
            break

    if exact_first_witness_k is None:
        raise RuntimeError("exact witness family did not cross the reducer threshold")
    if eventual_cutoff_k is None:
        raise RuntimeError("eventual cutoff not found within max_k")

    return {
        "proof_note_target": "universal tail obstruction for the fixed large-prime class reducer",
        "prime_threshold": prime_threshold,
        "fixed_large_prime_factor": factor,
        "family": {
            "parameter": "k >= 2",
            "divisor_count": "D = 2^k",
            "witness_value": "a_k = product of the first k primes",
            "exact_divisor_identity": "d(a_k) = 2^k",
            "elementary_upper_bound": "a_k < 2^(k(k+1)/2)",
            "elementary_source": "Bertrand gives p_i < 2^i, so primorial(k) < product_{i=1}^k 2^i",
        },
        "exact_first_witness_k": exact_first_witness_k,
        "eventual_cutoff_k": eventual_cutoff_k,
        "eventual_tail_statement": (
            "For every k >= eventual_cutoff_k, the elementary upper bound already "
            "lies below the fixed large-prime reducer threshold. So the class "
            "family D = 2^k remains unresolved forever under this reducer."
        ),
        "witness_rows": [row.to_dict() for row in witness_rows],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the tail obstruction script and emit a JSON artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_tail_obstruction(
        prime_threshold=args.prime_threshold,
        max_k=args.max_k,
    )
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

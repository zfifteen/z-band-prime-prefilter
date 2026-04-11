#!/usr/bin/env python3
"""Prototype the propagated boundary-state residue mask for exact next-prime search."""

from __future__ import annotations

import json
import time
from pathlib import Path
import sys

from sympy import isprime

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_prefilter.prefilter import DEFAULT_MR_BASES

START_RIGHT_PRIME = 10_000_000_000_037
STEPS = 100_000
MASK_WIDTH = 64
SMALL_PRIMES = (7, 11, 13, 17, 19, 23, 29, 31, 37)
OPEN_RESIDUES = (1, 7, 11, 13, 17, 19, 23, 29)


def build_open_offsets(residue30: int, count: int) -> list[int]:
    """Return the first `count` wheel-open offsets after a prime with residue `residue30`."""
    offsets: list[int] = []
    offset = 2
    while len(offsets) < count:
        if (residue30 + offset) % 30 in OPEN_RESIDUES:
            offsets.append(offset)
        offset += 2
    return offsets


OPEN_OFFSETS_BY_RESIDUE = {
    residue30: build_open_offsets(residue30, MASK_WIDTH)
    for residue30 in OPEN_RESIDUES
}


def build_mask_tables() -> dict[int, dict[tuple[int, int], int]]:
    """Build one certification mask table for each carried small-prime residue."""
    tables: dict[int, dict[tuple[int, int], int]] = {prime: {} for prime in SMALL_PRIMES}
    for residue30, offsets in OPEN_OFFSETS_BY_RESIDUE.items():
        for prime in SMALL_PRIMES:
            for current_residue in range(prime):
                mask = 0
                for index, offset in enumerate(offsets):
                    if (current_residue + offset) % prime == 0:
                        mask |= 1 << index
                tables[prime][(residue30, current_residue)] = mask
    return tables


MASK_TABLES = build_mask_tables()


def bare_miller_rabin_fixed_bases(
    n: int,
    bases: tuple[int, ...] = DEFAULT_MR_BASES,
) -> tuple[bool, int]:
    """Run the fixed-base Miller-Rabin path without a duplicated small-prime gate."""
    if n < 2:
        return False, 0
    if n % 2 == 0:
        return n == 2, 0

    d = n - 1
    s = 0
    while d % 2 == 0:
        d //= 2
        s += 1

    pow_calls = 0
    for base in bases:
        a = base % n
        if a in (0, 1, n - 1):
            continue

        x = pow(a, d, n)
        pow_calls += 1
        if x in (1, n - 1):
            continue

        witness_failed = True
        for _ in range(s - 1):
            x = pow(x, 2, n)
            pow_calls += 1
            if x == n - 1:
                witness_failed = False
                break

        if witness_failed:
            return False, pow_calls

    return True, pow_calls


def search_next_prime_baseline(
    current_right_prime: int,
    stats: dict[str, int],
) -> tuple[int, int]:
    """Search the next prime with the candidate-by-candidate small-prime gate."""
    offset = 2
    while True:
        candidate = current_right_prime + offset
        if candidate % 3 == 0 or candidate % 5 == 0:
            offset += 2
            continue

        for prime in SMALL_PRIMES:
            stats["small_prime_mods"] += 1
            if candidate % prime == 0:
                break
        else:
            stats["mr_calls"] += 1
            mr_passed, pow_calls = bare_miller_rabin_fixed_bases(candidate)
            stats["pow_calls"] += pow_calls
            if mr_passed:
                stats["isprime_calls"] += 1
                if isprime(candidate):
                    return candidate, offset

        offset += 2


def search_next_prime_boundary_mask(
    current_right_prime: int,
    residues: tuple[int, ...],
    stats: dict[str, int],
) -> tuple[int, int, bool]:
    """Search the next prime with the propagated boundary-state residue mask."""
    residue30 = current_right_prime % 30
    offsets = OPEN_OFFSETS_BY_RESIDUE[residue30]

    combined_mask = 0
    for index, prime in enumerate(SMALL_PRIMES):
        combined_mask |= MASK_TABLES[prime][(residue30, residues[index])]

    for index, offset in enumerate(offsets):
        if (combined_mask >> index) & 1:
            continue

        candidate = current_right_prime + offset
        stats["mr_calls"] += 1
        mr_passed, pow_calls = bare_miller_rabin_fixed_bases(candidate)
        stats["pow_calls"] += pow_calls
        if not mr_passed:
            continue

        stats["isprime_calls"] += 1
        if isprime(candidate):
            return candidate, offset, True

    offset = offsets[-1] + 2
    while True:
        candidate = current_right_prime + offset
        if candidate % 3 == 0 or candidate % 5 == 0:
            offset += 2
            continue

        for prime in SMALL_PRIMES:
            stats["small_prime_mods"] += 1
            if candidate % prime == 0:
                break
        else:
            stats["mr_calls"] += 1
            mr_passed, pow_calls = bare_miller_rabin_fixed_bases(candidate)
            stats["pow_calls"] += pow_calls
            if mr_passed:
                stats["isprime_calls"] += 1
                if isprime(candidate):
                    return candidate, offset, False

        offset += 2


def run_baseline() -> tuple[list[tuple[int, int]], dict[str, int], float]:
    """Run the exact baseline loop over the configured consecutive surface."""
    stats = {
        "small_prime_mods": 0,
        "mr_calls": 0,
        "pow_calls": 0,
        "isprime_calls": 0,
    }
    current_right_prime = START_RIGHT_PRIME
    chain: list[tuple[int, int]] = []

    start_time = time.perf_counter()
    for _ in range(STEPS):
        current_right_prime, gap_offset = search_next_prime_baseline(
            current_right_prime,
            stats,
        )
        chain.append((current_right_prime, gap_offset))
    elapsed = time.perf_counter() - start_time
    return chain, stats, elapsed


def run_boundary_mask(
    expected_chain: list[tuple[int, int]],
) -> tuple[dict[str, int], float, int]:
    """Run the propagated boundary-state hybrid and verify exact chain parity."""
    stats = {
        "small_prime_mods": 0,
        "mr_calls": 0,
        "pow_calls": 0,
        "isprime_calls": 0,
        "seed_residue_mods": len(SMALL_PRIMES),
    }
    residues = tuple(START_RIGHT_PRIME % prime for prime in SMALL_PRIMES)
    current_right_prime = START_RIGHT_PRIME
    resolved_in_window = 0

    start_time = time.perf_counter()
    for step, expected in enumerate(expected_chain):
        next_prime, gap_offset, resolved_here = search_next_prime_boundary_mask(
            current_right_prime,
            residues,
            stats,
        )
        if resolved_here:
            resolved_in_window += 1
        if next_prime != expected[0]:
            raise RuntimeError(
                f"chain mismatch at step {step}: expected {expected[0]}, got {next_prime}"
            )
        residues = tuple(
            (residues[index] + gap_offset) % prime
            for index, prime in enumerate(SMALL_PRIMES)
        )
        current_right_prime = next_prime
    elapsed = time.perf_counter() - start_time
    return stats, elapsed, resolved_in_window


def main() -> None:
    """Run the exact baseline and propagated boundary-state hybrid on one surface."""
    chain, baseline_stats, baseline_elapsed = run_baseline()
    hybrid_stats, hybrid_elapsed, resolved_in_window = run_boundary_mask(chain)

    state_entries = sum(len(table) for table in MASK_TABLES.values())
    payload = {
        "mechanism": (
            "propagated boundary-state 64-open residue mask for exact next-prime search"
        ),
        "start_right_prime": START_RIGHT_PRIME,
        "steps": STEPS,
        "mask_width": MASK_WIDTH,
        "small_primes": list(SMALL_PRIMES),
        "state_entries": state_entries,
        "u64_table_bytes": state_entries * 8,
        "end_right_prime": int(chain[-1][0]),
        "resolved_in_window": resolved_in_window,
        "resolved_in_window_fraction": resolved_in_window / STEPS,
        "baseline_small_prime_mods": baseline_stats["small_prime_mods"],
        "hybrid_small_prime_mods": hybrid_stats["small_prime_mods"],
        "hybrid_seed_residue_mods": hybrid_stats["seed_residue_mods"],
        "saved_small_prime_mods": (
            baseline_stats["small_prime_mods"] - hybrid_stats["small_prime_mods"]
        ),
        "saved_small_prime_mod_fraction": (
            (baseline_stats["small_prime_mods"] - hybrid_stats["small_prime_mods"])
            / baseline_stats["small_prime_mods"]
        ),
        "baseline_mr_calls": baseline_stats["mr_calls"],
        "hybrid_mr_calls": hybrid_stats["mr_calls"],
        "baseline_pow_calls": baseline_stats["pow_calls"],
        "hybrid_pow_calls": hybrid_stats["pow_calls"],
        "baseline_isprime_calls": baseline_stats["isprime_calls"],
        "hybrid_isprime_calls": hybrid_stats["isprime_calls"],
        "baseline_elapsed_s": baseline_elapsed,
        "hybrid_elapsed_s": hybrid_elapsed,
        "elapsed_speedup": baseline_elapsed / hybrid_elapsed,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

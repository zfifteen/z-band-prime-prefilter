"""Exact composite-field helpers used by prime-gap studies."""

from __future__ import annotations

import math

import gmpy2
import numpy as np


SEGMENT_SIZE = 1_000_000


def _small_primes(limit: int) -> np.ndarray:
    """Return every prime up to one small sieve limit."""
    sieve = np.ones(limit + 1, dtype=bool)
    sieve[:2] = False
    root = int(limit ** 0.5)
    for prime in range(2, root + 1):
        if sieve[prime]:
            sieve[prime * prime : limit + 1 : prime] = False
    return np.flatnonzero(sieve)


def _segmented_primes(limit: int, segment_size: int = SEGMENT_SIZE):
    """Yield primes up to one limit without materializing the full sieve."""
    if limit < 2:
        return

    base_limit = int(math.isqrt(limit))
    base_primes = _small_primes(base_limit)

    for segment_lo in range(2, limit + 1, segment_size):
        segment_hi = min(segment_lo + segment_size - 1, limit)
        sieve = np.ones(segment_hi - segment_lo + 1, dtype=bool)
        for prime in base_primes:
            prime_int = int(prime)
            prime_square = prime_int * prime_int
            if prime_square > segment_hi:
                break
            start = max(prime_square, ((segment_lo + prime_int - 1) // prime_int) * prime_int)
            sieve[start - segment_lo : segment_hi - segment_lo + 1 : prime_int] = False

        for offset in np.flatnonzero(sieve):
            yield segment_lo + int(offset)


def divisor_counts_segment(lo: int, hi: int) -> np.ndarray:
    """Compute exact divisor counts on one contiguous natural-number interval."""
    if lo < 1:
        raise ValueError("lo must be at least 1")
    if hi <= lo:
        raise ValueError("hi must be larger than lo")

    size = hi - lo
    values = np.arange(lo, hi, dtype=np.int64)
    residual = values.copy()
    divisor_count = np.ones(size, dtype=np.uint32)
    cube_root_limit, exact = gmpy2.iroot(hi - 1, 3)
    cube_root_limit = int(cube_root_limit)
    if not exact and (cube_root_limit + 1) ** 3 <= hi - 1:
        cube_root_limit += 1

    for prime in _segmented_primes(cube_root_limit):
        start = ((lo + prime - 1) // prime) * prime
        indices = np.arange(start - lo, size, prime, dtype=np.int64)
        if indices.size == 0:
            continue

        subvalues = residual[indices].copy()
        exponent = np.zeros(indices.size, dtype=np.uint8)
        while True:
            mask = (subvalues % prime) == 0
            if not mask.any():
                break
            subvalues[mask] //= prime
            exponent[mask] += 1

        residual[indices] = subvalues
        nonzero = exponent != 0
        if nonzero.any():
            divisor_count[indices[nonzero]] *= (exponent[nonzero] + 1).astype(np.uint32)

    for index, remainder in enumerate(residual):
        if remainder == 1:
            continue

        remainder_mpz = gmpy2.mpz(int(remainder))
        if gmpy2.is_prime(remainder_mpz):
            divisor_count[index] *= 2
            continue

        if gmpy2.is_square(remainder_mpz):
            root = gmpy2.isqrt(remainder_mpz)
            if gmpy2.is_prime(root):
                divisor_count[index] *= 3
                continue

        divisor_count[index] *= 4

    if lo <= 1 < hi:
        divisor_count[1 - lo] = 1
    return divisor_count

"""Exact composite-field helpers used by prime-gap studies."""

from __future__ import annotations

import math

import numpy as np


SEGMENT_SIZE = 1_000_000


def _integer_cube_root(value: int) -> tuple[int, bool]:
    """Return floor cube root and exactness for one non-negative integer."""
    root = int(round(value ** (1.0 / 3.0)))
    while (root + 1) ** 3 <= value:
        root += 1
    while root**3 > value:
        root -= 1
    return root, root**3 == value


def _strong_composite_witness(n: int, base: int, odd_part: int, shifts: int) -> bool:
    """Return True when one Miller-Rabin base proves compositeness."""
    value = pow(base, odd_part, n)
    if value == 1 or value == n - 1:
        return False
    for _ in range(shifts - 1):
        value = (value * value) % n
        if value == n - 1:
            return False
    return True


def _has_no_composite_witness(n: int) -> bool:
    """Return True when deterministic bases find no composite witness."""
    if n < 2:
        return False
    small_basis = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for base in small_basis:
        if n == base:
            return True
        if n % base == 0:
            return False

    odd_part = n - 1
    shifts = 0
    while odd_part % 2 == 0:
        odd_part //= 2
        shifts += 1

    for base in small_basis:
        if _strong_composite_witness(n, base, odd_part, shifts):
            return False
    return True


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
    cube_root_limit, exact = _integer_cube_root(hi - 1)
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

        remainder_int = int(remainder)
        if _has_no_composite_witness(remainder_int):
            divisor_count[index] *= 2
            continue

        root = math.isqrt(remainder_int)
        if root * root == remainder_int and _has_no_composite_witness(root):
            divisor_count[index] *= 3
            continue

        divisor_count[index] *= 4

    if lo <= 1 < hi:
        divisor_count[1 - lo] = 1
    return divisor_count

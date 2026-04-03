"""Segmented divisor-count helper compatible with runs.py.

This recreates the missing helper expected by the uploaded gap-ridge code.
It uses a pure Python + NumPy segmented factorization pass over [lo, hi).
"""

from __future__ import annotations

import math
from functools import lru_cache

import numpy as np


@lru_cache(maxsize=None)
def _primes_upto(limit: int) -> np.ndarray:
    """Return all primes <= limit as a NumPy array."""
    if limit < 2:
        return np.array([], dtype=np.int64)

    sieve = np.ones(limit + 1, dtype=np.bool_)
    sieve[:2] = False
    max_factor = math.isqrt(limit)
    for p in range(2, max_factor + 1):
        if sieve[p]:
            sieve[p * p : limit + 1 : p] = False
    return np.flatnonzero(sieve).astype(np.int64)


def divisor_counts_segment(lo: int, hi: int) -> np.ndarray:
    """Return divisor counts d(n) for every integer n in [lo, hi).

    Parameters
    ----------
    lo, hi:
        Integer interval bounds with 1 <= lo <= hi.

    Returns
    -------
    np.ndarray
        Array ``tau`` such that ``tau[i] == d(lo + i)``.
    """
    if hi < lo:
        raise ValueError("hi must be at least lo")
    if lo < 1:
        raise ValueError("lo must be at least 1")
    if hi == lo:
        return np.array([], dtype=np.int32)

    values = np.arange(lo, hi, dtype=np.int64)
    residual = values.copy()
    tau = np.ones(hi - lo, dtype=np.int32)
    max_factor = math.isqrt(hi - 1)

    for p in _primes_upto(max_factor):
        start = ((lo + p - 1) // p) * p
        if start >= hi:
            continue

        indexes = np.arange(start - lo, hi - lo, p, dtype=np.int64)
        chunk = residual[indexes]
        exponents = np.zeros(indexes.shape[0], dtype=np.int16)

        while True:
            mask = (chunk % p) == 0
            if not np.any(mask):
                break
            chunk[mask] //= p
            exponents[mask] += 1

        residual[indexes] = chunk
        tau[indexes] *= (exponents + 1)

    tau[residual > 1] *= 2
    return tau

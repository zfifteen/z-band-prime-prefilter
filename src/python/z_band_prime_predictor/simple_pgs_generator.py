"""Minimal emit-all PGS iprime generator."""

from __future__ import annotations

from math import isqrt


DEFAULT_CANDIDATE_BOUND = 128
PGS_SOURCE = "PGS"
FALLBACK_SOURCE = "fallback"
FALLBACK_REQUIRED_SOURCE = "fallback_required"
WHEEL_OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})


def has_trial_divisor(n: int) -> bool:
    """Return True when trial division finds a concrete divisor."""
    if n < 2:
        return True
    for divisor in range(2, isqrt(n) + 1):
        if n % divisor == 0:
            return True
    return False


def divisor_witness(n: int, max_divisor: int | None = None) -> int | None:
    """Return a concrete divisor, when one is visible."""
    if n < 2:
        return 1
    limit = isqrt(n) if max_divisor is None else min(isqrt(n), int(max_divisor))
    for divisor in range(2, limit + 1):
        if n % divisor == 0:
            return divisor
    return None


def first_prime_in_chamber(p: int, chamber_width: int) -> int | None:
    """Return the first trial-division prime in the current chamber."""
    for candidate in range(int(p) + 1, int(p) + int(chamber_width) + 1):
        if not has_trial_divisor(candidate):
            return candidate
    return None


def next_prime_by_trial_division(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> int:
    """Return the next prime using deterministic chamber expansion."""
    chamber_width = int(candidate_bound)
    if chamber_width < 1:
        raise ValueError("candidate_bound must be positive")
    while True:
        q = first_prime_in_chamber(int(p), chamber_width)
        if q is not None:
            return q
        chamber_width *= 2


def closure_reason(
    p: int,
    offset: int,
    max_divisor: int | None = None,
) -> str | None:
    """Return a PGS-visible reason that p + offset is not a boundary."""
    n = int(p) + int(offset)
    residue = n % 30
    if residue not in WHEEL_OPEN_RESIDUES_MOD30:
        return f"wheel_closed_residue:{residue}"
    witness = divisor_witness(n, max_divisor)
    if witness is not None and witness not in {1, n}:
        return f"divisor_witness:{witness}"
    return None


def admissible_offsets(p: int, candidate_bound: int) -> list[int]:
    """Return wheel-open boundary offsets inside the chamber."""
    return [
        offset
        for offset in range(1, int(candidate_bound) + 1)
        if (int(p) + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30
    ]


def pgs_chamber_closure_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    fallback_q: int | None = None,
    max_divisor: int | None = None,
) -> dict[str, object] | None:
    """Return the first v2 chamber-closure certificate."""
    offsets = admissible_offsets(int(p), int(candidate_bound))
    for gap_offset in offsets:
        q = int(p) + gap_offset
        if closure_reason(int(p), gap_offset, max_divisor) is not None:
            continue
        certificate = pgs_gap_certificate(
            int(p),
            gap_offset,
            int(candidate_bound),
            max_divisor,
        )
        if certificate is None:
            continue
        fallback_agreed = fallback_q is not None and q == int(fallback_q)
        certificate["fallback_agreed"] = fallback_agreed
        if fallback_q is None or fallback_agreed:
            return certificate
    return None


def pgs_gap_certificate(
    p: int,
    gap_offset: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    max_divisor: int | None = None,
) -> dict[str, object] | None:
    """Return a chamber-closure certificate for one proposed offset."""
    closed_offsets: list[int] = []
    reasons: dict[str, str] = {}
    unclosed_offsets: list[int] = []
    for offset in admissible_offsets(int(p), int(candidate_bound)):
        if offset >= int(gap_offset):
            break
        reason = closure_reason(int(p), offset, max_divisor)
        if reason is None:
            unclosed_offsets.append(offset)
            continue
        closed_offsets.append(offset)
        reasons[str(offset)] = reason
    if unclosed_offsets:
        return None

    return {
        "rule_id": "pgs_chamber_closure_v2",
        "p": int(p),
        "q": int(p) + int(gap_offset),
        "gap_offset": int(gap_offset),
        "candidate_bound": int(candidate_bound),
        "closed_offsets_before_q": closed_offsets,
        "closure_reason_by_offset": reasons,
        "unclosed_offsets_before_q": unclosed_offsets,
        "carrier_w": int(p),
        "carrier_d": 2,
        "used_forbidden_tool": False,
        "fallback_agreed": False,
    }


def pgs_boundary_certificate(
    p: int,
    fallback_q: int,
    boundary_offset: int | None = None,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, object] | None:
    """Return the first fallback-guarded PGS v2 certificate."""
    if boundary_offset is not None:
        certificate = pgs_gap_certificate(int(p), int(boundary_offset), candidate_bound)
        if certificate is not None and int(certificate["q"]) == int(fallback_q):
            certificate["fallback_agreed"] = True
            return certificate
        return None
    return pgs_chamber_closure_certificate(
        int(p),
        candidate_bound,
        int(fallback_q),
    )


def pgs_probe_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    max_divisor: int | None = None,
) -> dict[str, object] | None:
    """Return a PGS v2 certificate without running fallback."""
    return pgs_chamber_closure_certificate(
        int(p),
        candidate_bound,
        None,
        max_divisor,
    )


def resolve_q(
    p: int,
    boundary_offset: int | None = None,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> tuple[int, str, dict[str, object] | None]:
    """Resolve q and return its source."""
    fallback_q = next_prime_by_trial_division(int(p), candidate_bound)
    certificate = pgs_boundary_certificate(
        int(p),
        fallback_q,
        boundary_offset,
        candidate_bound,
    )
    if certificate is None:
        return fallback_q, FALLBACK_SOURCE, None
    return int(certificate["q"]), PGS_SOURCE, certificate


def emit_record(
    p: int,
    boundary_offset: int | None = None,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, int]:
    """Emit one minimal accurate iprime record."""
    q, _source, _certificate = resolve_q(int(p), boundary_offset, candidate_bound)
    return {
        "p": int(p),
        "q": q,
    }


def emit_records(
    anchors: list[int],
    boundary_offsets: dict[int, int] | None = None,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> list[dict[str, int]]:
    """Emit one minimal record per anchor."""
    offsets = {} if boundary_offsets is None else boundary_offsets
    return [
        emit_record(anchor, offsets.get(anchor), candidate_bound)
        for anchor in anchors
    ]

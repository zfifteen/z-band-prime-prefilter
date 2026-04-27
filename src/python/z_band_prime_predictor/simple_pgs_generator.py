"""Minimal PGS-only iprime generator."""

from __future__ import annotations

from z_band_prime_predictor.pgs_closure import (
    PGS_OPEN,
    pgs_closure_segment,
)


DEFAULT_CANDIDATE_BOUND = 128
PGS_GENERATOR_VERSION = "1.1.0"
PGS_GENERATOR_FREEZE_ID = "pgs_inference_generator_v1_1_pgs_only"
PGS_SOURCE = "PGS"
PGS_CHAMBER_RESET_RULE_ID = "pgs_chamber_reset_v1"


class PGSUnresolvedError(RuntimeError):
    """Raised when the PGS selector does not resolve inside the chamber."""


def pgs_chamber_reset_state_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, object] | None:
    """Return a certificate only when pure PGS closure leaves one survivor."""
    p = int(p)
    candidate_bound = int(candidate_bound)
    if candidate_bound < 1:
        raise ValueError("candidate_bound must be positive")

    statuses = pgs_closure_segment(p, candidate_bound)
    open_offsets = [
        offset
        for offset, status in enumerate(statuses, start=1)
        if int(status) == PGS_OPEN
    ]
    if len(open_offsets) != 1:
        return None

    gap_offset = int(open_offsets[0])
    rejected_offsets = [
        offset
        for offset, status in enumerate(statuses, start=1)
        if int(status) != PGS_OPEN and offset < gap_offset
    ]
    return chamber_reset_fields(
        {
            "rule_id": PGS_CHAMBER_RESET_RULE_ID,
            "p": p,
            "q": p + gap_offset,
            "gap_offset": gap_offset,
            "candidate_bound": candidate_bound,
            "closed_offsets_before_q": rejected_offsets,
            "closure_reason_by_offset": {},
            "unclosed_offsets_before_q": [],
            "active_count": len(open_offsets),
            "resolved_count": 1,
            "unresolved_count": 0,
            "tail_after_reset_offsets": [],
            "all_unresolved_after_reset": True,
            "carrier_w": None,
            "carrier_d": None,
            "lock_carrier_offset": None,
            "lock_carrier_d": None,
            "lower_d_threat_offset": None,
            "used_forbidden_tool": False,
        }
    )


def pgs_chamber_reset_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, object] | None:
    """Return the first resolved-survivor chamber-reset certificate."""
    return pgs_chamber_reset_state_certificate(int(p), int(candidate_bound))


def chamber_reset_fields(certificate: dict[str, object]) -> dict[str, object]:
    """Attach chamber-reset fields to one certificate."""
    certificate["rule_id"] = PGS_CHAMBER_RESET_RULE_ID
    certificate["chamber_reset_offset"] = int(certificate["gap_offset"])
    certificate["tail_candidates_block_emission"] = False
    certificate["post_reset_tail_policy"] = "later_chamber_material"
    return certificate


def pgs_probe_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, object] | None:
    """Return a chamber-reset certificate."""
    return pgs_chamber_reset_certificate(int(p), int(candidate_bound))


def resolve_q(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> tuple[int, str, dict[str, object]]:
    """Resolve q from the PGS selector."""
    certificate = pgs_probe_certificate(int(p), candidate_bound)
    if certificate is None:
        raise PGSUnresolvedError(
            f"PGS selector did not resolve p={int(p)} within bound={int(candidate_bound)}"
        )
    return int(certificate["q"]), PGS_SOURCE, certificate


def emit_record(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, int]:
    """Emit one minimal PGS iprime record."""
    q, _source, _certificate = resolve_q(int(p), candidate_bound)
    return {
        "p": int(p),
        "q": q,
    }


def emit_records(
    anchors: list[int],
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> list[dict[str, int]]:
    """Emit one minimal record per anchor."""
    return [
        emit_record(anchor, candidate_bound)
        for anchor in anchors
    ]

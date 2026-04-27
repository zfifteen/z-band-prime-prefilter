"""Minimal PGS-only iprime generator."""

from __future__ import annotations

from z_band_prime_composite_field import divisor_counts_segment


DEFAULT_CANDIDATE_BOUND = 128
PGS_GENERATOR_VERSION = "1.1.0"
PGS_GENERATOR_FREEZE_ID = "pgs_inference_generator_v1_1_pgs_only"
PGS_SOURCE = "PGS"
PGS_CHAMBER_RESET_RULE_ID = "pgs_chamber_reset_v1"
WHEEL_OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})
STATUS_REJECTED = "REJECTED"
STATUS_RESOLVED_SURVIVOR = "RESOLVED_SURVIVOR"
STATUS_UNRESOLVED = "UNRESOLVED"


class PGSUnresolvedError(RuntimeError):
    """Raised when the PGS selector does not resolve inside the chamber."""


def admissible_offsets(p: int, candidate_bound: int) -> list[int]:
    """Return wheel-open boundary offsets inside the chamber."""
    return [
        offset
        for offset in range(1, int(candidate_bound) + 1)
        if (int(p) + offset) % 30 in WHEEL_OPEN_RESIDUES_MOD30
    ]


def pgs_chamber_reset_state_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, object] | None:
    """Return the first GWR/NLSC chamber-reset survivor."""
    p = int(p)
    candidate_bound = int(candidate_bound)
    if candidate_bound < 1:
        raise ValueError("candidate_bound must be positive")

    counts = [
        int(value)
        for value in divisor_counts_segment(p + 1, p + candidate_bound + 1)
    ]
    offset_set = set(admissible_offsets(p, candidate_bound))
    candidate_states: list[dict[str, object]] = []
    carrier_offset: int | None = None
    carrier_d: int | None = None
    unresolved_count = 0

    for offset, divisor_count in enumerate(counts, start=1):
        n = p + offset
        if offset in offset_set:
            if divisor_count > 2:
                status = STATUS_REJECTED
            elif unresolved_count > 0:
                status = STATUS_UNRESOLVED
            else:
                status = STATUS_RESOLVED_SURVIVOR
            candidate_states.append(
                {
                    "offset": offset,
                    "n": n,
                    "status": status,
                    "carrier_offset": carrier_offset,
                    "carrier_d": carrier_d,
                }
            )

        if divisor_count > 2:
            if carrier_d is None or divisor_count < carrier_d:
                carrier_offset = offset
                carrier_d = divisor_count
        else:
            unresolved_count += 1

    lock_carrier_offset: int | None = None
    lock_carrier_d: int | None = None
    for state in candidate_states:
        if (
            state["status"] == STATUS_RESOLVED_SURVIVOR
            and state["carrier_offset"] is not None
        ):
            lock_carrier_offset = int(state["carrier_offset"])
            lock_carrier_d = int(state["carrier_d"])
            break

    threat_offset: int | None = None
    if lock_carrier_offset is not None and lock_carrier_d is not None:
        for offset in range(lock_carrier_offset + 1, candidate_bound + 1):
            divisor_count = counts[offset - 1]
            if divisor_count > 2 and divisor_count < lock_carrier_d:
                threat_offset = offset
                break

    active: list[dict[str, object]] = []
    resolved: list[dict[str, object]] = []
    unresolved: list[dict[str, object]] = []
    rejected_offsets: list[int] = []
    for state in candidate_states:
        final_status = str(state["status"])
        offset = int(state["offset"])
        if threat_offset is not None and offset > threat_offset:
            final_status = STATUS_REJECTED
        if final_status == STATUS_REJECTED:
            rejected_offsets.append(offset)
            continue
        active.append(state)
        if final_status == STATUS_RESOLVED_SURVIVOR:
            resolved.append(state)
        else:
            unresolved.append(state)

    if not resolved:
        return None

    first = resolved[0]
    gap_offset = int(first["offset"])
    carrier_offset = first["carrier_offset"]
    carrier_w = None if carrier_offset is None else p + int(carrier_offset)
    tail_after_reset = [
        int(state["offset"])
        for state in unresolved
        if int(state["offset"]) > gap_offset
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
            "active_count": len(active),
            "resolved_count": len(resolved),
            "unresolved_count": len(unresolved),
            "tail_after_reset_offsets": tail_after_reset,
            "all_unresolved_after_reset": len(tail_after_reset) == len(unresolved),
            "carrier_w": carrier_w,
            "carrier_d": first["carrier_d"],
            "lock_carrier_offset": lock_carrier_offset,
            "lock_carrier_d": lock_carrier_d,
            "lower_d_threat_offset": threat_offset,
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

"""Minimal emit-all PGS iprime generator."""

from __future__ import annotations

from math import isqrt

from z_band_prime_composite_field import divisor_counts_segment


DEFAULT_CANDIDATE_BOUND = 128
DEFAULT_CHAIN_LIMIT = 8
DEFAULT_VISIBLE_DIVISOR_BOUND = 10_000
PGS_GENERATOR_VERSION = "1.0.0"
PGS_GENERATOR_FREEZE_ID = "pgs_inference_generator_v1_0"
PGS_SOURCE = "PGS"
SHADOW_SEED_RECOVERY_SOURCE = "shadow_seed_recovery"
CHAIN_HORIZON_CLOSURE_SOURCE = "chain_horizon_closure"
CHAIN_FALLBACK_SOURCE = "chain_fallback"
FALLBACK_SOURCE = "fallback"
FALLBACK_REQUIRED_SOURCE = "fallback_required"
PGS_CHAMBER_RESET_RULE_ID = "pgs_chamber_reset_v1"
SHADOW_SEED_RECOVERY_RULE_ID = "shadow_seed_trial_recovery_v1"
WHEEL_OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})
STATUS_REJECTED = "REJECTED"
STATUS_RESOLVED_SURVIVOR = "RESOLVED_SURVIVOR"
STATUS_UNRESOLVED = "UNRESOLVED"


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


def pgs_chamber_reset_state_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> dict[str, object] | None:
    """Return the first GWR/NLSC chamber-reset survivor."""
    p = int(p)
    candidate_bound = int(candidate_bound)
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
            "fallback_agreed": False,
        }
    )


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


def pgs_chamber_reset_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    fallback_q: int | None = None,
    max_divisor: int | None = None,
) -> dict[str, object] | None:
    """Return the first resolved-survivor chamber-reset certificate."""
    if fallback_q is None:
        return pgs_chamber_reset_state_certificate(int(p), int(candidate_bound))

    certificate = pgs_chamber_reset_state_certificate(int(p), int(candidate_bound))
    if certificate is None:
        return None
    if int(certificate["q"]) != int(fallback_q):
        return None
    certificate["fallback_agreed"] = True
    return certificate


def chamber_reset_fields(certificate: dict[str, object]) -> dict[str, object]:
    """Attach chamber-reset fields to one certificate."""
    certificate["rule_id"] = PGS_CHAMBER_RESET_RULE_ID
    certificate["chamber_reset_offset"] = int(certificate["gap_offset"])
    certificate["tail_candidates_block_emission"] = False
    certificate["post_reset_tail_policy"] = "later_chamber_material"
    return certificate


def visible_open_chain_offsets(
    p: int,
    seed_offset: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    chain_limit: int = DEFAULT_CHAIN_LIMIT,
    max_divisor: int | None = None,
) -> list[int]:
    """Return visible-open rightward chain offsets after one seed."""
    offsets = admissible_offsets(int(p), int(candidate_bound))
    chain: list[int] = []
    current = int(seed_offset)
    while len(chain) < int(chain_limit):
        visible = [
            offset
            for offset in offsets
            if offset > current and closure_reason(int(p), offset, max_divisor) is None
        ]
        if not visible:
            break
        current = min(visible)
        chain.append(current)
    return chain


def chain_fallback_result(
    p: int,
    seed_offset: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    chain_limit: int = DEFAULT_CHAIN_LIMIT,
    max_divisor: int | None = DEFAULT_VISIBLE_DIVISOR_BOUND,
) -> tuple[int | None, dict[str, object]]:
    """Return the first exact chain survivor and chain sidecar fields."""
    chain_offsets = visible_open_chain_offsets(
        int(p),
        int(seed_offset),
        int(candidate_bound),
        int(chain_limit),
        max_divisor,
    )
    chain_nodes = [int(p) + offset for offset in chain_offsets]
    checked_nodes: list[int] = []
    selected_position: int | None = None
    selected_q: int | None = None
    for position, candidate in enumerate(chain_nodes, start=1):
        checked_nodes.append(candidate)
        if not has_trial_divisor(candidate):
            selected_position = position
            selected_q = candidate
            break
    return selected_q, {
        "chain_seed": int(p) + int(seed_offset),
        "chain_limit": int(chain_limit),
        "chain_position_selected": selected_position,
        "chain_nodes_checked": checked_nodes,
        "chain_fallback_success": selected_q is not None,
        "full_fallback_used": False,
    }


def chain_horizon_closure_result(
    p: int,
    seed_offset: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    chain_limit: int = DEFAULT_CHAIN_LIMIT,
    max_divisor: int | None = DEFAULT_VISIBLE_DIVISOR_BOUND,
    horizon_bound: int | None = None,
) -> tuple[int | None, dict[str, object]]:
    """Return the first chain node not closed by divisor horizon."""
    chain_offsets = visible_open_chain_offsets(
        int(p),
        int(seed_offset),
        int(candidate_bound),
        int(chain_limit),
        max_divisor,
    )
    checked_nodes: list[int] = []
    closed_nodes: list[int] = []
    closure_witnesses: dict[str, int] = {}
    selected_position: int | None = None
    selected_q: int | None = None
    complete_horizon = horizon_bound is None
    for position, offset in enumerate(chain_offsets, start=1):
        candidate = int(p) + int(offset)
        checked_nodes.append(candidate)
        witness = divisor_witness(candidate, horizon_bound)
        if witness is None:
            selected_position = position
            selected_q = candidate
            break
        closed_nodes.append(candidate)
        closure_witnesses[str(candidate)] = int(witness)
    return selected_q, {
        "chain_seed": int(p) + int(seed_offset),
        "chain_limit": int(chain_limit),
        "chain_position_selected": selected_position,
        "chain_nodes_checked": checked_nodes,
        "chain_horizon_closed_nodes": closed_nodes,
        "chain_horizon_closure_witnesses": closure_witnesses,
        "chain_horizon_bound": horizon_bound,
        "chain_horizon_complete": complete_horizon,
        "chain_horizon_closure_success": selected_q is not None,
        "chain_fallback_success": False,
        "full_fallback_used": False,
    }


def shadow_seed_gwr_recovery_result(
    p: int,
    seed_offset: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
) -> tuple[int, dict[str, object]]:
    """Return the first exact right boundary after a shadow seed."""
    seed = int(p) + int(seed_offset)
    chamber_width = int(candidate_bound)
    if chamber_width < 1:
        raise ValueError("candidate_bound must be positive")
    checked_nodes: list[int] = []
    while True:
        upper = int(p) + chamber_width
        for candidate in range(seed + 1, upper + 1):
            checked_nodes.append(candidate)
            if not has_trial_divisor(candidate):
                return candidate, {
                    "chain_seed": seed,
                    "chain_limit": DEFAULT_CHAIN_LIMIT,
                    "chain_position_selected": len(checked_nodes),
                    "chain_nodes_checked": checked_nodes,
                    "chain_horizon_closed_nodes": [],
                    "chain_horizon_closure_witnesses": {},
                    "chain_horizon_bound": None,
                    "chain_horizon_complete": True,
                    "chain_horizon_closure_success": False,
                    "chain_fallback_success": False,
                    "full_fallback_used": False,
                }
        chamber_width *= 2


def pgs_gap_certificate(
    p: int,
    gap_offset: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    max_divisor: int | None = None,
) -> dict[str, object] | None:
    """Return a chamber-closure certificate for one proposed offset."""
    if closure_reason(int(p), int(gap_offset), max_divisor) is not None:
        return None

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
    """Return the first fallback-guarded chamber-reset certificate."""
    if boundary_offset is not None:
        certificate = pgs_gap_certificate(int(p), int(boundary_offset), candidate_bound)
        if certificate is not None and int(certificate["q"]) == int(fallback_q):
            chamber_reset_fields(certificate)
            certificate["fallback_agreed"] = True
            return certificate
        return None
    return pgs_chamber_reset_certificate(
        int(p),
        candidate_bound,
        int(fallback_q),
    )


def pgs_probe_certificate(
    p: int,
    candidate_bound: int = DEFAULT_CANDIDATE_BOUND,
    max_divisor: int | None = None,
) -> dict[str, object] | None:
    """Return a chamber-reset certificate without fallback confirmation."""
    return pgs_chamber_reset_certificate(
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
    certificate = pgs_probe_certificate(
        int(p),
        candidate_bound,
        DEFAULT_VISIBLE_DIVISOR_BOUND,
    )
    if certificate is not None and boundary_offset is not None:
        boundary_certificate = pgs_gap_certificate(
            int(p),
            int(boundary_offset),
            candidate_bound,
            DEFAULT_VISIBLE_DIVISOR_BOUND,
        )
        certificate = None if boundary_certificate is None else chamber_reset_fields(
            boundary_certificate
        )
    if certificate is not None:
        q0 = int(certificate["q"])
        certificate["fallback_agreed"] = False
        certificate.update(
            {
                "chain_seed": None,
                "chain_limit": DEFAULT_CHAIN_LIMIT,
                "chain_position_selected": None,
                "chain_nodes_checked": [],
                "chain_fallback_success": False,
                "full_fallback_used": False,
            }
        )
        return q0, PGS_SOURCE, certificate

    fallback_q = next_prime_by_trial_division(int(p), candidate_bound)
    return fallback_q, FALLBACK_SOURCE, {
        "chain_seed": None,
        "chain_limit": DEFAULT_CHAIN_LIMIT,
        "chain_position_selected": None,
        "chain_nodes_checked": [],
        "chain_fallback_success": False,
        "full_fallback_used": True,
    }


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

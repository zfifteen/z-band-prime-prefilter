#!/usr/bin/env python3
"""Compute proof-bridge status from explicit large-p constants."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = ROOT / "output" / "gwr_proof" / "asymptotic_bridge_load_scan_2e7.json"
DUSART_X0 = 396_738
DUSART_GAP_DENOMINATOR = 25.0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the conditional BHP tail bound and the bounded Dusart "
            "envelope against the exact verified base surface."
        ),
    )
    parser.add_argument(
        "--theta",
        type=float,
        default=0.525,
        help="Exponent in the explicit prime-gap bound g(p) <= A * p^theta.",
    )
    parser.add_argument(
        "--c",
        type=float,
        default=1.5379,
        help="Constant in the divisor-function majoration exp(c log p / log log p).",
    )
    parser.add_argument(
        "--gap-constant",
        type=float,
        default=1.0,
        help="Explicit multiplicative constant A in g(p) <= A * p^theta.",
    )
    parser.add_argument(
        "--verified-hi",
        type=int,
        default=20_000_001,
        help="Exclusive upper endpoint of the exact verified finite base.",
    )
    parser.add_argument(
        "--artifact",
        type=Path,
        default=DEFAULT_ARTIFACT,
        help="JSON artifact from asymptotic_bridge_load_scan.py.",
    )
    return parser


def bridge_upper_bound(
    p: float,
    theta: float,
    c: float,
    gap_constant: float,
) -> float:
    """Return the explicit large-p bridge upper bound."""
    if p <= math.e**math.e:
        raise ValueError("p must exceed e^e so log log p is positive")
    if gap_constant <= 0.0:
        raise ValueError("gap_constant must be positive")
    return (
        gap_constant
        * (p ** (theta - 1.0))
        / math.log(p)
        * math.exp(c * math.log(p) / math.log(math.log(p)))
    )


def compute_explicit_n0(
    theta: float,
    c: float,
    gap_constant: float,
    start: int,
) -> int:
    """Return the first integer at or above `start` where the bridge bound is < 1."""
    low = max(start, 16)
    if bridge_upper_bound(low, theta, c, gap_constant) < 1.0:
        return low

    high = low
    for _ in range(80):
        high *= 2
        if bridge_upper_bound(high, theta, c, gap_constant) < 1.0:
            break
    else:
        raise RuntimeError("failed to find a bridge threshold below 2^(80) * start")

    while low + 1 < high:
        mid = (low + high) // 2
        if bridge_upper_bound(mid, theta, c, gap_constant) < 1.0:
            high = mid
        else:
            low = mid

    return high


def dusart_bridge_upper_bound(p: float, c: float) -> float:
    """Return the explicit bridge upper bound under Dusart's gap inequality."""
    if p < DUSART_X0:
        raise ValueError(f"p must be at least {DUSART_X0} for the Dusart bound")
    if p <= math.e**math.e:
        raise ValueError("p must exceed e^e so log log p is positive")
    log_p = math.log(p)
    return math.exp(c * log_p / math.log(log_p)) / (
        DUSART_GAP_DENOMINATOR * (log_p**3)
    )


def dusart_log_envelope_derivative(p: float, c: float) -> float:
    """Return d/d(log p) of log U(p,c) for the Dusart envelope."""
    if p < DUSART_X0:
        raise ValueError(f"p must be at least {DUSART_X0} for the Dusart bound")
    log_p = math.log(p)
    log_log_p = math.log(log_p)
    return c * (log_log_p - 1.0) / (log_log_p**2) - 3.0 / log_p


def dusart_envelope_crossover(c: float, start: int = DUSART_X0) -> int:
    """Return the largest integer p where the Dusart envelope stays below 1."""
    low = max(start, DUSART_X0)
    if dusart_bridge_upper_bound(low, c) >= 1.0:
        raise RuntimeError("Dusart envelope is already at or above 1 at its start")

    high = low
    for _ in range(80):
        high *= 2
        if dusart_bridge_upper_bound(high, c) >= 1.0:
            break
    else:
        raise RuntimeError("failed to find a Dusart envelope crossover below 2^(80) * start")

    while low + 1 < high:
        mid = (low + high) // 2
        if dusart_bridge_upper_bound(mid, c) < 1.0:
            low = mid
        else:
            high = mid

    return low


def load_finite_base(artifact_path: Path) -> dict[str, float | int]:
    """Load the exact verified finite-base summary from JSON."""
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    return {
        "earlier_candidate_count": int(payload["earlier_candidate_count"]),
        "bridge_failure_count": int(payload["bridge_failure_count"]),
        "max_bridge_load": float(payload["max_bridge_load"]),
    }


def format_repo_path(path: Path) -> str:
    """Return a repo-relative string when the path is inside the workspace."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def build_dusart_bounded_case(c: float, verified_hi: int) -> dict[str, object]:
    """Return the bounded unconditional bridge interval implied by Dusart."""
    coverage_hi = dusart_envelope_crossover(c)
    derivative_at_start = dusart_log_envelope_derivative(DUSART_X0, c)
    upper_at_verified_base = None
    if verified_hi - 1 >= DUSART_X0:
        upper_at_verified_base = dusart_bridge_upper_bound(verified_hi - 1, c)

    return {
        "gap_bound": "Dusart (2018)",
        "c": c,
        "coverage_lo_inclusive": DUSART_X0,
        "coverage_hi_inclusive": coverage_hi,
        "bridge_upper_bound_at_dusart_start": dusart_bridge_upper_bound(DUSART_X0, c),
        "bridge_upper_bound_at_verified_base": upper_at_verified_base,
        "log_envelope_derivative_at_dusart_start": derivative_at_start,
        "envelope_increasing_from_dusart_start": derivative_at_start > 0.0,
        "finite_base_within_coverage": coverage_hi >= verified_hi - 1,
    }


def build_report(
    theta: float,
    c: float,
    gap_constant: float,
    verified_hi: int,
    artifact_path: Path,
) -> dict[str, object]:
    """Return the certificate payload."""
    n0 = compute_explicit_n0(
        theta=theta,
        c=c,
        gap_constant=gap_constant,
        start=16,
    )
    finite_base = load_finite_base(artifact_path)

    finite_base_covers_bridge = (
        finite_base["bridge_failure_count"] == 0 and n0 <= verified_hi - 1
    )

    return {
        "parameters": {
            "theta": theta,
            "c": c,
            "gap_constant": gap_constant,
            "verified_hi": verified_hi,
            "artifact": format_repo_path(artifact_path),
        },
        "explicit_n0": n0,
        "bridge_upper_bound_at_n0": bridge_upper_bound(n0, theta, c, gap_constant),
        "bridge_upper_bound_at_verified_base": bridge_upper_bound(
            verified_hi - 1,
            theta,
            c,
            gap_constant,
        ),
        "finite_base": finite_base,
        "finite_base_covers_bridge": finite_base_covers_bridge,
        "dusart_bounded_case": build_dusart_bounded_case(c, verified_hi),
    }


def print_human_summary(report: dict[str, object]) -> None:
    """Print a compact human-readable summary."""
    params = report["parameters"]
    finite_base = report["finite_base"]
    dusart = report["dusart_bounded_case"]
    print(
        "Conditional BHP tail parameters: "
        f"theta={params['theta']}, c={params['c']}, A={params['gap_constant']}"
    )
    print(f"Conditional BHP tail N0 from chosen constants: {int(report['explicit_n0']):,}")
    print(
        "Conditional BHP bridge upper bound at N0: "
        f"{float(report['bridge_upper_bound_at_n0']):.6e}"
    )
    print(
        "Conditional BHP bridge upper bound at verified base: "
        f"{float(report['bridge_upper_bound_at_verified_base']):.6e}"
    )
    print()
    print("Dusart bounded unconditional regime:")
    print(
        "  Coverage: "
        f"{int(dusart['coverage_lo_inclusive']):,} <= p <= "
        f"{int(dusart['coverage_hi_inclusive']):,}"
    )
    print(
        "  Bridge upper bound at Dusart start: "
        f"{float(dusart['bridge_upper_bound_at_dusart_start']):.6e}"
    )
    if dusart["bridge_upper_bound_at_verified_base"] is not None:
        print(
            "  Bridge upper bound at verified base: "
            f"{float(dusart['bridge_upper_bound_at_verified_base']):.6e}"
        )
    print(
        "  Log-envelope derivative at Dusart start: "
        f"{float(dusart['log_envelope_derivative_at_dusart_start']):.6e}"
    )
    print(
        "  Envelope increasing from Dusart start: "
        f"{bool(dusart['envelope_increasing_from_dusart_start'])}"
    )
    print("  Note: bounded unconditional coverage only; no universal tail under Dusart.")
    print()
    print("Finite base:")
    print(f"  Earlier candidates checked: {int(finite_base['earlier_candidate_count']):,}")
    print(f"  Max realized bridge load: {float(finite_base['max_bridge_load']):.12f}")
    print(f"  Bridge failures: {int(finite_base['bridge_failure_count'])}")
    print()
    if bool(report["finite_base_covers_bridge"]):
        print(
            "Conditional tail status: provided BHP constants place the tail "
            "threshold at or below the verified base."
        )
    else:
        print(
            "Conditional tail status: provided BHP constants do not yet place "
            "the tail threshold at the verified base."
        )
    if bool(dusart["finite_base_within_coverage"]):
        print("Dusart status: the verified finite base lies inside the bounded unconditional regime.")
    else:
        print("Dusart status: the verified finite base extends beyond the bounded unconditional regime.")


def main(argv: list[str] | None = None) -> int:
    """Run the certificate helper."""
    args = build_parser().parse_args(argv)
    report = build_report(
        theta=args.theta,
        c=args.c,
        gap_constant=args.gap_constant,
        verified_hi=args.verified_hi,
        artifact_path=args.artifact,
    )
    print_human_summary(report)
    print()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

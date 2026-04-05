#!/usr/bin/env python3
"""Compute a proof-bridge certificate from explicit large-p constants."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT = ROOT / "output" / "gwr_proof" / "asymptotic_bridge_load_scan_2e7.json"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the large-p bridge bound B(k,w) < A * p^(theta-1) / log(p) * "
            "exp(c log(p)/log log(p)) against the exact verified base surface."
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


def load_finite_base(artifact_path: Path) -> dict[str, float | int]:
    """Load the exact verified finite-base summary from JSON."""
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    return {
        "earlier_candidate_count": int(payload["earlier_candidate_count"]),
        "bridge_failure_count": int(payload["bridge_failure_count"]),
        "max_bridge_load": float(payload["max_bridge_load"]),
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
        start=max(16, verified_hi - 1),
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
            "artifact": str(artifact_path),
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
    }


def print_human_summary(report: dict[str, object]) -> None:
    """Print a compact human-readable summary."""
    params = report["parameters"]
    finite_base = report["finite_base"]
    print(
        "Explicit bridge parameters: "
        f"theta={params['theta']}, c={params['c']}, A={params['gap_constant']}"
    )
    print(f"Explicit N0 from chosen constants: {int(report['explicit_n0']):,}")
    print(
        "Bridge upper bound at N0: "
        f"{float(report['bridge_upper_bound_at_n0']):.6e}"
    )
    print(
        "Bridge upper bound at verified base: "
        f"{float(report['bridge_upper_bound_at_verified_base']):.6e}"
    )
    print()
    print("Finite base:")
    print(f"  Earlier candidates checked: {int(finite_base['earlier_candidate_count']):,}")
    print(f"  Max realized bridge load: {float(finite_base['max_bridge_load']):.12f}")
    print(f"  Bridge failures: {int(finite_base['bridge_failure_count'])}")
    print()
    if bool(report["finite_base_covers_bridge"]):
        print("Certificate status: provided constants close the bridge at or below the verified base.")
    else:
        print(
            "Certificate status: provided constants do not yet close the bridge "
            "at the verified base; extend the exact scan or improve the explicit constants."
        )


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

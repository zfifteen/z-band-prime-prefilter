#!/usr/bin/env python3
"""Test whether the current earlier-spoiler inequality alone yields a finite class bound."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class WitnessRow:
    """One explicit unresolved divisor-class witness for the current reduction."""

    m: int
    winner_divisor_count: int
    earlier_divisor_count: int
    earlier_value: int
    earlier_value_divisor_count: int
    theorem_threshold: int
    theorem_eliminates_candidate: bool

    def to_dict(self) -> dict[str, int | bool]:
        """Return a JSON-ready mapping."""
        return asdict(self)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Test whether the current earlier-spoiler inequality alone yields "
            "a finite divisor-class obstruction bound."
        ),
    )
    parser.add_argument(
        "--max-m",
        type=int,
        default=20,
        help=(
            "Largest witness-family index to emit. "
            "The obstruction family starts at m = 4."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON output path.",
    )
    return parser


def witness_row(m: int) -> WitnessRow:
    """Construct one explicit unresolved divisor-class witness."""
    if m < 4:
        raise ValueError("witness family starts at m = 4")

    winner_divisor_count = (2 * m) - 1
    earlier_divisor_count = 2 * m
    earlier_value = 3 * (2 ** (m - 1))
    theorem_threshold = 2 ** (winner_divisor_count - 2)

    return WitnessRow(
        m=m,
        winner_divisor_count=winner_divisor_count,
        earlier_divisor_count=earlier_divisor_count,
        earlier_value=earlier_value,
        earlier_value_divisor_count=earlier_divisor_count,
        theorem_threshold=theorem_threshold,
        theorem_eliminates_candidate=earlier_value >= theorem_threshold,
    )


def analyze_current_reduction(max_m: int) -> dict[str, object]:
    """Return the exact status of the current class-only inequality test."""
    if max_m < 4:
        raise ValueError("max_m must be at least 4")

    witnesses = [witness_row(m) for m in range(4, max_m + 1)]
    if any(row.theorem_eliminates_candidate for row in witnesses):
        raise RuntimeError("obstruction family construction is inconsistent")

    return {
        "proof_note_target": "class-only earlier-spoiler inequality test",
        "current_reduction": (
            "If an earlier spoiler with divisor counts D > delta beats the "
            "winner-class candidate, then a^(D-delta) < 2^(delta-2)."
        ),
        "route_b3_closed": None,
        "result": (
            "The current inequality alone leaves an infinite unresolved "
            "divisor-class family."
        ),
        "obstruction_family": {
            "parameter": "m >= 4",
            "winner_divisor_count": "delta = 2m - 1",
            "earlier_divisor_count": "D = 2m",
            "earlier_value": "a = 3 * 2^(m - 1)",
            "exact_divisor_identity": "d(a) = 2m",
            "unresolved_inequality": "a = 3 * 2^(m - 1) < 2^(2m - 3) = 2^(delta - 2)",
        },
        "scope_limit": (
            "This script does not construct an actual prime gap, an actual "
            "winner value w, or prove that the witness classes occur as a "
            "winner/earlier pair inside a prime gap."
        ),
        "why_route_b3_fails": [
            "Each witness is a valid divisor-class instance for the current inequality.",
            "Each witness remains unresolved because D - delta = 1 and a < 2^(delta - 2).",
            "The witness values a = 3 * 2^(m - 1) grow without bound as m grows.",
            "So the inequality alone leaves unresolved class instances at arbitrarily large values.",
            "By itself, this does not settle whether actual prime-gap admissibility closes the whole finite-reduction route.",
        ],
        "witness_rows": [row.to_dict() for row in witnesses],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the finite-remainder attempt and emit a JSON artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = analyze_current_reduction(args.max_m)
    serialized = json.dumps(payload, indent=2)

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

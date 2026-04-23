#!/usr/bin/env python3
"""Document the exact three-gap PGS neighborhood around one modulus."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import gmpy2


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment
from z_band_prime_predictor import (
    d4_gap_profile,
    divisor_gap_profile,
    gap_dmin,
    gwr_next_gap_profile,
    gwr_next_prime,
    next_prime_after,
)


DEFAULT_OUTPUT_DIR = ROOT / "output" / "semiprime_branch"
SCAN_BLOCK = 64
MAX_FIELD_VALUE = (1 << 63) - 1 - SCAN_BLOCK


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        description="Document the exact three-gap PGS neighborhood around one modulus.",
    )
    parser.add_argument(
        "--n",
        required=True,
        help="Odd composite modulus N, in decimal or 0x-prefixed hexadecimal.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the JSON summary and Markdown report.",
    )
    return parser


def parse_modulus(text: str) -> int:
    """Parse one modulus string in decimal or 0x-prefixed hexadecimal."""
    try:
        value = int(text, 0)
    except ValueError as exc:
        raise ValueError(f"unable to parse modulus {text!r}") from exc
    return value


def validate_modulus(n: int) -> None:
    """Validate that one modulus fits the current exact neighborhood probe."""
    if n <= 3:
        raise ValueError("N must be greater than 3")
    if n % 2 == 0:
        raise ValueError("N must be odd")
    if gmpy2.is_prime(n):
        raise ValueError("N must be composite")
    if n > MAX_FIELD_VALUE:
        raise ValueError(
            f"N={n} exceeds the current exact divisor-field range {MAX_FIELD_VALUE}"
        )


def previous_prime_before(n: int, block: int = SCAN_BLOCK) -> int:
    """Return the largest prime less than or equal to n by exact leftward scan."""
    if n < 2:
        raise ValueError("no prime exists below 2")
    if block < 1:
        raise ValueError("block must be positive")

    search_hi = n + 1
    while search_hi > 2:
        search_lo = max(2, search_hi - block)
        counts = divisor_counts_segment(search_lo, search_hi)
        for index in range(len(counts) - 1, -1, -1):
            if int(counts[index]) == 2:
                return search_lo + index
        search_hi = search_lo

    raise RuntimeError(f"failed to find a prime at or below {n}")


def prime_cube_root(n: int) -> int | None:
    """Return the prime cube root of n when n is exactly p^3."""
    root, exact = gmpy2.iroot(gmpy2.mpz(n), 3)
    if not exact or not gmpy2.is_prime(root):
        return None
    return int(root)


def carrier_family(n: int, divisor_count: int) -> str:
    """Return the coarse carrier family for one exact composite interior value."""
    if divisor_count < 3:
        raise ValueError("divisor_count must describe one composite interior value")
    if divisor_count == 3:
        return "prime_square"
    if divisor_count == 4:
        if prime_cube_root(n) is not None:
            return "prime_cube"
        if n % 2 == 0:
            return "even_semiprime"
        return "odd_semiprime"
    if n % 2 == 0:
        return "higher_divisor_even"
    return "higher_divisor_odd"


def artifact_stem(n: int) -> str:
    """Return the deterministic artifact stem for one modulus."""
    hex_body = format(n, "x")
    padded = hex_body.rjust(8, "0")
    prefix = padded[:8]
    suffix = padded[-8:]
    return f"pgs_modulus_gap_orientation_{n.bit_length()}bit_{prefix}_{suffix}"


def _interior_rows(left_prime: int, right_prime: int, winner: int | None) -> list[dict[str, object]]:
    """Return the full exact interior table for one prime gap."""
    if right_prime - left_prime <= 1:
        return []

    values = list(range(left_prime + 1, right_prime))
    counts = divisor_counts_segment(left_prime + 1, right_prime)
    dmin = min(int(raw_d) for raw_d in counts)
    first_dmin = None
    first_d4 = None
    for value, raw_d in zip(values, counts):
        d = int(raw_d)
        if first_dmin is None and d == dmin:
            first_dmin = value
        if first_d4 is None and d == 4:
            first_d4 = value

    rows: list[dict[str, object]] = []
    for value, raw_d in zip(values, counts):
        d = int(raw_d)
        rows.append(
            {
                "n": value,
                "offset": value - left_prime,
                "d": d,
                "L": (1.0 - d / 2.0) * math.log(value),
                "carrier_family": carrier_family(value, d),
                "is_gwr_winner": value == winner,
                "is_first_dmin": value == first_dmin,
                "is_first_d4": value == first_d4,
            }
        )
    return rows


def build_gap_payload(role: str, left_prime: int, right_prime: int, n: int) -> dict[str, object]:
    """Return one exact gap payload in the fixed milestone schema."""
    profile = gwr_next_gap_profile(left_prime, block=SCAN_BLOCK)
    if int(profile["next_prime"]) != right_prime:
        raise AssertionError(
            f"gap mismatch for role={role}: expected right_prime={right_prime}, "
            f"got {profile['next_prime']}"
        )

    winner_offset = profile["winner_offset"]
    winner_d = profile["winner_d"]
    winner = None if winner_offset is None else left_prime + int(winner_offset)
    contains_n = bool(left_prime < n < right_prime)
    payload = {
        "role": role,
        "left_prime": left_prime,
        "right_prime": right_prime,
        "gap_width": right_prime - left_prime,
        "has_interior": right_prime - left_prime > 1,
        "contains_n": contains_n,
        "n_offset_from_left": (n - left_prime) if contains_n else None,
        "n_offset_from_right": (right_prime - n) if contains_n else None,
        "winner": winner,
        "winner_d": None if winner_d is None else int(winner_d),
        "winner_offset": None if winner_offset is None else int(winner_offset),
        "carrier_family": None if winner is None else carrier_family(int(winner), int(winner_d)),
        "dmin": gap_dmin(left_prime, right_prime),
        "d3_profile": divisor_gap_profile(left_prime, right_prime, 3),
        "d4_profile": d4_gap_profile(left_prime, right_prime),
        "interior_rows": _interior_rows(left_prime, right_prime, winner),
    }
    return payload


def orient_modulus(n: int) -> dict[str, object]:
    """Return the exact three-gap neighborhood summary around one modulus."""
    validate_modulus(n)

    p_left = previous_prime_before(n - 1, block=SCAN_BLOCK)
    p_right = next_prime_after(n, block=SCAN_BLOCK)
    p_prev = previous_prime_before(p_left - 1, block=SCAN_BLOCK)
    p_next = gwr_next_prime(p_right, block=SCAN_BLOCK)

    gaps = [
        build_gap_payload("previous", p_prev, p_left, n),
        build_gap_payload("containing", p_left, p_right, n),
        build_gap_payload("following", p_right, p_next, n),
    ]

    return {
        "n": n,
        "n_hex": format(n, "x"),
        "n_bits": n.bit_length(),
        "scan_block": SCAN_BLOCK,
        "p_prev": p_prev,
        "p_left": p_left,
        "p_right": p_right,
        "p_next": p_next,
        "containing_gap_width": p_right - p_left,
        "n_offset_from_left": n - p_left,
        "n_offset_from_right": p_right - n,
        "gaps": gaps,
    }


def _markdown_value(value: object) -> str:
    """Render one stable Markdown scalar."""
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def _render_summary_table(gap: dict[str, object]) -> str:
    """Render the short summary table for one gap section."""
    rows = [
        ("left_prime", gap["left_prime"]),
        ("right_prime", gap["right_prime"]),
        ("gap_width", gap["gap_width"]),
        ("has_interior", gap["has_interior"]),
        ("contains_n", gap["contains_n"]),
        ("n_offset_from_left", gap["n_offset_from_left"]),
        ("n_offset_from_right", gap["n_offset_from_right"]),
        ("dmin", gap["dmin"]),
        ("winner", gap["winner"]),
        ("winner_d", gap["winner_d"]),
        ("winner_offset", gap["winner_offset"]),
        ("carrier_family", gap["carrier_family"]),
    ]
    lines = [
        "| field | value |",
        "|---|---|",
    ]
    for key, value in rows:
        lines.append(f"| {key} | {_markdown_value(value)} |")
    return "\n".join(lines)


def _render_interior_table(gap: dict[str, object]) -> str:
    """Render the full interior Markdown table for one gap."""
    lines = [
        "| n | offset | d | L | carrier_family | is_gwr_winner | is_first_dmin | is_first_d4 |",
        "|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in gap["interior_rows"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_value(row["n"]),
                    _markdown_value(row["offset"]),
                    _markdown_value(row["d"]),
                    _markdown_value(row["L"]),
                    _markdown_value(row["carrier_family"]),
                    _markdown_value(row["is_gwr_winner"]),
                    _markdown_value(row["is_first_dmin"]),
                    _markdown_value(row["is_first_d4"]),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_report(summary: dict[str, object]) -> str:
    """Render the human-readable Markdown report for one modulus."""
    p_prev = summary["p_prev"]
    p_left = summary["p_left"]
    n = summary["n"]
    p_right = summary["p_right"]
    p_next = summary["p_next"]
    lines = [
        "# PGS Modulus Gap Orientation",
        "",
        "## Modulus Anchor",
        "",
        f"- `N = {n}`",
        f"- `hex = 0x{summary['n_hex']}`",
        f"- `bits = {summary['n_bits']}`",
        f"- `scan_block = {summary['scan_block']}`",
        "",
        f"`{p_prev} < {p_left} < {n} < {p_right} < {p_next}`",
        "",
        "## Containing-Gap Position",
        "",
        f"- containing gap: `({p_left}, {p_right})`",
        f"- gap width: `{summary['containing_gap_width']}`",
        f"- offset from left prime: `{summary['n_offset_from_left']}`",
        f"- offset from right prime: `{summary['n_offset_from_right']}`",
    ]

    for gap in summary["gaps"]:
        lines.extend(
            [
                "",
                f"## {str(gap['role']).capitalize()} Gap",
                "",
                _render_summary_table(gap),
                "",
            ]
        )
        if gap["winner"] is None:
            lines.append("Exact GWR winner: none.")
        else:
            lines.append(
                "Exact GWR winner: "
                f"`{gap['winner']}` with `d={gap['winner_d']}`, "
                f"offset `{gap['winner_offset']}`, family `{gap['carrier_family']}`."
            )
        lines.extend(
            [
                "",
                _render_interior_table(gap),
            ]
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """Run the exact modulus-orientation milestone and emit artifacts."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        n = parse_modulus(args.n)
        summary = orient_modulus(n)
    except ValueError as exc:
        parser.exit(2, f"{parser.prog}: error: {exc}\n")

    report = render_report(summary)
    stem = artifact_stem(n)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / f"{stem}_summary.json"
    report_path = args.output_dir / f"{stem}_report.md"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(report, encoding="utf-8")
    print(summary_path)
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Near-miss profile for higher-divisor pressure lock abstentions."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .composite_exclusion_boundary_probe import (
        certified_divisor_class,
        run_probe,
    )
    from .higher_divisor_pressure_lock_activation_profile import first_open_offset
    from .resolved_boundary_absorption_safety_probe import (
        candidate_carrier,
        carrier_identity,
    )
    from .resolved_boundary_lock_separator_probe import (
        candidate_record_by_offset,
        gap_width_class,
        jsonable,
    )
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from composite_exclusion_boundary_probe import (
        certified_divisor_class,
        run_probe,
    )
    from higher_divisor_pressure_lock_activation_profile import first_open_offset
    from resolved_boundary_absorption_safety_probe import (
        candidate_carrier,
        carrier_identity,
    )
    from resolved_boundary_lock_separator_probe import (
        candidate_record_by_offset,
        gap_width_class,
        jsonable,
    )


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")
SUMMARY_FILENAME = "lock_near_miss_profile_summary.json"
RECORDS_FILENAME = "lock_near_miss_profile_records.jsonl"
DEFAULT_SURFACES = ("11..1000000", "100000..200000", "1000000..1100000")
ELIGIBLE_CARRIER_FAMILIES = {
    "known_basis_prime_power",
    "known_basis_semiprime",
}


def build_parser() -> argparse.ArgumentParser:
    """Build the near-miss profiler CLI."""
    parser = argparse.ArgumentParser(
        description="Offline near-miss profile for higher-divisor pressure lock.",
    )
    parser.add_argument(
        "--surfaces",
        nargs="+",
        default=list(DEFAULT_SURFACES),
        help="Inclusive anchor surfaces formatted as START..MAX.",
    )
    parser.add_argument(
        "--candidate-bound",
        type=int,
        default=64,
        help="Largest candidate boundary offset.",
    )
    parser.add_argument(
        "--witness-bound",
        type=int,
        default=97,
        help="Largest positive witness factor.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for JSON and JSONL artifacts.",
    )
    return parser


def parse_surface(surface: str) -> tuple[int, int]:
    """Parse one inclusive surface string."""
    parts = surface.split("..")
    if len(parts) != 2:
        raise ValueError(f"surface must be START..MAX: {surface}")
    start_anchor = int(parts[0].replace("_", ""))
    max_anchor = int(parts[1].replace("_", ""))
    if max_anchor < start_anchor:
        raise ValueError(f"surface max must be >= start: {surface}")
    return start_anchor, max_anchor


def pressure_signature(record: dict[str, Any]) -> str:
    """Return a compact pressure signature token."""
    higher = len(record["higher_divisor_pressure_between_candidate_and_later_unresolved"])
    reset = len(record["reset_evidence_between_candidate_and_later_unresolved"])
    square = len(record["square_pressure_between_candidate_and_later_unresolved"])
    semiprime = len(record["semiprime_pressure_between_candidate_and_later_unresolved"])
    return f"H{higher}_R{reset}_S{square}_SP{semiprime}"


def pressure_offsets(
    anchor_p: int,
    start_offset: int,
    stop_offset: int,
    carrier_d: int | None,
    witness_bound: int,
) -> dict[str, list[int]]:
    """Return legal pressure offsets in one open interval."""
    pressure = {
        "higher_divisor_pressure_offsets": [],
        "reset_evidence_offsets": [],
        "square_pressure_offsets": [],
        "semiprime_pressure_offsets": [],
    }
    if carrier_d is None:
        return pressure
    for offset in range(start_offset + 1, stop_offset):
        certificate = certified_divisor_class(anchor_p + offset, witness_bound)
        if certificate is None:
            continue
        divisor_class = int(certificate["divisor_class"])
        family = str(certificate["family"])
        if divisor_class > int(carrier_d):
            pressure["higher_divisor_pressure_offsets"].append(offset)
        if divisor_class <= int(carrier_d):
            pressure["reset_evidence_offsets"].append(offset)
        if family == "known_basis_semiprime":
            pressure["semiprime_pressure_offsets"].append(offset)
        payload = certificate["certificate"]
        if (
            family == "known_basis_prime_power"
            and int(payload.get("exponent", 0)) == 2
        ):
            pressure["square_pressure_offsets"].append(offset)
    return pressure


def previous_chamber_signal(previous_gap_width: int | None) -> bool:
    """Return whether previous gap memory lies in the activating width regime."""
    return previous_gap_width is not None and previous_gap_width <= 16


def reason_tags_for_record(
    record: dict[str, Any],
    false_resolved_survivors: list[int],
    higher_before_candidate: list[int],
    higher_after_later_unresolved: list[int],
) -> list[str]:
    """Return deterministic abstention reason tags."""
    tags = ["missing_higher_divisor_pressure"]
    if higher_before_candidate or higher_after_later_unresolved:
        tags.append("wrong_pressure_location")
    if higher_after_later_unresolved:
        tags.append("pressure_appears_after_unresolved_alternative")
    if record["carrier_family"] not in ELIGIBLE_CARRIER_FAMILIES:
        tags.append("carrier_not_in_eligible_family")
    if not false_resolved_survivors:
        tags.append("no_resolved_false_survivor_pair")
    if record["square_pressure_between_candidate_and_later_unresolved"]:
        tags.append("square_pressure_instead_of_higher_divisor_pressure")
    if record["semiprime_pressure_between_candidate_and_later_unresolved"]:
        tags.append("semiprime_pressure_instead_of_higher_divisor_pressure")
    previous_gap_width = record["previous_chamber_pressure"]["previous_gap_width"]
    if previous_chamber_signal(previous_gap_width):
        tags.append("previous_chamber_signal_present")
    has_lock_signature = any(
        (
            bool(record["reset_evidence_between_candidate_and_later_unresolved"]),
            bool(record["square_pressure_between_candidate_and_later_unresolved"]),
            bool(record["semiprime_pressure_between_candidate_and_later_unresolved"]),
            bool(record["extension_changes_carrier"]),
            previous_chamber_signal(previous_gap_width),
        )
    )
    if not has_lock_signature:
        tags.append("no_carrier_lock_signature")
    return tags


def substitute_tags_for_record(
    record: dict[str, Any],
    higher_before_candidate: list[int],
    higher_after_later_unresolved: list[int],
) -> list[str]:
    """Return pressure substitutes present in one abstention."""
    tags: list[str] = []
    if record["square_pressure_between_candidate_and_later_unresolved"]:
        tags.append("square_pressure")
    if record["semiprime_pressure_between_candidate_and_later_unresolved"]:
        tags.append("semiprime_pressure")
    if record["reset_evidence_between_candidate_and_later_unresolved"]:
        tags.append("reset_evidence")
    if bool(record["extension_changes_carrier"]):
        tags.append("carrier_extension_change")
    previous_gap_width = record["previous_chamber_pressure"]["previous_gap_width"]
    if previous_chamber_signal(previous_gap_width):
        tags.append("previous_chamber_signal")
    if higher_before_candidate or higher_after_later_unresolved:
        tags.append("higher_divisor_wrong_location")
    if not tags:
        tags.append("no_pressure_substitute")
    return tags


def near_miss_record(
    row: dict[str, Any],
    previous_row: dict[str, Any] | None,
    witness_bound: int,
    candidate_bound: int,
) -> dict[str, Any] | None:
    """Return one near-miss record for the resolved true boundary."""
    anchor_p = int(row["anchor_p"])
    actual = int(row["actual_boundary_offset_label"])
    survivors = [int(offset) for offset in row["survivors"]]
    unresolved = [int(offset) for offset in row["unresolved"]]
    if actual not in survivors:
        return None
    later_unresolved = [offset for offset in unresolved if offset > actual]
    if not later_unresolved:
        return None
    candidate = candidate_record_by_offset(row, actual)
    carrier = candidate_carrier(anchor_p, actual, witness_bound)
    carrier_d = carrier["carrier_d"]
    pressure_to_later = pressure_offsets(
        anchor_p,
        actual,
        max(later_unresolved),
        carrier_d,
        witness_bound,
    )
    if pressure_to_later["higher_divisor_pressure_offsets"]:
        return None

    pressure_before_candidate = pressure_offsets(
        anchor_p,
        0,
        actual,
        carrier_d,
        witness_bound,
    )
    pressure_after_later_unresolved = pressure_offsets(
        anchor_p,
        max(later_unresolved),
        candidate_bound + 1,
        carrier_d,
        witness_bound,
    )
    later_carrier_identities = [
        carrier_identity(candidate_carrier(anchor_p, offset, witness_bound))
        for offset in later_unresolved
    ]
    carrier_id = carrier_identity(carrier)
    extension_changes_carrier = any(
        identity != carrier_id for identity in later_carrier_identities
    )
    previous_gap_width = (
        None if previous_row is None else anchor_p - int(previous_row["anchor_p"])
    )
    record = {
        "carrier_offset": carrier["carrier_offset"],
        "carrier_divisor_count": carrier_d,
        "carrier_family": carrier["carrier_family"],
        "reset_evidence_between_candidate_and_later_unresolved": (
            pressure_to_later["reset_evidence_offsets"]
        ),
        "higher_divisor_pressure_between_candidate_and_later_unresolved": (
            pressure_to_later["higher_divisor_pressure_offsets"]
        ),
        "square_pressure_between_candidate_and_later_unresolved": (
            pressure_to_later["square_pressure_offsets"]
        ),
        "semiprime_pressure_between_candidate_and_later_unresolved": (
            pressure_to_later["semiprime_pressure_offsets"]
        ),
        "extension_changes_carrier": extension_changes_carrier,
        "previous_chamber_pressure": {
            "previous_anchor_p": (
                None if previous_row is None else int(previous_row["anchor_p"])
            ),
            "previous_gap_width": previous_gap_width,
            "previous_gap_width_class": gap_width_class(previous_gap_width),
        },
    }
    higher_before_candidate = pressure_before_candidate[
        "higher_divisor_pressure_offsets"
    ]
    higher_after_later_unresolved = pressure_after_later_unresolved[
        "higher_divisor_pressure_offsets"
    ]
    false_resolved_survivors = [offset for offset in survivors if offset != actual]
    reason_tags = reason_tags_for_record(
        record,
        false_resolved_survivors,
        higher_before_candidate,
        higher_after_later_unresolved,
    )
    pressure_substitute_tags = substitute_tags_for_record(
        record,
        higher_before_candidate,
        higher_after_later_unresolved,
    )
    return {
        "anchor_p": anchor_p,
        "actual_boundary_offset_label": actual,
        "resolved_candidate_offset": actual,
        "later_unresolved_candidate_offsets": later_unresolved,
        "false_resolved_survivor_offsets": false_resolved_survivors,
        "near_miss_reason_tags": reason_tags,
        "pressure_substitute_tags": pressure_substitute_tags,
        "pressure_signature": pressure_signature(record),
        "carrier_offset": record["carrier_offset"],
        "carrier_divisor_count": carrier_d,
        "carrier_family": record["carrier_family"],
        "first_open_offset": first_open_offset(anchor_p),
        "single_hole_closure_used": bool(
            candidate.get("single_hole_positive_witness_closure")
        ),
        "higher_divisor_before_candidate_offsets": higher_before_candidate,
        "higher_divisor_after_unresolved_offsets": higher_after_later_unresolved,
        "reset_evidence_between_candidate_and_later_unresolved": record[
            "reset_evidence_between_candidate_and_later_unresolved"
        ],
        "square_pressure_between_candidate_and_later_unresolved": record[
            "square_pressure_between_candidate_and_later_unresolved"
        ],
        "semiprime_pressure_between_candidate_and_later_unresolved": record[
            "semiprime_pressure_between_candidate_and_later_unresolved"
        ],
        "extension_changes_carrier": bool(record["extension_changes_carrier"]),
        "previous_gap_width": previous_gap_width,
        "previous_gap_width_class": gap_width_class(previous_gap_width),
    }


def surface_profile(
    surface: str,
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return near-miss records and summary for one surface."""
    start_anchor, max_anchor = parse_surface(surface)
    rows, _ = run_probe(
        start_anchor=start_anchor,
        max_anchor=max_anchor,
        candidate_bound=candidate_bound,
        enable_single_hole_positive_witness_closure=True,
        witness_bound=witness_bound,
        enable_carrier_locked_pressure_ceiling=True,
        carrier_lock_predicate="unresolved_alternatives_before_threat",
        enable_higher_divisor_pressure_locked_absorption=False,
    )
    records: list[dict[str, Any]] = []
    previous_row: dict[str, Any] | None = None
    for row in rows:
        record = near_miss_record(
            row,
            previous_row,
            witness_bound,
            candidate_bound,
        )
        if record is not None:
            records.append(record)
        previous_row = row
    return records, {
        "surface": surface,
        "row_count": len(rows),
        "near_miss_count": len(records),
    }


def count_tag(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    """Return sorted counts from a list-valued tag field."""
    counts: Counter[str] = Counter()
    for record in records:
        counts.update(str(tag) for tag in record[field])
    return {
        key: count
        for key, count in sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0]),
        )
    }


def adjacent_lock_families(
    substitute_counts: dict[str, int],
) -> list[dict[str, Any]]:
    """Return candidate adjacent lock families ranked by observed support."""
    family_map = {
        "square_pressure_lock": "square_pressure",
        "semiprime_wheel_lock": "semiprime_pressure",
        "previous_chamber_reset_lock": "previous_chamber_signal",
        "carrier_extension_absorption_lock": "carrier_extension_change",
        "reset_evidence_lock": "reset_evidence",
        "higher_divisor_location_lock": "higher_divisor_wrong_location",
    }
    rows = [
        {
            "candidate_family": family,
            "supporting_signal": signal,
            "support_count": int(substitute_counts.get(signal, 0)),
        }
        for family, signal in family_map.items()
    ]
    return sorted(
        rows,
        key=lambda row: (-int(row["support_count"]), str(row["candidate_family"])),
    )


def run_profile(
    surfaces: list[str],
    candidate_bound: int,
    witness_bound: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the near-miss profile."""
    started = time.perf_counter()
    all_records: list[dict[str, Any]] = []
    surface_summaries: list[dict[str, Any]] = []
    for surface in surfaces:
        records, summary = surface_profile(
            surface,
            candidate_bound,
            witness_bound,
        )
        all_records.extend(records)
        surface_summaries.append(summary)

    reason_counts = count_tag(all_records, "near_miss_reason_tags")
    substitute_counts = count_tag(all_records, "pressure_substitute_tags")
    families = adjacent_lock_families(substitute_counts)
    best_family = next(
        (
            str(row["candidate_family"])
            for row in families
            if int(row["support_count"]) > 0
        ),
        "NONE",
    )
    summary = {
        "mode": "offline_higher_divisor_pressure_lock_near_miss_profile",
        "surfaces": surfaces,
        "candidate_bound": candidate_bound,
        "witness_bound": witness_bound,
        "near_miss_count": len(all_records),
        "near_miss_reason_counts": reason_counts,
        "top_pressure_substitute_counts": substitute_counts,
        "candidate_adjacent_lock_families": families,
        "best_next_lock_family_candidate": best_family,
        "surface_summaries": surface_summaries,
        "boundary_law_005_status": "candidate_not_approved_for_generation",
        "prime_emission_status": "forbidden",
        "runtime_seconds": time.perf_counter() - started,
    }
    return all_records, summary


def write_artifacts(
    records: list[dict[str, Any]],
    summary: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    """Write LF-terminated JSONL records and JSON summary."""
    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / RECORDS_FILENAME
    with records_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(jsonable(record), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(
        json.dumps(jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "records_path": records_path,
        "summary_path": summary_path,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the near-miss profile and write artifacts."""
    args = build_parser().parse_args(argv)
    records, summary = run_profile(
        surfaces=args.surfaces,
        candidate_bound=args.candidate_bound,
        witness_bound=args.witness_bound,
    )
    write_artifacts(records, summary, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Check whether Grok Solution 1 is testable against current artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOW_INPUTS = [
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_1e5" / "diagnostics.jsonl",
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_1e6" / "diagnostics.jsonl",
]
DEFAULT_HIGH_INPUT = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_GENERATOR = (
    ROOT / "src" / "python" / "z_band_prime_predictor" / "simple_pgs_generator.py"
)
DEFAULT_OUTPUT_DIR = ROOT / "output" / "simple_pgs_solution_01_state_contract_probe"

REQUIRED_FIELDS = {
    "chamber_state": ["chamber_state", "S"],
    "gap_signature": ["gap_signature", "gs"],
    "pressure_vector": ["pressure_vector"],
    "visible_closure_data": ["visible_closure_data", "V"],
    "terminal_pattern": ["terminal_pattern", "T"],
}

TRANSITION_NAMES = [
    "PGS_state_transition",
    "pgs_state_transition",
    "state_transition",
    "terminal_closure_signature",
]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows from one artifact."""
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def flatten_keys(record: object, prefix: str = "") -> set[str]:
    """Return nested keys using both leaf and dotted names."""
    keys: set[str] = set()
    if isinstance(record, dict):
        for key, value in record.items():
            name = str(key)
            dotted = name if not prefix else f"{prefix}.{name}"
            keys.add(name)
            keys.add(dotted)
            keys.update(flatten_keys(value, dotted))
    elif isinstance(record, list):
        for index, value in enumerate(record):
            keys.update(flatten_keys(value, f"{prefix}[{index}]"))
    return keys


def has_alias(keys: set[str], aliases: list[str]) -> bool:
    """Return true when any exact alias is present."""
    return any(alias in keys for alias in aliases)


def summarize_rows(
    dataset: str,
    rows: list[dict[str, object]],
    row_filter: str,
) -> list[dict[str, object]]:
    """Summarize required-field availability for one dataset."""
    if row_filter == "all":
        selected = rows
    else:
        selected = [row for row in rows if row.get("source") == row_filter]

    out: list[dict[str, object]] = []
    for field_name, aliases in REQUIRED_FIELDS.items():
        present_count = 0
        example_present = ""
        for row in selected:
            keys = flatten_keys(row)
            if has_alias(keys, aliases):
                present_count += 1
                if not example_present:
                    example_present = ",".join(sorted(set(aliases) & keys))
        out.append(
            {
                "dataset": dataset,
                "row_filter": row_filter,
                "rows_checked": len(selected),
                "required_object": field_name,
                "aliases": "|".join(aliases),
                "present_count": present_count,
                "present_percent": 0.0
                if not selected
                else 100.0 * present_count / len(selected),
                "example_present_alias": example_present,
            }
        )
    return out


def rows_with_all_required(
    rows: list[dict[str, object]],
    row_filter: str,
) -> int:
    """Count rows carrying every required object."""
    if row_filter == "all":
        selected = rows
    else:
        selected = [row for row in rows if row.get("source") == row_filter]
    count = 0
    for row in selected:
        keys = flatten_keys(row)
        if all(has_alias(keys, aliases) for aliases in REQUIRED_FIELDS.values()):
            count += 1
    return count


def transition_operator_available(generator_path: Path) -> bool:
    """Check whether the named transition operator exists in generator source."""
    text = generator_path.read_text(encoding="utf-8")
    return any(name in text for name in TRANSITION_NAMES)


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    """Write LF-terminated CSV rows."""
    if not rows:
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def write_json(record: dict[str, object], path: Path) -> None:
    """Write LF-terminated JSON."""
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Check whether Grok Solution 1 has its required state."
    )
    parser.add_argument(
        "--low-input",
        action="append",
        type=Path,
        default=None,
        help="Low-scale diagnostics JSONL input. May be repeated.",
    )
    parser.add_argument(
        "--high-input",
        type=Path,
        default=DEFAULT_HIGH_INPUT,
        help="High-scale rows JSONL input.",
    )
    parser.add_argument(
        "--generator",
        type=Path,
        default=DEFAULT_GENERATOR,
        help="Generator source file to scan for transition operator names.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the state-contract probe."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    low_inputs = args.low_input if args.low_input is not None else DEFAULT_LOW_INPUTS
    availability_rows: list[dict[str, object]] = []
    dataset_summaries: list[dict[str, object]] = []

    for path in low_inputs:
        rows = read_jsonl(path)
        dataset = path.parent.name
        availability_rows.extend(summarize_rows(dataset, rows, "PGS"))
        dataset_summaries.append(
            {
                "dataset": dataset,
                "path": str(path.relative_to(ROOT)),
                "rows": len(rows),
                "row_filter": "PGS",
                "rows_with_all_required_objects": rows_with_all_required(rows, "PGS"),
            }
        )

    high_rows = read_jsonl(args.high_input)
    availability_rows.extend(
        summarize_rows(args.high_input.parent.name, high_rows, "shadow_seed_recovery")
    )
    dataset_summaries.append(
        {
            "dataset": args.high_input.parent.name,
            "path": str(args.high_input.relative_to(ROOT)),
            "rows": len(high_rows),
            "row_filter": "shadow_seed_recovery",
            "rows_with_all_required_objects": rows_with_all_required(
                high_rows, "shadow_seed_recovery"
            ),
        }
    )

    operator_present = transition_operator_available(args.generator)
    testable = (
        operator_present
        and all(
            int(row["rows_with_all_required_objects"]) > 0
            for row in dataset_summaries
        )
    )
    missing_objects = [
        field_name
        for field_name, aliases in REQUIRED_FIELDS.items()
        if all(int(row["present_count"]) == 0 for row in availability_rows if row["required_object"] == field_name)
    ]

    summary = {
        "solution_id": "grok_solution_01_shadow_seed_boundary_recovery_law",
        "testable_as_stated": testable,
        "promotion_eligible": False,
        "transition_operator_available": operator_present,
        "transition_operator_names_checked": TRANSITION_NAMES,
        "required_objects": REQUIRED_FIELDS,
        "missing_required_objects_across_tested_artifacts": missing_objects,
        "datasets": dataset_summaries,
        "verdict": "not_testable_as_stated"
        if not testable
        else "state_contract_present_but_rule_not_implemented",
        "reason": ""
        if testable
        else (
            "The proposed law requires chamber_state S, gap signature gs, "
            "pressure_vector, visible_closure_data V, terminal pattern T, and "
            "a named PGS state transition operator. Current minimal-generator "
            "artifacts do not carry that state contract."
        ),
        "next_action": (
            "Reject Solution 1 as a drop-in replacement, or ask for the law "
            "to be restated using only the current certificate and chain fields. "
            "Adding S/gs/V/T would be a new state-capture experiment, not a "
            "test of the submitted rule as written."
        ),
    }

    write_csv(availability_rows, args.output_dir / "field_availability.csv")
    write_json(summary, args.output_dir / "summary.json")
    print(
        "solution_01 testable_as_stated={testable} "
        "transition_operator_available={operator} "
        "missing_objects={missing}".format(
            testable=str(testable).lower(),
            operator=str(operator_present).lower(),
            missing=",".join(missing_objects) if missing_objects else "none",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

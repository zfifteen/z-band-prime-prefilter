"""Test Meta Solution 3: Shadow Seed Frontier Exhaustion."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CANDIDATES = (
    ROOT
    / "output"
    / "simple_pgs_shadow_seed_recovery_displacement_probe"
    / "candidate_rows.csv"
)
DEFAULT_SHADOW_ROWS = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "output" / "simple_pgs_solution_03_frontier_exhaustion_probe"
)


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read CSV rows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows."""
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


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


def grouped_candidate_rows(
    rows: list[dict[str, str]],
) -> dict[tuple[int, int, int], list[dict[str, str]]]:
    """Group materialized candidates by shadow row."""
    groups: dict[tuple[int, int, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (int(row["scale"]), int(row["anchor_p"]), int(row["seed_q0"]))
        groups[key].append(row)
    for group in groups.values():
        group.sort(key=lambda row: int(row["candidate_n"]))
    return dict(groups)


def witness_set(rows: list[dict[str, str]]) -> set[int]:
    """Return materialized visible divisor witnesses."""
    witnesses: set[int] = set()
    for row in rows:
        raw = row["visible_divisor_witness_under_10000"]
        if not raw:
            continue
        witness = int(raw)
        if witness > 1:
            witnesses.add(witness)
    return witnesses


def visible_mark(row: dict[str, str]) -> bool:
    """Return the artifact-native visible closure mark."""
    return bool(row["visible_closure_reason"])


def witness_congruence_mark(
    p: int,
    candidate: int,
    witnesses: set[int],
) -> bool:
    """Return the materialized witness-congruence mark."""
    return any(candidate % witness == p % witness for witness in witnesses)


def odd_candidate(row: dict[str, str]) -> bool:
    """Return whether candidate row is odd."""
    return int(row["candidate_n"]) % 2 == 1


def first_unmarked_after_run(
    rows: list[dict[str, str]],
    mark_by_candidate: dict[int, bool],
    require_odd: bool,
    require_residue_exhaustion: bool,
    p: int,
    seed_q0: int,
    witnesses: set[int],
) -> tuple[int | None, dict[str, object]]:
    """Apply the frontier-exhaustion run rule on materialized rows."""
    stream = [row for row in rows if (not require_odd or odd_candidate(row))]
    if not stream:
        return None, {
            "failure_reason": "empty_stream",
            "run_length": 0,
            "residue_exhausted": False,
            "open_witness_count": len(witnesses),
            "closed_witness_count": 0,
        }

    first = int(stream[0]["candidate_n"])
    if not mark_by_candidate.get(first, False):
        return None, {
            "failure_reason": "first_candidate_unmarked",
            "run_length": 0,
            "residue_exhausted": False,
            "open_witness_count": len(witnesses),
            "closed_witness_count": 0,
        }

    run: list[int] = []
    selected: int | None = None
    for row in stream:
        candidate = int(row["candidate_n"])
        if mark_by_candidate.get(candidate, False):
            run.append(candidate)
            continue
        selected = candidate
        break

    open_witnesses = {
        witness for witness in witnesses if seed_q0 % witness != p % witness
    }
    closed_witnesses = {
        witness
        for witness in open_witnesses
        if any(candidate % witness == p % witness for candidate in run)
    }
    residue_exhausted = closed_witnesses == open_witnesses
    if selected is None:
        return None, {
            "failure_reason": "no_unmarked_candidate_in_materialized_stream",
            "run_length": len(run),
            "residue_exhausted": residue_exhausted,
            "open_witness_count": len(open_witnesses),
            "closed_witness_count": len(closed_witnesses),
        }
    if require_residue_exhaustion and not residue_exhausted:
        return None, {
            "failure_reason": "residue_not_exhausted_at_break",
            "run_length": len(run),
            "residue_exhausted": residue_exhausted,
            "open_witness_count": len(open_witnesses),
            "closed_witness_count": len(closed_witnesses),
        }
    return selected, {
        "failure_reason": "",
        "run_length": len(run),
        "residue_exhausted": residue_exhausted,
        "open_witness_count": len(open_witnesses),
        "closed_witness_count": len(closed_witnesses),
    }


def failure_mode(selected: int | None, true_q: int) -> str:
    """Classify one selected candidate."""
    if selected is None:
        return "no_selection"
    if int(selected) == int(true_q):
        return "correct"
    if int(selected) < int(true_q):
        return "selected_too_early"
    return "selected_too_late"


def build_selection_rows(
    groups: dict[tuple[int, int, int], list[dict[str, str]]],
) -> list[dict[str, object]]:
    """Build one selection row per rule and shadow row."""
    out: list[dict[str, object]] = []
    for (scale, p, seed_q0), rows in sorted(groups.items()):
        true_q = int(rows[0]["recovered_q_for_audit_only"])
        witnesses = witness_set(rows)
        visible_marks = {
            int(row["candidate_n"]): visible_mark(row)
            for row in rows
        }
        witness_marks = {
            int(row["candidate_n"]): witness_congruence_mark(
                p,
                int(row["candidate_n"]),
                witnesses,
            )
            for row in rows
        }
        rule_specs = [
            ("M1_visible_run_all", visible_marks, False, False),
            ("M2_visible_run_odd", visible_marks, True, False),
            ("M3_witness_run_odd", witness_marks, True, False),
            ("M4_witness_run_odd_resclosed", witness_marks, True, True),
        ]
        for rule_id, marks, require_odd, require_residue in rule_specs:
            selected, details = first_unmarked_after_run(
                rows,
                marks,
                require_odd,
                require_residue,
                p,
                seed_q0,
                witnesses,
            )
            out.append(
                {
                    "scale": scale,
                    "rule_id": rule_id,
                    "anchor_p": p,
                    "seed_q0": seed_q0,
                    "true_q_for_audit_only": true_q,
                    "selected_q": "" if selected is None else selected,
                    "selected_delta_from_true": ""
                    if selected is None
                    else selected - true_q,
                    "failure_mode": failure_mode(selected, true_q),
                    "run_length": details["run_length"],
                    "failure_reason": details["failure_reason"],
                    "residue_exhausted": details["residue_exhausted"],
                    "open_witness_count": details["open_witness_count"],
                    "closed_witness_count": details["closed_witness_count"],
                    "materialized_witness_count": len(witnesses),
                }
            )
    return out


def rate(count: int, total: int) -> float:
    """Return count / total."""
    return 0.0 if int(total) == 0 else int(count) / int(total)


def summarize(selection_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Summarize rule outcomes."""
    base_pgs_counts = {10**12: 151, 10**15: 108, 10**18: 105}
    emitted_counts = {10**12: 253, 10**15: 249, 10**18: 250}
    groups: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for row in selection_rows:
        groups[(int(row["scale"]), str(row["rule_id"]))].append(row)

    out: list[dict[str, object]] = []
    for (scale, rule_id), rows in sorted(groups.items()):
        correct = sum(1 for row in rows if row["failure_mode"] == "correct")
        no_selection = sum(1 for row in rows if row["failure_mode"] == "no_selection")
        too_early = sum(1 for row in rows if row["failure_mode"] == "selected_too_early")
        too_late = sum(1 for row in rows if row["failure_mode"] == "selected_too_late")
        audit_failed = len(rows) - correct - no_selection
        emitted = emitted_counts.get(scale, 0)
        projected_pgs = base_pgs_counts.get(scale, 0) + correct
        out.append(
            {
                "scale": scale,
                "rule_id": rule_id,
                "shadow_seed_rows": len(rows),
                "correct": correct,
                "correct_percent": rate(correct, len(rows)) * 100.0,
                "no_selection": no_selection,
                "selected_too_early": too_early,
                "selected_too_late": too_late,
                "audit_failed_if_promoted": audit_failed,
                "projected_pgs_count": projected_pgs,
                "projected_pgs_percent": rate(projected_pgs, emitted) * 100.0,
                "promotion_eligible": (
                    no_selection == 0
                    and audit_failed == 0
                    and emitted > 0
                    and rate(projected_pgs, emitted) >= 0.50
                ),
            }
        )
    return out


def materialized_contract_report(fieldnames: list[str]) -> list[dict[str, object]]:
    """Report whether submitted SFE inputs are present as materialized fields."""
    required = {
        "W_p": ["W_p", "witness_moduli", "witness_moduli_set"],
        "Open(q0)": ["Open(q0)", "open_q0", "open_residues_at_q0"],
        "S_p(t)": ["S_p", "mark_indicator", "mark"],
    }
    fields = set(fieldnames)
    out: list[dict[str, object]] = []
    for object_name, aliases in required.items():
        present = [alias for alias in aliases if alias in fields]
        out.append(
            {
                "required_object": object_name,
                "aliases_checked": "|".join(aliases),
                "present": bool(present),
                "present_field": "|".join(present),
            }
        )
    return out


def materialized_coverage_rows(
    shadow_rows: list[dict[str, object]],
    groups: dict[tuple[int, int, int], list[dict[str, str]]],
) -> list[dict[str, object]]:
    """Return materialized candidate coverage by scale."""
    expected: dict[int, int] = defaultdict(int)
    materialized: dict[int, int] = defaultdict(int)
    for row in shadow_rows:
        if row.get("source") != "shadow_seed_recovery":
            continue
        expected[int(row["scale"])] += 1
    for scale, _p, _seed_q0 in groups:
        materialized[int(scale)] += 1
    out: list[dict[str, object]] = []
    for scale in sorted(set(expected) | set(materialized)):
        out.append(
            {
                "scale": scale,
                "expected_shadow_seed_rows": expected.get(scale, 0),
                "materialized_candidate_groups": materialized.get(scale, 0),
                "missing_candidate_groups": expected.get(scale, 0)
                - materialized.get(scale, 0),
                "coverage_percent": 0.0
                if expected.get(scale, 0) == 0
                else 100.0 * materialized.get(scale, 0) / expected[scale],
            }
        )
    return out


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Test Shadow Seed Frontier Exhaustion on materialized rows."
    )
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--shadow-rows", type=Path, default=DEFAULT_SHADOW_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    """Run the probe."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_rows = read_csv(args.candidate_rows)
    shadow_rows = read_jsonl(args.shadow_rows)
    fieldnames = list(candidate_rows[0]) if candidate_rows else []
    groups = grouped_candidate_rows(candidate_rows)
    coverage_rows = materialized_coverage_rows(shadow_rows, groups)
    selection_rows = build_selection_rows(groups)
    summary_rows = summarize(selection_rows)
    contract_rows = materialized_contract_report(fieldnames)
    payload = {
        "solution_id": "meta_solution_03_shadow_seed_frontier_exhaustion",
        "generator_changed": False,
        "materialized_shadow_groups": len(groups),
        "selection_rows": len(selection_rows),
        "materialized_coverage": coverage_rows,
        "materialized_contract": contract_rows,
        "summary_rows": summary_rows,
        "promotion_eligible": any(
            bool(row["promotion_eligible"]) for row in summary_rows
        ),
        "verdict": "candidate_found"
        if any(bool(row["promotion_eligible"]) for row in summary_rows)
        else "rejected",
        "reason": (
            "The submitted materialized inputs W_p, Open(q0), and S_p(t) are "
            "not present in current artifacts. Artifact-native mark-stream "
            "proxies do not select the terminal boundary with zero failures."
        ),
    }
    write_csv(contract_rows, args.output_dir / "materialized_contract.csv")
    write_csv(coverage_rows, args.output_dir / "materialized_coverage.csv")
    write_csv(selection_rows, args.output_dir / "frontier_selection_rows.csv")
    write_csv(summary_rows, args.output_dir / "frontier_summary.csv")
    write_json(payload, args.output_dir / "summary.json")
    print(
        "frontier groups={groups} promotion_eligible={eligible}".format(
            groups=len(groups),
            eligible=str(payload["promotion_eligible"]).lower(),
        )
    )
    for row in summary_rows:
        print(
            "scale={scale} rule={rule_id} correct={correct}/{shadow_seed_rows} "
            "no_selection={no_selection} audit_failed_if_promoted="
            "{audit_failed_if_promoted} projected_pgs_percent="
            "{projected_pgs_percent:.2f}% promotion_eligible="
            "{promotion_eligible}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

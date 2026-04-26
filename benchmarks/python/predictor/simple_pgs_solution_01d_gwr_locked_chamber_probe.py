"""Test Grok Solution 1d: GWR-locked chamber recovery from a shadow seed."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    DEFAULT_CANDIDATE_BOUND,
    DEFAULT_VISIBLE_DIVISOR_BOUND,
    PGS_SOURCE,
    admissible_offsets,
    closure_reason,
)


DEFAULT_INPUT = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "output" / "simple_pgs_solution_01d_gwr_locked_chamber_probe"
)
DEFAULT_GENERATOR = (
    ROOT / "src" / "python" / "z_band_prime_predictor" / "simple_pgs_generator.py"
)
CLAIMED_PARAMETER = "gwr_winner"


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


def parameter_available(generator_path: Path) -> bool:
    """Return whether the submitted probe parameter already exists."""
    text = generator_path.read_text(encoding="utf-8")
    return CLAIMED_PARAMETER in text


def first_visible_after_locked_seed(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> int | None:
    """Return the weak executable reading: restart visible closure after q0."""
    seed_offset = int(seed_q0) - int(p)
    offsets = admissible_offsets(int(p), int(candidate_bound))
    for gap_offset in offsets:
        if gap_offset <= seed_offset:
            continue
        if closure_reason(int(p), gap_offset, int(visible_divisor_bound)) is not None:
            continue
        unclosed_before = False
        for prior_offset in offsets:
            if prior_offset <= seed_offset:
                continue
            if prior_offset >= gap_offset:
                break
            if (
                closure_reason(int(p), prior_offset, int(visible_divisor_bound))
                is None
            ):
                unclosed_before = True
                break
        if not unclosed_before:
            return int(p) + gap_offset
    return None


def strict_gwr_lock_terminal_signal(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> int | None:
    """Return no q because a locked winner is not a boundary signal."""
    _ = (p, seed_q0, candidate_bound, visible_divisor_bound)
    return None


def nlsc_locked_offset_signal(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> int | None:
    """Return no q because NLSC gives a ceiling without the missing margin."""
    _ = (p, seed_q0, candidate_bound, visible_divisor_bound)
    return None


def rate(count: int, total: int) -> float:
    """Return count / total."""
    return 0.0 if int(total) == 0 else int(count) / int(total)


def failure_mode(selected_q: int | None, true_q: int) -> str:
    """Classify one selector result."""
    if selected_q is None:
        return "no_selection"
    if int(selected_q) == int(true_q):
        return "correct"
    if int(selected_q) < int(true_q):
        return "selected_too_early"
    return "selected_too_late"


def build_probe_rows(
    rows: list[dict[str, object]],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Build one row per selector interpretation per shadow row."""
    selectors = (
        ("weak_visible_closure_with_gwr_lock", first_visible_after_locked_seed),
        ("strict_gwr_lock_no_terminal_signal", strict_gwr_lock_terminal_signal),
        ("nlsc_locked_offset_missing_margin", nlsc_locked_offset_signal),
    )
    out: list[dict[str, object]] = []
    for row in rows:
        if row.get("source") != "shadow_seed_recovery":
            continue
        scale = int(row["scale"])
        p = int(row["p"])
        seed_q0 = int(row["chain_seed"])
        true_q = int(row["q"])
        for selector_name, selector in selectors:
            selected_q = selector(
                p,
                seed_q0,
                int(candidate_bound),
                int(visible_divisor_bound),
            )
            out.append(
                {
                    "scale": scale,
                    "selector": selector_name,
                    "anchor_p": p,
                    "seed_q0": seed_q0,
                    "true_q_for_audit_only": true_q,
                    "selected_q": "" if selected_q is None else selected_q,
                    "selected_delta_from_true": ""
                    if selected_q is None
                    else int(selected_q) - true_q,
                    "failure_mode": failure_mode(selected_q, true_q),
                    "candidate_bound": int(candidate_bound),
                    "visible_divisor_bound": int(visible_divisor_bound),
                }
            )
    return out


def summarize(
    source_rows: list[dict[str, object]],
    probe_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Summarize each selector interpretation."""
    emitted_by_scale: dict[int, int] = {}
    base_pgs_by_scale: dict[int, int] = {}
    for row in source_rows:
        scale = int(row["scale"])
        if row.get("q") is not None:
            emitted_by_scale[scale] = emitted_by_scale.get(scale, 0) + 1
        if row.get("source") == PGS_SOURCE:
            base_pgs_by_scale[scale] = base_pgs_by_scale.get(scale, 0) + 1

    groups: dict[tuple[int, str], list[dict[str, object]]] = {}
    for row in probe_rows:
        key = (int(row["scale"]), str(row["selector"]))
        groups.setdefault(key, []).append(row)

    out: list[dict[str, object]] = []
    for (scale, selector), rows in sorted(groups.items()):
        correct = sum(1 for row in rows if row["failure_mode"] == "correct")
        no_selection = sum(1 for row in rows if row["failure_mode"] == "no_selection")
        too_early = sum(1 for row in rows if row["failure_mode"] == "selected_too_early")
        too_late = sum(1 for row in rows if row["failure_mode"] == "selected_too_late")
        emitted = emitted_by_scale.get(scale, 0)
        projected_pgs = base_pgs_by_scale.get(scale, 0) + correct
        audit_failed = len(rows) - correct - no_selection
        out.append(
            {
                "scale": scale,
                "selector": selector,
                "shadow_seed_rows": len(rows),
                "correct": correct,
                "correct_percent": rate(correct, len(rows)) * 100.0,
                "no_selection": no_selection,
                "selected_too_early": too_early,
                "selected_too_late": too_late,
                "audit_failed_if_promoted": audit_failed,
                "emitted_count": emitted,
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


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Test GWR-locked chamber recovery from a shadow seed."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--generator", type=Path, default=DEFAULT_GENERATOR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--candidate-bound", type=int, default=DEFAULT_CANDIDATE_BOUND)
    parser.add_argument(
        "--visible-divisor-bound",
        type=int,
        default=DEFAULT_VISIBLE_DIVISOR_BOUND,
    )
    return parser.parse_args()


def main() -> int:
    """Run the probe."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = read_jsonl(args.input)
    probe_rows = build_probe_rows(
        source_rows,
        int(args.candidate_bound),
        int(args.visible_divisor_bound),
    )
    summary_rows = summarize(source_rows, probe_rows)
    param_present = parameter_available(args.generator)
    payload = {
        "solution_id": "grok_solution_01d_gwr_locked_chamber_recovery_law",
        "generator_changed": False,
        "claimed_probe_parameter": CLAIMED_PARAMETER,
        "claimed_probe_parameter_available": param_present,
        "candidate_bound": int(args.candidate_bound),
        "visible_divisor_bound": int(args.visible_divisor_bound),
        "probe_rows": len(probe_rows),
        "summary_rows": summary_rows,
        "promotion_eligible": param_present
        and any(row["promotion_eligible"] for row in summary_rows),
        "verdict": "rejected",
        "reason": (
            "Locking q0 as the GWR winner does not provide a terminal boundary "
            "offset from current visible state. The weak executable reading "
            "still selects too early, while the strict GWR/NLSC readings have "
            "no boundary signal without the missing margin or offset."
        ),
    }
    write_csv(probe_rows, args.output_dir / "rows.csv")
    write_csv(summary_rows, args.output_dir / "summary.csv")
    write_json(payload, args.output_dir / "summary.json")
    print(
        "solution_01d claimed_parameter_available={present} "
        "promotion_eligible={eligible} probe_rows={rows}".format(
            present=str(param_present).lower(),
            eligible=str(payload["promotion_eligible"]).lower(),
            rows=len(probe_rows),
        )
    )
    for row in summary_rows:
        print(
            "scale={scale} selector={selector} correct={correct}/{shadow_seed_rows} "
            "no_selection={no_selection} audit_failed_if_promoted="
            "{audit_failed_if_promoted} projected_pgs_percent="
            "{projected_pgs_percent:.2f}% promotion_eligible="
            "{promotion_eligible}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

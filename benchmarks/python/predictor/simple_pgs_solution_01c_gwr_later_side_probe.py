"""Test Grok Solution 1c against existing GWR/NLSC implementation contracts."""

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

from z_band_prime_predictor.gpe_boundary_selector import (  # noqa: E402
    GPEBoundarySelectorState,
    InsufficientBoundarySelectorStateError,
    select_next_boundary_prime,
)
from z_band_prime_predictor.gpe_nlsc_selector import (  # noqa: E402
    GPENLSCSelectorState,
    UndefinedNLSCSelectorBranchError,
    select_d4_nlsc_boundary_prime,
)
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    DEFAULT_CANDIDATE_BOUND,
    DEFAULT_VISIBLE_DIVISOR_BOUND,
    PGS_SOURCE,
)


DEFAULT_INPUT = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_GENERATOR = (
    ROOT / "src" / "python" / "z_band_prime_predictor" / "simple_pgs_generator.py"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "output" / "simple_pgs_solution_01c_gwr_later_side_probe"
)
CLAIMED_FUNCTION = "apply_gwr_later_side_closure"


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


def claimed_function_available(generator_path: Path) -> bool:
    """Return whether the proposed drop-in function exists."""
    text = generator_path.read_text(encoding="utf-8")
    return CLAIMED_FUNCTION in text


def milestone1_without_boundary_offset(p: int, q0: int) -> tuple[int | None, str]:
    """Run the existing boundary selector with only p and q0."""
    try:
        selected = select_next_boundary_prime(
            int(p),
            GPEBoundarySelectorState(boundary_offset=None),
            int(q0),
            4,
        )
    except InsufficientBoundarySelectorStateError as error:
        return None, type(error).__name__
    except Exception as error:  # noqa: BLE001
        return None, type(error).__name__
    return selected, "selected"


def d4_nlsc_without_margin(p: int, q0: int) -> tuple[int | None, str]:
    """Run the existing d=4 NLSC selector with only p and q0."""
    try:
        selected = select_d4_nlsc_boundary_prime(
            int(p),
            GPENLSCSelectorState(
                threat_horizon=None,
                square_ceiling_margin=None,
            ),
            int(q0),
            4,
        )
    except (InsufficientBoundarySelectorStateError, UndefinedNLSCSelectorBranchError) as error:
        return None, type(error).__name__
    except Exception as error:  # noqa: BLE001
        return None, type(error).__name__
    return selected, "selected"


def rate(count: int, total: int) -> float:
    """Return count / total."""
    return 0.0 if int(total) == 0 else int(count) / int(total)


def failure_mode(selected: int | None, true_q: int) -> str:
    """Classify one selector result."""
    if selected is None:
        return "no_selection"
    if int(selected) == int(true_q):
        return "correct"
    if int(selected) < int(true_q):
        return "selected_too_early"
    return "selected_too_late"


def build_probe_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Build selector-contract rows for shadow-seed recovery inputs."""
    out: list[dict[str, object]] = []
    for row in rows:
        if row.get("source") != "shadow_seed_recovery":
            continue
        scale = int(row["scale"])
        p = int(row["p"])
        q0 = int(row["chain_seed"])
        true_q = int(row["q"])
        for selector_name, runner in (
            ("milestone1_boundary_without_offset", milestone1_without_boundary_offset),
            ("d4_nlsc_without_threat_or_margin", d4_nlsc_without_margin),
        ):
            selected, status = runner(p, q0)
            out.append(
                {
                    "scale": scale,
                    "selector": selector_name,
                    "anchor_p": p,
                    "seed_q0": q0,
                    "true_q_for_audit_only": true_q,
                    "selected_q": "" if selected is None else selected,
                    "selector_status": status,
                    "failure_mode": failure_mode(selected, true_q),
                }
            )
    return out


def summarize(
    source_rows: list[dict[str, object]],
    probe_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Summarize selector-contract outcomes."""
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
        audit_failed = len(rows) - correct - no_selection
        emitted = emitted_by_scale.get(scale, 0)
        projected_pgs = base_pgs_by_scale.get(scale, 0) + correct
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
        description="Test the claimed GWR later-side closure drop-in contract."
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
    probe_rows = build_probe_rows(source_rows)
    summary_rows = summarize(source_rows, probe_rows)
    function_present = claimed_function_available(args.generator)
    payload = {
        "solution_id": "grok_solution_01c_gwr_later_side_closure_law",
        "generator_changed": False,
        "claimed_drop_in_function": CLAIMED_FUNCTION,
        "claimed_drop_in_function_available": function_present,
        "candidate_bound": int(args.candidate_bound),
        "visible_divisor_bound": int(args.visible_divisor_bound),
        "probe_rows": len(probe_rows),
        "summary_rows": summary_rows,
        "promotion_eligible": function_present
        and any(row["promotion_eligible"] for row in summary_rows),
        "verdict": "rejected",
        "reason": (
            "The claimed drop-in function is not implemented in the minimal "
            "generator. The existing GWR/NLSC selector contracts do not select "
            "a boundary from only p and q0; they fail explicitly because the "
            "boundary offset or square-ceiling margin is missing."
        ),
    }
    write_csv(probe_rows, args.output_dir / "rows.csv")
    write_csv(summary_rows, args.output_dir / "summary.csv")
    write_json(payload, args.output_dir / "summary.json")
    print(
        "solution_01c claimed_function_available={present} "
        "promotion_eligible={eligible} probe_rows={rows}".format(
            present=str(function_present).lower(),
            eligible=str(payload["promotion_eligible"]).lower(),
            rows=len(probe_rows),
        )
    )
    for row in summary_rows:
        print(
            "scale={scale} selector={selector} correct={correct}/{shadow_seed_rows} "
            "no_selection={no_selection} projected_pgs_percent={projected_pgs_percent:.2f}% "
            "promotion_eligible={promotion_eligible}".format(**row)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

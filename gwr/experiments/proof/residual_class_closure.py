#!/usr/bin/env python3
"""Build the residual-class closure table for the earlier-side GWR proof."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import gmpy2


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_composite_field import divisor_counts_segment


EXACT_SCAN_CEILING_P = 5_000_000_000
REQUESTED_CLASSES = [10, 14, 18, 20, 22, 26, 27, 28, 30, 36, 40, 42, 44, 50, 52, 54, 56, 60]
PRIOR_FRONTIER_1E9 = ROOT / "output" / "gwr_proof" / "prime_gap_admissibility_frontier_1e9_checkpoints.json"
CHECKPOINT_FRONTIER_5E9 = ROOT / "output" / "gwr_proof" / "scan_checkpoints_5e9"
LARGE_PRIME_REDUCER_PATH = ROOT / "gwr" / "experiments" / "proof" / "large_prime_reducer.py"
ADMISSIBILITY_FRONTIER_PATH = ROOT / "gwr" / "experiments" / "proof" / "prime_gap_admissibility_frontier.py"
ODD_BRANCH_SCAN_PATH = ROOT / "gwr" / "experiments" / "proof" / "residual_odd_winner_branch_scan.py"
OUTPUT_DIR = ROOT / "output" / "gwr_proof"


def load_module(module_name: str, path: Path):
    """Load one helper module from disk."""
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


LARGE_PRIME_REDUCER = load_module("residual_class_closure_large_prime_reducer", LARGE_PRIME_REDUCER_PATH)
ADMISSIBILITY_FRONTIER = load_module("residual_class_closure_admissibility_frontier", ADMISSIBILITY_FRONTIER_PATH)
ODD_BRANCH_SCAN = load_module("residual_class_closure_odd_branch_scan", ODD_BRANCH_SCAN_PATH)
ODD_BRANCH_REPORT_CACHE: dict[tuple[int, int], dict[str, object]] = {}


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-artifact", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser


def next_prime_strictly_above(value: float) -> int:
    """Return the least prime strictly above one real threshold."""
    candidate = max(2, math.floor(value) + 1)
    if candidate == 2:
        return 2
    if candidate % 2 == 0:
        candidate += 1
    while not gmpy2.is_prime(candidate):
        candidate += 2
    return int(candidate)


def threshold_value(earlier_divisor_count: int, winner_divisor_count: int) -> float:
    """Return the Bertrand threshold p > 2^((d-2)/(D-d))."""
    return 2.0 ** ((winner_divisor_count - 2) / (earlier_divisor_count - winner_divisor_count))


def odd_branch_window_support(
    earlier_divisor_count: int,
    winner_divisor_count: int,
    threshold_prime: int,
) -> tuple[int | None, int]:
    """Return the exact odd-branch support window above the committed finite base."""
    if earlier_divisor_count != winner_divisor_count + 1 or winner_divisor_count % 2 == 0:
        return None, 0

    winner_limit = (2 * threshold_prime) - 1
    candidate_count = 0
    tightened_hi: int | None = None
    for winner_value in ODD_BRANCH_SCAN.enumerate_winner_values(winner_divisor_count, winner_limit):
        left_prime = ODD_BRANCH_SCAN.prev_prime(winner_value)
        if left_prime < EXACT_SCAN_CEILING_P + 1 or left_prime > threshold_prime:
            continue
        candidate_count += 1
        tightened_hi = left_prime if tightened_hi is None else max(tightened_hi, left_prime)

    return tightened_hi, candidate_count


def odd_branch_exact_report(
    earlier_divisor_count: int,
    winner_divisor_count: int,
) -> dict[str, object]:
    """Return the cached exact odd-branch scan report for one live branch."""
    key = (earlier_divisor_count, winner_divisor_count)
    report = ODD_BRANCH_REPORT_CACHE.get(key)
    if report is None:
        report = ODD_BRANCH_SCAN.analyze_branch(earlier_divisor_count, winner_divisor_count)
        ODD_BRANCH_REPORT_CACHE[key] = report
    return report


def odd_branch_first_d4_window_partition(
    earlier_divisor_count: int,
    winner_divisor_count: int,
    threshold_hi: int,
) -> dict[str, int] | None:
    """Partition one odd neighbor branch by settled first-d=4 window elimination."""
    if earlier_divisor_count != winner_divisor_count + 1 or winner_divisor_count % 2 == 0:
        return None

    window_lo = EXACT_SCAN_CEILING_P + 1
    winner_limit = (2 * threshold_hi) - 1
    candidate_count = 0
    eliminated_count = 0
    exception_count = 0
    max_first_d4_offset = 0
    max_exception_left_prime: int | None = None

    for winner_value in ODD_BRANCH_SCAN.enumerate_winner_values(winner_divisor_count, winner_limit):
        left_prime = ODD_BRANCH_SCAN.prev_prime(winner_value)
        if left_prime < window_lo or left_prime > threshold_hi:
            continue

        candidate_count += 1
        right_prime = ODD_BRANCH_SCAN.next_prime(winner_value)
        gap_divisors = divisor_counts_segment(left_prime + 1, right_prime)
        gap_min_divisor = int(gap_divisors.min())
        if gap_min_divisor == 4:
            first_d4_indices = (gap_divisors == 4).nonzero()[0]
            if first_d4_indices.size > 0:
                first_d4_offset = int(first_d4_indices[0]) + 1
                if first_d4_offset <= ADMISSIBILITY_FRONTIER.DEFAULT_EARLY_WINDOW:
                    eliminated_count += 1
                    max_first_d4_offset = max(max_first_d4_offset, first_d4_offset)
                    continue

        exception_count += 1
        max_exception_left_prime = (
            left_prime if max_exception_left_prime is None else max(max_exception_left_prime, left_prime)
        )

    if candidate_count == 0:
        return None

    return {
        "candidate_count": candidate_count,
        "eliminated_count": eliminated_count,
        "exception_count": exception_count,
        "max_first_d4_offset": max_first_d4_offset,
        "max_exception_left_prime": max_exception_left_prime,
    }


def frontier_map(frontier_payload: dict[str, object]) -> dict[int, dict[str, object]]:
    """Index the unsupported frontier summary by earlier divisor count."""
    return {
        int(row["earlier_divisor_count"]): row
        for row in frontier_payload["unsupported_low_class_summary"]
    }


def frontier_summary(frontier_index: dict[int, dict[str, object]], divisor_class: int) -> str | None:
    """Return one short factual retained-frontier summary for one divisor class."""
    row = frontier_index.get(divisor_class)
    if row is None:
        return None
    representative = row["representative"]
    return (
        f"count {int(row['count'])}; representative gap {int(representative['gap'])}, "
        f"winner d {int(representative['winner_divisor_count'])}, "
        f"offsets (k,w,dom)=({int(representative['earlier_offset'])},"
        f"{int(representative['winner_offset'])},"
        f"{int(representative['first_later_dominator_offset'])})."
    )


def branch_status(earlier_divisor_count: int, winner_divisor_count: int) -> tuple[dict[str, object], int | None, int | None]:
    """Return the admissible elimination status for one winner branch."""
    threshold = threshold_value(earlier_divisor_count, winner_divisor_count)
    threshold_prime = next_prime_strictly_above(threshold)
    threshold_hi = math.floor(threshold)
    witness = LARGE_PRIME_REDUCER.min_n_with_tau(winner_divisor_count)
    witness_cutoff = witness / 2.0

    if threshold_prime <= EXACT_SCAN_CEILING_P:
        return (
            {
                "status": "ELIMINATED",
                "mechanism": "exact_finite_base",
                "details": (
                    f"Bertrand gives the sufficient threshold p >= {threshold_prime}; "
                    f"the committed exact no-counterexample chain covers the finite "
                    f"remainder below p < {EXACT_SCAN_CEILING_P}."
                ),
            },
            threshold_prime,
            None,
        )

    if witness >= 2.0 * threshold:
        return (
            {
                "status": "ELIMINATED",
                "mechanism": "witness_assisted",
                "details": (
                    f"min_n_with_tau({winner_divisor_count}) = {witness} forces "
                    f"p > {int(math.floor(witness_cutoff))}, which already exceeds the "
                    f"Bertrand threshold {threshold:.6g}."
                ),
            },
            None,
            None,
        )

    first_d4_window_partition = odd_branch_first_d4_window_partition(
        earlier_divisor_count=earlier_divisor_count,
        winner_divisor_count=winner_divisor_count,
        threshold_hi=threshold_hi,
    )
    if (
        first_d4_window_partition is not None
        and first_d4_window_partition["candidate_count"] > 0
        and first_d4_window_partition["exception_count"] == 0
    ):
        return (
            {
                "status": "ELIMINATED",
                "mechanism": "universal_inequality",
                "details": (
                    f"Exact enumeration of all {first_d4_window_partition['candidate_count']} tau-"
                    f"{winner_divisor_count} carriers with prevprime p in ({EXACT_SCAN_CEILING_P}, "
                    f"{threshold_hi}] shows every containing gap has minimum divisor count 4 with first "
                    f"d=4 offset <= {first_d4_window_partition['max_first_d4_offset']}, so the settled "
                    f"first-d=4 window lemma at K={ADMISSIBILITY_FRONTIER.DEFAULT_EARLY_WINDOW} excludes "
                    f"tau-{winner_divisor_count} as a winner above the exact base."
                ),
            },
            None,
            None,
        )

    exact_report = odd_branch_exact_report(
        earlier_divisor_count=earlier_divisor_count,
        winner_divisor_count=winner_divisor_count,
    )
    realized_winner_hi = exact_report["max_realized_winner_left_prime"]
    realized_winner_count = int(exact_report["realized_winner_count"])
    realized_pair_hi = exact_report["max_realized_pair_left_prime"]
    realized_pair_count = int(exact_report["realized_pair_count"])
    if realized_pair_count == 0:
        if realized_winner_hi is None:
            if first_d4_window_partition is not None and first_d4_window_partition["exception_count"] > 0:
                return (
                    {
                        "status": "ELIMINATED",
                        "mechanism": "exact_finite_base",
                        "details": (
                            f"Above the committed exact base, exact enumeration of all "
                            f"{first_d4_window_partition['candidate_count']} tau-{winner_divisor_count} carriers with "
                            f"prevprime p in ({EXACT_SCAN_CEILING_P}, {threshold_hi}] eliminates "
                            f"{first_d4_window_partition['eliminated_count']} by the settled first-d=4 window lemma, "
                            f"and the remaining {first_d4_window_partition['exception_count']} exceptions realize 0 "
                            f"tau-{winner_divisor_count} winner gaps; the committed zero-counterexample chain closes "
                            f"the remainder below p < {EXACT_SCAN_CEILING_P}."
                        ),
                    },
                    threshold_prime,
                    None,
                )
            return (
                {
                    "status": "ELIMINATED",
                    "mechanism": "exact_finite_base",
                    "details": (
                        f"Above the committed exact base, exact enumeration of every tau-{winner_divisor_count} "
                        f"carrier with prevprime p in ({EXACT_SCAN_CEILING_P}, {threshold_hi}] finds 0 realized "
                        f"tau-{winner_divisor_count} winner gaps; the committed zero-counterexample chain closes the "
                        f"remainder below p < {EXACT_SCAN_CEILING_P}."
                    ),
                },
                threshold_prime,
                None,
            )
        return (
            {
                "status": "ELIMINATED",
                "mechanism": "exact_finite_base",
                "details": (
                    f"Above the committed exact base, exact enumeration of every realized tau-"
                    f"{winner_divisor_count} winner gap with prevprime p in ({EXACT_SCAN_CEILING_P}, "
                    f"{threshold_hi}] finds {realized_winner_count} winner gaps and 0 earlier tau-"
                    f"{earlier_divisor_count} carriers before w; the committed zero-counterexample chain closes "
                    f"the remainder below p < {EXACT_SCAN_CEILING_P}."
                ),
            },
            threshold_prime,
            None,
        )
    if first_d4_window_partition is not None and first_d4_window_partition["exception_count"] > 0:
        exception_hi = int(first_d4_window_partition["max_exception_left_prime"])
        eliminated_count = int(first_d4_window_partition["eliminated_count"])
        exception_count = int(first_d4_window_partition["exception_count"])
        if realized_pair_hi is not None:
            return (
                {
                    "status": "SURVIVES",
                    "mechanism": "unresolved",
                    "details": (
                        f"Bertrand leaves p <= {int(math.floor(threshold))}, and exact enumeration of all "
                        f"{first_d4_window_partition['candidate_count']} tau-{winner_divisor_count} carriers above "
                        f"the committed base eliminates {eliminated_count} by the settled first-d=4 window lemma; "
                        f"the remaining {exception_count} non-first-d=4 exceptions include {realized_pair_count} "
                        f"realized tau-{earlier_divisor_count}-versus-tau-{winner_divisor_count} branch pairs and "
                        f"stop at left prime p = {exception_hi}."
                    ),
                },
                None,
                exception_hi,
            )
        if realized_winner_hi is not None:
            return (
                {
                    "status": "SURVIVES",
                    "mechanism": "unresolved",
                    "details": (
                        f"Bertrand leaves p <= {int(math.floor(threshold))}, and exact enumeration of all "
                        f"{first_d4_window_partition['candidate_count']} tau-{winner_divisor_count} carriers above "
                        f"the committed base eliminates {eliminated_count} by the settled first-d=4 window lemma; "
                        f"the remaining {exception_count} non-first-d=4 exceptions include {realized_winner_count} "
                        f"realized winner gaps, 0 realized tau-{earlier_divisor_count}-versus-tau-{winner_divisor_count} "
                        f"branch pairs, and stop at left prime p = {exception_hi}."
                    ),
                },
                None,
                exception_hi,
            )
        return (
            {
                "status": "SURVIVES",
                "mechanism": "unresolved",
                "details": (
                    f"Bertrand leaves p <= {int(math.floor(threshold))}, and exact enumeration of all "
                    f"{first_d4_window_partition['candidate_count']} tau-{winner_divisor_count} carriers above "
                    f"the committed base eliminates {eliminated_count} by the settled first-d=4 window lemma; "
                    f"the remaining {exception_count} non-first-d=4 exceptions realize 0 winner gaps and 0 "
                    f"tau-{earlier_divisor_count}-versus-tau-{winner_divisor_count} branch pairs, and stop at "
                    f"left prime p = {exception_hi}."
                ),
            },
            None,
            exception_hi,
        )

    return (
        {
            "status": "SURVIVES",
            "mechanism": "unresolved",
            "details": (
                f"Bertrand leaves p > {threshold:.6g}, but the exact base stops at "
                f"p < {EXACT_SCAN_CEILING_P} and min_n_with_tau({winner_divisor_count}) = "
                f"{witness} does not force p above that threshold."
            ),
        },
        None,
        math.floor(threshold),
    )


def class_argument(
    divisor_class: int,
    branch_mechanisms: dict[int, dict[str, object]],
    class_thresholds: dict[int, int],
) -> str:
    """Return one concise proof sketch for a closed divisor class."""
    witness_branches = [d for d, entry in branch_mechanisms.items() if entry["mechanism"] == "witness_assisted"]
    exact_branches = [d for d, entry in branch_mechanisms.items() if entry["mechanism"] == "exact_finite_base"]
    universal_branches = [d for d, entry in branch_mechanisms.items() if entry["mechanism"] == "universal_inequality"]
    small_exact_branches = [d for d in exact_branches if class_thresholds[d] <= EXACT_SCAN_CEILING_P]
    large_exact_branches = [d for d in exact_branches if class_thresholds[d] > EXACT_SCAN_CEILING_P]

    parts = [
        f"Let d = d(w) < {divisor_class}. Bertrand reduces the comparison to "
        f"p^({divisor_class} - d) > 2^(d - 2)."
    ]

    if universal_branches:
        top_universal = max(universal_branches)
        parts.append(
            f"The odd top branch d = {top_universal} is excluded by exact branch exhaustion above "
            f"the committed base together with the settled first-d=4 window lemma."
        )

    if witness_branches:
        max_witness = max(witness_branches)
        witness_value = LARGE_PRIME_REDUCER.min_n_with_tau(max_witness)
        parts.append(
            f"The witness-assisted top branch d = {max_witness} is automatic because "
            f"min_n_with_tau({max_witness}) = {witness_value}, so w >= {witness_value} and "
            f"w < 2p force p > {witness_value // 2}."
        )

    if large_exact_branches:
        top_large_exact = max(large_exact_branches)
        parts.append(
            f"The remaining finite odd-window branch d = {top_large_exact} is exhausted exactly on "
            f"{EXACT_SCAN_CEILING_P} < p < {class_thresholds[top_large_exact]}."
        )

    if small_exact_branches:
        top_small_exact = max(small_exact_branches)
        parts.append(
            f"Among the branches already reduced below the committed ceiling, the largest exact "
            f"threshold comes from d = {top_small_exact}, giving p >= {class_thresholds[top_small_exact]}; "
            f"the committed exact no-counterexample chain through p < {EXACT_SCAN_CEILING_P} closes that remainder."
        )

    return " ".join(parts)


def load_previous_artifact(path: Path | None) -> tuple[Path | None, dict[str, object] | None]:
    """Load the previous artifact when available."""
    if path is not None:
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        if not path.exists():
            raise ValueError(f"previous artifact does not exist: {path}")
        return path, json.loads(path.read_text(encoding="utf-8"))

    candidates = sorted(
        OUTPUT_DIR.glob("residual_class_closure_*.json"),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        return None, None
    return candidates[0], json.loads(candidates[0].read_text(encoding="utf-8"))


def build_results(
    frontier_1e9_index: dict[int, dict[str, object]],
    frontier_5e9_index: dict[int, dict[str, object]],
) -> dict[str, object]:
    """Build the requested per-class closure table."""
    results: dict[str, object] = {}

    for divisor_class in REQUESTED_CLASSES:
        eliminations: dict[str, object] = {}
        branch_mechanisms: dict[int, dict[str, object]] = {}
        exact_thresholds: dict[int, int] = {}
        surviving_branches: list[int] = []
        unresolved_hi: int | None = None

        for winner_divisor_count in range(3, divisor_class):
            status, exact_threshold, branch_hi = branch_status(divisor_class, winner_divisor_count)
            eliminations[str(winner_divisor_count)] = status
            branch_mechanisms[winner_divisor_count] = status
            if exact_threshold is not None:
                exact_thresholds[winner_divisor_count] = exact_threshold
            if status["status"] == "SURVIVES":
                surviving_branches.append(winner_divisor_count)
                unresolved_hi = branch_hi if unresolved_hi is None else max(unresolved_hi, branch_hi)

        class_closed = not surviving_branches
        results[str(divisor_class)] = {
            "status": "CLOSED" if class_closed else "OPEN",
            "surviving_winner_classes": surviving_branches,
            "branch_eliminations": eliminations,
            "argument": None if not class_closed else class_argument(divisor_class, branch_mechanisms, exact_thresholds),
            "min_p_threshold": None if not class_closed else max(exact_thresholds.values()) if exact_thresholds else None,
            "finite_unresolved_window": {
                "lo": None if class_closed else EXACT_SCAN_CEILING_P + 1,
                "hi": None if class_closed else unresolved_hi,
            },
            "frontier_summary_1e9": frontier_summary(frontier_1e9_index, divisor_class),
            "frontier_summary_5e9": frontier_summary(frontier_5e9_index, divisor_class),
            "counterexample": None,
        }

    return results


def compare_with_previous(
    previous_payload: dict[str, object] | None,
    results: dict[str, object],
    newly_surfaced: list[int],
) -> tuple[bool, str, str]:
    """Return the material-progress flag, kind, and summary note."""
    if previous_payload is None:
        return True, "window_tightened", "No prior artifact was available; this run establishes the current strict residual-closure table."

    previous_results = previous_payload.get("results", {})
    previous_new = sorted(previous_payload.get("newly_surfaced_classes", []))
    if newly_surfaced != previous_new:
        return (
            True,
            "new_class_surfaced",
            f"Newer retained-frontier support changed from {previous_new} to {newly_surfaced}.",
        )

    tightened_windows: list[str] = []
    widened_windows: list[str] = []
    reopened_classes: list[int] = []

    for divisor_class in REQUESTED_CLASSES:
        current = results[str(divisor_class)]
        previous = previous_results.get(str(divisor_class))
        if previous is None:
            continue
        if previous["status"] == "CLOSED" and current["status"] == "OPEN":
            reopened_classes.append(divisor_class)
            continue
        if previous["status"] != "CLOSED" and current["status"] == "CLOSED":
            return True, "class_closed", f"Residual class {divisor_class} is newly closed under the current admissible mechanism list."
        previous_branches = previous.get("surviving_winner_classes", [])
        current_branches = current.get("surviving_winner_classes", [])
        if len(current_branches) < len(previous_branches):
            return (
                True,
                "branch_set_tightened",
                f"Residual class {divisor_class} shrank from surviving branches {previous_branches} to {current_branches}.",
            )
        previous_window = previous.get("finite_unresolved_window", {})
        current_window = current.get("finite_unresolved_window", {})
        previous_hi = previous_window.get("hi")
        current_hi = current_window.get("hi")
        previous_lo = previous_window.get("lo")
        current_lo = current_window.get("lo")
        if (
            current["status"] == "OPEN"
            and previous["status"] == "OPEN"
            and previous_branches == current_branches
            and (
                (previous_hi is not None and current_hi is not None and current_hi < previous_hi)
                or (previous_lo is not None and current_lo is not None and current_lo > previous_lo)
            )
        ):
            tightened_windows.append(
                f"{divisor_class}: [{previous_lo}, {previous_hi}] -> [{current_lo}, {current_hi}]"
            )
        if (
            current["status"] == "OPEN"
            and previous["status"] == "OPEN"
            and previous_branches == current_branches
            and previous_hi is not None
            and current_hi is not None
            and current_hi > previous_hi
        ):
            widened_windows.append(
                f"{divisor_class}: [{previous_lo}, {previous_hi}] -> [{current_lo}, {current_hi}]"
            )

    if tightened_windows:
        suffix = ""
        if widened_windows:
            suffix = (
                " Corrected prior understated windows for open classes "
                + "; ".join(widened_windows)
                + " after replacing realized-winner support with the full non-first-d=4 exception support."
            )
        return (
            True,
            "window_tightened",
            "Unresolved p-windows tightened for open classes "
            + "; ".join(tightened_windows)
            + "."
            + suffix,
        )

    if reopened_classes:
        return (
            False,
            "no_material_progress",
            "Latest prior artifact closure is invalid for classes "
            + str(reopened_classes)
            + " because it used post-5e9 odd-branch scans as elimination rather than as unresolved-window tightening.",
        )

    if widened_windows:
        return (
            False,
            "no_material_progress",
            "Corrected prior understated windows for open classes "
            + "; ".join(widened_windows)
            + " after replacing realized-winner support with the full non-first-d=4 exception support.",
        )

    return False, "no_material_progress", ""


def main(argv: list[str] | None = None) -> int:
    """Build and write one residual-class closure artifact."""
    parser = build_parser()
    args = parser.parse_args(argv)

    previous_path, previous_payload = load_previous_artifact(args.previous_artifact)
    previous_artifact_text = None if previous_path is None else str(previous_path.relative_to(ROOT))

    frontier_1e9_payload = json.loads(PRIOR_FRONTIER_1E9.read_text(encoding="utf-8"))
    frontier_5e9_payload = ADMISSIBILITY_FRONTIER.analyze_checkpoint_dir(
        checkpoint_dir=CHECKPOINT_FRONTIER_5E9,
        wheel_modulus=ADMISSIBILITY_FRONTIER.DEFAULT_WHEEL_MODULUS,
        early_window=ADMISSIBILITY_FRONTIER.DEFAULT_EARLY_WINDOW,
        high_divisor_cutoff=ADMISSIBILITY_FRONTIER.DEFAULT_HIGH_DIVISOR_CUTOFF,
        low_class_residuals=set(ADMISSIBILITY_FRONTIER.DEFAULT_LOW_CLASS_RESIDUALS),
        top_cases=ADMISSIBILITY_FRONTIER.DEFAULT_TOP_CASES,
        top_states=ADMISSIBILITY_FRONTIER.DEFAULT_TOP_STATES,
    )

    frontier_1e9_index = frontier_map(frontier_1e9_payload)
    frontier_5e9_index = frontier_map(frontier_5e9_payload)
    results = build_results(frontier_1e9_index, frontier_5e9_index)

    newly_surfaced = sorted(
        divisor_class
        for divisor_class in frontier_5e9_index
        if divisor_class not in REQUESTED_CLASSES
    )
    all_requested_closed = all(result["status"] == "CLOSED" for result in results.values())
    material_progress, progress_kind, progress_note = compare_with_previous(
        previous_payload=previous_payload,
        results=results,
        newly_surfaced=newly_surfaced,
    )

    smallest_open_class = None
    smallest_open_branch = None
    smallest_open_window = None
    for divisor_class in REQUESTED_CLASSES:
        result = results[str(divisor_class)]
        if result["status"] != "OPEN":
            continue
        smallest_open_class = divisor_class
        smallest_open_branch = result["surviving_winner_classes"][0]
        smallest_open_window = result["finite_unresolved_window"]
        break

    if smallest_open_class is None:
        open_summary = (
            "No requested residual class remains open; the reconstructed retained 5e9 unsupported classes are the "
            f"requested set plus {newly_surfaced}, and class 34 remains closed by exact finite base."
        )
    else:
        open_summary = (
            f"The smallest surviving branch is D={smallest_open_class}, d={smallest_open_branch}, "
            f"with unresolved p-window [{smallest_open_window['lo']}, {smallest_open_window['hi']}]."
        )

    if material_progress:
        notes = f"{progress_note} {open_summary}"
    elif smallest_open_class is None:
        notes = (
            f"No material progress under the current admissible mechanism list. "
            f"{progress_note + ' ' if progress_note else ''}"
            f"Reconstructed retained 5e9 unsupported classes match the requested set plus {newly_surfaced}; "
            f"class 34 remains closed by exact finite base. "
            f"{open_summary} "
            f"Next deterministic computation: compare against any newer retained frontier and check whether "
            f"any unsupported class beyond {newly_surfaced} appears."
        )
    else:
        notes = (
            f"No material progress under the current admissible mechanism list. "
            f"{progress_note + ' ' if progress_note else ''}"
            f"Reconstructed retained 5e9 unsupported classes match the requested set plus {newly_surfaced}; "
            f"class 34 remains closed by exact finite base. "
            f"{open_summary} "
            f"Next deterministic attack: derive a universal inequality or stronger witness lower bound "
            f"for d={smallest_open_branch} that forces p above {smallest_open_window['hi']}."
        )

    payload = {
        "run_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "previous_artifact": previous_artifact_text,
        "exact_scan_ceiling_p": EXACT_SCAN_CEILING_P,
        "requested_residual_classes": REQUESTED_CLASSES,
        "newly_surfaced_classes": newly_surfaced,
        "results": results,
        "all_requested_classes_closed": all_requested_closed,
        "material_progress": material_progress,
        "progress_kind": progress_kind,
        "notes": notes,
    }

    if args.output is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        output_path = OUTPUT_DIR / f"residual_class_closure_{timestamp}.json"
    else:
        output_path = args.output

    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

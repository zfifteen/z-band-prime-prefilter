"""Mine the missing boundary margin for the GWR-locked chamber proposal."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from math import isqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    DEFAULT_CANDIDATE_BOUND,
    DEFAULT_VISIBLE_DIVISOR_BOUND,
    PGS_SOURCE,
    WHEEL_OPEN_RESIDUES_MOD30,
    closure_reason,
)


DEFAULT_ROWS = (
    ROOT / "output" / "simple_pgs_shadow_seed_gwr_solution_probe" / "rows.jsonl"
)
DEFAULT_CANDIDATES = (
    ROOT
    / "output"
    / "simple_pgs_shadow_seed_recovery_displacement_probe"
    / "candidate_rows.csv"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "output" / "simple_pgs_solution_01d_locked_state_integration_probe"
)


def read_jsonl(path: Path) -> list[dict[str, object]]:
    """Read JSONL rows."""
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def read_csv(path: Path) -> list[dict[str, str]]:
    """Read CSV rows."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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


def next_open_square_after(n: int) -> int:
    """Return the first square after n with a wheel-open residue."""
    root = isqrt(int(n)) + 1
    while True:
        square = root * root
        if square % 30 in WHEEL_OPEN_RESIDUES_MOD30:
            return square
        root += 1


def visible_open_nodes(
    p: int,
    seed_q0: int,
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[int]:
    """Return visible-open candidates after the locked seed."""
    nodes: list[int] = []
    upper = int(p) + int(candidate_bound)
    for candidate in range(int(seed_q0) + 1, upper + 1):
        offset = candidate - int(p)
        if (
            candidate % 30 in WHEEL_OPEN_RESIDUES_MOD30
            and closure_reason(int(p), offset, int(visible_divisor_bound)) is None
        ):
            nodes.append(candidate)
    return nodes


def compact_vector(values: list[int]) -> str:
    """Return a stable compact vector string."""
    return ".".join(str(value) for value in values)


def candidate_carrier_d(rows: list[dict[str, str]]) -> dict[tuple[int, int, int], int]:
    """Return probe-only carrier_d values already measured in candidate rows."""
    out: dict[tuple[int, int, int], int] = {}
    for row in rows:
        key = (int(row["scale"]), int(row["anchor_p"]), int(row["seed_q0"]))
        out.setdefault(key, int(row["carrier_d"]))
    return out


def build_locked_state_rows(
    rows: list[dict[str, object]],
    carrier_d_by_key: dict[tuple[int, int, int], int],
    candidate_bound: int,
    visible_divisor_bound: int,
) -> list[dict[str, object]]:
    """Build one locked-chamber state row per shadow-seed recovery row."""
    out: list[dict[str, object]] = []
    for row in rows:
        if row.get("source") != "shadow_seed_recovery":
            continue
        scale = int(row["scale"])
        p = int(row["p"])
        seed_q0 = int(row["chain_seed"])
        true_q = int(row["q"])
        key = (scale, p, seed_q0)
        visible = visible_open_nodes(
            p,
            seed_q0,
            int(candidate_bound),
            int(visible_divisor_bound),
        )
        visible_deltas = [node - seed_q0 for node in visible]
        visible_gaps = [
            visible[index] - visible[index - 1]
            for index in range(1, len(visible))
        ]
        open_square = next_open_square_after(seed_q0)
        terminal_delta = true_q - seed_q0
        terminal_visible_index = (
            visible.index(true_q) + 1 if true_q in visible else None
        )
        out.append(
            {
                "scale": scale,
                "anchor_p": p,
                "seed_q0": seed_q0,
                "true_q_for_audit_only": true_q,
                "terminal_delta_from_seed_for_audit_only": terminal_delta,
                "terminal_visible_index_for_audit_only": ""
                if terminal_visible_index is None
                else terminal_visible_index,
                "seed_offset_from_anchor": seed_q0 - p,
                "candidate_bound": int(candidate_bound),
                "visible_divisor_bound": int(visible_divisor_bound),
                "carrier_d_probe_only": carrier_d_by_key.get(key, ""),
                "p_mod_30": p % 30,
                "p_mod_210": p % 210,
                "p_mod_2310": p % 2310,
                "seed_mod_30": seed_q0 % 30,
                "seed_mod_210": seed_q0 % 210,
                "seed_mod_2310": seed_q0 % 2310,
                "visible_open_count_after_seed": len(visible),
                "visible_delta_vector": compact_vector(visible_deltas),
                "visible_delta_prefix_2": compact_vector(visible_deltas[:2]),
                "visible_delta_prefix_3": compact_vector(visible_deltas[:3]),
                "visible_delta_prefix_4": compact_vector(visible_deltas[:4]),
                "visible_delta_prefix_8": compact_vector(visible_deltas[:8]),
                "visible_gap_prefix_3": compact_vector(visible_gaps[:3]),
                "visible_gap_prefix_4": compact_vector(visible_gaps[:4]),
                "visible_gap_prefix_8": compact_vector(visible_gaps[:8]),
                "open_square_delta_from_seed": open_square - seed_q0,
                "open_square_visible_count_before": sum(
                    1 for node in visible if node < open_square
                ),
                "candidate_bound_contains_terminal": true_q <= p + int(candidate_bound),
            }
        )
    return out


def state_key(row: dict[str, object], key_name: str) -> tuple[object, ...]:
    """Return one candidate locked-state key."""
    if key_name == "K_seed_mods":
        return (row["seed_mod_30"], row["seed_mod_210"], row["seed_offset_from_anchor"])
    if key_name == "K_seed_mods_carrier":
        return (
            row["seed_mod_30"],
            row["seed_mod_210"],
            row["seed_offset_from_anchor"],
            row["carrier_d_probe_only"],
        )
    if key_name == "K_visible_prefix_2":
        return (row["seed_mod_30"], row["visible_delta_prefix_2"])
    if key_name == "K_visible_prefix_3":
        return (row["seed_mod_30"], row["visible_delta_prefix_3"])
    if key_name == "K_visible_prefix_4":
        return (row["seed_mod_30"], row["visible_delta_prefix_4"])
    if key_name == "K_visible_prefix_8":
        return (row["seed_mod_30"], row["visible_delta_prefix_8"])
    if key_name == "K_gap_prefix_4":
        return (row["seed_mod_30"], row["visible_gap_prefix_4"])
    if key_name == "K_square_visible_count":
        return (
            row["seed_mod_30"],
            row["open_square_visible_count_before"],
            row["visible_open_count_after_seed"],
        )
    if key_name == "K_square_delta_bucket":
        return (
            row["seed_mod_30"],
            int(row["open_square_delta_from_seed"]) // 16,
            row["open_square_visible_count_before"],
        )
    if key_name == "K_locked_full_visible":
        return (
            row["seed_mod_30"],
            row["seed_mod_210"],
            row["seed_offset_from_anchor"],
            row["carrier_d_probe_only"],
            row["visible_delta_vector"],
            row["open_square_visible_count_before"],
        )
    raise ValueError(f"unknown key_name: {key_name}")


KEY_NAMES = [
    "K_seed_mods",
    "K_seed_mods_carrier",
    "K_visible_prefix_2",
    "K_visible_prefix_3",
    "K_visible_prefix_4",
    "K_visible_prefix_8",
    "K_gap_prefix_4",
    "K_square_visible_count",
    "K_square_delta_bucket",
    "K_locked_full_visible",
]


def build_margin_map(
    rows: list[dict[str, object]],
    key_name: str,
) -> dict[tuple[object, ...], set[int]]:
    """Return key -> observed terminal deltas."""
    groups: dict[tuple[object, ...], set[int]] = defaultdict(set)
    for row in rows:
        groups[state_key(row, key_name)].add(
            int(row["terminal_delta_from_seed_for_audit_only"])
        )
    return groups


def summarize_keys(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Report whether any key determines the locked margin."""
    out: list[dict[str, object]] = []
    for key_name in KEY_NAMES:
        groups = build_margin_map(rows, key_name)
        collision_keys = {
            key: margins for key, margins in groups.items() if len(margins) > 1
        }
        repeated_keys = {
            key
            for key in groups
            if sum(1 for row in rows if state_key(row, key_name) == key) > 1
        }
        rows_in_zero_collision_keys = sum(
            1
            for row in rows
            if len(groups[state_key(row, key_name)]) == 1
        )
        out.append(
            {
                "key_name": key_name,
                "row_count": len(rows),
                "key_count": len(groups),
                "repeated_key_count": len(repeated_keys),
                "collision_key_count": len(collision_keys),
                "rows_in_zero_collision_keys": rows_in_zero_collision_keys,
                "rows_in_zero_collision_keys_percent": 0.0
                if not rows
                else 100.0 * rows_in_zero_collision_keys / len(rows),
                "zero_collision_all_rows": len(collision_keys) == 0,
            }
        )
    return out


def leave_one_out_replay(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Replay learned margin keys without using the held-out row."""
    out: list[dict[str, object]] = []
    for key_name in KEY_NAMES:
        for index, row in enumerate(rows):
            training = rows[:index] + rows[index + 1 :]
            margin_map = build_margin_map(training, key_name)
            key = state_key(row, key_name)
            margins = margin_map.get(key, set())
            selected_delta = next(iter(margins)) if len(margins) == 1 else None
            true_delta = int(row["terminal_delta_from_seed_for_audit_only"])
            if selected_delta is None:
                failure_mode = "no_selection"
                selected_q = ""
            else:
                selected_q = int(row["seed_q0"]) + selected_delta
                if selected_delta == true_delta:
                    failure_mode = "correct"
                elif selected_delta < true_delta:
                    failure_mode = "selected_too_early"
                else:
                    failure_mode = "selected_too_late"
            out.append(
                {
                    "scale": row["scale"],
                    "key_name": key_name,
                    "anchor_p": row["anchor_p"],
                    "seed_q0": row["seed_q0"],
                    "true_q_for_audit_only": row["true_q_for_audit_only"],
                    "selected_q": selected_q,
                    "failure_mode": failure_mode,
                }
            )
    return out


def summarize_replay(
    source_rows: list[dict[str, object]],
    replay_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Summarize leave-one-out replay by scale and key."""
    emitted_by_scale: dict[int, int] = {}
    base_pgs_by_scale: dict[int, int] = {}
    for row in source_rows:
        scale = int(row["scale"])
        if row.get("q") is not None:
            emitted_by_scale[scale] = emitted_by_scale.get(scale, 0) + 1
        if row.get("source") == PGS_SOURCE:
            base_pgs_by_scale[scale] = base_pgs_by_scale.get(scale, 0) + 1

    groups: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    for row in replay_rows:
        groups[(int(row["scale"]), str(row["key_name"]))].append(row)

    out: list[dict[str, object]] = []
    for (scale, key_name), rows in sorted(groups.items()):
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
                "key_name": key_name,
                "shadow_seed_rows": len(rows),
                "correct": correct,
                "no_selection": no_selection,
                "selected_too_early": too_early,
                "selected_too_late": too_late,
                "audit_failed_if_promoted": audit_failed,
                "projected_pgs_count": projected_pgs,
                "projected_pgs_percent": 0.0
                if emitted == 0
                else 100.0 * projected_pgs / emitted,
                "promotion_eligible": (
                    no_selection == 0
                    and audit_failed == 0
                    and emitted > 0
                    and projected_pgs / emitted >= 0.50
                ),
            }
        )
    return out


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Mine locked-chamber state keys for the boundary margin."
    )
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--candidate-bound", type=int, default=DEFAULT_CANDIDATE_BOUND)
    parser.add_argument(
        "--visible-divisor-bound",
        type=int,
        default=DEFAULT_VISIBLE_DIVISOR_BOUND,
    )
    return parser.parse_args()


def main() -> int:
    """Run the locked-state integration probe."""
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = read_jsonl(args.rows)
    carrier_d_by_key = candidate_carrier_d(read_csv(args.candidate_rows))
    state_rows = build_locked_state_rows(
        source_rows,
        carrier_d_by_key,
        int(args.candidate_bound),
        int(args.visible_divisor_bound),
    )
    key_rows = summarize_keys(state_rows)
    replay_rows = leave_one_out_replay(state_rows)
    replay_summary = summarize_replay(source_rows, replay_rows)
    payload = {
        "solution_id": "grok_solution_01d_gwr_locked_chamber_integration",
        "generator_changed": False,
        "candidate_bound": int(args.candidate_bound),
        "visible_divisor_bound": int(args.visible_divisor_bound),
        "locked_state_rows": len(state_rows),
        "key_rows": key_rows,
        "replay_summary_rows": replay_summary,
        "promotion_eligible": any(
            bool(row["promotion_eligible"]) for row in replay_summary
        ),
        "verdict": "no_promotable_locked_state_key"
        if not any(bool(row["promotion_eligible"]) for row in replay_summary)
        else "candidate_key_found",
        "reason": (
            "The fair integration computes locked-chamber state and tests "
            "whether the boundary margin is a deterministic visible-state "
            "function. No leave-one-out key promoted with zero failures while "
            "clearing the high-scale PGS gate."
        ),
    }
    write_csv(state_rows, args.output_dir / "locked_chamber_states.csv")
    write_csv(key_rows, args.output_dir / "locked_state_key_report.csv")
    write_csv(replay_rows, args.output_dir / "locked_state_replay.csv")
    write_csv(replay_summary, args.output_dir / "locked_state_replay_summary.csv")
    write_json(payload, args.output_dir / "summary.json")
    print(
        "locked_state_rows={rows} promotion_eligible={eligible}".format(
            rows=len(state_rows),
            eligible=str(payload["promotion_eligible"]).lower(),
        )
    )
    for row in replay_summary:
        if row["scale"] in {10**15, 10**18}:
            print(
                "scale={scale} key={key_name} correct={correct}/{shadow_seed_rows} "
                "no_selection={no_selection} audit_failed_if_promoted="
                "{audit_failed_if_promoted} projected_pgs_percent="
                "{projected_pgs_percent:.2f}% promotion_eligible="
                "{promotion_eligible}".format(**row)
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

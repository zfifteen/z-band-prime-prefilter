"""Milestone 0 pure PGS prime-inference scaffold.

This module owns the generation side of the MVP. It does not import classical
primality helpers, next-prime helpers, the old predictor walker, or the shared
divisor-count field. Until a clean PGS boundary law is installed, it fails
closed and records that failure as the generation artifact.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


RULE_SET_VERSION = "pgs-prime-inference-mvp-m0"
MILESTONE = "milestone_0_purity_scaffold"
SUPPORTED_ANCHOR_PRIME = 11
FAILURE_REASON = "BOUNDARY_LAW_UNAVAILABLE"
TRACE_FILENAME = "pgs_prime_inference_pure_trace.jsonl"
SUMMARY_FILENAME = "pgs_prime_inference_pure_summary.json"
OPEN_RESIDUES_MOD30 = frozenset({1, 7, 11, 13, 17, 19, 23, 29})


@dataclass(frozen=True)
class PureGenerationRecord:
    """One pure-generation trace row."""

    step_index: int
    anchor_prime_p: int
    inferred_prime_q_hat: int | None
    inferred_gap_width: int | None
    winner_carrier_w: int | None
    winner_offset: int | None
    winner_divisor_count: int | None
    winner_family: str | None
    first_open_offset: int
    closure_status: str
    threat_margin: int | None
    rule_set_version: str
    inference_status: str
    failure_reason: str | None


def first_open_offset(anchor_prime: int) -> int:
    """Return the first positive even offset open on the mod-30 wheel."""
    residue = anchor_prime % 30
    for offset in (2, 4, 6, 8, 10, 12):
        if (residue + offset) % 30 in OPEN_RESIDUES_MOD30:
            return offset
    raise RuntimeError(f"no wheel-open offset found for anchor {anchor_prime}")


def milestone_0_failure_record(anchor_prime: int) -> PureGenerationRecord:
    """Return the fail-closed Milestone 0 trace record."""
    return PureGenerationRecord(
        step_index=1,
        anchor_prime_p=anchor_prime,
        inferred_prime_q_hat=None,
        inferred_gap_width=None,
        winner_carrier_w=None,
        winner_offset=None,
        winner_divisor_count=None,
        winner_family=None,
        first_open_offset=first_open_offset(anchor_prime),
        closure_status="unresolved",
        threat_margin=None,
        rule_set_version=RULE_SET_VERSION,
        inference_status="failed_closed",
        failure_reason=FAILURE_REASON,
    )


def run_pure_generation(anchor_prime: int, count: int) -> tuple[list[PureGenerationRecord], dict[str, Any]]:
    """Run the pure Milestone 0 generator and return trace rows plus summary."""
    if anchor_prime != SUPPORTED_ANCHOR_PRIME:
        raise ValueError("Milestone 0 pure mode only supports anchor prime 11")
    if count < 1:
        raise ValueError("count must be at least 1")

    started = time.perf_counter()
    records = [milestone_0_failure_record(anchor_prime)]
    summary: dict[str, Any] = {
        "mode": "pure",
        "milestone": MILESTONE,
        "anchor_prime": anchor_prime,
        "requested_count": count,
        "rule_set_version": RULE_SET_VERSION,
        "emitted_inferred_count": 0,
        "generation_failure_count": 1,
        "generation_status": "failed_closed",
        "failure_reason": FAILURE_REASON,
        "trace_record_count": len(records),
        "runtime_seconds": time.perf_counter() - started,
    }
    return records, summary


def write_pure_artifacts(anchor_prime: int, count: int, output_dir: Path) -> dict[str, Path]:
    """Run pure generation and write LF-terminated JSONL and summary artifacts."""
    records, summary = run_pure_generation(anchor_prime=anchor_prime, count=count)
    output_dir.mkdir(parents=True, exist_ok=True)

    trace_path = output_dir / TRACE_FILENAME
    with trace_path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    summary_path = output_dir / SUMMARY_FILENAME
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {"trace_path": trace_path, "summary_path": summary_path}


__all__ = [
    "FAILURE_REASON",
    "MILESTONE",
    "RULE_SET_VERSION",
    "SUMMARY_FILENAME",
    "SUPPORTED_ANCHOR_PRIME",
    "TRACE_FILENAME",
    "PureGenerationRecord",
    "first_open_offset",
    "milestone_0_failure_record",
    "run_pure_generation",
    "write_pure_artifacts",
]

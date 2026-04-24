"""External audit for already-emitted PGS prime-inference traces."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from sympy import isprime, nextprime


AUDIT_SUMMARY_FILENAME = "pgs_prime_inference_audit_summary.json"
VALIDATION_BACKEND = "sympy.isprime+sympy.nextprime"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read one LF-terminated JSONL trace."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row {line_number} is not an object")
            rows.append(row)
    return rows


def audit_trace(trace_path: Path) -> dict[str, Any]:
    """Validate emitted inference rows after generation has completed."""
    started = time.perf_counter()
    rows = _load_jsonl(trace_path)

    generation_failure_count = 0
    inferred_count = 0
    confirmed_count = 0
    validation_failure_count = 0
    first_failed_record: dict[str, Any] | None = None

    for row in rows:
        if row.get("inference_status") != "emitted" or row.get("inferred_prime_q_hat") is None:
            generation_failure_count += 1
            if first_failed_record is None:
                first_failed_record = {
                    "failure_type": "generation_failure",
                    "record": row,
                }
            continue

        inferred_count += 1
        anchor_prime = int(row["anchor_prime_p"])
        inferred_prime = int(row["inferred_prime_q_hat"])
        expected_next_prime = int(nextprime(anchor_prime))
        if inferred_prime == expected_next_prime and bool(isprime(inferred_prime)):
            confirmed_count += 1
            continue

        validation_failure_count += 1
        if first_failed_record is None:
            first_failed_record = {
                "failure_type": "validation_failure",
                "expected_next_prime": expected_next_prime,
                "record": row,
            }

    summary: dict[str, Any] = {
        "mode": "audit",
        "trace_path": str(trace_path),
        "validation_backend": VALIDATION_BACKEND,
        "trace_record_count": len(rows),
        "generation_failure_count": generation_failure_count,
        "inferred_count": inferred_count,
        "confirmed_count": confirmed_count,
        "validation_failure_count": validation_failure_count,
        "first_failure_index": None,
        "first_failed_record": first_failed_record,
        "validation_time": time.perf_counter() - started,
    }

    for index, row in enumerate(rows, start=1):
        if row.get("inference_status") != "emitted" or row.get("inferred_prime_q_hat") is None:
            summary["first_failure_index"] = index
            break
        anchor_prime = int(row["anchor_prime_p"])
        inferred_prime = int(row["inferred_prime_q_hat"])
        if inferred_prime != int(nextprime(anchor_prime)) or not bool(isprime(inferred_prime)):
            summary["first_failure_index"] = index
            break

    return summary


def write_audit_artifact(trace_path: Path, output_dir: Path) -> Path:
    """Audit an existing trace and write one summary JSON artifact."""
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = audit_trace(trace_path)
    summary_path = output_dir / AUDIT_SUMMARY_FILENAME
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary_path


__all__ = [
    "AUDIT_SUMMARY_FILENAME",
    "VALIDATION_BACKEND",
    "audit_trace",
    "write_audit_artifact",
]

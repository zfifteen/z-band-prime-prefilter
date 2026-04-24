#!/usr/bin/env python3
"""CLI for the PGS Prime Inference Generator Milestone 0 scaffold."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from .audit import write_audit_artifact
    from .pure_generator import SUPPORTED_ANCHOR_PRIME, write_pure_artifacts
except ImportError:  # pragma: no cover - direct script execution
    MODULE_DIR = Path(__file__).resolve().parent
    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))
    from audit import write_audit_artifact
    from pure_generator import SUPPORTED_ANCHOR_PRIME, write_pure_artifacts


DEFAULT_OUTPUT_DIR = Path("output/prime_inference_generator")


def build_parser() -> argparse.ArgumentParser:
    """Build the MVP CLI parser."""
    parser = argparse.ArgumentParser(
        description="PGS Prime Inference Generator MVP scaffold.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated JSONL and JSON artifacts.",
    )
    parser.add_argument(
        "--mode",
        choices=["pure"],
        help="Run pure PGS generation. Validation is a separate audit command.",
    )
    parser.add_argument(
        "--anchor-prime",
        type=int,
        default=SUPPORTED_ANCHOR_PRIME,
        help="Known anchor prime. Milestone 0 supports only 11.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="Requested inferred prime count.",
    )
    parser.add_argument(
        "--audit-existing-jsonl",
        type=Path,
        help="Audit an already-emitted JSONL trace.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run pure generation or audit over an existing trace."""
    args = build_parser().parse_args(argv)
    if args.audit_existing_jsonl is not None:
        if args.mode is not None:
            raise ValueError("audit mode must not be combined with --mode pure")
        write_audit_artifact(args.audit_existing_jsonl, args.output_dir)
        return 0

    if args.mode != "pure":
        raise ValueError("use --mode pure or --audit-existing-jsonl")

    write_pure_artifacts(
        anchor_prime=args.anchor_prime,
        count=args.count,
        output_dir=args.output_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

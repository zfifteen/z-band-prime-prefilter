"""Tests for the minimal PGS iprime generator restart."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIR = ROOT / "src" / "python"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

import z_band_prime_predictor.pgs_closure as pgs_closure  # noqa: E402
import z_band_prime_predictor.simple_pgs_generator as simple_pgs_generator  # noqa: E402
from z_band_prime_predictor.pgs_closure import (  # noqa: E402
    PGS_CLOSED,
    PGS_OPEN,
    pgs_closure_segment,
)
from z_band_prime_predictor.simple_pgs_generator import (  # noqa: E402
    PGS_CHAMBER_RESET_RULE_ID,
    PGS_GENERATOR_FREEZE_ID,
    PGS_GENERATOR_VERSION,
    PGSUnresolvedError,
    PGS_SOURCE,
    emit_record,
    emit_records,
    pgs_probe_certificate,
)
from z_band_prime_predictor.simple_pgs_controller import (  # noqa: E402
    diagnostic_record,
    diagnostic_records,
    main as controller_main,
    summary,
)
from z_band_prime_predictor.simple_pgs_audit import (  # noqa: E402
    audit_report,
    audit_summary,
    main as audit_main,
)


def test_record_has_only_p_and_q():
    """The minimal record contract should stay physically small."""
    record = emit_record(11, candidate_bound=2)

    assert set(record) == {"p", "q"}
    assert record == {"p": 11, "q": 13}


def test_generator_freeze_version_is_locked():
    """The frozen generator iteration should have a stable version id."""
    assert PGS_GENERATOR_VERSION == "1.1.0"
    assert PGS_GENERATOR_FREEZE_ID == "pgs_inference_generator_v1_1_pgs_only"


def test_emit_records_emits_when_each_anchor_has_one_pgs_survivor():
    """Every supplied anchor should emit when PGS closure leaves one survivor."""
    anchors = [11, 17, 29]
    records = emit_records(anchors, candidate_bound=2)

    assert len(records) == len(anchors)
    assert [record["p"] for record in records] == anchors
    assert all(set(record) == {"p", "q"} for record in records)
    assert records == [
        {"p": 11, "q": 13},
        {"p": 17, "q": 19},
        {"p": 29, "q": 31},
    ]


def test_emit_record_fails_closed_for_multiple_pgs_survivors():
    """The generator must not guess when pure PGS closure leaves survivors."""
    try:
        emit_record(11)
    except PGSUnresolvedError as exc:
        assert "PGS selector did not resolve" in str(exc)
    else:
        raise AssertionError("expected PGSUnresolvedError")


def test_pgs_closure_segment_marks_only_wheel_open_candidates_open():
    """The classifier should report open status without prime labels."""
    statuses = pgs_closure_segment(11, 8)

    assert statuses.tolist() == [
        PGS_CLOSED,
        PGS_OPEN,
        PGS_CLOSED,
        PGS_CLOSED,
        PGS_CLOSED,
        PGS_OPEN,
        PGS_CLOSED,
        PGS_OPEN,
    ]


def test_pgs_closure_segment_rejects_nonpositive_bound():
    """The classifier should fail explicitly on an invalid chamber bound."""
    try:
        pgs_closure_segment(11, 0)
    except ValueError as exc:
        assert "candidate_bound must be positive" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_pgs_closure_source_has_no_forbidden_classical_tools():
    """The classifier source must not contain forbidden prime-oracle tools."""
    source = (
        SOURCE_DIR / "z_band_prime_predictor" / "pgs_closure.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "divisor_counts_segment",
        "z_band_prime_composite_field",
        "trial",
        "factor",
        "factorint",
        "gmpy2",
        "sympy",
        "nextprime",
        "isprime",
        "is_prime",
        "primerange",
        "sieve",
        "Miller",
        "miller",
    ]
    assert all(term not in source for term in forbidden_terms)


def test_pgs_runtime_does_not_call_forbidden_prime_oracles(monkeypatch):
    """The generator path should survive forbidden-oracle sentinels."""
    import gmpy2
    import sympy

    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden prime oracle called")

    monkeypatch.setattr(gmpy2, "is_prime", forbidden)
    monkeypatch.setattr(sympy, "isprime", forbidden)
    monkeypatch.setattr(sympy, "nextprime", forbidden)

    assert pgs_closure.pgs_closure_segment(11, 2).tolist() == [
        PGS_CLOSED,
        PGS_OPEN,
    ]
    assert emit_record(11, candidate_bound=2) == {"p": 11, "q": 13}


def test_pgs_result_is_not_validated_by_fallback_before_labeling():
    """A PGS-selected row should have no fallback agreement field."""
    record = diagnostic_record(11, candidate_bound=2)
    assert record["p"] == 11
    assert record["q"] == 13
    assert record["source"] == PGS_SOURCE
    assert record["certificate"]["rule_id"] == PGS_CHAMBER_RESET_RULE_ID
    assert record["certificate"]["gap_offset"] == 2
    assert "fallback_agreed" not in record["certificate"]
    assert diagnostic_record(17, candidate_bound=2)["source"] == PGS_SOURCE


def test_pgs_source_is_not_confirmed_by_trial_division(monkeypatch):
    """A future trial-free PGS certificate must not be prime-checked inline."""
    def fake_probe_certificate(_p, _candidate_bound):
        return {"q": 13, "rule_id": "trial_free_fixture", "gap_offset": 2}

    monkeypatch.setattr(
        simple_pgs_generator,
        "pgs_probe_certificate",
        fake_probe_certificate,
    )

    q, source, certificate = simple_pgs_generator.resolve_q(11)

    assert q == 13
    assert source == PGS_SOURCE
    assert "fallback_agreed" not in certificate


def test_pgs_unresolved_raises_without_fallback(monkeypatch):
    """The PGS-only generator should fail explicitly instead of falling back."""
    def unresolved(_p, _candidate_bound):
        return None

    monkeypatch.setattr(simple_pgs_generator, "pgs_probe_certificate", unresolved)

    try:
        simple_pgs_generator.resolve_q(11)
    except PGSUnresolvedError as exc:
        assert "PGS selector did not resolve" in str(exc)
    else:
        raise AssertionError("expected PGSUnresolvedError")


def test_high_scale_multiple_survivors_fail_closed():
    """The selector must not emit from a multi-survivor PGS chamber."""
    assert pgs_probe_certificate(1000000033, 1024) is None
    try:
        emit_record(1000000033, candidate_bound=1024)
    except PGSUnresolvedError as exc:
        assert "PGS selector did not resolve" in str(exc)
    else:
        raise AssertionError("expected PGSUnresolvedError")


def test_sidecar_diagnostics_report_source_outside_emitted_stream():
    """Diagnostics may report source without changing emitted records."""
    records = emit_records([11, 17], candidate_bound=2)
    diagnostics = diagnostic_records([11, 17], candidate_bound=2)

    assert records == [{"p": 11, "q": 13}, {"p": 17, "q": 19}]
    assert diagnostics[0]["source"] == PGS_SOURCE
    assert diagnostics[0]["certificate"]["gap_offset"] == 2
    assert diagnostics[1]["source"] == PGS_SOURCE
    assert diagnostics[1]["certificate"]["gap_offset"] == 2
    assert diagnostics[1]["chain_seed"] is None
    assert diagnostics[1]["chain_limit"] is None
    assert diagnostics[1]["chain_position_selected"] is None
    assert diagnostics[1]["chain_nodes_checked"] == []
    assert diagnostics[1]["chain_horizon_closed_nodes"] == []
    assert diagnostics[1]["chain_horizon_closure_witnesses"] == {}
    assert diagnostics[1]["chain_horizon_bound"] is None
    assert diagnostics[1]["chain_horizon_complete"] is False
    assert diagnostics[1]["chain_horizon_closure_success"] is False
    assert diagnostics[1]["chain_fallback_success"] is False
    assert diagnostics[1]["full_fallback_used"] is False


def test_minimal_summaries_have_only_requested_counts():
    """Summaries should not grow metadata fields."""
    records = emit_records([11, 17], candidate_bound=2)

    assert summary(records) == {"anchors": 2, "emitted": 2}


def test_cli_writes_lf_records_and_summary(tmp_path):
    """The controller CLI should write LF-terminated artifacts."""
    assert (
        controller_main(
            [
                "--anchors",
                "11,17",
                "--candidate-bound",
                "2",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )

    records_path = tmp_path / "records.jsonl"
    diagnostics_path = tmp_path / "diagnostics.jsonl"
    summary_path = tmp_path / "summary.json"
    assert b"\r\n" not in records_path.read_bytes()
    assert b"\r\n" not in diagnostics_path.read_bytes()
    assert b"\r\n" not in summary_path.read_bytes()

    records = [
        json.loads(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
    ]
    assert all(set(record) == {"p", "q"} for record in records)
    diagnostics = [
        json.loads(line)
        for line in diagnostics_path.read_text(encoding="utf-8").splitlines()
    ]
    assert all(
        set(record)
        == {
            "p",
            "q",
            "source",
            "certificate",
            "chain_seed",
            "chain_limit",
            "chain_position_selected",
            "chain_nodes_checked",
            "chain_horizon_closed_nodes",
            "chain_horizon_closure_witnesses",
            "chain_horizon_bound",
            "chain_horizon_complete",
            "chain_horizon_closure_success",
            "chain_fallback_success",
            "full_fallback_used",
        }
        for record in diagnostics
    )
    assert diagnostics[0]["source"] == PGS_SOURCE
    assert diagnostics[0]["certificate"]["gap_offset"] == 2
    assert diagnostics[1]["source"] == PGS_SOURCE
    assert diagnostics[1]["certificate"]["gap_offset"] == 2
    assert json.loads(summary_path.read_text(encoding="utf-8")) == {
        "anchors": 2,
        "emitted": 2,
    }


def test_audit_cli_writes_report_outside_generator(tmp_path):
    """Audit/report output should come from the audit module, not generator."""
    generator_dir = tmp_path / "generated"
    audit_dir = tmp_path / "audit"
    assert (
        controller_main(
            [
                "--anchors",
                "11,17",
                "--candidate-bound",
                "2",
                "--output-dir",
                str(generator_dir),
            ]
        )
        == 0
    )
    assert (
        audit_main(
            [
                "--records",
                str(generator_dir / "records.jsonl"),
                "--diagnostics",
                str(generator_dir / "diagnostics.jsonl"),
                "--output-dir",
                str(audit_dir),
            ]
        )
        == 0
    )

    summary_path = audit_dir / "summary.json"
    report_path = audit_dir / "report.json"
    assert b"\r\n" not in summary_path.read_bytes()
    assert b"\r\n" not in report_path.read_bytes()
    assert json.loads(summary_path.read_text(encoding="utf-8")) == {
        "anchors": 2,
        "confirmed": 2,
        "emitted": 2,
        "failed": 0,
    }
    assert json.loads(report_path.read_text(encoding="utf-8")) == {
        "anchors_scanned": 2,
        "emitted_count": 2,
        "audit_confirmed": 2,
        "audit_failed": 0,
        "accuracy_status": "PASS",
        "pgs_status": "PGS_PASS",
        "pgs_count": 2,
        "shadow_seed_recovery_count": 0,
        "chain_horizon_closure_count": 0,
        "chain_fallback_count": 0,
        "fallback_count": 0,
        "pgs_rate": 1.0,
        "shadow_seed_recovery_rate": 0.0,
        "chain_horizon_closure_rate": 0.0,
        "chain_fallback_rate": 0.0,
        "fallback_rate": 0.0,
        "pgs_percent": 100.0,
        "shadow_seed_recovery_percent": 0.0,
        "chain_horizon_closure_percent": 0.0,
        "chain_fallback_percent": 0.0,
        "fallback_percent": 0.0,
        "generator_status": "PGS_PASS",
        "pgs_by_rule": {PGS_CHAMBER_RESET_RULE_ID: 2},
        "pgs_missing_certificate_count": 0,
        "first_failure": None,
    }


def test_audit_report_surfaces_fallback_displacement_metrics():
    """The report should make PGS displacement the visible metric."""
    records = emit_records([11, 17, 29], candidate_bound=2)
    diagnostics = diagnostic_records([11, 17, 29], candidate_bound=2)

    assert audit_report(records, diagnostics) == {
        "anchors_scanned": 3,
        "emitted_count": 3,
        "audit_confirmed": 3,
        "audit_failed": 0,
        "accuracy_status": "PASS",
        "pgs_status": "PGS_PASS",
        "pgs_count": 3,
        "shadow_seed_recovery_count": 0,
        "chain_horizon_closure_count": 0,
        "chain_fallback_count": 0,
        "fallback_count": 0,
        "pgs_rate": 1.0,
        "shadow_seed_recovery_rate": 0.0,
        "chain_horizon_closure_rate": 0.0,
        "chain_fallback_rate": 0.0,
        "fallback_rate": 0.0,
        "pgs_percent": 100.0,
        "shadow_seed_recovery_percent": 0.0,
        "chain_horizon_closure_percent": 0.0,
        "chain_fallback_percent": 0.0,
        "fallback_percent": 0.0,
        "generator_status": "PGS_PASS",
        "pgs_by_rule": {PGS_CHAMBER_RESET_RULE_ID: 3},
        "pgs_missing_certificate_count": 0,
        "first_failure": None,
    }


def test_new_generator_does_not_import_old_graph_generator():
    """The clean restart must not reuse the graph generator."""
    source = (
        SOURCE_DIR / "z_band_prime_predictor" / "simple_pgs_generator.py"
    ).read_text(encoding="utf-8")

    assert "prime_inference_generator" not in source
    assert "experimental_graph_prime_generator" not in source
    assert "boundary_certificate_graph" not in source


def test_new_generator_does_not_use_forbidden_classical_tools():
    """The generator must not contain classical or fallback helpers."""
    source = (
        SOURCE_DIR / "z_band_prime_predictor" / "simple_pgs_generator.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "trial",
        "fallback",
        "has_trial",
        "divisor_witness",
        "divisor_counts_segment",
        "z_band_prime_composite_field",
        "next_prime",
        "sympy",
        "nextprime",
        "isprime",
        "primerange",
        "factorint",
        "gmpy2",
        "Miller",
        "miller",
    ]
    assert all(term not in source for term in forbidden_terms)


def test_new_generator_file_does_not_contain_audit_code():
    """Audit/report code must live outside the generator file."""
    source = (
        SOURCE_DIR / "z_band_prime_predictor" / "simple_pgs_generator.py"
    ).read_text(encoding="utf-8")

    forbidden_terms = [
        "audit",
        "report",
        "confirmed",
        "failed",
        "actual_q",
        "argparse",
        "json",
        "Path",
        "write",
        "diagnostic",
        "summary",
        "main",
    ]
    assert all(term not in source for term in forbidden_terms)


def test_controller_can_orchestrate_generation_and_audit(tmp_path):
    """The controller should orchestrate generation artifacts and audit."""
    assert (
        controller_main(
            [
                "--anchors",
                "11,17,29",
                "--candidate-bound",
                "2",
                "--audit",
                "--output-dir",
                str(tmp_path),
            ]
        )
        == 0
    )

    assert json.loads((tmp_path / "summary.json").read_text(encoding="utf-8")) == {
        "anchors": 3,
        "emitted": 3,
    }
    assert json.loads(
        (tmp_path / "audit_summary.json").read_text(encoding="utf-8")
    ) == {
        "anchors": 3,
        "emitted": 3,
        "confirmed": 3,
        "failed": 0,
    }
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8")) == {
        "anchors_scanned": 3,
        "emitted_count": 3,
        "audit_confirmed": 3,
        "audit_failed": 0,
        "accuracy_status": "PASS",
        "pgs_status": "PGS_PASS",
        "pgs_count": 3,
        "shadow_seed_recovery_count": 0,
        "chain_horizon_closure_count": 0,
        "chain_fallback_count": 0,
        "fallback_count": 0,
        "pgs_rate": 1.0,
        "shadow_seed_recovery_rate": 0.0,
        "chain_horizon_closure_rate": 0.0,
        "chain_fallback_rate": 0.0,
        "fallback_rate": 0.0,
        "pgs_percent": 100.0,
        "shadow_seed_recovery_percent": 0.0,
        "chain_horizon_closure_percent": 0.0,
        "chain_fallback_percent": 0.0,
        "fallback_percent": 0.0,
        "generator_status": "PGS_PASS",
        "pgs_by_rule": {PGS_CHAMBER_RESET_RULE_ID: 3},
        "pgs_missing_certificate_count": 0,
        "first_failure": None,
    }

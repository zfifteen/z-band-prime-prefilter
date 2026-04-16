"""Doc-surface consistency checks for live proof-status wording."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def iter_live_markdown_files() -> list[Path]:
    """Return the non-archived markdown files on the live docs surface."""
    files = [ROOT / "README.md", ROOT / "GWR_PROOF.md"]
    files.extend((ROOT / "docs").rglob("*.md"))
    files.extend((ROOT / "gwr").rglob("*.md"))

    live_files: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        if "archive" in path.parts:
            continue
        if path in seen or not path.exists():
            continue
        seen.add(path)
        live_files.append(path)
    return sorted(live_files)


def test_live_markdown_has_no_stale_proof_status_phrases():
    """Live docs should not contain stale proof-status phrasing."""
    banned_phrases = [
        "conditionally proved under the recorded BHP/Robin assumptions",
        "conditionally proved for every prime gap",
        "GWR is already conditionally proved",
        "theorem candidate",
        "theorem candidates",
        "gwr/findings/no_later_simpler_composite_theorem.md",
        "gwr/findings/square_exclusion_first_d4_theorem.md",
        "standalone-candidates/",
    ]

    offending: list[str] = []
    for path in iter_live_markdown_files():
        text = path.read_text(encoding="utf-8")
        for phrase in banned_phrases:
            if phrase in text:
                offending.append(f"{path.relative_to(ROOT)} :: {phrase}")

    assert not offending, "stale live proof-status wording found:\n" + "\n".join(offending)


def test_live_proof_status_anchors_remain_present():
    """The headline proof-status anchors should stay explicit."""
    gwr_proof = (ROOT / "GWR_PROOF.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    headline = (ROOT / "docs" / "current_headline_results.md").read_text(encoding="utf-8")

    assert "current proof surface" in gwr_proof
    assert "proved and closed" in gwr_proof
    assert "exact corollary of the proved GWR theorem" in readme
    assert "fixed cutoff theorem is false" in headline

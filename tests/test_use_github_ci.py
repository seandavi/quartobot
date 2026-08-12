"""Tests for `quartobot use github-ci`."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from quartobot.cli import main
from quartobot.use_github_ci import (
    apply_github_ci,
    format_outcome,
)

# ──────────────────────────────────────────── lean (default) mode


def test_lean_apply_writes_ci_machinery(tmp_path):
    """Lean default: render.yml + pr-closed.yml; no banner files."""
    outcome = apply_github_ci(tmp_path)
    assert outcome.project_type == "manuscript"
    assert outcome.with_versioned_snapshots is False
    must_exist = [
        ".github/workflows/render.yml",
        ".github/workflows/pr-closed.yml",
    ]
    for rel in must_exist:
        assert (tmp_path / rel).exists(), f"{rel} not created"

    # Banner files are versioned-snapshots-only.
    assert not (tmp_path / "_version-banner.html.template").exists()
    assert not (tmp_path / "_version-banner.html").exists()

    render = (tmp_path / ".github/workflows/render.yml").read_text()
    assert "project-type: manuscript" in render
    # Lean mode targets the lean reusable workflow.
    assert "render-reusable-lean.yml" in render
    assert "uses: seandavi/quartobot/.github/workflows/render-reusable-lean.yml@main" in render
    assert "render-reusable.yml@" not in render

    pr_closed = (tmp_path / ".github/workflows/pr-closed.yml").read_text()
    assert "Clean up PR preview" in pr_closed
    assert "types: [closed]" in pr_closed


def test_lean_apply_no_manual_merge_snippet(tmp_path):
    """Lean mode doesn't need a banner include in _quarto.yml."""
    pre_render_cmd = (
        "quartobot resolve --from-scan . --output references.json --id-mode citation-key"
    )
    (tmp_path / "_quarto.yml").write_text(
        f"project:\n  type: default\n  pre-render: {pre_render_cmd}\n"
    )
    outcome = apply_github_ci(tmp_path)
    assert outcome.manual_merge_snippet is None


def test_lean_format_outcome_mentions_versions_page(tmp_path):
    outcome = apply_github_ci(tmp_path)
    out = format_outcome(outcome, project=tmp_path)
    assert "Pipeline:     lean" in out
    assert "render.yml" in out
    assert "pr-closed.yml" in out
    assert "/versions/" in out


# ──────────────────────────────────────────── versioned-snapshots mode


def test_versioned_apply_writes_banner_files(tmp_path):
    """`--with-versioned-snapshots` writes the banner files."""
    outcome = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    assert outcome.with_versioned_snapshots is True
    must_exist = [
        "_version-banner.html.template",
        "_version-banner.html",
        ".github/workflows/render.yml",
        ".github/workflows/pr-closed.yml",
    ]
    for rel in must_exist:
        assert (tmp_path / rel).exists(), f"{rel} not created"

    render = (tmp_path / ".github/workflows/render.yml").read_text()
    # Versioned mode targets the v0.1 reusable workflow.
    assert "uses: seandavi/quartobot/.github/workflows/render-reusable.yml@main" in render
    assert "render-reusable.yml@" in render
    assert "render-reusable-lean.yml" not in render


def test_versioned_manual_merge_snippet_when_yml_lacks_include(tmp_path):
    pre_render_cmd = (
        "quartobot resolve --from-scan . --output references.json --id-mode citation-key"
    )
    (tmp_path / "_quarto.yml").write_text(
        "project:\n"
        "  type: default\n"
        f"  pre-render: {pre_render_cmd}\n"
        "bibliography:\n"
        "  - references.bib\n"
        "  - references.json\n"
    )
    outcome = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    assert outcome.manual_merge_snippet is not None
    assert "_version-banner.html" in outcome.manual_merge_snippet
    assert "include-before-body" in outcome.manual_merge_snippet


def test_versioned_manual_merge_snippet_suppressed_when_already_included(tmp_path):
    (tmp_path / "_quarto.yml").write_text(
        "project:\n"
        "  type: default\n"
        "format:\n"
        "  html:\n"
        "    include-before-body:\n"
        "      - _version-banner.html\n"
    )
    outcome = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    assert outcome.manual_merge_snippet is None


def test_versioned_manual_merge_snippet_suppressed_when_yml_missing(tmp_path):
    outcome = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    assert outcome.manual_merge_snippet is None


def test_versioned_manual_merge_snippet_robust_to_broken_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    outcome = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    assert outcome.manual_merge_snippet is not None


def test_versioned_format_outcome_mentions_permalink(tmp_path):
    outcome = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    out = format_outcome(outcome, project=tmp_path)
    assert "Pipeline:     versioned-snapshots" in out
    assert "per-commit permalink" in out
    assert "_version-banner.html" in out


# ──────────────────────────────────────────── project-type detection


def test_apply_respects_book_project_type(tmp_path):
    outcome = apply_github_ci(tmp_path, project_type="book")
    assert outcome.project_type == "book"
    render = (tmp_path / ".github/workflows/render.yml").read_text()
    assert "project-type: book" in render


def test_apply_auto_detects_book(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "book"}}))
    outcome = apply_github_ci(tmp_path)
    assert outcome.project_type == "book"


# ──────────────────────────────────────────── idempotency


def test_lean_apply_is_idempotent(tmp_path):
    apply_github_ci(tmp_path)
    snapshot = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    outcome_second = apply_github_ci(tmp_path)
    for p, content in snapshot.items():
        assert p.read_text() == content, f"{p} changed on re-run"
    for action in outcome_second.actions:
        assert action.status == "skipped-exists", f"{action.path} status: {action.status}"


def test_versioned_apply_is_idempotent(tmp_path):
    apply_github_ci(tmp_path, with_versioned_snapshots=True)
    snapshot = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    outcome_second = apply_github_ci(tmp_path, with_versioned_snapshots=True)
    for p, content in snapshot.items():
        assert p.read_text() == content, f"{p} changed on re-run"
    for action in outcome_second.actions:
        assert action.status == "skipped-exists", f"{action.path} status: {action.status}"


def test_apply_does_not_overwrite_existing_files(tmp_path):
    files = {
        "_version-banner.html.template": "original template\n",
        "_version-banner.html": "original banner\n",
        ".github/workflows/render.yml": "original workflow\n",
        ".github/workflows/pr-closed.yml": "original pr-closed\n",
    }
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    apply_github_ci(tmp_path, with_versioned_snapshots=True)
    for rel, expected in files.items():
        assert (tmp_path / rel).read_text() == expected, f"{rel} was overwritten"


# ──────────────────────────────────────────── CLI bindings


def test_cli_use_group_help_lists_github_ci():
    runner = CliRunner()
    result = runner.invoke(main, ["use", "--help"])
    assert result.exit_code == 0, result.output
    assert "github-ci" in result.output


def test_cli_use_github_ci_in_empty_dir_defaults_to_lean(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["use", "github-ci", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".github/workflows/render.yml").exists()
    # Lean default doesn't write banner files.
    assert not (tmp_path / "_version-banner.html").exists()
    assert "Pipeline:     lean" in result.output


def test_cli_use_github_ci_with_versioned_snapshots_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["use", "github-ci", str(tmp_path), "--with-versioned-snapshots"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".github/workflows/render.yml").exists()
    assert (tmp_path / "_version-banner.html").exists()
    assert (tmp_path / "_version-banner.html.template").exists()
    assert "Pipeline:     versioned-snapshots" in result.output


def test_cli_use_github_ci_default_path_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["use", "github-ci"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".github/workflows/render.yml").exists()


def test_cli_init_then_use_github_ci_lean_round_trip(tmp_path):
    """Default init + use github-ci should land the lean pipeline without
    needing the banner include in _quarto.yml."""
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    use_result = runner.invoke(main, ["use", "github-ci", str(tmp_path)])
    assert use_result.exit_code == 0, use_result.output
    assert (tmp_path / "_quarto.yml").exists()
    assert (tmp_path / "references.bib").exists()
    assert (tmp_path / ".github/workflows/render.yml").exists()
    assert (tmp_path / ".github/workflows/pr-closed.yml").exists()
    # No banner files, no merge snippet to print.
    assert not (tmp_path / "_version-banner.html").exists()
    assert "include-before-body" not in use_result.output


def test_cli_init_then_use_github_ci_versioned_round_trip(tmp_path):
    runner = CliRunner()
    init_result = runner.invoke(main, ["init", str(tmp_path)])
    assert init_result.exit_code == 0, init_result.output
    use_result = runner.invoke(
        main,
        ["use", "github-ci", str(tmp_path), "--with-versioned-snapshots"],
    )
    assert use_result.exit_code == 0, use_result.output
    assert (tmp_path / "_version-banner.html.template").exists()
    assert (tmp_path / "_version-banner.html").exists()
    # init writes _quarto.yml without the banner include; the merge
    # snippet should be in the output.
    assert "_version-banner.html" in use_result.output
    assert "include-before-body" in use_result.output

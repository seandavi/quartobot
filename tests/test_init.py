"""Tests for the init command and module."""

from __future__ import annotations

import yaml
from click.testing import CliRunner

from quartobot.cli import main
from quartobot.init_project import (
    Action,
    InitOutcome,
    _ensure_gitignore,
    detect_project_type,
    format_outcome,
    init_project,
)


def test_detect_no_yml(tmp_path):
    assert detect_project_type(tmp_path) == "unknown"


def test_detect_book(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "book"}}))
    assert detect_project_type(tmp_path) == "book"


def test_detect_manuscript_default_type(tmp_path):
    (tmp_path / "_quarto.yml").write_text("title: foo\n")
    assert detect_project_type(tmp_path) == "manuscript"


def test_detect_manuscript_explicit_default(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "default"}}))
    assert detect_project_type(tmp_path) == "manuscript"


def test_detect_broken_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    assert detect_project_type(tmp_path) == "unknown"


def test_init_empty_project_writes_only_pipeline_files(tmp_path):
    outcome = init_project(tmp_path)
    assert outcome.project_type == "manuscript"
    must_exist = [
        "_quarto.yml",
        "references.bib",
        ".gitignore",
    ]
    for rel in must_exist:
        assert (tmp_path / rel).exists(), f"{rel} not created"
    # The CI machinery now belongs to `quartobot use github-ci`.
    must_not_exist = [
        "_version-banner.html.template",
        "_version-banner.html",
        ".github/workflows/render.yml",
        ".github/workflows/pr-closed.yml",
    ]
    for rel in must_not_exist:
        assert not (tmp_path / rel).exists(), f"{rel} should not be written by init"
    # The scaffolded _quarto.yml wires the pre-render hook, not a filter,
    # and no longer pulls in the banner include.
    yml = (tmp_path / "_quarto.yml").read_text()
    assert "quartobot resolve" in yml
    assert "--id-mode citation-key" in yml
    assert "filters:" not in yml
    assert "manubot-" not in yml
    assert "_version-banner.html" not in yml


def test_init_book_project_writes_book_quarto_yml(tmp_path):
    outcome = init_project(tmp_path, project_type="book")
    assert outcome.project_type == "book"
    cfg = yaml.safe_load((tmp_path / "_quarto.yml").read_text())
    assert cfg["project"]["type"] == "book"
    # Book yml also drops the banner include.
    assert "_version-banner.html" not in (tmp_path / "_quarto.yml").read_text()


def test_init_auto_detects_book(tmp_path):
    (tmp_path / "_quarto.yml").write_text(yaml.safe_dump({"project": {"type": "book"}}))
    outcome = init_project(tmp_path, project_type="auto")
    assert outcome.project_type == "book"
    assert outcome.manual_merge_snippet is not None
    assert any(a.status == "manual-merge" and a.path.name == "_quarto.yml" for a in outcome.actions)
    # The snippet for manual merge no longer mentions the banner include —
    # that's `use github-ci`'s job.
    assert "_version-banner.html" not in outcome.manual_merge_snippet


def test_init_does_not_overwrite_existing_files(tmp_path):
    files = {
        "_quarto.yml": "original yml\n",
        "references.bib": "@misc{orig, title={Original}}\n",
    }
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    init_project(tmp_path)
    for rel, expected in files.items():
        assert (tmp_path / rel).read_text() == expected, f"{rel} was overwritten"


def test_init_is_idempotent(tmp_path):
    init_project(tmp_path)
    snapshot = {p: p.read_text() for p in tmp_path.rglob("*") if p.is_file()}
    init_project(tmp_path)
    for p, content in snapshot.items():
        assert p.read_text() == content, f"{p} changed on re-init"


def test_init_skips_github_workflows(tmp_path):
    init_project(tmp_path)
    assert not (tmp_path / ".github").exists()


def test_gitignore_created_when_absent(tmp_path):
    action = _ensure_gitignore(tmp_path)
    assert action.status == "appended"
    content = (tmp_path / ".gitignore").read_text()
    assert "_freeze/" in content
    # Both the BibLaTeX artifact pandoc reads and the CSL JSON cache
    # should be ignored — they're both regenerated every render.
    assert "references.resolved.bib" in content
    assert "references.json" in content


def test_gitignore_appends_only_missing_lines(tmp_path):
    (tmp_path / ".gitignore").write_text("existing\n_freeze/\nother\n")
    action = _ensure_gitignore(tmp_path)
    assert action.status == "appended"
    content = (tmp_path / ".gitignore").read_text()
    assert "existing" in content
    assert "other" in content
    assert content.count("_freeze/") == 1
    assert "references.json" in content


def test_gitignore_idempotent_when_all_present(tmp_path):
    _ensure_gitignore(tmp_path)
    action_second = _ensure_gitignore(tmp_path)
    assert action_second.status == "skipped-exists"


def test_format_emits_expected_glyphs(tmp_path):
    outcome = InitOutcome(
        project_type="manuscript",
        actions=[
            Action(path=tmp_path / "_quarto.yml", status="written"),
            Action(path=tmp_path / ".gitignore", status="appended", detail="2 lines"),
            Action(path=tmp_path / "references.bib", status="skipped-exists"),
        ],
    )
    out = format_outcome(outcome, project=tmp_path)
    assert "+ _quarto.yml" in out
    assert "~ .gitignore" in out
    assert "· references.bib" in out
    assert "manuscript" in out
    assert "uv tool install" in out
    # Hint pointing at the follow-up command.
    assert "quartobot use github-ci" in out


def test_format_includes_manual_merge_snippet(tmp_path):
    outcome = InitOutcome(
        project_type="manuscript",
        manual_merge_snippet="# merge me\nproject:\n  pre-render: quartobot resolve\n",
        actions=[
            Action(path=tmp_path / "_quarto.yml", status="manual-merge"),
        ],
    )
    out = format_outcome(outcome, project=tmp_path)
    assert "merge me" in out


def test_cli_init_in_empty_dir(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Next steps:" in result.output
    assert (tmp_path / "_quarto.yml").exists()
    assert not (tmp_path / ".github").exists()


def test_cli_init_book_flag(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["init", str(tmp_path), "--project-type", "book"])
    assert result.exit_code == 0, result.output
    cfg = yaml.safe_load((tmp_path / "_quarto.yml").read_text())
    assert cfg["project"]["type"] == "book"


def test_cli_init_default_path_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "_quarto.yml").exists()

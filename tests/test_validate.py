"""Tests for the validate command and module."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from quartobot.cli import main
from quartobot.validate import (
    Check,
    ValidateOutcome,
    _check_bibliography_declared,
    _check_no_duplicate_cites,
    _check_pre_render_hook,
    _check_quarto_yml_exists,
    _check_resolved_bib_in_bibliography,
    _load_quarto_yml,
    format_outcome,
    validate_project,
)

_GOOD_PRE_RENDER = "quartobot resolve --from-scan . --id-mode citation-key"


def _make_project(
    tmp_path: Path,
    *,
    quarto_yml: object = "ok",
    qmd_content: str = "Some prose.\n",
) -> Path:
    """Build a small Quarto project tree under tmp_path."""
    if quarto_yml == "ok":
        import yaml

        cfg = {
            "project": {"pre-render": _GOOD_PRE_RENDER},
            "bibliography": ["references.bib", "references.resolved.bib"],
        }
        (tmp_path / "_quarto.yml").write_text(yaml.safe_dump(cfg))
    elif isinstance(quarto_yml, dict):
        import yaml

        (tmp_path / "_quarto.yml").write_text(yaml.safe_dump(quarto_yml))
    elif quarto_yml == "broken":
        (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    elif quarto_yml is None:
        pass

    (tmp_path / "index.qmd").write_text(qmd_content)
    return tmp_path


def test_load_missing_yml(tmp_path):
    assert _load_quarto_yml(tmp_path) is None


def test_load_broken_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("not: valid: yaml: at all\n: : :")
    assert _load_quarto_yml(tmp_path) is None


def test_load_non_mapping_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("- a\n- b\n")
    assert _load_quarto_yml(tmp_path) is None


def test_load_ok_yml(tmp_path):
    (tmp_path / "_quarto.yml").write_text("title: ok\n")
    assert _load_quarto_yml(tmp_path) == {"title": "ok"}


def test_quarto_yml_exists(tmp_path):
    _make_project(tmp_path)
    c = _check_quarto_yml_exists(tmp_path)
    assert c.passed


def test_quarto_yml_missing(tmp_path):
    _make_project(tmp_path, quarto_yml=None)
    c = _check_quarto_yml_exists(tmp_path)
    assert not c.passed


def test_bibliography_declared_as_list():
    cfg = {"bibliography": ["references.bib", "references.resolved.bib"]}
    c = _check_bibliography_declared(cfg)
    assert c.passed


def test_bibliography_declared_as_string():
    cfg = {"bibliography": "references.bib"}
    c = _check_bibliography_declared(cfg)
    assert c.passed


def test_bibliography_missing():
    c = _check_bibliography_declared({})
    assert not c.passed


def test_bibliography_garbage_type():
    c = _check_bibliography_declared({"bibliography": 42})
    assert not c.passed


def test_pre_render_hook_set_as_string():
    cfg = {"project": {"pre-render": _GOOD_PRE_RENDER}}
    c = _check_pre_render_hook(cfg)
    assert c.passed


def test_pre_render_hook_set_as_list():
    # Quarto accepts a list of pre-render commands; check substring detection
    # still works against the joined form.
    cfg = {"project": {"pre-render": ["echo hi", _GOOD_PRE_RENDER]}}
    c = _check_pre_render_hook(cfg)
    assert c.passed


def test_pre_render_hook_missing():
    cfg = {"project": {"type": "default"}}
    c = _check_pre_render_hook(cfg)
    assert not c.passed
    assert "missing" in (c.detail or "")


def test_pre_render_hook_no_project_key():
    c = _check_pre_render_hook({})
    assert not c.passed


def test_pre_render_hook_calls_something_else():
    cfg = {"project": {"pre-render": "echo hello"}}
    c = _check_pre_render_hook(cfg)
    assert not c.passed
    assert "quartobot resolve" in (c.detail or "")


def test_pre_render_hook_missing_citation_key_flag():
    # `quartobot resolve` declared, but with the wrong --id-mode (or none) —
    # this silently breaks pandoc-citeproc matching, so validate flags it.
    cfg = {"project": {"pre-render": "quartobot resolve --from-scan ."}}
    c = _check_pre_render_hook(cfg)
    assert not c.passed
    assert "citation-key" in (c.detail or "")


def test_resolved_bib_in_bibliography():
    cfg = {"bibliography": ["references.bib", "references.resolved.bib"]}
    c = _check_resolved_bib_in_bibliography(cfg)
    assert c.passed


def test_legacy_references_json_in_bibliography_passes_with_hint():
    # Back-compat: unmigrated v0.3 projects keep passing, but the
    # detail string nudges them to switch.
    cfg = {"bibliography": ["references.bib", "references.json"]}
    c = _check_resolved_bib_in_bibliography(cfg)
    assert c.passed
    assert "legacy" in (c.detail or "").lower()


def test_resolved_bib_missing_from_bibliography():
    cfg = {"bibliography": ["references.bib"]}
    c = _check_resolved_bib_in_bibliography(cfg)
    assert not c.passed
    assert "Citeproc won't" in (c.detail or "")


def test_resolved_bib_no_bibliography_at_all():
    c = _check_resolved_bib_in_bibliography({})
    assert not c.passed


def test_no_dup_cites_clean(tmp_path):
    _make_project(tmp_path, qmd_content="One @doi:10.1/x cite.\n")
    c = _check_no_duplicate_cites(tmp_path)
    assert c.passed


def test_duplicate_cites_flagged_cross_file(tmp_path):
    p = _make_project(tmp_path, qmd_content="See @doi:10.1/x.\n")
    (p / "other.qmd").write_text("Also @doi:10.1/x.\n")
    c = _check_no_duplicate_cites(p)
    assert not c.passed
    # Message names files, not vague "multiple", and the count is true.
    assert "across multiple files" in (c.detail or "")
    assert "2 files" in (c.detail or "")


def test_same_file_repetition_does_not_fail_validate(tmp_path):
    # Issue #63: same key cited multiple times in one file is normal
    # academic writing (one source, several claims). Must not fail.
    p = _make_project(
        tmp_path,
        qmd_content=(
            "The GTEx paper [@doi:10.1038/ng.2653] established the result.\n"
            "Later, [@doi:10.1038/ng.2653] is cited again for emphasis.\n"
        ),
    )
    c = _check_no_duplicate_cites(p)
    assert c.passed, c.detail


def test_cross_file_duplicate_message_names_real_counts(tmp_path):
    # The pre-fix message said "appear in multiple files" even when all
    # occurrences were in one file. Make sure the new message reports
    # the real per-key file count.
    p = _make_project(tmp_path, qmd_content="See @doi:10.1/x.\n")
    (p / "two.qmd").write_text("Also @doi:10.1/x.\n")
    (p / "three.qmd").write_text("Once more @doi:10.1/x.\n")
    c = _check_no_duplicate_cites(p)
    assert not c.passed
    assert "3 files" in (c.detail or "")


def test_validate_happy_path(tmp_path):
    _make_project(tmp_path, qmd_content="Cite @doi:10.1371/journal.pcbi.1007128.\n")
    outcome = validate_project(tmp_path)
    assert outcome.passed, outcome.failures
    # _quarto.yml + bibliography + pre-render + resolved-bib + dup-cites
    assert len(outcome.checks) == 5


def test_validate_missing_pre_render(tmp_path):
    cfg = {"bibliography": ["references.bib", "references.resolved.bib"]}
    _make_project(tmp_path, quarto_yml=cfg)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "pre-render hook" in [c.name for c in outcome.failures]


def test_validate_resolved_bib_not_in_bibliography(tmp_path):
    cfg = {
        "project": {"pre-render": _GOOD_PRE_RENDER},
        "bibliography": ["references.bib"],
    }
    _make_project(tmp_path, quarto_yml=cfg)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "resolved bibliography in `bibliography:`" in [c.name for c in outcome.failures]


def test_validate_no_quarto_yml(tmp_path):
    _make_project(tmp_path, quarto_yml=None)
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "_quarto.yml exists" in [c.name for c in outcome.failures]
    # Config checks skipped when _quarto.yml is missing.
    assert len(outcome.checks) == 2


def test_validate_broken_yml(tmp_path):
    _make_project(tmp_path, quarto_yml="broken")
    outcome = validate_project(tmp_path)
    assert not outcome.passed
    assert "_quarto.yml parses as YAML" in [c.name for c in outcome.failures]


def test_format_all_passing():
    outcome = ValidateOutcome(
        checks=[
            Check(name="a", passed=True),
            Check(name="b", passed=True, detail="extra info"),
        ]
    )
    out = format_outcome(outcome)
    assert "✓ a" in out
    assert "✓ b — extra info" in out
    assert "All 2 check(s) passed" in out


def test_format_with_failure():
    outcome = ValidateOutcome(
        checks=[
            Check(name="a", passed=True),
            Check(name="b", passed=False, detail="broken"),
        ]
    )
    out = format_outcome(outcome)
    assert "✗ b — broken" in out
    assert "1 of 2 check(s) failed" in out


def test_cli_happy_path_exits_zero(tmp_path):
    _make_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(tmp_path)])
    assert result.exit_code == 0, result.output


def test_cli_failure_exits_one(tmp_path):
    _make_project(tmp_path, quarto_yml={"bibliography": ["references.bib"]})
    runner = CliRunner()
    result = runner.invoke(main, ["validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "✗ pre-render hook" in result.output

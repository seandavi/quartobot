"""Pre-flight validation of a Quarto project for the quartobot pattern.

`quartobot validate` runs a battery of static checks before render:

- `_quarto.yml` exists and declares `bibliography:`.
- `project.pre-render` declares a `quartobot resolve` invocation with
  `--id-mode citation-key` (the mode that lets pandoc-citeproc match
  prose keys against the resolved bibliography).
- The pre-render hook's bibliography output is listed under
  `bibliography:`. The current artifact is `references.resolved.bib`;
  the legacy `references.json` is still accepted with a migration
  hint. Otherwise the hook writes a file that citeproc never reads.
- No cite key appears in more than one file (same-file repetition is
  the normal academic-writing case and is not flagged; cross-file
  duplication is the case the chunked-content pattern can produce by
  accident).

Citation-resolution checks (do all `@doi:` keys actually resolve at
Crossref?) are deliberately out of scope for v0.1 — they'd require
network access. Run `quartobot resolve --dry-run --from-scan .` if you
want that check separately.

Exits 0 if every check passes, 1 if any fail.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from quartobot.scan import scan_path


@dataclass(frozen=True)
class Check:
    """One pre-flight check and its outcome."""

    name: str
    """Short label of what was checked."""
    passed: bool
    """Whether the check passed."""
    detail: str | None = None
    """Optional human-readable detail (e.g. error message)."""


@dataclass
class ValidateOutcome:
    """The aggregate of every check run by `validate_project`."""

    checks: list[Check] = field(default_factory=list)

    @property
    def failures(self) -> list[Check]:
        """Return only failed checks."""
        return [c for c in self.checks if not c.passed]

    @property
    def passed(self) -> bool:
        """True if every check passed."""
        return all(c.passed for c in self.checks)


def _load_quarto_yml(path: Path) -> dict[str, Any] | None:
    """Read `_quarto.yml` from the project root. None if missing or unparsable."""
    yml = path / "_quarto.yml"
    if not yml.exists():
        return None
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if not isinstance(loaded, dict):
        return None
    return loaded


def _check_quarto_yml_exists(project: Path) -> Check:
    """`_quarto.yml` must exist for any Quarto project."""
    yml = project / "_quarto.yml"
    if yml.exists():
        return Check(name="_quarto.yml exists", passed=True)
    return Check(
        name="_quarto.yml exists",
        passed=False,
        detail=f"{yml} not found — is this a Quarto project?",
    )


def _bibliography_list(config: dict[str, Any]) -> list[str]:
    """Normalize `_quarto.yml`'s `bibliography:` value to a list of paths."""
    value = config.get("bibliography")
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _check_bibliography_declared(config: dict[str, Any]) -> Check:
    """`bibliography:` must be set in `_quarto.yml`."""
    bibs = _bibliography_list(config)
    if not bibs:
        return Check(
            name="bibliography declared",
            passed=False,
            detail="_quarto.yml has no `bibliography:` key",
        )
    return Check(
        name="bibliography declared",
        passed=True,
        detail=f"{len(bibs)} file(s): {', '.join(bibs)}",
    )


def _pre_render_value(config: dict[str, Any]) -> str | None:
    """Return `project.pre-render` as a single string, or None.

    Quarto accepts `pre-render:` as either a scalar string or a list of
    strings (each command runs in order). Normalize to a single joined
    string so a substring check across either shape just works.
    """
    project = config.get("project")
    if not isinstance(project, dict):
        return None
    raw = project.get("pre-render")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        return "\n".join(str(item) for item in raw)
    return None


def _check_pre_render_hook(config: dict[str, Any]) -> Check:
    """`project.pre-render` must call `quartobot resolve` with `--id-mode citation-key`."""
    value = _pre_render_value(config)
    if value is None:
        return Check(
            name="pre-render hook",
            passed=False,
            detail=(
                "missing — add to `_quarto.yml`:\n"
                "    project:\n"
                "      pre-render: quartobot resolve --from-scan . "
                "--id-mode citation-key"
            ),
        )
    if "quartobot resolve" not in value:
        return Check(
            name="pre-render hook",
            passed=False,
            detail=(
                f"`project.pre-render` is set but does not call `quartobot resolve`: {value!r}"
            ),
        )
    if "citation-key" not in value:
        return Check(
            name="pre-render hook",
            passed=False,
            detail=(
                "`quartobot resolve` is invoked but `--id-mode citation-key` is missing. "
                "Without it, CSL `id`s are manubot's short hashes "
                "(`YuJbg3zO`), not the prose keys (`doi:10.1371/...`), and "
                "pandoc-citeproc silently fails to match any cites."
            ),
        )
    return Check(
        name="pre-render hook",
        passed=True,
        detail="`quartobot resolve --id-mode citation-key` declared",
    )


def _check_resolved_bib_in_bibliography(config: dict[str, Any]) -> Check:
    """The pre-render hook's BibLaTeX output must be in `bibliography:`.

    The current artifact is ``references.resolved.bib``. The legacy
    ``references.json`` from v0.3 and earlier still counts as a pass
    (so unmigrated projects keep rendering), but the detail string
    nudges users toward the BibLaTeX file — that's the one Quarto's
    ``manuscript`` project type can read cleanly.
    """
    bibs = _bibliography_list(config)
    if "references.resolved.bib" in bibs:
        return Check(
            name="resolved bibliography in `bibliography:`",
            passed=True,
            detail="`references.resolved.bib` listed in `bibliography:`",
        )
    if "references.json" in bibs:
        return Check(
            name="resolved bibliography in `bibliography:`",
            passed=True,
            detail=(
                "`references.json` listed in `bibliography:` — legacy "
                "v0.3 pattern. Works for `type: default` projects but "
                "breaks Quarto's `type: manuscript` Google Scholar "
                "post-process. Switch to `references.resolved.bib` to "
                "support both."
            ),
        )
    return Check(
        name="resolved bibliography in `bibliography:`",
        passed=False,
        detail=(
            f"`references.resolved.bib` is not in `bibliography:` "
            f"({bibs}). Citeproc won't read the resolved entries the "
            f"pre-render hook writes."
        ),
    )


def _check_no_duplicate_cites(project: Path) -> Check:
    """Cite keys appearing across multiple files break pre-commit-hook flow.

    Same-key-twice-in-one-file is the normal academic-writing case (one
    source backing claims in two paragraphs) and is not flagged. Only
    cross-file occurrences trip this check.
    """
    result = scan_path(project)
    duplicates = result.duplicates
    if not duplicates:
        return Check(
            name="no duplicate cite keys",
            passed=True,
            detail=f"{len(result.unique_keys)} unique key(s) in {result.files_scanned} file(s)",
        )
    # Build "@key (N files)" examples so the message names actual files
    # and counts, not vague pluralization.
    items = sorted(duplicates.items(), key=lambda kv: kv[0])
    examples = []
    for key, occs in items[:3]:
        n_files = len({occ.file for occ in occs})
        examples.append(f"{key} ({n_files} files)")
    suffix = f" (e.g. {', '.join(examples)})"
    if len(items) > 3:
        suffix += f" — {len(items) - 3} more"
    return Check(
        name="no duplicate cite keys",
        passed=False,
        detail=f"{len(duplicates)} key(s) appear across multiple files{suffix}",
    )


def validate_project(project: Path) -> ValidateOutcome:
    """Run every check against `project` (the Quarto project root)."""
    outcome = ValidateOutcome()

    yml_check = _check_quarto_yml_exists(project)
    outcome.checks.append(yml_check)

    if yml_check.passed:
        config = _load_quarto_yml(project)
        if config is None:
            outcome.checks.append(
                Check(
                    name="_quarto.yml parses as YAML",
                    passed=False,
                    detail="failed to parse — fix YAML syntax",
                )
            )
        else:
            outcome.checks.append(_check_bibliography_declared(config))
            outcome.checks.append(_check_pre_render_hook(config))
            outcome.checks.append(_check_resolved_bib_in_bibliography(config))

    # Duplicate-cite scan is independent of _quarto.yml.
    outcome.checks.append(_check_no_duplicate_cites(project))

    return outcome


def format_outcome(outcome: ValidateOutcome) -> str:
    """Pretty-print a ValidateOutcome."""
    lines: list[str] = []
    for c in outcome.checks:
        glyph = "✓" if c.passed else "✗"
        line = f"  {glyph} {c.name}"
        if c.detail:
            line += f" — {c.detail}"
        lines.append(line)
    lines.append("")
    n_fail = len(outcome.failures)
    if n_fail == 0:
        lines.append(f"All {len(outcome.checks)} check(s) passed.")
    else:
        lines.append(f"{n_fail} of {len(outcome.checks)} check(s) failed. Exit 1.")
    return "\n".join(lines)


__all__: Sequence[str] = (
    "Check",
    "ValidateOutcome",
    "format_outcome",
    "validate_project",
)

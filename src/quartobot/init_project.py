"""Scaffold the citation-pipeline pieces of the quartobot pattern.

`quartobot init` writes the minimum a vanilla Quarto project needs to
adopt the citation pipeline: a `_quarto.yml` wired with the
`quartobot resolve` pre-render hook + `bibliography:` list, a seed
`references.bib`, and a `.gitignore` augment so `references.json`
(regenerated each render) stays out of the repo.

The GitHub Actions render workflow, version banner, and PR-preview
cleanup live in `quartobot use github-ci` now — opt-in machinery, not
part of the citation-pipeline minimum.

Conservative by default:

- Files that already exist are NEVER overwritten. `init` skips them and
  reports what it skipped.
- `_quarto.yml` is the one file where partial overlap is likely — for
  that path, if the file exists, init prints a YAML snippet the user
  should merge in manually.
- `.gitignore` gets new lines appended (idempotent).

No interactive prompts, no auto-merge. Re-running is safe and a no-op
once everything's in place.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

# ---------------------------------------------------------------- templates


_QUARTO_YML_MANUSCRIPT = """\
project:
  type: default
  # Resolves @doi:, @pmid:, @arxiv:, @isbn:, @url:, @wikidata:, @pmcid:,
  # and bare DOIs before pandoc runs. The resolved CSL JSON lands in
  # references.json (gitignored — regenerated each render) and pandoc
  # citeproc reads it alongside hand-curated entries in references.bib.
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

bibliography:
  - references.bib
  - references.json

format:
  html:
    toc: true
    embed-resources: true
  pdf:
    documentclass: article
    keep-tex: true
"""

_QUARTO_YML_BOOK = """\
project:
  type: book
  # See the manuscript template for what the pre-render hook does.
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

book:
  title: "My quartobot book"
  author: "Your Name"
  date: today
  chapters:
    - index.qmd
  search: true
  page-navigation: true

bibliography:
  - references.bib
  - references.json

format:
  html:
    theme: cosmo
    toc: true
"""

_REFERENCES_BIB = """\
% Hand-curated entries live here. Auto-resolved entries written by
% `quartobot resolve` land in references.json (regenerated each render,
% ignored by git).
"""


_GITIGNORE_LINES = [
    "# quartobot",
    "_book/",
    "_freeze/",
    ".quarto/",
    "references.json",
    "*.bak-*",
    "*_files/",
    "**/*.quarto_ipynb",
]


# ---------------------------------------------------------------- outcome types


ActionStatus = Literal["written", "skipped-exists", "appended", "manual-merge"]


@dataclass(frozen=True)
class Action:
    """One file write (or non-write) attempted by an init or use run."""

    path: Path
    status: ActionStatus
    detail: str | None = None


@dataclass
class InitOutcome:
    """The aggregate result of an init run."""

    actions: list[Action] = field(default_factory=list)
    project_type: str = "manuscript"
    manual_merge_snippet: str | None = None


# ---------------------------------------------------------------- helpers


def detect_project_type(project: Path) -> str:
    """Read `_quarto.yml`; return `"manuscript"`, `"book"`, or `"unknown"`.

    A missing or unparsable `_quarto.yml` returns `"unknown"` — init
    treats that as the manuscript default.
    """
    yml = project / "_quarto.yml"
    if not yml.exists():
        return "unknown"
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return "unknown"
    if not isinstance(loaded, dict):
        return "unknown"
    proj = loaded.get("project")
    if isinstance(proj, dict) and proj.get("type") == "book":
        return "book"
    return "manuscript"


def write_if_missing(path: Path, content: str) -> Action:
    """Write `content` at `path` only if the file isn't already there.

    Returns an Action with `written` or `skipped-exists`. Public so
    other scaffolders (`quartobot use ...`) can share the same
    never-clobber convention without depending on a private helper.
    """
    if path.exists():
        return Action(path=path, status="skipped-exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return Action(path=path, status="written")


def _ensure_gitignore(project: Path) -> Action:
    """Append missing lines to `.gitignore`. Idempotent."""
    gi = project / ".gitignore"
    existing = gi.read_text(encoding="utf-8").splitlines() if gi.exists() else []
    existing_set = set(existing)
    to_add = [line for line in _GITIGNORE_LINES if line not in existing_set]
    if not to_add:
        return Action(path=gi, status="skipped-exists", detail="all lines present")
    if existing and existing[-1] != "":
        existing.append("")  # leading blank separator
    new_lines = existing + to_add + [""]
    gi.write_text("\n".join(new_lines), encoding="utf-8")
    return Action(
        path=gi,
        status="appended",
        detail=f"added {len(to_add)} line(s)",
    )


# ---------------------------------------------------------------- top-level


def init_project(
    project: Path,
    *,
    project_type: str = "auto",
) -> InitOutcome:
    """Scaffold the citation-pipeline pieces into `project`.

    Args:
        project: Path to an existing Quarto project root (or empty dir).
        project_type: `"auto"` (detect from existing `_quarto.yml`),
            `"manuscript"`, or `"book"`. `"auto"` defaults to
            `"manuscript"` when there's nothing to detect from.

    Returns:
        `InitOutcome` describing each file action.
    """
    if project_type == "auto":
        detected = detect_project_type(project)
        ptype = detected if detected != "unknown" else "manuscript"
    else:
        ptype = project_type

    outcome = InitOutcome(project_type=ptype)

    # _quarto.yml — never overwrite. If absent, write the appropriate
    # default. If present, print a snippet for manual merge.
    yml_path = project / "_quarto.yml"
    if yml_path.exists():
        outcome.actions.append(
            Action(
                path=yml_path,
                status="manual-merge",
                detail="merge the pre-render block manually",
            )
        )
        outcome.manual_merge_snippet = _quarto_yml_snippet_for_manual_merge()
    else:
        content = _QUARTO_YML_BOOK if ptype == "book" else _QUARTO_YML_MANUSCRIPT
        outcome.actions.append(write_if_missing(yml_path, content))

    # The seed bibliography is the only other file init writes.
    outcome.actions.append(write_if_missing(project / "references.bib", _REFERENCES_BIB))

    # .gitignore is the one file modified in place (idempotent append).
    outcome.actions.append(_ensure_gitignore(project))

    return outcome


def _quarto_yml_snippet_for_manual_merge() -> str:
    """Return the YAML lines to add to an existing `_quarto.yml`."""
    return """\
# Add to your existing _quarto.yml. The pre-render line goes under
# `project:` next to your existing `type:` value.

project:
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

bibliography:
  - references.bib
  - references.json
"""


def format_outcome(outcome: InitOutcome, *, project: Path) -> str:
    """Pretty-print an InitOutcome."""
    glyphs = {
        "written": "+",
        "appended": "~",
        "skipped-exists": "·",
        "manual-merge": "!",
    }
    lines: list[str] = []
    lines.append(f"Project type: {outcome.project_type}")
    lines.append("")
    for action in outcome.actions:
        try:
            relative = action.path.relative_to(project)
        except ValueError:
            relative = action.path
        glyph = glyphs.get(action.status, "?")
        line = f"  {glyph} {relative}  [{action.status}]"
        if action.detail:
            line += f" — {action.detail}"
        lines.append(line)
    lines.append("")
    if outcome.manual_merge_snippet:
        lines.append(outcome.manual_merge_snippet)
    lines.append("Next steps:")
    lines.append("  1. Confirm `quartobot` is on PATH: `quartobot --version`")
    lines.append("     (install with `uv tool install git+https://github.com/quartobot/quartobot`)")
    lines.append("  2. Add citations to your prose: @doi:..., @pmid:..., etc.")
    lines.append("  3. quarto render")
    lines.append("")
    lines.append(
        "To add the version banner + GitHub Actions CI, run `quartobot use github-ci` after this."
    )
    return "\n".join(lines)


__all__: Sequence[str] = (
    "Action",
    "InitOutcome",
    "_ensure_gitignore",
    "detect_project_type",
    "format_outcome",
    "init_project",
    "write_if_missing",
)

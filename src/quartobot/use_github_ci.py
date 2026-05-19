"""Scaffold the GitHub Actions render workflow.

`quartobot use github-ci` writes a thin `.github/workflows/render.yml`
that calls one of two upstream reusable workflows, plus a PR-preview
cleanup workflow.

The default is the **lean** pipeline (Option B per #118): latest at
``/``, PR previews at ``/pr/<n>/``, a generated ``/versions/`` page,
sticky PR comment with preview links. Built on Quarto's own publish
machinery, so the surface area is intentionally narrow.

The opt-in **versioned-snapshots** pipeline (``--with-versioned-snapshots``)
adds the manubot-style per-commit ``/v/<sha>/`` permalink deploy, the
``quartobot snapshots`` retention policy, and the in-page HTML version
banner. This was quartobot's v0.1 default; it now requires an explicit
flag.

Idempotent. Files already on disk are reported as ``skipped-exists``,
not overwritten. In versioned-snapshots mode, the command also prints
a YAML snippet for the user to merge into ``_quarto.yml`` if the
banner include isn't already declared.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from quartobot.init_project import (
    Action,
    detect_project_type,
    write_if_missing,
)

# ---------------------------------------------------------------- templates


# Embedded HTML banners. Lines are long because CSS is inlined for
# users who want to drop the file into a fresh project without
# wrangling a separate stylesheet. Lint exceptions tagged per-line.
# fmt: off
_VERSION_BANNER_TEMPLATE = (
    '<div class="version-banner" style="background:#fff7e0;border-bottom:2px solid #f0b400;padding:0.55rem 1rem;font-family:system-ui,-apple-system,\'Segoe UI\',sans-serif;font-size:0.92rem;text-align:center;color:#3a2c00;">\n'  # noqa: E501
    "  <strong>This version:</strong>\n"
    '  <a href="__VERSION_URL__" style="color:#3a2c00;text-decoration:underline;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;">__VERSION_SHA__</a>\n'  # noqa: E501
    "  &nbsp;&middot;&nbsp;\n"
    '  <a href="__VERSION_LATEST__" style="color:#3a2c00;">latest&nbsp;HTML</a>\n'
    "  &nbsp;&middot;&nbsp;\n"
    '  <a href="__VERSION_GH__" style="color:#3a2c00;">GitHub</a>\n'
    "</div>\n"
)

_VERSION_BANNER_DEV = (
    '<div class="version-banner" style="background:#eef2ff;border-bottom:2px solid #6366f1;padding:0.55rem 1rem;font-family:system-ui,-apple-system,\'Segoe UI\',sans-serif;font-size:0.92rem;text-align:center;color:#1e1b4b;">\n'  # noqa: E501
    "  <strong>Development build</strong> &middot; permalink set by CI on push to <code>main</code>\n"  # noqa: E501
    "</div>\n"
)
# fmt: on


def _render_workflow(project_type: str, *, with_versioned_snapshots: bool) -> str:
    """Return the render-workflow caller for the given project type.

    Thin wrapper around an upstream reusable workflow; the consumer
    side is just the trigger config plus the ``uses:`` line and a
    handful of inputs.

    Args:
        project_type: Quarto project shape (``manuscript`` or ``book``).
        with_versioned_snapshots: When ``True``, target the v0.1
            reusable workflow (per-commit ``/v/<sha>/`` permalinks +
            retention + banner). When ``False`` (default), target the
            lean Option-B workflow.
    """
    reusable = "render-reusable.yml" if with_versioned_snapshots else "render-reusable-lean.yml"
    docs_url = f"https://github.com/quartobot/quartobot/blob/main/.github/workflows/{reusable}"
    return f"""\
# Renders on every push and PR via the upstream reusable workflow.
# Override inputs in the `with:` block below; see
#   {docs_url}
# for the full list.

name: Render

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:

jobs:
  render:
    uses: quartobot/quartobot/.github/workflows/{reusable}@main
    permissions:
      contents: write
      pull-requests: write
    with:
      project-type: {project_type}
"""


_PR_CLOSED_WORKFLOW = """\
name: Clean up PR preview

on:
  pull_request:
    types: [closed]

permissions:
  contents: write

concurrency:
  group: gh-pages-deploy
  cancel-in-progress: false

jobs:
  cleanup:
    runs-on: ubuntu-latest
    if: github.event.pull_request.head.repo.full_name == github.repository
    steps:
      - name: Check whether gh-pages branch exists
        id: branch
        run: |
          REPO_URL="https://github.com/${{ github.repository }}.git"
          if git ls-remote --exit-code --heads "$REPO_URL" gh-pages >/dev/null 2>&1; then
            echo "exists=true" >> "$GITHUB_OUTPUT"
          else
            echo "exists=false" >> "$GITHUB_OUTPUT"
          fi

      - name: Check out gh-pages
        if: steps.branch.outputs.exists == 'true'
        uses: actions/checkout@v4
        with:
          ref: gh-pages
          fetch-depth: 1

      - name: Remove PR preview directory
        if: steps.branch.outputs.exists == 'true'
        run: |
          pr="${{ github.event.pull_request.number }}"
          [ -d "pr/${pr}" ] && rm -rf "pr/${pr}" || exit 0

      - name: Commit and push
        if: steps.branch.outputs.exists == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          if git diff --cached --quiet; then exit 0; fi
          git commit -m "Clean up preview for PR #${{ github.event.pull_request.number }}"
          git push
"""


_BANNER_INCLUDE_SNIPPET = """\
# Add to your existing _quarto.yml so the version banner renders at
# the top of the HTML output. PDF/DOCX outputs skip the include
# automatically.

format:
  html:
    include-before-body:
      - _version-banner.html
"""


# ---------------------------------------------------------------- outcome type


@dataclass
class UseOutcome:
    """The aggregate result of a ``quartobot use github-ci`` run."""

    actions: list[Action] = field(default_factory=list)
    project_type: str = "manuscript"
    manual_merge_snippet: str | None = None
    with_versioned_snapshots: bool = False


# ---------------------------------------------------------------- helpers


def _banner_already_included(project: Path) -> bool:
    """True if `_quarto.yml` already declares the banner include.

    Walks `format` -> (each html-like format) -> `include-in-header`
    and `include-before-body` and checks for `_version-banner.html`.
    A bare `format: html` string can't carry includes, so it's a no.
    Anything else (a missing file, a YAML parse error, a `format`
    that's the wrong shape) returns False so the caller still prints
    the snippet — false-negative is conservative; the user merges
    something that may already be there, which is harmless.
    """
    yml = project / "_quarto.yml"
    if not yml.exists():
        return False
    try:
        loaded = yaml.safe_load(yml.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return False
    if not isinstance(loaded, dict):
        return False

    formats = loaded.get("format")
    if not isinstance(formats, dict):
        return False

    include_keys = ("include-in-header", "include-before-body")
    for fmt_value in formats.values():
        if not isinstance(fmt_value, dict):
            continue
        for key in include_keys:
            target = fmt_value.get(key)
            if isinstance(target, str) and "_version-banner.html" in target:
                return True
            if isinstance(target, list):
                if any(isinstance(x, str) and "_version-banner.html" in x for x in target):
                    return True
    return False


# ---------------------------------------------------------------- top-level


def apply_github_ci(
    project: Path,
    project_type: str = "auto",
    *,
    with_versioned_snapshots: bool = False,
) -> UseOutcome:
    """Scaffold the GitHub Actions CI into ``project``.

    Args:
        project: Path to an existing Quarto project root.
        project_type: ``"auto"`` (detect from ``_quarto.yml``),
            ``"manuscript"``, or ``"book"``. ``"auto"`` defaults to
            ``"manuscript"`` when there's nothing to detect from.
        with_versioned_snapshots: When ``True``, scaffold the v0.1
            manubot-style pipeline: per-commit ``/v/<sha>/`` permalink
            deploys, snapshot retention, in-page version banner.
            When ``False`` (default), scaffold the lean Option-B
            pipeline: latest at root, PR previews, ``/versions/`` page,
            sticky PR comment. No banner files written, no
            ``_quarto.yml`` merge snippet.

    Returns:
        :class:`UseOutcome` describing each file action and an
        optional manual-merge snippet (only in versioned-snapshots
        mode).
    """
    if project_type == "auto":
        detected = detect_project_type(project)
        ptype = detected if detected != "unknown" else "manuscript"
    else:
        ptype = project_type

    outcome = UseOutcome(project_type=ptype, with_versioned_snapshots=with_versioned_snapshots)

    if with_versioned_snapshots:
        # Banner files only land in versioned-snapshots mode. The lean
        # default doesn't use them.
        outcome.actions.append(
            write_if_missing(
                project / "_version-banner.html.template",
                _VERSION_BANNER_TEMPLATE,
            )
        )
        outcome.actions.append(
            write_if_missing(project / "_version-banner.html", _VERSION_BANNER_DEV)
        )

    outcome.actions.append(
        write_if_missing(
            project / ".github" / "workflows" / "render.yml",
            _render_workflow(ptype, with_versioned_snapshots=with_versioned_snapshots),
        )
    )
    outcome.actions.append(
        write_if_missing(
            project / ".github" / "workflows" / "pr-closed.yml",
            _PR_CLOSED_WORKFLOW,
        )
    )

    # Banner include snippet is only relevant in versioned-snapshots
    # mode. In lean mode, the versions page replaces the banner.
    if with_versioned_snapshots:
        yml = project / "_quarto.yml"
        if yml.exists() and not _banner_already_included(project):
            outcome.manual_merge_snippet = _BANNER_INCLUDE_SNIPPET

    return outcome


def format_outcome(outcome: UseOutcome, *, project: Path) -> str:
    """Pretty-print a UseOutcome."""
    glyphs = {
        "written": "+",
        "appended": "~",
        "skipped-exists": "·",
        "manual-merge": "!",
    }
    lines: list[str] = []
    mode = "versioned-snapshots" if outcome.with_versioned_snapshots else "lean"
    lines.append(f"Project type: {outcome.project_type}")
    lines.append(f"Pipeline:     {mode}")
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
    lines.append("  1. Commit the new files and push to GitHub.")
    lines.append("  2. The render workflow fires on push to main and on PRs.")
    if outcome.with_versioned_snapshots:
        lines.append("  3. After the first push, CI swaps the dev banner for a")
        lines.append("     per-commit permalink + 'latest' link, and snapshot")
        lines.append("     retention starts pruning aged-out `v/<sha>/` dirs.")
    else:
        lines.append("  3. After the first push, the manuscript lands at `/`,")
        lines.append("     the `/versions/` page lists tagged releases and open")
        lines.append("     PR previews, and PRs get a sticky comment with links.")
    return "\n".join(lines)


__all__: Sequence[str] = (
    "UseOutcome",
    "apply_github_ci",
    "format_outcome",
)

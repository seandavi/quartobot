---
title: Workflows and actions
description: Reference for the reusable workflows and composite actions quartobot ships — inputs, defaults, when to use each, and how to compose your own pipeline.
---

quartobot ships two reusable GitHub Actions workflows and three
composite actions. Most users don't need to wire them by hand —
`quartobot use github-ci` scaffolds a thin consumer workflow that
calls one of the reusable workflows. This page is the reference for
when you need to override an input, compose your own pipeline, or
understand exactly what the CI is doing.

## Picking a reusable workflow

| | `render-reusable-lean.yml` (default in v0.3+) | `render-reusable.yml` (manubot pattern) |
|---|---|---|
| Latest at `/` | ✓ | ✓ |
| PR preview at `/pr/<n>/` | ✓ | ✓ |
| Sticky PR comment | ✓ | ✓ |
| `/versions/` page | ✓ | ✓ (planned in this workflow too) |
| Per-commit `/v/<sha>/` permalinks | — | ✓ |
| Snapshot retention | — | ✓ |
| HTML version banner | — | ✓ |
| Scaffolded by `quartobot use github-ci` | (default) | `--with-versioned-snapshots` |

If you're starting a new project, **use lean.** Opt into the
versioned-snapshots workflow when you actually need per-commit
permalinks — preprint reviewers citing a specific commit's rendering,
the manubot-pattern in full.

## Reusable workflows

### `render-reusable-lean.yml`

The lean default. Setup quartobot → install Quarto → run `quarto
render` → stage outputs (latest + PR preview) → update `/versions/`
page → deploy to gh-pages → sticky PR comment.

**Minimum consumer workflow:**

```yaml
# .github/workflows/render.yml
name: Render
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
  workflow_dispatch:
jobs:
  render:
    uses: seandavi/quartobot/.github/workflows/render-reusable-lean.yml@main
    permissions:
      contents: write
      pull-requests: write
```

**Inputs (all optional):**

| Input | Default | Description |
|---|---|---|
| `formats` | `html,pdf,docx` | Comma-separated render formats. `html`, `html,pdf`, `html,pdf,docx`, etc. |
| `project-type` | `manuscript` | `manuscript` (per-format file copy from project root) or `book` (copy the whole `_book/` site recursively). |
| `manuscript-name` | `manuscript` | Base name for the PDF/DOCX alias under `/` and `/pr/<n>/` — the PR sticky comment links to it. Ignored when `project-type: book`. |
| `book-output-dir` | `_book` | Output directory Quarto books write to. Only used when `project-type: book`. |
| `python-version` | `3.12` | Python version for the quartobot install. |
| `quartobot-spec` | `quartobot` | Pip spec for the quartobot CLI. Defaults to the published PyPI package; pin a tag (`quartobot==0.3.0`), point at a fork, or use a workspace path for in-tree testing. |
| `quarto-version` | `release` | `release` for latest stable; `pre-release` is also recognized. Pass a specific version like `"1.5.57"` for reproducible CI. |
| `tinytex` | `"true"` | Install TinyTeX (required for PDF render). Set `"false"` to skip if HTML-only. |
| `project` | `.` | Directory holding `_quarto.yml`. Defaults to the repo root. |
| `project-title` | `""` (repository name) | Title for the `/versions/` page. Defaults to the repository name; pass an explicit value for a friendlier display. |

**Overriding inputs:**

```yaml
jobs:
  render:
    uses: seandavi/quartobot/.github/workflows/render-reusable-lean.yml@main
    permissions:
      contents: write
      pull-requests: write
    with:
      formats: "html,pdf"
      quarto-version: "1.5.57"
      project-title: "My Paper"
```

### `render-reusable.yml`

The v0.1 / manubot-pattern workflow. Everything the lean workflow
does, plus a per-commit `/v/<sha>/` deploy on every push, snapshot
retention pruning before each deploy, and a `sed`-substituted HTML
version banner included into the rendered HTML.

**When to use:** preprint workflows where readers need to cite a
specific commit's rendering ("we used the version at
`/v/<commit-sha>/`"). Otherwise, prefer the lean workflow — the
versioned pattern has substantially more moving parts (banner
template, retention policy config, the `_version-banner.html`
include in `_quarto.yml`).

**Minimum consumer workflow:** identical shape to the lean one,
just pointing at the other file:

```yaml
jobs:
  render:
    uses: seandavi/quartobot/.github/workflows/render-reusable.yml@main
    permissions:
      contents: write
      pull-requests: write
```

**Additional inputs over the lean workflow:**

| Input | Default | Description |
|---|---|---|
| `banner-template` | `_version-banner.html.template` | Path to the placeholder-containing banner template (sed substitution input). |
| `banner-output` | `_version-banner.html` | Path the substituted banner is written to. The `_quarto.yml` `format.html.include-before-body:` should reference this same path. |

All the lean workflow's inputs apply here too.

**Retention policy** is configured per-project under `quartobot.snapshots`
in `_quarto.yml`:

```yaml
quartobot:
  snapshots:
    latest: keep              # / is always the most recent build
    tagged: keep              # any v/<sha> whose commit has a git tag survives
    recent: 10                # rolling window: last N untagged builds
    pruned_behavior: redirect # `redirect` (default) or `delete`
    size_budget_mb: 800       # 80% of the 1 GB GitHub Pages soft limit
    on_over_budget: fail      # `fail` (default) or `warn`
```

See [Differences from manubot](../differences-from-manubot/) for
the full design rationale on the retention model.

## Composite actions

The three composite actions are the building blocks the reusable
workflows are built from. You can also use them directly — useful
when neither reusable workflow fits your pipeline (custom deploy
target, multi-stage build, integration with non-Quarto steps).

### `setup-quartobot`

Installs Python, the `quartobot` CLI on PATH (so the Quarto
pre-render hook subprocess can invoke it), pandoc, Quarto, and
TinyTeX. Used as the first step in both reusable workflows.

**Path:** `seandavi/quartobot/actions/setup-quartobot@main`

| Input | Default | Description |
|---|---|---|
| `python-version` | `3.12` | Python to install. |
| `quartobot-spec` | `quartobot` | Pip spec — PyPI package by default; override with a git ref, a fork, or a workspace path for in-tree testing. |
| `quarto-version` | `release` | `release` / `pre-release` / specific version like `"1.5.57"`. |
| `tinytex` | `"true"` | Install TinyTeX. Skip for HTML-only renders. |
| `project` | `.` | Directory holding `_quarto.yml`. |

**Why pandoc?** Quarto bundles its own pandoc, but `manubot.cite`
shells out to a standalone `pandoc` via `shutil.which("pandoc")` to
convert biblatex (`.bib`) entries to CSL JSON. Without a system
pandoc, manubot silently returns an empty bibliography and `.bib`
keys are treated as unresolved. This action installs one.

### `render-manuscript`

Renders a Quarto project to one or more formats with heartbeat
output during long PDF renders. Optionally uploads render logs as
a workflow artifact.

**Path:** `seandavi/quartobot/actions/render-manuscript@main`

| Input | Default | Description |
|---|---|---|
| `project` | `.` | Path to the Quarto project directory. |
| `formats` | `html,pdf,docx` | Comma-separated formats. |
| `upload-logs` | `"true"` | Upload `render-<fmt>.log` files as the `render-logs` artifact. Set `"false"` to skip. |
| `log-artifact-name` | `render-logs` | Artifact name when `upload-logs: true`. |

**Heartbeat output:** PDF renders under TinyTeX can be slow. The
action emits a `[heartbeat]` line every 30 seconds during the PDF
step so the workflow log doesn't look hung.

### `prune-snapshots`

Applies the project's snapshot retention policy to the gh-pages
branch. Only used by `render-reusable.yml` (versioned-snapshots);
the lean workflow doesn't deploy per-commit snapshots and so
doesn't need pruning.

**Path:** `seandavi/quartobot/actions/prune-snapshots@main`

| Input | Default | Description |
|---|---|---|
| `mode` | `apply` | `apply` prunes + pushes the result. `echo` runs read-only (inventory + decision logged, no mutations). Use `echo` on PR builds. |
| `project` | `.` | Directory holding `_quarto.yml` (used to load `quartobot.snapshots` config). |
| `gh-pages-branch` | `gh-pages` | Name of the gh-pages branch. |
| `latest-sha` | `""` (auto) | Full SHA of the build currently being deployed. Defaults to head SHA on PRs, `github.sha` otherwise. |

**Outputs:**

| Output | Description |
|---|---|
| `pruned-count` | Number of `v/<sha>/` directories pruned. |
| `over-budget` | `"true"` if projected post-prune size still exceeds `size_budget_mb`. |

## Pinning convention

The examples above use `@main`. **In production, pin to a tag.**
Tags are immutable; `main` moves with every commit. The release
flow ships tags like `v0.3.0`:

```yaml
uses: seandavi/quartobot/.github/workflows/render-reusable-lean.yml@v0.3.0
```

The reusable workflows internally also reference the actions via
`@main` while the project is pre-1.0; once a tagged release is
declared stable, those internal references will be swept to the
matching tag in a release commit.

## Composing your own pipeline

If neither reusable workflow fits — custom deploy target (Netlify,
Quarto Pub, Vercel), multi-stage build, integration with
non-Quarto steps — the composite actions compose into a workflow
you fully control:

```yaml
name: Custom render
on:
  push: { branches: [main] }
jobs:
  render:
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/checkout@v4
      - uses: seandavi/quartobot/actions/setup-quartobot@main
      - uses: seandavi/quartobot/actions/render-manuscript@main
        with:
          formats: "html,pdf"
      # ... your own deploy / publish steps here
```

The pre-render hook for citation resolution fires inside
`quarto render` — `setup-quartobot` puts `quartobot` on PATH so it
can be invoked by Quarto without further configuration.

## See also

- [CLI reference](../cli/) — `quartobot use github-ci` is the
  scaffolder that writes a consumer workflow against one of the
  reusable workflows above.
- [First manuscript in 15 minutes](../first-manuscript/) — the
  guided walkthrough that uses the default lean workflow end-to-end.
- [Differences from manubot](../differences-from-manubot/) — design
  rationale on the lean-default and the retention policy.
- [Troubleshooting](../troubleshooting/) — when the canonical path
  breaks.

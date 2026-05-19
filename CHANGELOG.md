# Changelog

## v0.3.0 — 2026-05-19

The release that makes quartobot ready to onboard non-Sean users. The
default `use github-ci` pipeline shrinks to "Quarto's own publish +
quartobot's pre-render hook"; the manubot-pattern per-commit
permalink layer becomes opt-in. Two new commands ship: `versions`
(generates the `/versions/` page that replaces the deployed-pages
banner) and `reconcile` (resolves bib/json citation-key collisions
with explicit modes and timestamped backups). A run of persona
reviews tunes the docs for the four audiences we onboard from
(Quarto, manubot, JOSS reviewers, and researchers further upstream
on the markdown/git on-ramp).

### Added

- `quartobot versions update` — generates the `/versions/` page and
  `state.json` companion on gh-pages. Cross-references the on-disk
  inventory (`v/<sha>/` snapshots, `pr/<n>/` previews) with
  caller-supplied git facts (latest sha, tags, open PRs) and renders
  a static HTML page listing tagged releases, recent commits on
  main, and open PR previews. No JS, inline CSS, self-healing from
  gh-pages contents if `state.json` is corrupted. Replaces the
  deployed-pages HTML version banner as the version-discovery
  surface. Composes with `quartobot.snapshots`. Implements part of
  #118.
- `quartobot reconcile` — explicit resolution of citation-key
  collisions between `references.bib` and `references.json`. Three
  modes: `--accept-bibtex` drops conflicting entries from
  `references.json`; `--accept-json` drops from `references.bib`;
  `--manual` walks collisions one at a time with a side-by-side
  picker. No default; user must pick to surface a deliberate choice
  rather than rely on pandoc-citeproc's silent later-wins. Both
  files get a timestamped `.bak-<ISO-TS>` backup before mutation, so
  any choice is one `mv` away from undo. `--dry-run` previews
  without writing. `quartobot init` adds `*.bak-*` to the
  `.gitignore` template. Closes #10, implements #122.
- `quartobot use github-ci --with-versioned-snapshots` — opt-in flag
  to scaffold the v0.1/v0.2 manubot-style pipeline (per-commit
  `/v/<sha>/` permalink deploys, snapshot retention via
  `quartobot.snapshots`, in-page version banner). The lean default
  (see "Changed" below) skips these; the flag puts them back. Part
  of #118.
- New reusable workflow `.github/workflows/render-reusable-lean.yml`
  for the new default. Setup quartobot → quarto-actions/render →
  stage (latest at `/`, PR preview at `/pr/<n>/`) → `quartobot
  versions update` → deploy via peaceiris/actions-gh-pages → sticky
  PR comment. No per-commit deploys, no banner injection, no
  snapshot prune. The v0.1 `render-reusable.yml` stays in place
  unchanged for opt-in users (notably the Venice manuscript which
  pins to `@main`).
- Docs: **Coming from…** per-persona migration page covering Quarto
  authors with manual `.bib`, manubot users, Zotero users, raw
  LaTeX / Overleaf users. Prerequisites self-assessment for the
  four-skill baseline (Markdown, GitHub, terminal, PRs), with
  on-ramp pointers. Honest "When quartobot isn't for you" section
  that names the cases where another tool fits better.
- Docs: **Troubleshooting** page (closes #110). PATH issue during
  `quarto render`, failed identifier resolution, cache semantics
  (`references.json` is the cache), `references.bib` + JSON
  precedence, `--id-mode citation-key` requirement, network
  behavior. Sourced from `install.md` (PATH) and `resolve.py`
  (cache + failure paths) so the answers reflect actual behavior.
- Docs site: maintainer attribution ("Maintained by Sean Davis") on
  the landing-page footer + a per-page "Report an issue" link
  client-side-appended next to Starlight's "Edit page" link, with
  the page title and URL pre-filled in the issue body.
- Docs site: Google Analytics 4 (`G-QNEGW3C1W0`) wired via Starlight
  head injection with custom CTA events (`install_command_copy`,
  `hero_cta_click`, `layer_cta_click`, `card_click`). Closes #113.
- Carry-forward from the prior Unreleased: "How to validate a
  manuscript" how-to (closes #81), "How to use quartobot in a
  Quarto book" (closes #79), "How to resolve a single citation"
  (closes #80), "How to use quartobot in a Jupyter notebook
  manuscript" (closes #77), "First manuscript in 15 minutes"
  tutorial (closes #82), "MCP + Claude Desktop" tutorial (closes
  #83), "How to use quartobot in a Quarto website" (closes #78),
  "Shell-tool agents grounding citations" tutorial (closes #84).

### Changed

- **`quartobot use github-ci` defaults to the lean pipeline.**
  Latest deploy at `/`, PR preview at `/pr/<n>/`, generated
  `/versions/` page, sticky PR comment. No per-commit `/v/<sha>/`
  permalinks, no HTML version banner, no snapshot retention by
  default. The v0.1/v0.2 manubot-pattern pipeline (per-commit
  permalinks + banner + retention) moves behind the opt-in
  `--with-versioned-snapshots` flag. Existing repos pinning to
  `render-reusable.yml@main` are unaffected; the new default writes
  a `render.yml` that calls `render-reusable-lean.yml`. Migration:
  regenerate your workflow with `quartobot use github-ci` (lean) or
  add `--with-versioned-snapshots` (v0.1 behavior). Part of #118.
- `quartobot init` now scaffolds only the citation-pipeline pieces
  (`_quarto.yml` pre-render line + `bibliography:` list,
  `references.bib` seed, `.gitignore` augment). The GitHub Actions
  render workflow, version banner, and PR-preview cleanup moved to
  the `quartobot use github-ci` command. `use` is the parking lot
  for opt-in capabilities, R `usethis`-style. If you ran `init`
  before v0.3, run `quartobot use github-ci` after to get what it
  used to do. Closes #87.
- Landing-page Layer 4 reframed for the lean default. Now leads
  with "Citations resolve in CI; reviewers preview in the PR" and
  surfaces per-commit permalinks as opt-in. The reviewer-UX callout
  is preserved.
- Template (`template/`) wired for the lean pipeline. Banner files
  deleted; `_quarto.yml` drops the `include-before-body` line;
  `render.yml` points at the lean reusable workflow.

### Fixed

- Coming-from and troubleshooting pages use `../page/` (not
  `./page/`) for sibling-page references. Starlight resolves
  `./foo/` from `coming-from.md` as `/coming-from/foo/`, which
  404s.

### Architecture

- New `quartobot.versions` module — pure-function `/versions/` page
  generation. Composes with `quartobot.snapshots`'s `Inventory`. No
  shelling out, no network. The state file (`versions/state.json`)
  is rebuildable from gh-pages contents on the next render if it
  gets corrupted.
- New `quartobot.reconcile` module — small brace-counter BibTeX
  parser (no `bibtexparser` dependency) sufficient for key
  extraction and block-level mutation. Three resolution functions
  share a `ReconcileOutcome` shape carrying decisions and per-file
  changes. Manual picker takes a `prompt` callable for
  testability; the CLI binds it to stdin.
- `pyproject.toml` and `__init__.py` bumped to `0.3.0`.

## v0.2.0 — 2026-05-16

The accumulated work since v0.1.0: a real docs site under
`seandavi.github.io/quartobot/`, an MCP server for agentic authoring,
snapshot retention for `gh-pages`, Jupyter notebook scanning, the org
move to `quartobot/`, and a pile of correctness fixes around citation
keys, the validate gate, and the render-CI defaults.

### Added

- `quartobot mcp` — an MCP (Model Context Protocol) server exposing
  citation-resolution tools for agentic authoring workflows (Claude
  Desktop, Codex, Gemini Code Assist, Cursor). Three read-only tools
  register: `resolve_citation` wraps `manubot.cite.citekey_to_csl_item`,
  `scan_project` and `validate_project` wrap their CLI counterparts.
  Stdio transport only; no write tools. Ships as an opt-in extra so
  the base install is unchanged: `uv tool install 'quartobot[mcp]'`.
  Closes #71.
- `quartobot resolve --output -` streams CSL JSON to stdout instead of
  writing a file. The one-shot lookup shape for shell-tool agents and
  scripts (`quartobot resolve --output - doi:… | jq '.[0].title'`). The
  human-readable summary moves to stderr in stdout mode, and no cache
  write happens; cache reads still work when `--cache <path>` is set
  explicitly. Closes #73.
- `quartobot snapshots` — CLI subcommand and retention-policy module
  for the per-commit permalink directories on `gh-pages`. Ships with
  a composite action wired into the reusable render workflow so old
  snapshots are pruned automatically.
- Starlight docs site at `seandavi.github.io/quartobot/`. CI gates
  on a built-site link-check via `linkinator` so internal references
  don't ship broken.
- `scan` reads Jupyter notebooks (`.ipynb`) — markdown cells are
  walked, cite keys reported with `file:cellN:line` for the
  duplicate-locations view. Crawl knobs: `--no-recursive` keeps the
  walk shallow, render outputs and tool caches (`_site/`, `_book/`,
  `_freeze/`, `.quarto/`, `.git/`, `.ipynb_checkpoints/`,
  `node_modules/`, etc.) skipped at any depth.

### Changed

- Repo moved to the `quartobot` GitHub org; docs Pages URL is now
  `seandavi.github.io/quartobot/`. Closes #55, #62.
- `quartobot validate` no longer fails on a key cited several times in
  the same file — only cross-file duplicates count, and the failure
  message reports the actual file count per key. `quartobot scan`
  exits 0 in every case; duplicates are reported, not gated. Closes
  #63.

### Fixed

- `scan` and `resolve` strip a trailing `/` (and other pandoc-terminator
  punctuation) from `@url:` cite keys so the resolver-side `id` matches
  what pandoc-citeproc looks up. Previously `references.json` carried
  `url:.../path/` while citeproc looked up `url:.../path` and silently
  degraded the citation to `[?]`. Closes #61.
- `render-reusable.yml`: `quarto-version` default is now `release` (was
  `""`). A freshly-init'd workflow that omits or passes an empty
  `quarto-version` installs the latest stable Quarto instead of 404ing
  on `…/releases/download/v/quarto--linux-amd64.deb`. The
  `setup-quartobot` composite action also normalizes empty input to
  `release` defensively so any consumer still pinned to a pre-fix tag
  recovers. Closes #60.
- Docs internal links use relative paths so the Astro `base` resolves
  them correctly under `/quartobot/` instead of 404ing at site root.
  Closes #69.
- Install docs cover users without `uv` (pipx parallel path, "install
  uv first" guidance, PATH troubleshooting for Quarto pre-render
  subprocess). Closes #64.

### Architecture

- Settled on the `quartobot resolve` pre-render hook as the citation
  pipeline. Templates, examples, `quartobot init` scaffolding, and
  the composite CI actions all wire `project.pre-render: quartobot
  resolve --from-scan . --output references.json --id-mode citation-key`
  in `_quarto.yml`; pandoc-citeproc reads the resulting CSL JSON
  directly. See `docs/citation-pipeline.md` for the rationale.
- **Breaking:** `_extensions/seandavi/quarto-manubot-cite/` removed.
  There is no extension to `quarto add`. The on-ramp is
  `uv tool install git+https://github.com/seandavi/quartobot`.
- `examples/extension-minimal/` renamed to `examples/minimal/`.
- `quartobot validate`: dropped `extension installed`,
  `manubot-bibliography-cache`, `manubot-output-bibliography` checks;
  added `pre-render hook` and `references.json in bibliography`
  checks. Happy-path check count is now 5 (was 6).
- `setup-quartobot` composite action: dropped the `extension-source`
  input and the "Install quarto-manubot-cite extension" step; renamed
  the manubot install step to "Install quartobot CLI" with a
  `quartobot-spec` input.

## v0.1.0 — 2026-05-14

First useful release. Installs cleanly from git
(`uv tool install git+https://github.com/seandavi/quartobot`) and
will publish to PyPI on this tag once the trusted-publisher setup
on the PyPI side is complete.

### `quartobot` CLI

- `scan` — walks a Quarto project and groups manubot cite keys by
  prefix, with duplicate detection.
- `validate` — pre-flight static checks against `_quarto.yml` and
  the extension setup (six checks).
- `resolve` — pre-fetches citations via `manubot.cite` and writes
  CSL JSON. `--id-mode citation-key` writes the CSL `id` as the
  user's prose key (e.g. `doi:10.1371/…`), suitable for
  pandoc-citeproc matching without a filter.
- `init` — scaffolds the pattern into an existing Quarto project.

### Quarto extension

- `quarto add seandavi/quartobot@v0.1.0` installs `quarto-manubot-cite`,
  wiring `pandoc-manubot-cite` as a pandoc filter.

### CI building blocks

- Reusable render workflow (`render-reusable.yml`) callable from
  any consumer repo with a ten-line wrapper.
- Composite actions: `setup-quartobot`, `render-manuscript`.

### Templates

- `template/` — `quartobot-manuscript` GitHub template (Quarto
  Manuscripts + extension + CI for permalinks, version banners,
  PR previews).
- `template-book/` — book variant.

### Design

- `docs/citation-pipeline.md` proposes a pre-render-hook
  architecture as the successor to the filter. End-to-end
  validated in CI by `.github/workflows/test-prerender-e2e.yml`.
  Not yet committed publicly to the user-facing templates —
  pending manubot-team review.

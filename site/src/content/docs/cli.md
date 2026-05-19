---
title: "The CLI: quartobot"
description: Pre-render and out-of-render commands for citation pipelines on Quarto.
---

A Python CLI for pre-render and out-of-render work. `quartobot resolve`
runs as a Quarto pre-render hook and calls `manubot.cite` directly to
populate the bibliography before pandoc starts. `scan`, `validate`,
`init`, and `use` round out the surface for CI-lint and scaffolding.

```bash
uv tool install git+https://github.com/seandavi/quartobot
```

`quartobot` depends on `manubot` as a Python library. See
[Install](../install/) for `uvx`, editable, and post-v0.1-tag
`pip install` paths.

## Pre-render commands

### `quartobot scan`

Walks `.qmd`, `.md`, `.Rmd`, and `.ipynb` files under a path, extracts
every cite key, classifies each one (manubot prefix, bare DOI, or
hand-curated), groups the results, and reports repetition counts and
cross-file duplicates with file:line locations. Pure read. No network.
Pure reporter, too — `scan` always exits 0 once it finishes; gating
lives in `validate`.

```
$ quartobot scan .
arxiv:
  2104.10729 (2x)
doi:
  10.1038/s41586-024-12345
  10.1371/journal.pcbi.1007128 (3x)
pmid:
  31479462
(hand-curated):
  quarto2024

5 unique key(s), 7 total occurrence(s) across 3 file(s).

Duplicates:
  @doi:10.1371/journal.pcbi.1007128:
    intro.qmd:14
    methods.qmd:42
    notebook.ipynb:cell3:9
```

Prefixes are listed alphabetically; hand-curated keys appear last.

The scan is heuristic — it strips YAML/TOML frontmatter, fenced code
blocks (`` ``` `` / `~~~`), and inline code spans before searching, so
decoys like `@fake:notacite` inside backticks won't surface. For
`.ipynb` files, only markdown cells are scanned; cell index appears
alongside line number (`paper.ipynb:cell3:9`). The authoritative
parse happens at render time inside pandoc citeproc.

Pass `--no-recursive` to scan only files directly under the given
path. Render outputs and tool caches (`_site/`, `_book/`, `_freeze/`,
`.quarto/`, `.git/`, `.ipynb_checkpoints/`, etc.) are skipped at any
depth.

Exit codes:

- `0` — scan completed. Always. Repeated keys show up in the listing
  (`(Nx)` next to the identifier, plus a "Duplicates:" section when a
  key crosses file boundaries) but they don't gate the exit.
- `2` — bad arguments.

Wire `validate` into pre-commit / CI when you want a gate.

### `quartobot resolve`

Pre-fetch persistent-identifier citations via `manubot.cite` and write
the resulting CSL JSON to disk. Designed to run as a Quarto
pre-render hook declared in `_quarto.yml`:

```yaml
project:
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key
```

```
$ quartobot resolve --from-scan . --output references.json
  ✓ doi:10.1371/journal.pcbi.1007128 → YuJbg3zO
  ✓ pmid:31479462 → r3UbYxrJ
  ✓ arxiv:2104.10729 → OCxCvqZo (cached)

3 resolved (1 from cache). Wrote 3 entries to references.json.
```

Pass keys as arguments (`quartobot resolve doi:10.x/y pmid:12345`) or
use `--from-scan PATH` to resolve every persistent-identifier key in a
project. Hand-curated keys (no recognized prefix) are skipped — those
live in `references.bib` and pandoc citeproc handles them.

`--id-mode citation-key` writes the CSL `id` field as the user's
prose key (`doi:10.1371/...`) so pandoc-citeproc matches `[@doi:...]`
in the source directly. Without it, manubot's canonical short hash
(`YuJbg3zO`) goes in `id` and pandoc-citeproc silently fails to match
prose keys. The pre-render hook architecture depends on this flag.

The `--cache` option defaults to `--output`, so re-runs are idempotent:
the output file IS the cache. `--dry-run` reports what would be
resolved without making any network calls.

Pass `--output -` to stream the CSL JSON to stdout instead of a file —
the one-shot lookup shape for shell-tool agents and scripts that pipe
through `jq`:

```
$ quartobot resolve --output - doi:10.1371/journal.pcbi.1007128 | jq '.[0].title'
"Open collaborative writing with Manubot"
```

In stdout mode the summary line goes to stderr and no cache write
happens. Cache reads still work when `--cache <path>` is set
explicitly.

Exit codes:

- `0` — every key resolved (cache hits count as success).
- `1` — one or more keys failed (network error, Crossref 404, etc.).
- `2` — bad arguments.

### `quartobot validate`

Pre-flight / CI-lint surface. Static config checks against a Quarto
project — no network. Run this in CI to catch the most common foot-guns
before they reach a render.

```
$ quartobot validate .
  ✓ _quarto.yml exists
  ✓ bibliography declared — 2 file(s): references.bib, references.json
  ✗ pre-render hook — `quartobot resolve` is invoked but `--id-mode citation-key` is missing. Without it, CSL `id`s are manubot's short hashes (`YuJbg3zO`), not the prose keys (`doi:10.1371/...`), and pandoc-citeproc silently fails to match any cites.
  ✓ references.json in bibliography — `references.json` listed in `bibliography:`
  ✓ no duplicate cite keys — 5 unique key(s) in 3 file(s)

1 of 5 check(s) failed. Exit 1.
```

Checks run:

- `_quarto.yml` exists and parses as YAML.
- `bibliography:` is declared (as a string or list).
- `project.pre-render` calls `quartobot resolve` with `--id-mode citation-key`.
  The flag is load-bearing — without it, manubot's canonical short
  hashes replace the user's prose keys and pandoc-citeproc silently
  fails to match anything.
- `references.json` appears in `bibliography:` — the most common
  silent failure under the pre-render hook architecture, since
  without it pandoc citeproc never reads what `quartobot resolve`
  wrote.
- No cite key appears in more than one file. Same-key-twice in the
  same file is the normal academic-writing case (one source, several
  claims) and is not flagged. The check is intentionally narrow:
  cross-file duplication is the case the chunked-content pattern can
  produce by accident; same-file repetition is intent.

Citation-resolution checks ("does this DOI actually resolve at
Crossref?") are out of scope here — they need network. Run
`quartobot resolve --dry-run --from-scan .` separately for that.

Exit codes: `0` if every check passes, `1` on any failure.

## Scaffolding commands

### `quartobot init`

Scaffold the citation pipeline into an existing (or empty) Quarto
project:

```
$ quartobot init
Project type: manuscript

  + _quarto.yml  [written]
  + references.bib  [written]
  ~ .gitignore  [appended] — added 7 line(s)

Next steps:
  1. Confirm `quartobot` is on PATH: `quartobot --version`
     (install with `uv tool install git+https://github.com/seandavi/quartobot`)
  2. Add citations to your prose: @doi:..., @pmid:..., etc.
  3. quarto render

To add the version banner + GitHub Actions CI, run `quartobot use github-ci` after this.
```

`init` writes only what the citation pipeline needs: `_quarto.yml`
wired with the `quartobot resolve` pre-render hook and a
`bibliography:` list, a seed `references.bib`, and a `.gitignore`
augment so `references.json` (regenerated each render) stays out of
the repo. Three files, nothing else.

Conservative — never overwrites existing files. If `_quarto.yml`
already exists, prints a YAML snippet to merge in manually instead of
touching it. `.gitignore` is the one file modified in place
(idempotent, appends only).

`--project-type {auto,manuscript,book}` controls what gets written;
`auto` detects from `_quarto.yml`, falling back to `manuscript`.

### `quartobot use github-ci`

Scaffold the GitHub Actions render workflow + PR-preview cleanup —
the manuscript-as-software CI machinery that used to ride along
with `init`. Opt-in, idempotent, scoped to one job.

By default it scaffolds the **lean pipeline**: latest deploy at `/`,
PR preview at `/pr/<n>/`, generated `/versions/` page, sticky PR
comment. No per-commit permalinks, no banner, no snapshot retention.

```
$ quartobot use github-ci
Project type: manuscript
Pipeline:     lean

  + .github/workflows/render.yml  [written]
  + .github/workflows/pr-closed.yml  [written]

Next steps:
  1. Commit the new files and push to GitHub.
  2. The render workflow fires on push to main and on PRs.
  3. After the first push, the manuscript lands at `/`,
     the `/versions/` page lists tagged releases and open
     PR previews, and PRs get a sticky comment with links.
```

For the v0.1 manubot-pattern pipeline (per-commit `/v/<sha>/`
permalinks + snapshot retention + HTML version banner), pass
`--with-versioned-snapshots`. That mode also writes
`_version-banner.html.template` + `_version-banner.html` and prints
a snippet for the `_quarto.yml` banner include.

The scaffolded `render.yml` is a thin caller of one of the upstream
reusable workflows. For the full input list, the composite-action
references, and the standalone-composition pattern, see
[Workflows and actions](../workflows-and-actions/).

Re-running is safe: files already on disk are left alone and report
as `skipped-exists`. When `_quarto.yml` already declares the banner
include (versioned-snapshots mode), the manual-merge snippet is
suppressed.

`use` is a click group, designed to grow. `github-ci` is the first
inhabitant; future siblings (`use jupyter-notebooks`, `use pre-commit`,
`use mcp`, `use joss-paper`) are scoped but not yet shipped. The
naming convention follows R's `usethis` package: one verb (`use`),
one role per subcommand.

## Philosophy

The CLI calls `manubot.cite` (the resolver library) directly from a
Quarto pre-render hook and lets pandoc citeproc (the renderer) consume
the resulting CSL JSON. Every command is either pre-render (do work
ahead of `quarto render` so the render itself is faster and more
reliable) or out-of-render (`init`, `scan`, `validate` — work that
doesn't touch render at all).

Opaque-by-default for the CI surface: a consumer's `.github/workflows/render.yml`
is a thin caller pointing at the upstream reusable workflow. `quartobot
detach` (when it ships) is the escape hatch when consumers want to
fork the pipeline. The opposite of `r-lib/actions`, which copies 150
lines into every consumer repo. quartobot's default is friendlier; the
escape hatch matches their model for users who want it.

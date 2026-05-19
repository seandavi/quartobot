<h1 align="center">quartobot</h1>

<p align="center">
  <strong>Citation resolution and manuscript-as-software CI for Quarto.</strong><br>
  Paste a DOI in your prose. Render the manuscript. The bibliography is already correct.
</p>

<p align="center">
  <a href="https://pypi.org/project/quartobot/"><img src="https://img.shields.io/pypi/v/quartobot.svg?label=pypi&color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/quartobot/"><img src="https://img.shields.io/pypi/pyversions/quartobot.svg" alt="Python versions"></a>
  <a href="https://pypi.org/project/quartobot/"><img src="https://img.shields.io/pypi/dm/quartobot.svg?label=downloads&color=blue" alt="PyPI downloads"></a>
  <a href="https://github.com/seandavi/quartobot/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://seandavi.github.io/quartobot/"><img src="https://img.shields.io/badge/docs-live-blue.svg" alt="Docs"></a>
</p>

<p align="center">
  <a href="https://github.com/seandavi/quartobot/actions/workflows/test-python.yml"><img src="https://github.com/seandavi/quartobot/actions/workflows/test-python.yml/badge.svg" alt="Tests"></a>
  <a href="https://github.com/seandavi/quartobot/actions/workflows/test-prerender-e2e.yml"><img src="https://github.com/seandavi/quartobot/actions/workflows/test-prerender-e2e.yml/badge.svg" alt="Pre-render hook end-to-end"></a>
  <a href="https://github.com/seandavi/quartobot/actions/workflows/docs-link-check.yml"><img src="https://github.com/seandavi/quartobot/actions/workflows/docs-link-check.yml/badge.svg" alt="Docs link check"></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff"></a>
</p>

<p align="center">
  <img src="docs/demo.gif" alt="quartobot CLI demo: scan, resolve, references.json" width="780">
</p>

---

```bash
uv tool install quartobot
```

Documentation: **[seandavi.github.io/quartobot](https://seandavi.github.io/quartobot/)** · Source: **[seandavi/quartobot](https://github.com/seandavi/quartobot)** · PyPI: **[`quartobot`](https://pypi.org/project/quartobot/)**

## What it does

Authors write persistent-identifier cite keys directly in prose:

```markdown
We follow @doi:10.1371/journal.pcbi.1007128, with the dataset described
in @pmid:31479462 and methods inspired by @arxiv:2104.10729.
```

A Quarto `project.pre-render:` hook resolves each key to canonical
metadata before pandoc-citeproc runs, writes the result to a
`references.json` you can commit, and the manuscript renders the same
way on every machine. **No `quartobot` install needed at render time,
no live Crossref / PubMed / arXiv hit per render.** CI gets the same
behavior the author saw locally, and a network blip mid-render is no
longer a build failure.

Supported prefixes: `@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`,
`@wikidata:`, `@pmc:`, plus hand-curated keys from a project `.bib`.
Resolution goes through [manubot](https://github.com/manubot/manubot)'s
`citekey_to_csl_item` — eight years of accumulated source-API quirks
behind a single function call. quartobot itself doesn't reimplement
resolution; it provides the Quarto integration, the CI scaffolding,
and an agent-facing MCP surface.

## Quick start

```bash
uv tool install quartobot
quarto create project manuscript my-paper
cd my-paper && quartobot init
# Optional: scaffold render + PR-preview CI.
quartobot use github-ci
```

That's the canonical path. Three other on-ramps live in
[Choose a path in](https://seandavi.github.io/quartobot/getting-started/)
for "I have an existing Quarto project" and the resolver-only
minimum.

## The CLI

| Command | What it does |
|---|---|
| **`resolve`** | The pre-render hook. Invoked by Quarto from `_quarto.yml`'s `project.pre-render:` line. Reads cite keys, writes CSL JSON. |
| **`scan`** / **`validate`** | CI-lint surfaces. Cite-key inventory and static `_quarto.yml` checks. |
| **`init`** | Scaffolds the citation pipeline into an existing Quarto project. Three files only. |
| **`use github-ci`** | Layers the render + PR-preview CI on top. Lean default; `--with-versioned-snapshots` for the manubot per-commit-permalink pattern. |
| **`reconcile`** | Resolves `references.bib` ↔ `references.json` citation-key collisions with explicit modes. Backup-then-mutate. |
| **`versions`** | Generates the `/versions/` page on gh-pages — tagged releases + open PR previews. |
| **`mcp`** | Stdio MCP server. Agents in Claude Desktop, Codex, Gemini Code Assist call the same resolver as part of drafting. |

Full reference: [CLI](https://seandavi.github.io/quartobot/cli/) and
[Workflows and actions](https://seandavi.github.io/quartobot/workflows-and-actions/).

## Why this exists

[manubot/manubot#332](https://github.com/manubot/manubot/issues/332)
("Quarto integration") was opened by Anthony Gitter in April 2022
after a conversation with Sean Davis. Four years on, no PR, no
assignee — but Quarto Manuscripts shipped as a first-party project
type, and the integration turned out to be small once the resolver
question was settled. This repo is the work to close that issue.

The longer story:
[Differences from manubot](https://seandavi.github.io/quartobot/differences-from-manubot/),
[Design](https://github.com/seandavi/quartobot/blob/main/DESIGN.md),
[Citation pipeline](https://github.com/seandavi/quartobot/blob/main/docs/citation-pipeline.md).

## Working example

[seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
runs the CI / permalink / banner half of the pattern on a live
25-author preprint from the Bioconductor Spatial Hackathon. That's
the production reference the template lifted from.

## See also

- **Docs site:** [seandavi.github.io/quartobot](https://seandavi.github.io/quartobot/) — install, CLI reference, tutorials, migration guides, MCP setup
- **Coming from another tool:** [Quarto](https://seandavi.github.io/quartobot/coming-from/#coming-from-quarto-with-a-manual-referencesbib) · [manubot](https://seandavi.github.io/quartobot/coming-from/#coming-from-manubot) · [Zotero](https://seandavi.github.io/quartobot/coming-from/#coming-from-zotero) · [LaTeX](https://seandavi.github.io/quartobot/coming-from/#coming-from-raw-latex-or-overleaf)
- **Release process:** [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) — grounded in actual failure modes
- **Contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- **Changelog:** [`CHANGELOG.md`](CHANGELOG.md)

## Demo recording

The GIF above was recorded with [`asciinema`](https://github.com/asciinema/asciinema) (cast) + [`agg`](https://github.com/asciinema/agg) (cast → GIF). To re-record after changing the demo flow:

```bash
brew install asciinema agg
./scripts/demo-setup.sh
asciinema rec docs/demo.cast --command "bash scripts/demo.sh" --overwrite
agg docs/demo.cast docs/demo.gif --font-size 18 --theme dracula --speed 1.2
```

The `scripts/demo.tape` file is a vhs alternative for a higher-fidelity render once a Chrome/Chromium environment is available.

## License

[MIT](LICENSE).

---

<p align="center">
  Maintained by <a href="https://github.com/seandavi">Sean Davis</a>.<br>
  <em>quartobot is an independent community project. It builds on Quarto but is not affiliated with or endorsed by Posit, PBC.</em>
</p>

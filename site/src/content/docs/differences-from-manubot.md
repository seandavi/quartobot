---
title: Differences from manubot
description: What carries over, what changes, what Quarto adds.
---

quartobot reuses `manubot.cite` (the resolver library) and adopts the
manuscript-as-software pattern wholesale. The cite-key syntax is
identical. The `/v/<sha>/` permalink convention is identical. The
hand-curated bibliography slot is identical in spirit. What's different
is the publishing substrate underneath.

## What's the same

- **Citation by persistent identifier.** `@doi:`, `@pmid:`, `@arxiv:`,
  `@isbn:`, `@url:`, `@wikidata:`, `@pmcid:`, plus bare DOIs
  (`@10.1371/journal.pcbi.1007128`). Same prefixes, same normalization
  rules, same handlers — `quartobot resolve` calls `manubot.cite`
  directly, so you're getting manubot's resolver behavior unchanged.
  One small canonicalization layered on top: a trailing `/` in a
  `@url:` key (and trailing `.,;:!?`) is stripped at scan time, because
  pandoc's cite-key parser strips it during parse and the resolver-side
  and consumer-side keys would otherwise disagree. The stripped form is
  what lands in `references.resolved.bib`.
- **CSL JSON for auto-resolved entries, `.bib` for hand-curated.**
  Both declared in the project config, merged at render by pandoc
  citeproc.
- **Versioned permalinks at `/v/<full-sha>/`.** Long-form SHA in the
  URL, short SHA shown to humans. Latest-main at `/`. Snapshots
  immutable.
- **Versioned-source workflow.** Git repository, every commit
  rendered by CI, PRs reviewable as diffs over prose.
- **Cite manubot.** [Himmelstein et al. 2019](https://doi.org/10.1371/journal.pcbi.1007128)
  is the foundational paper. If you use quartobot in published
  work, cite it.

## What's different

**Project shape.** Manubot is manuscript-shaped by design — the
[rootstock](https://github.com/manubot/rootstock) template assumes a
single document with sequential `content/01.foo.md`, `02.bar.md`,
etc. that get concatenated at build. Quarto covers manuscripts but
also books, websites, slides, dashboards, and courseware — each a
first-party project type with its own conventions. quartobot ships
manuscript and book templates today; the same pre-render hook works
on every Quarto project type, so the pattern travels with you if you
later want a book, a course site, or a poster.

**Citation invocation.** Manubot ships `pandoc-manubot-cite`, a
pandoc filter you can declare in `_quarto.yml`. quartobot doesn't
use that filter. Instead, `quartobot resolve` runs as a Quarto
pre-render hook before pandoc starts and writes CSL JSON to
`references.json`; pandoc citeproc reads that file directly with no
custom filter in the chain. The rationale is in
[`docs/citation-pipeline.md`](https://github.com/seandavi/quartobot/blob/main/docs/citation-pipeline.md) —
two material UX gotchas in the filter shape (manubot's pandoc 3.x
version check, the resolver's PATH requirement at render time)
become structurally unreachable under the pre-render seam, and the
seam opens a citation-plugin architecture that the filter form
couldn't support.

**Build pipeline.** Manubot has a bespoke build pipeline
(`build/build.sh` + a chain of Python scripts) that concatenates
content, runs the filter, generates HTML and PDF, and stages
outputs. quartobot uses Quarto's standard render pipeline (which
runs pandoc with citeproc, executes code where present, and writes
to the project's configured output dir) plus a thin GitHub Actions
workflow on top for the permalink / banner / PR-preview machinery.
The CI workflow is ten lines in a consumer repo (`render.yml`
calling our reusable workflow); the manubot-side `build/` directory
has no equivalent here.

**Filename and prose syntax.** Manubot uses `.md`. Quarto uses
`.qmd` for files that may contain executable code, and reads `.md`
the same way for pure-prose files. Manubot markdown is a subset of
pandoc markdown; Quarto markdown is a superset that adds
cross-references (`@fig-`, `@tbl-`, `@sec-`, `@eq-`),
format-conditional content (`::: {.content-visible when-format="…"}`),
shortcodes, and a richer set of fenced-div extensions. Your existing
manubot prose will render through Quarto unchanged in the common
case; the new affordances are opt-in.

**Code execution.** Manubot doesn't natively execute code — figures
and tables go in as static files. Quarto runs R, Python, and Julia
through `knitr` and Jupyter kernels at render time, embeds output
back into the document, and caches results in `_freeze/`. For a
manuscript driven by code (hackathons, computational biology, ML),
that's the difference between "regenerate figures by hand and check
them in" and "edit the source, push, CI re-runs the analysis."

**Theming and visual surface.** Manubot has one look. Quarto ships
Bootswatch themes, custom SCSS support, light/dark variants, syntax
highlighting themes, code-copy buttons, accessible semantic HTML by
default. Authors can change the entire look with `theme: cosmo` →
`theme: flatly` in `_quarto.yml`.

**Output formats.** Manubot's primary outputs are HTML and PDF.
Quarto adds DOCX (often required for journal submission), JATS XML
(what journals actually ingest), ePub, and revealjs slides — all
from the same source. The manuscript template's CI renders HTML,
PDF, and DOCX on every push.

**Visual editor.** RStudio and VS Code both ship a Quarto visual
editor with citation-insert from DOI / Crossref / PubMed built in —
a partial in-IDE version of what auto-resolution automates at build
time, useful when you want to look up a citation interactively. No
equivalent in manubot's tooling.

## What Quarto adds on top

These come from Quarto, not from quartobot, but they're available
on any quartobot project because the substrate is Quarto:

- **Cross-references** that number themselves across formats:
  `@fig-volcano-plot`, `@tbl-cohort`, `@sec-methods`, `@eq-bayes`.
- **Margin notes** via `.column-margin` — Tufte-style sidebar
  content without templating gymnastics.
- **Callouts** (`note`, `tip`, `warning`, `important`, `caution`)
  for asides that aren't blockquotes.
- **Tabsets** for tabbed HTML content where it helps.
- **Hypothes.is annotations** in one config line:
  `format.html.comments.hypothesis: true`.
- **Full-text search** built-in on book and website project types.
- **Includes and shortcodes** for splitting files and passing values
  from CI cleanly.

## What manubot has that quartobot doesn't

Mostly nothing structural — quartobot deliberately reuses manubot's
load-bearing pieces. The list of things you'd lose moving over is
narrow:

- **Manubot's rootstock template integration.** Manubot ships a
  specific template repo with its own conventions. quartobot deliberately
  doesn't: Quarto already ships `quarto create project manuscript`
  (and `book`, and `website`), and `quartobot init` layers the
  citation-resolution + CI machinery on top. Different shape, same
  outcome.
- **Manubot-specific author / reviewer affiliations metadata.**
  Manubot's `metadata.yaml` has bespoke fields for author ORCIDs,
  reviewer credit, contribution statements. Quarto's YAML
  front-matter has analogous fields (`author:`, `affiliations:`)
  but the shape isn't a one-to-one match — see
  [Migrating from manubot](../migrating-from-manubot/) for the
  translation.
- **manubot CLI commands beyond `cite`.** Manubot has a fuller CLI
  (`manubot process`, `manubot webpage`, etc.) that orchestrates
  its bespoke build. quartobot's CLI is smaller (`scan`, `validate`,
  `resolve`, `init`) because the rendering itself is Quarto's job.

If you're using manubot for the resolver and the manuscript-as-software
pattern, you're using exactly what quartobot keeps. If you're using
manubot for the rootstock conventions specifically, see the
[migration guide](../migrating-from-manubot/) for the translation.

## See also

- [Migrating from manubot](../migrating-from-manubot/) — concrete steps
- [`docs/citation-pipeline.md`](https://github.com/seandavi/quartobot/blob/main/docs/citation-pipeline.md) — why the pre-render hook, not a filter
- [manubot](https://github.com/manubot/manubot) — the upstream
- [Himmelstein et al. 2019](https://doi.org/10.1371/journal.pcbi.1007128) — the foundational paper

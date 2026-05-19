# Design

## What the pattern is

Manubot pioneered "manuscript as software": a manuscript lives in a git
repository, every commit is rendered into HTML/PDF/DOCX by CI, every
commit has an immutable permalink, citations are resolved automatically
from persistent identifiers (DOIs, PubMed IDs, arXiv IDs, ISBNs), and
collaboration happens through pull requests. The pattern is now eight
years old and has been used for hundreds of scholarly preprints; the
underlying paper is [Himmelstein et al. 2019](https://doi.org/10.1371/journal.pcbi.1007128).

The Quarto ecosystem now covers more of academic publishing than manubot
ever did — manuscripts, books, websites, slides, dashboards, blogs,
courseware — but the manubot pattern does not yet exist there natively.
Authors who want it must either accept manubot's full toolchain (which
is bespoke) or rebuild the pattern themselves on top of Quarto from
scratch.

This project closes that gap.

## What "the pattern" means concretely

Six components, in roughly the order an author encounters them:

1. **One source of truth in git.** Prose is markdown (`.qmd`),
   bibliography is plain text, figures are tracked. Everything an author
   needs to reproduce the document is in the repo.

2. **Citation by persistent identifier.** Authors paste a DOI, a PubMed
   ID, an arXiv ID, an ISBN, or a URL into their prose using
   `@doi:10.x/y` (or bare `@10.x/y`) and CI resolves it into a real
   bibliography entry on next build. No manual `.bib` curation.

3. **Multi-format render in CI.** HTML, PDF, DOCX (and JATS XML for
   submission) all built from the same source on every push.

4. **Immutable per-commit permalinks.** Every commit produces a snapshot
   at `https://<owner>.github.io/<repo>/v/<commit-sha>/`. The permalink
   is embedded in the rendered HTML so a downloaded file always knows
   which version it is.

5. **PR previews.** Every pull request gets its own rendered preview at
   `…/pr/<n>/` and a sticky comment with the links so reviewers don't
   need a local Quarto install.

6. **One-click adoption.** Authors don't have to assemble the workflow
   themselves — they click "Use this template," paste in their prose,
   and start writing.

## What already exists (so we don't rebuild it)

- **Quarto Manuscripts** (first-party Quarto project type, since 1.4)
  gives us #1 and most of #3. It ships a working `_quarto.yml`,
  `publish.yml` GitHub Action, and gh-pages deploy.
- **`manubot.cite`**, the resolver library inside the `manubot` Python
  package, gives us #2 — `citekey_to_csl_item` resolves `@doi:`,
  `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`, `@zotero:`, and
  infers prefixes for bare identifiers, plus ~1,677 more CURIE prefixes
  through a bundled Bioregistry. Output is CSL JSON. Manubot is
  actively maintained (v0.6.1, July 2024). `quartobot resolve` calls
  this library directly from a Quarto pre-render hook; see
  [`docs/citation-pipeline.md`](docs/citation-pipeline.md) for why
  this shape rather than wrapping `pandoc-manubot-cite` as a pandoc
  filter.
- The CI pieces for #4 and #5 — versioned permalinks, embedded version
  banner, sticky PR preview comments — are already running in
  [seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)
  on a real 25-author preprint. They need to be lifted out of that
  bespoke repo and into a clean template.

What is *missing* is the wiring: nobody has documented that
`manubot.cite` works inside a Quarto project, nobody has published a
Python package that ergonomically wires the resolver into a Quarto
render, and nobody has packaged Quarto Manuscripts + that wiring + the
CI pattern as a single one-click template.

See [`docs/prior-art.md`](docs/prior-art.md) for a fuller inventory.

## What we ship

The shipping surface is a Python CLI plus a GitHub template.

### `quartobot` — Python CLI

The CLI is the load-bearing artifact. Four commands today:

- `quartobot resolve` — pre-fetches citations via `manubot.cite` and
  writes CSL JSON to disk. Runs as a Quarto pre-render hook
  (`project.pre-render:` in `_quarto.yml`), so the network work
  happens before pandoc starts and CI never sees a Crossref hiccup
  mid-render. `--id-mode citation-key` writes the CSL `id` as the
  user's prose key, which lets pandoc-citeproc match `[@doi:...]`
  directly with no custom filter in the chain.
- `quartobot scan` — walks a project and summarizes cite keys grouped
  by prefix, with duplicate detection.
- `quartobot validate` — pre-flight static checks against `_quarto.yml`
  (`_quarto.yml` exists, `bibliography:` declared, `project.pre-render`
  calls `quartobot resolve --id-mode citation-key`, `references.json`
  is in the bibliography list, no duplicate cite keys).
- `quartobot init` — scaffolds the pattern into an existing Quarto
  project: writes `_quarto.yml` (when absent) with the pre-render hook
  wired in, seeds `references.bib`, drops in the version-banner
  template, adds a ten-line workflow.

Install: `uv tool install git+https://github.com/seandavi/quartobot`
(or `uv pip install -e .` from a clone for repo dev). ~1k lines of
Python plus tests.

### `quartobot-manuscript` — Template repository

A GitHub template that combines:

- Quarto Manuscripts project layout (`_quarto.yml`, `index.qmd`, sample
  sections, `references.bib`/`references.json`).
- The CLI wired in (pre-render hook + bibliography slot).
- A CI workflow (`.github/workflows/render.yml`) that gives every
  commit an immutable permalink, embeds it in the rendered HTML,
  publishes PR previews with sticky comments, and deploys HTML + PDF +
  DOCX to GitHub Pages.
- A README walking a new author through the three steps from
  "use this template" to "click the rendered URL."

Adoption is `gh repo create my-paper --template seandavi/quartobot-manuscript`.

A book variant of the same template (`template-book/` in this repo)
exercises the pattern on Quarto's book project type. Posters, slides,
and website variants are plausible v2+ work — the pattern is identical,
only the project type differs.

## Key design decisions (and why)

| Decision | Choice | Why |
|----------|--------|-----|
| Bibliography format for auto-resolved entries | **CSL JSON**, alongside any hand-curated `references.bib` | CSL JSON's `id` field accepts arbitrary strings, so `@doi:10.1038/foo` can be both the citation key and the BibTeX-equivalent entry id. BibTeX keys forbid `/` and `:` and would require key transformation, which defeats the manubot point. |
| Citation key normalization | Lowercase prefix, identifier preserved as-is (`@doi:10.X/y`, not `@DOI:10.X/y`) | Matches manubot's own convention; lets us reuse `manubot.cite` directly. |
| Resolver implementation | Reuse `manubot.cite` (already in the `manubot` Python package) | Tested, maintained, covers all the identifier types deeply for seven first-class handlers plus ~1,677 more via Bioregistry CURIE fallback. Good error handling, rate-limit awareness. We get this for free. `quartobot resolve` calls the library directly from a Quarto pre-render hook; manubot's `pandoc-manubot-cite` is not invoked at any point. |
| Resolver invocation | Pre-render hook | Quarto's own docs recommend pre-render scripts for "produce inputs the standard pipeline consumes" and Lua filters for AST work; they explicitly steer away from external-process filters like `pandoc-manubot-cite`. The filter shape v0.1 originally shipped caused two real UX gotchas (pandoc 3.x version check, PATH requirement) that the pre-render shape makes structurally unreachable. Settled 2026-05-14 after a live end-to-end walkthrough. See [`docs/citation-pipeline.md`](docs/citation-pipeline.md). |
| Caching | The resolved `references.json` IS the cache | `quartobot resolve` is idempotent against its own output — re-running with an existing `references.json` skips the network for keys already present. One file, gitignored, regenerated on demand. |
| Permalink format | `/v/<full-sha>/` per the manubot convention | Long-form SHA so the snapshot URL contains a verifiable identifier. Short SHA shown to humans in the banner. |
| Snapshot retention | **Explicit, configurable policy** (`quartobot.snapshots` in `_quarto.yml`); defaults: keep latest, keep tagged commits, keep last 10 untagged, redirect older to `/`, 800 MB budget, fail on over-budget | Manubot inherits append-only `/v/<sha>/` accumulation as an implementation accident of its `ghp-import` push pattern. Quartobot uses `peaceiris/actions-gh-pages keep_files: true`, which doesn't force that constraint — so retention can be a first-class feature, not silent growth. The 800 MB ceiling fails the build before GitHub's 1 GB Pages soft limit triggers admin emails. Tagged commits get the "this version matters" lifetime guarantee; everything else cycles. Pruned snapshots become ~1 KB meta-refresh stubs so externally-cited URLs do not 404. See [issue #58](https://github.com/seandavi/quartobot/issues/58) for the full rationale and contrast with Manubot. |
| Version banner placement | Title-adjacent callout in HTML only; PDF/DOCX skip via `content-visible when-format="html"` | Quarto's right-side TOC is generated from headings; injecting arbitrary content there requires templates we don't want to maintain. |
| PR preview links | Sticky PR comment from `marocchino/sticky-pull-request-comment` | The HTML doesn't need a PR-aware banner — the comment is the right surface. Keeps the HTML simple. |
| License | MIT | OSI-approved, matches Quarto and manubot, JOSS-friendly. |

## Quarto features we get for free

One of the strongest arguments for building on Quarto is how much
already-mature publishing infrastructure comes with the box. Many of
these are things manubot either doesn't have, has only weakly, or has
re-implemented bespokely. Choosing Quarto means choosing this stack as
our baseline:

**Output and formats**

- One source → HTML, PDF, DOCX, **JATS XML** (the format journals want
  for submission), ePub, and reveal.js slides. The Quarto Manuscripts
  project type is explicitly designed around this fan-out.
- Format-conditional content via `::: {.content-visible when-format="…"}`
  so HTML-only or PDF-only blocks (e.g., the version banner) are a
  one-line change rather than a build-system fight.

**Theming and visual surface**

- Built-in theme support (Bootswatch themes, custom SCSS, light/dark
  variants). Authors can change the entire look with `theme: cosmo`
  → `theme: flatly` and re-render. Manubot has one look; Quarto has
  dozens out of the box and infinite customization.
- Syntax highlighting themes; copy-to-clipboard on code blocks.
- Accessible semantic HTML by default, alt-text propagation through
  formats.

**Layout primitives**

- **Margin notes / sidenotes** via the `.column-margin` class — Tufte
  style content placement that is awkward to retrofit elsewhere.
- **Callouts** (`note`, `tip`, `warning`, `important`, `caution`) for
  asides that aren't blockquotes — the version banner uses one of
  these.
- **Tabsets** for HTML-only tabbed content where it helps.
- Multi-column page layout (`.column-page`, `.column-screen`) for
  figures or tables that want more horizontal room than the body.

**Citations and references**

- Pandoc citeproc + CSL — every journal style ever written is one
  config line away. Bibliography accepted as `.bib`, `.json` (CSL
  JSON), `.yaml`, `.ris`. Multiple files merged at render.
- Cross-references (`@fig-`, `@tbl-`, `@sec-`, `@eq-`, `@thm-`, …) that
  number themselves and adapt across formats. This is the substrate
  the manubot-style citation extension drops into.

**Computation**

- First-class execution of R, Python, and Julia via `knitr` and
  Jupyter. Cell output (figures, tables, printed values) embeds back
  into the document with caching (`_freeze/`). Manubot does not natively
  execute code; Quarto is built around it. For a hackathon-style
  manuscript with code-driven figures this matters a lot.

**Annotation, comments, search**

- **Hypothes.is** annotations are a single config line:
  `format.html.comments.hypothesis: true`. (See [#6](https://github.com/seandavi/quartobot/issues/6)
  for why this dropped the iframe-shell idea.)
- Full-text search built-in for book and website project types.

**Authoring ergonomics**

- Visual editor in RStudio and VS Code, WYSIWYG over Quarto markdown,
  for collaborators who don't want to think in markup.
- DOI / Crossref / PubMed citation insert in the visual editor (already
  a partial in-IDE version of what `pandoc-manubot-cite` automates at
  build time).
- Includes (`{{< include >}}`) and metadata shortcodes (`{{< meta >}}`)
  that let us split files and pass values from CI cleanly.

**Internationalization, accessibility, semantic markup** — all default,
not after-the-fact additions.

**What this means for quartobot**

Almost everything quartobot adds is *narrowing* — the manubot-pattern
opinions about CI, permalinks, citation auto-resolution — sitting on
top of a much broader publishing stack. Authors who outgrow the
manuscript template can keep all of the Quarto features above as they
move to books, websites, or slide decks. That's the part the manubot
ecosystem can't currently match without rebuilding.

## Open questions

- **Naming.** `quartobot` is sticky and signals lineage; `quarto-manubot-pattern`
  is neutral and descriptive. The first round of co-author conversation
  (especially with the manubot team) will probably settle this.
- **Scope of the v1 template.** Manuscript only, or also book? The
  pattern transfers, but each project type has its own defaults to
  settle. I'd ship the manuscript template first and add a book variant
  driven by demand.
- **Relationship to the existing Quarto Manuscripts template.** Should
  `quartobot-manuscript` *extend* the first-party template (so we
  inherit upstream improvements), or *fork* it (so we have control over
  defaults)? Probably extend.
- **What happens when the resolver fails mid-build.** Crossref
  occasionally hiccups; PubMed has stricter rate limits. The build
  should degrade gracefully — warn, skip, mark as `[citation pending]`
  in the rendered output, but not fail the whole render.

## Out of scope (for now)

- Living reviews / dashboards / slides templates. Pattern transfers but
  not a v1 deliverable.
- Replacing or competing with manubot. The framing is adoption, not
  displacement.
- A reference-management UI. CiteDrive and Zotero exist; we're not in
  that business.
- Hosting infrastructure. GitHub Pages does the job for free; we leave
  it there.

---
title: "How to use quartobot in a Quarto book"
description: Wire the pre-render hook into a chapter-shaped Quarto book project — shared bibliography across chapters, version banner per chapter, _book/ as the output directory.
---

A Quarto book is a multi-chapter project that renders to `_book/`
with per-chapter HTML pages, full-text search, and a sidebar. Wiring
quartobot into it works the same as for manuscripts; what changes is
the output directory (`_book/` not `_output/`), the cross-chapter
citation flow, and the per-chapter render of the version banner.

## Minimal wiring

Use Quarto's scaffolder for the project shape, then layer the
citation pipeline on top:

```bash
quarto create project book my-book
cd my-book
quartobot init
```

Because `quarto create project` already wrote a `_quarto.yml`,
`quartobot init` won't touch it. It prints a YAML snippet to merge in
by hand — the `pre-render:` line plus the `bibliography:` list. Paste
it in. The result:

```yaml
project:
  type: book
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

book:
  title: "My book"
  chapters:
    - index.qmd
    - intro.qmd
    - methods.qmd
    - summary.qmd

bibliography:
  - references.bib
  - references.json
```

That's the minimum. Cite keys in any chapter resolve before pandoc
runs.

## Cross-chapter citations

`quartobot resolve --from-scan .` walks every chapter and writes one
shared `references.json`. A cite key that appears in chapters 2 and 5
resolves once; both chapters' rendered HTML reference the same
bibliography entry. pandoc-citeproc's default per-page reference list
shows only the entries actually cited on that page (or chapter,
here) — so a reader on the methods chapter sees only the methods
chapter's references, even though `references.json` carries every
key the whole book cites.

## Output directory

Quarto books write to `_book/` (configurable via
`project.output-dir:`). The reusable CI workflow that
`quartobot use github-ci` scaffolds copies `_book/` into the
gh-pages permalink tree (`/v/<sha>/` for books, same as manuscripts).

If you override `project.output-dir:` to something other than
`_book/`, also pass the new path to the reusable workflow's
`book-output-dir` input — the CI side doesn't auto-detect.
Alternatively, detach the workflow and run your own. The
[`render.yml`](https://github.com/seandavi/quartobot/blob/main/.github/workflows/render-reusable.yml)
documents the full input list.

## Version banner per chapter

`quartobot use github-ci` writes a `_version-banner.html` include
and prints a YAML snippet to paste into `_quarto.yml` so it actually
renders. The snippet uses `format.html.include-before-body`, which
lands the banner above the chapter's content (the same key `use
github-ci`'s manual-merge output declares). Every rendered chapter
then carries the banner — usually what you want, since every chapter
says which commit it came from. If you want the banner only on the
title page, scope the include via a `_metadata.yml` in that
chapter's directory rather than at the project level.

## Worked example

A three-chapter book skeleton. The directory:

```
my-book/
├── _quarto.yml
├── index.qmd
├── chapters/
│   ├── methods.qmd
│   └── results.qmd
└── references.bib
```

`_quarto.yml`:

```yaml
project:
  type: book
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

book:
  title: "Worked example"
  chapters:
    - index.qmd
    - chapters/methods.qmd
    - chapters/results.qmd

bibliography:
  - references.bib
  - references.json
```

`index.qmd` is plain prose — an introduction with no citations.

`chapters/methods.qmd` cites the manubot paper:

```markdown
# Methods

We processed transcripts with the tidyverse
[@doi:10.21105/joss.01686] for data wrangling and visualization.
```

`chapters/results.qmd` cites the GTEx pilot and re-cites the same
DOI:

```markdown
# Results

Comparing against the GTEx pilot's tissue panel
[@pmid:23715323], we re-ran the tidyverse pipeline
[@doi:10.21105/joss.01686] across the same donors.
```

Scan from the project root:

```
$ quartobot scan .
doi:
  10.21105/joss.01686 (2x)
pmid:
  23715323

2 unique key(s), 3 total occurrence(s) across 3 file(s).
```

`scan` groups by prefix and tags repeated keys with `(Nx)` so you
can see at a glance which references the book leans on most. The
DOI shows up twice — once in `methods.qmd`, once in `results.qmd`.
That's a same-key-cited-in-multiple-files case; if the duplicate
crosses chapter boundaries by accident (you wanted to remove one),
`quartobot validate` will surface it under "Duplicates:" as a CI
gate (informational here in `scan`, gate in `validate`).

Then render:

```bash
quarto render
```

The pre-render hook fires once, resolves both keys (the DOI from
Crossref, the PMID from PubMed), writes `references.json`, and hands
control back to pandoc. Output:

```
_book/
├── index.html
├── chapters/
│   ├── methods.html
│   └── results.html
└── search.json
```

`_book/chapters/methods.html` carries one reference at the bottom —
the manubot paper. `_book/chapters/results.html` carries two — the
GTEx pilot and the manubot paper. Both pages link the same
bibliography entry for the DOI; pandoc-citeproc renders the per-page
reference list from the shared `references.json`.

## See also

- [First manuscript tutorial](../first-manuscript/) — same flow,
  single-document shape.
- [CLI reference: `resolve`](../cli/#quartobot-resolve) — the full
  flag surface for the pre-render hook.
- [Worked book example](https://github.com/seandavi/quartobot/tree/main/examples/book-minimal) —
  minimal book exercising the pre-render hook in the main repo.

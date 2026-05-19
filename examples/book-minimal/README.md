# book-minimal

The smallest Quarto **book** project that exercises the
`quartobot resolve` pre-render hook. Mirrors the shape of
[`../minimal/`](../minimal/), but uses `project: type: book` to
demonstrate that the citation pipeline isn't limited to manuscripts.

## Run it

```bash
cd examples/book-minimal/

# Once: install the quartobot CLI on PATH.
uv tool install git+https://github.com/seandavi/quartobot

# Each render: the pre-render hook in _quarto.yml runs `quartobot resolve`
# before pandoc, across all chapters.
quarto render
open _book/index.html
```

## What you should see

- `_book/` directory with `index.html` (preface) and chapter pages
  (`chapters/intro.html`, `chapters/methods.html`,
  `chapters/discussion.html`), plus the standard Quarto book site
  assets (search index, sidebar, theme bundles).
- `references.json` at the project root with one CSL JSON entry per
  unique persistent-identifier cite key found across chapters, keyed
  by the user's prose form.
- Each chapter's HTML carries its own bibliography section at the
  bottom listing only the cites that chapter references — Quarto
  book's idiomatic layout.

## Per-chapter vs aggregated bibliography

Quarto book HTML output puts each chapter's references at the bottom of
that chapter. If you want a single aggregated references page,
that's currently a Quarto feature gap for book HTML — separate from
the citation pipeline. Track in
[seandavi/quartobot#34](https://github.com/seandavi/quartobot/issues/34).

## Why this isn't the template

The template (`../../template-book/` once that ships) adds: a version
banner, per-commit permalinks via CI, PR previews, gh-pages deploy.
All of that is the *pattern*. The example here is just the pre-render
hook wiring on a book project type.

If you want the pattern, use the template. If you want to add
persistent-identifier citations to an existing Quarto book, this is
the shape.

## See also

- [Manuscript-shape minimal example](../minimal/)
- [Citation pipeline](../../docs/citation-pipeline.md) — why pre-render hook, not a pandoc filter.
- The book template (in progress, tracked at
  [#36](https://github.com/seandavi/quartobot/issues/36))

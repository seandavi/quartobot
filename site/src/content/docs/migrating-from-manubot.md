---
title: Migrating from manubot
description: Step-by-step translation from a rootstock manubot manuscript to a quartobot project.
---

If you have an existing manubot manuscript built on
[rootstock](https://github.com/manubot/rootstock) and you want to move
it to quartobot, here's the translation. The pattern is preserved —
prose source in git, auto-resolved citations, per-commit permalinks,
PR-reviewed prose. What you change is the build pipeline and a few
filename conventions.

:::note
Read [Differences from manubot](../differences-from-manubot/) first if
you haven't yet — it's the context for the choices below.
:::

## Before you start

- **Don't delete anything.** Migrate on a branch (or a separate
  worktree); keep the manubot setup intact until the new one renders
  correctly.
- **Decide the project shape.** Most manubot manuscripts map cleanly
  onto Quarto's manuscript template (single `paper.qmd` plus
  references). Longer works — theses, reviews, books in progress —
  map better onto the book template (chapter-per-file). Pick one;
  you can switch later, the file shape is the only thing that
  changes.
- **What carries over unchanged:** your prose, your cite keys, your
  hand-curated references, your figures. What changes: the build
  pipeline, the metadata file's shape, the directory layout.

## Step 1 — Install the quartobot CLI

```bash
uv tool install git+https://github.com/seandavi/quartobot
quartobot --version
```

Puts `quartobot` on your user PATH (`~/.local/bin/` typically).
Quarto's pre-render subprocess needs to find it there. See
[Install](../install/) for `uvx`, editable, and post-v0.1-tag
`pip install` paths.

## Step 2 — Scaffold the Quarto project

In the same repo, alongside your existing `content/`, `build/`, and
`ci/` directories:

```bash
quartobot init
```

`init` writes:

- `_quarto.yml` with the pre-render hook wired to `quartobot resolve`
- `references.bib` (seed for hand-curated entries — empty)
- `_version-banner.html.template` + `_version-banner.html` (dev
  placeholder)
- `.github/workflows/render.yml` (ten-line caller of the upstream
  reusable workflow)
- `.github/workflows/pr-closed.yml` (preview teardown)
- `.gitignore` augments

For a book project, pass `--project-type book` — same files, plus
`chapters/` is where your content lives.

```bash
quartobot init --project-type book
```

## Step 3 — Move your content

### Manuscript shape (single document)

Manubot's `content/01-abstract.md`, `02-introduction.md`, … get
concatenated at build into one manuscript. Quarto's manuscript
template uses one `paper.qmd` (or whatever you name it) for the same
thing. The mechanical translation:

```bash
# Order matters — match manubot's numeric prefix order.
cat content/*.md > paper.qmd
```

Then move the YAML front-matter from `content/metadata.yaml` into the
top of `paper.qmd` between `---` fences (see Step 4).

The `.md`/`.qmd` syntax overlap is high enough that prose usually
needs no edits. Things to spot-check after the concat:

- **Heading levels.** Manubot expects `#` for the document title
  and `##` for top-level sections; Quarto's manuscript template
  treats the YAML `title:` field as the title and uses `#` for
  top-level sections. Drop the first `# Title` line and let Quarto
  render the title from the YAML.
- **Cite keys.** No change — `@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`
  etc. all work identically. Bare DOIs (`@10.1371/…`) also work.
- **Figure references.** Manubot uses `![](images/foo.png)`;
  Quarto adds named cross-references via
  `{#fig-foo}`. If you want auto-numbered figure cross-references,
  add the ID; if your prose says "Figure 3" by hand, no change
  needed.
- **Math.** Both use `$…$` and `$$…$$`. No change.

### Book shape (chapter-per-file)

Rename your manubot content files into `chapters/`:

```bash
mkdir -p chapters
for f in content/[0-9]*.md; do
  base=$(basename "$f" .md)
  # Drop the leading "01-" / "02-" prefix if you want clean URLs;
  # keep it if you want to preserve manubot's filenames.
  cp "$f" "chapters/${base#[0-9]*-}.qmd"
done
```

Edit `_quarto.yml` to list the chapters in order under `book.chapters:`.
Move `metadata.yaml` content into the `book:` block in `_quarto.yml`
(see Step 4).

## Step 4 — Move your metadata

Manubot's `content/metadata.yaml` looks like:

```yaml
title: My manuscript title
keywords:
  - reproducibility
authors:
  - github: alice
    name: Alice Author
    initials: AA
    orcid: 0000-0000-0000-0000
    email: alice@example.org
    corresponding: true
    affiliations:
      - Department of Examples, University of Demonstration
```

Quarto's equivalent goes either in the file's YAML front-matter (for
the manuscript shape) or under `book:` in `_quarto.yml` (for the book
shape). The field names mostly map:

```yaml
title: "My manuscript title"
keywords:
  - reproducibility
author:
  - name: Alice Author
    affiliation: Department of Examples, University of Demonstration
    orcid: 0000-0000-0000-0000
    email: alice@example.org
    corresponding: true
```

Differences worth flagging:

- `authors:` → `author:` (singular key, still takes a list — Quarto's
  convention).
- `github:` and `initials:` don't have direct equivalents. Quarto
  doesn't render them; if you want them on the manuscript, add them
  in an author block extension or drop them. Manubot uses these for
  contribution attribution in the rendered author block — see
  Quarto's `attribution:` field for a similar surface.
- `affiliations:` (list per author in manubot) → `affiliation:`
  (string, singular) for the simple case, or `affiliations:` (list of
  refs into a top-level `affiliations:` block) for multiple
  affiliations per author. Quarto's affiliation reference shape is
  documented at
  [quarto.org/docs/journals/authors.html](https://quarto.org/docs/journals/authors.html).
- `funders:` / `acknowledgments:` go in the front-matter the same way
  manubot puts them in metadata; Quarto reads them per the journal
  template you're targeting.

## Step 5 — Move your hand-curated references

Manubot's `content/manual-references.json` (CSL JSON) or
`content/manual-references.yaml` (CSL YAML) or
`content/manual-references.bib` all map onto `references.bib` (BibTeX)
or stay as their original format — pandoc citeproc reads `.bib`,
`.json` (CSL JSON), and `.yaml` (CSL YAML) interchangeably.

The simplest move:

```bash
# If you had a .bib already, just copy it.
cp content/manual-references.bib references.bib
```

Or convert CSL JSON to BibTeX with `pandoc-citeproc`:

```bash
pandoc -f csljson -t biblatex content/manual-references.json -o references.bib
```

Then make sure `_quarto.yml` lists it under `bibliography:`. The
template `quartobot init` writes already does:

```yaml
bibliography:
  - references.bib    # hand-curated
  - references.resolved.bib   # auto-resolved by `quartobot resolve`
```

If you had `manual-references.json` populated by manubot's resolver
runs (not hand-curated), discard it. The pre-render hook regenerates
the auto-resolved `references.json` on next render from the cite keys
in your prose.

## Step 6 — Swap the CI pipeline

Delete `build/` and the manubot CI workflow:

```bash
git rm -r build/
git rm ci/build.yaml 2>/dev/null  # or wherever your manubot workflow lives
git rm .github/workflows/manubot.yaml 2>/dev/null
```

`quartobot init` already wrote `.github/workflows/render.yml` — a
ten-line caller of the upstream
[reusable workflow](https://github.com/seandavi/quartobot/blob/main/.github/workflows/render-reusable.yml).
That workflow handles render → permalink staging → gh-pages deploy →
sticky PR comment, the same surface manubot's `build/build.sh` +
`build/webpage.sh` covered.

The deployed URL layout is preserved: `https://<owner>.github.io/<repo>/v/<sha>/`
for per-commit snapshots, `https://<owner>.github.io/<repo>/` for
latest main, `https://<owner>.github.io/<repo>/pr/<n>/` for open PR
previews. Existing links into your manuscript's snapshot URLs keep
working.

## Step 7 — Local test

```bash
quarto render
```

The pre-render hook runs `quartobot resolve` first, writes
`references.json`. Then pandoc renders the document; citeproc reads
both bibliographies. Open `index.html` (manuscript) or `_book/index.html`
(book) and check that:

- Every `@doi:` / `@pmid:` / `@arxiv:` cite resolved (no
  `[Unresolved citation: …]` markers).
- Hand-curated cites from `references.bib` rendered.
- Figures show up.
- The version banner is the dev placeholder (gets replaced by CI on
  push to main).

`quartobot validate .` runs the same checks the CI lint step does:

```bash
quartobot validate .
```

Expect 5 checks; failures usually mean the pre-render line in
`_quarto.yml` is malformed or `references.json` isn't in the
`bibliography:` list.

## Step 8 — Push

```bash
git add .
git commit -m "Migrate to quartobot"
git push
```

CI takes it from there. On first push to main, enable GitHub Pages
in Settings → Pages → Source: GitHub Actions (or "Deploy from a
branch → gh-pages" depending on which reusable workflow path you're
on). If the manubot setup was already deploying to gh-pages with the
same `/v/<sha>/` layout, the deploy slots in without breaking
existing snapshot URLs.

## What to delete after the dust settles

Once the new pipeline has rendered cleanly on main:

- `content/` directory
- `build/` directory
- `ci/` directory (if manubot-specific)
- Old manubot workflow files
- Any `webpage/` source-controlled checkout (the gh-pages branch is
  managed by CI now)

Keep the gh-pages branch intact — it has your historical snapshots at
`/v/<old-sha>/`, and the new pipeline writes new ones alongside.

## See also

- [Differences from manubot](../differences-from-manubot/) — what
  carries over and what changes
- [Getting started](../getting-started/) — for the abridged
  fresh-project version
- [CLI reference](../cli/) — `init`, `scan`, `validate`, `resolve`, `mcp`

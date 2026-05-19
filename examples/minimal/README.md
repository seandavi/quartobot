# minimal

The smallest Quarto project that exercises the `quartobot resolve`
pre-render hook. Use this if you want to try the citation pipeline on
its own without adopting the full `quartobot-manuscript` template.

## Run it

```bash
cd examples/minimal/

# Once: install the quartobot CLI on PATH.
uv tool install git+https://github.com/seandavi/quartobot

# Each render: the pre-render hook in _quarto.yml runs `quartobot resolve`
# before pandoc; no extra steps.
quarto render index.qmd
open index.html
```

## What you should see

- `references.json` written at the project root with one CSL JSON
  entry for the resolved DOI (`10.1371/journal.pcbi.1007128`), keyed
  by the user's prose form (`doi:10.1371/journal.pcbi.1007128`).
- The rendered HTML shows both `@doi:…` and `@quarto2024` citations
  in a numbered bibliography.

The second render skips the network round-trip when `references.json`
already contains the entry (`quartobot resolve` is idempotent against
its own output). `@quarto2024` is read directly from `references.bib`
and never needs a network call.

## Generated artifacts

The render produces `index.html`, `references.json`, and `_freeze/`.
All three are gitignored (`examples/minimal/.gitignore`) so this
directory stays clean inside the repo.

## Why this isn't the template

The template (`../../template/`) adds: a version banner, per-commit
permalinks via CI, PR previews, multi-format render (HTML + PDF + DOCX),
gh-pages deploy. All of that is the *pattern*. The example here is just
the pre-render hook wiring on a bare Quarto project.

If you want the pattern, use the template. If you want to add
persistent-identifier citations to an existing Quarto project, this is
the shape.

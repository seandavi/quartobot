---
title: "How to use quartobot in a Jupyter notebook manuscript"
description: Cite keys in markdown cells, the pre-render hook on notebook source, what scan reports for .ipynb projects.
---

Quarto renders `.ipynb` natively. You can author a manuscript in
JupyterLab, run analysis in code cells, and have the same `@doi:`
citation flow as a `.qmd` manuscript. This page covers the bits
specific to the notebook shape — where cite keys belong, how the
pre-render hook reads them, and what `quartobot scan` reports.

## Where cite keys go

Markdown cells only. A cite key like `@doi:10.1371/journal.pcbi.1007128`
inside a markdown cell renders exactly the way it does in a `.qmd`
file. Cite keys appearing in code-cell strings or comments are
ignored — by both Quarto's renderer and `quartobot scan`. Strings in
code aren't prose, so they aren't citations.

A two-cell `paper.ipynb` looks like this in JSON:

```json
{
  "cells": [
    {
      "cell_type": "markdown",
      "source": [
        "## Introduction\n",
        "\n",
        "The manubot pattern [@doi:10.1371/journal.pcbi.1007128]\n",
        "treats a paper as software.\n"
      ]
    },
    {
      "cell_type": "code",
      "source": [
        "import pandas as pd\n",
        "# @doi:10.5555/ignored — comment, not a citation\n"
      ]
    }
  ]
}
```

The first cell holds prose with one DOI citation. The second cell is
analysis code. `scan` reads the first cell and ignores the second,
including the DOI-looking string in the comment.

## Wire the pre-render hook

Same shape as a `.qmd` manuscript. Create the project, swap the
entry point to a notebook (or point at an existing `.ipynb`), then
add the citation pipeline:

```bash
quarto create project manuscript my-paper
cd my-paper
rm index.qmd
jupyter lab paper.ipynb        # author your notebook
quartobot init
```

Because `quarto create project` already wrote `_quarto.yml`, `init`
won't touch it — it prints a YAML snippet to paste in. Copy that
snippet (the `pre-render:` line plus the `bibliography:` list) into
the existing `_quarto.yml` under the existing `project:` block. The
hook then reads `.ipynb` markdown cells the same way it reads `.qmd`
body text — same scanner, same cite-key extraction, same resolver
underneath. The [first-manuscript tutorial](../first-manuscript/)
covers the full sequence end-to-end; it works identically with
notebook source.

The relevant `_quarto.yml` lines after `init`:

```yaml
project:
  type: manuscript
  pre-render: quartobot resolve --from-scan . --id-mode citation-key

bibliography:
  - references.bib
  - references.resolved.bib
```

Run `quarto render`. The hook resolves every cite key in every
markdown cell, writes CSL JSON to `references.resolved.bib`, and pandoc-citeproc
formats the citations in the rendered output.

## What `quartobot scan` reports

On the two-cell `paper.ipynb` from above:

```
$ quartobot scan paper.ipynb
doi:
  10.1371/journal.pcbi.1007128

1 unique key(s), 1 total occurrence(s) across 1 file(s).
```

On a larger project with duplicates across files, the locations show
which cell a cite key came from:

```
$ quartobot scan .
doi:
  10.1371/journal.pcbi.1007128 (2x)
pmid:
  31479462

2 unique key(s), 3 total occurrence(s) across 2 file(s).

Duplicates:
  @doi:10.1371/journal.pcbi.1007128:
    paper.ipynb:cell3:5
    methods.qmd:14
```

The `cellN` index is 1-based and matches the order cells appear in
the notebook JSON — the same order JupyterLab shows in the cell
sidebar. `:5` is the 1-based line within that cell. Cell 3 line 5
in JupyterLab is the same cell 3 line 5 that scan reports.

`quartobot scan .` walks the project recursively; `quartobot scan paper.ipynb`
scans one file directly. Both work the same way on notebooks.

## Excluded paths

`scan` skips `.ipynb_checkpoints/` at any depth — JupyterLab's
autosave directory is never useful to walk.

It also skips `*.quarto_ipynb` files. These are notebook copies
Quarto generates during render from `.qmd` source; they're staged
artifacts, not authoring source, and `quartobot init` adds them to
`.gitignore`. `scan` ignoring them keeps duplicate counts honest
when a project mixes `.qmd` and `.ipynb` inputs.

## See also

- [First manuscript (15 min)](../first-manuscript/) — end-to-end
  onramp; works identically with `.ipynb` source.
- [CLI reference: `scan`](../cli/#quartobot-scan) — every flag,
  every exit code.

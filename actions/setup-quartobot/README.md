# setup-quartobot

Composite action: installs everything needed to render a Quarto project
that uses the `quartobot resolve` pre-render hook.

```yaml
- uses: actions/checkout@v4
- uses: seandavi/quartobot/actions/setup-quartobot@v0.1
  with:
    project: "."          # where _quarto.yml lives (default: .)
    python-version: "3.12"
    quartobot-spec: "git+https://github.com/seandavi/quartobot"
    quarto-version: "release"  # default; latest stable
    tinytex: "true"       # set "false" to skip TeX install
```

## What it does

1. `actions/setup-python@v5` with pip cache.
2. `r-lib/actions/setup-pandoc@v2` — system pandoc on PATH (needed so
   manubot's bibliography loader can read .bib files).
3. `pip install '<quartobot-spec>'` — installs the `quartobot` CLI on
   PATH, including `manubot` as a Python dependency. Quarto's pre-render
   subprocess finds `quartobot` here.
4. `quarto-dev/quarto-actions/setup@v2` with TinyTeX by default.

## When to skip TinyTeX

If you render HTML only and want a faster CI job, set `tinytex: "false"`.
TinyTeX is required for PDF rendering and adds ~30 seconds to the job.

## Pinning

For reproducible CI, pin everything explicitly:

```yaml
with:
  python-version: "3.12"
  quartobot-spec: "quartobot==0.1.0"
  quarto-version: "1.5.57"
```

## See also

- [`render-manuscript`](../render-manuscript/) — the matching render step.
- [Citation pipeline rationale](../../docs/citation-pipeline.md) — why
  the pre-render hook shape.

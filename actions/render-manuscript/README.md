# render-manuscript

Composite action: renders a Quarto project to one or more formats.

```yaml
- uses: seandavi/quartobot/actions/render-manuscript@v0.1
  with:
    project: "."                # path to the Quarto project dir
    formats: "html,pdf,docx"    # comma-separated
    upload-logs: "true"         # render-*.log as artifact
```

## What it does

1. Prints a diagnostics block (Quarto version, Pandoc version, TeX
   engine version, project file listing).
2. Runs `quarto render --to <fmt> --execute-debug` for each requested
   format, capturing stdout to `render-<fmt>.log`.
3. For PDF renders, emits a heartbeat line every 30 seconds so a stalled
   TinyTeX run shows up in the workflow log instead of timing out
   silently.
4. Uploads the render logs as a workflow artifact (skippable).

## Pair with setup-quartobot

This action assumes Quarto and the `quartobot` CLI are already on PATH
so that the `project.pre-render` hook in `_quarto.yml` resolves
citations before pandoc starts. Use [`setup-quartobot`](../setup-quartobot/)
in the step before:

```yaml
- uses: actions/checkout@v4
- uses: seandavi/quartobot/actions/setup-quartobot@v0.1
- uses: seandavi/quartobot/actions/render-manuscript@v0.1
```

## Formats

Quarto supports a long list (`html`, `pdf`, `docx`, `epub`, `jats`,
`revealjs`, `gfm`, plus several others). Whatever you pass here is
handed to `quarto render --to`. Defaults to the manuscript triple:
`html,pdf,docx`.

## Exit behavior

The action fails fast — any single format failing stops the loop and
fails the action. Render logs upload regardless (`if: always()`) so
post-mortem is straightforward.

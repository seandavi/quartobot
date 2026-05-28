# manuscript-typed example

A minimal Quarto project that sets `type: manuscript` in `_quarto.yml`
and exercises the quartobot pre-render hook. Outputs land in
`_manuscript/` (Quarto's convention for manuscript projects),
including the MECA bundle and JATS sidecar.

This example is the regression test for [the v0.6.0 workflow fix][1]
that taught `render-reusable-lean.yml` to stage `_manuscript/`
wholesale instead of looking for output files at the project root.

[1]: https://github.com/seandavi/quartobot/pull/138

## Run it locally

```bash
cd examples/manuscript-typed
quarto render
ls _manuscript/
```

You should see `index.html`, `index.docx`, `_manuscript.zip` (MECA),
and JATS XML.

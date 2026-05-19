---
title: Troubleshooting
description: Common quartobot failures and the canonical fix for each — PATH, failed resolution, cache, missing citations, pandoc warnings.
---

The things first-time users run into, with the canonical fix for each.

## `command not found: quartobot` during `quarto render`

`quartobot --version` works in your shell, but `quarto render` fails
with `command not found: quartobot`. The shell and Quarto's
pre-render subprocess see different `PATH`s.

`uv tool install` puts `quartobot` at `~/.local/bin/quartobot` (or
similar). That directory has to be on the `PATH` the user Quarto
runs as, not just the venv-activated `PATH` in your terminal.

```bash
uv tool update-shell      # ensures ~/.local/bin is in PATH
# log out + back in, or open a fresh terminal
which quartobot           # confirm it's findable
quarto check              # confirm Quarto agrees
quarto render
```

For `pipx`-installed quartobot, run `pipx ensurepath` instead.

The full canonical answer lives in [Install: verify Quarto can find
it](../install/#verify-quarto-can-find-it).

## A cite key won't resolve

`quartobot resolve` logs lines like:

```
  ✓ doi:10.21105/joss.01686 → JlsZJsmU
  ✗ doi:10.99/bogus.999 — HTTPError: 404 Client Error
2 resolved, 1 failed
```

Failed keys do **not** end up in `references.json`. The resolver
continues processing the remaining keys, exits with status 1, and
leaves the partial output in place. CI will mark the render failed.

To investigate one key in isolation:

```bash
quartobot resolve --output - doi:10.99/bogus.999
```

That writes the resolution attempt to stderr and the JSON (or nothing,
on failure) to stdout, without touching `references.json`.

When a key genuinely can't be auto-resolved (a preprint not yet on
Crossref, a paper whose DOI metadata is garbage, an old report with no
identifier at all), drop a hand-curated entry into `references.bib`
under any ID you like — including the same prefix-colon-id form your
prose uses. pandoc-citeproc reads `.bib` and `.json` together; matches
in either are fine.

```bibtex
@misc{doi:10.99/bogus.999,
  author = {Doe, J.},
  title  = {The paper whose DOI metadata is wrong},
  year   = {2026},
  url    = {https://example.org/preprint.pdf}
}
```

## How caching works

There is no hidden cache directory. The cache is `references.json`
itself.

`quartobot resolve --cache <path>` reads previously-resolved entries
from `<path>`; cache hits skip the network call entirely. The
pre-render hook in `_quarto.yml` doesn't pass `--cache` explicitly
because `--cache` defaults to whatever `--output` points at. So a
second render reads the entries the first render wrote, and only
hits the network for keys it hasn't seen before.

Consequences:

- **First render** writes `references.json` and needs network for
  every persistent-identifier key. On a paper with 50 DOIs this
  takes a few seconds.
- **Subsequent renders** are network-free for keys already in the
  file. New keys get fetched and added.
- **Committing `references.json`** to the repo means CI never hits
  the network either, which is the whole point. Crossref / PubMed
  outages don't break your CI build.

## Forcing a refresh

A registrar fixed a typo in a paper title; your `references.json`
still has the old one. Or a preprint posted to Crossref between
renders.

Two ways to invalidate:

```bash
# Refresh a single key:
jq 'map(select(.id != "doi:10.21105/joss.01686"))' \
   references.json > references.json.new && mv references.json.new references.json
quarto render

# Refresh everything:
rm references.json
quarto render
```

Both work because the pre-render hook re-runs on the next render and
re-fetches anything missing from the cache.

## Pandoc warns "Citation not found"

The render output shows `@doi:10.x/y` rendered as literal text instead
of a formatted citation, plus a pandoc warning like:

```
[WARNING] Citeproc: citation doi:10.21105/joss.01686 not found
```

The cite key is in your prose but not in any bibliography. Two
common causes:

1. **The resolver failed and didn't write that key to
   `references.json`.** Run `quartobot resolve` directly — check for
   a `✗` line in the output.
2. **The key isn't a persistent-identifier prefix** (e.g.,
   `@smith2023`) and isn't in `references.bib` either. Hand-curated
   keys belong in `.bib`; quartobot only resolves the seven manubot
   prefixes (`doi:`, `pmid:`, `arxiv:`, `isbn:`, `url:`, `wikidata:`,
   `pmc:`).

`quartobot validate` flags both classes of problem before you render.

## `--id-mode citation-key` is required

If your prose has `[@doi:10.x/y]` but the rendered PDF shows it as
literal `[@doi:10.x/y]` even though `references.json` has an entry
for the DOI, check that `--id-mode citation-key` is on the
pre-render line in `_quarto.yml`:

```yaml
project:
  pre-render: >-
    quartobot resolve --from-scan .
    --output references.json
    --id-mode citation-key
```

Without `--id-mode citation-key`, the CSL `id` field is manubot's
hash form (e.g., `JlsZJsmU`), not the citation key as it appears in
your prose. pandoc-citeproc then can't match `[@doi:10.x/y]` to
anything in `references.json` and the cite renders as literal text.

`quartobot validate` flags this too.

## Network behavior

The pre-render hook needs network on the first render of a project (or
the first time a new key appears in prose). Subsequent renders are
network-free as long as `references.json` is committed and the cited
keys haven't changed.

For an offline-first workflow:

- Run `quarto render` once with network. `references.json` is now
  populated.
- Commit `references.json`.
- All subsequent renders — local, CI, on a plane — are network-free.

The dry-run mode reports what would be resolved without making any
network calls:

```bash
quartobot resolve --from-scan . --dry-run
```

Useful for confirming the cite-key scan picked up what you expect
before you trust an actual render.

## See also

- [Install reference](../install/) — every install method, what to
  use when.
- [Validate a manuscript](../validate-manuscript/) — the pre-flight
  check that catches most of these before the render fails.
- [Resolve a single citation](../resolve-single-citation/) — the
  one-key shell workflow, useful for debugging.

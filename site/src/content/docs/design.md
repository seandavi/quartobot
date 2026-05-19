---
title: Design
description: Index of architecture decisions, prior art, and publication plan.
---

This page indexes the design material. The substantive documents live in
the repo itself; this site links into them rather than duplicating.

## Architecture

[`DESIGN.md`](https://github.com/seandavi/quartobot/blob/main/DESIGN.md)
is the authoritative design document. It covers:

- What "the pattern" means concretely — six components in the order an
  author encounters them.
- What already exists upstream (`pandoc-manubot-cite`, Quarto Manuscripts,
  the Venice CI pieces) so we don't rebuild it.
- The decisions table — why CSL JSON, why `/v/<full-sha>/`, why the
  HTML-only banner, why the sticky PR comment.
- Quarto features quartobot gets for free.
- Open questions still being worked through.

## Prior art

[`docs/prior-art.md`](https://github.com/seandavi/quartobot/blob/main/docs/prior-art.md)
inventories what already exists in this space: `pandoc-manubot-cite`,
`pandoc-url2cite`, `pandoc-doi2bib`, Quarto Manuscripts, CiteDrive,
Quarto's visual-editor citation insert, and the existing scholarly
Quarto templates we don't compete with.

## Publication plan

[`docs/publication-plan.md`](https://github.com/seandavi/quartobot/blob/main/docs/publication-plan.md)
covers the framing for the JOSS paper (the contribution is the pattern,
not the resolver), the target co-author list (Anthony Gitter, Daniel
Himmelstein, possibly Quarto / Posit folks), and the venue strategy
(JOSS first; a methods/commentary paper later if the pattern gets
adopted across project types).

## Conversation notes

[`docs/conversation-notes.md`](https://github.com/seandavi/quartobot/blob/main/docs/conversation-notes.md)
is the thinking that produced the design — what was decided, what was
explicitly ruled out, what changed our minds during the working sessions.

## Citation pipeline architecture

[`docs/citation-pipeline.md`](https://github.com/seandavi/quartobot/blob/main/docs/citation-pipeline.md)
covers the settled architecture: `_quarto.yml` declares
`project.pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key`,
the hook runs before pandoc, and pandoc-citeproc reads the resulting
CSL JSON directly. No filter, no `_extensions/`, no `quarto add` step.

The architecture replaced an earlier shape that wired
`pandoc-manubot-cite` as a Lua filter declared in `_quarto.yml`. Two
material UX gotchas in the filter shape — manubot's pandoc 3.x
version check, and the resolver's PATH requirement at render time —
are structurally unreachable under the pre-render seam. A plugin
architecture for deepening manubot's shallow CURIE prefixes follows
from the same seam.

Settled 2026-05-14 after a live end-to-end walkthrough confirmed the
behavior. Templates, examples, and `quartobot init` all wire the
pre-render hook.

## The roadmap

The roadmap lives in [GitHub issues](https://github.com/seandavi/quartobot/issues),
organized into three milestones:

- [**v0.1 — first public release**](https://github.com/seandavi/quartobot/milestone/1):
  CLI + manuscript template + book template + composite actions +
  reusable workflow, with Zenodo DOI on tag.
- [**v0.2 — JOSS-ready**](https://github.com/seandavi/quartobot/milestone/2):
  documentation site complete, JOSS paper submitted.
- [**v2 — beyond manuscripts**](https://github.com/seandavi/quartobot/milestone/3):
  Hypothes.is integration, and broader Quarto project types.

## How to contribute to the design

[`CONTRIBUTING.md`](https://github.com/seandavi/quartobot/blob/main/CONTRIBUTING.md)
covers the mechanics. The short version: open an issue using the
[design proposal template](https://github.com/seandavi/quartobot/issues/new?template=design.md),
state the question, the options you considered, and the option you'd
pick. Strong opinions on pattern naming, defaults, scope, or co-author
strategy are all in scope.

---
title: Coming from...
description: Self-assessment for adopting quartobot from Google Docs, manubot, native Quarto, Zotero, or LaTeX. Prerequisites + migration paths.
---

quartobot pulls people in from a few different starting points. Each
has a different "you'll need to learn this" delta. This page is the
honest assessment — what you'll trade, what you'll gain, what to learn
first.

## Prerequisites

You'll be most comfortable with quartobot if you already:

- **Write in Markdown.** Quarto's source language is Markdown with
  Quarto extensions. If you're new to Markdown, [Quarto's Get
  Started](https://quarto.org/docs/get-started/) covers the basics
  in ~15 minutes.
- **Have a GitHub account** and know how to push to a repo. quartobot
  is a git-native workflow. If you've never used GitHub, the
  [GitHub Quickstart](https://docs.github.com/en/get-started/quickstart)
  is the right starting point — you don't need to be a deep git user,
  but the words "commit," "push," "branch," "pull request" should
  feel familiar.
- **Are willing to open a terminal.** Day-to-day is short:
  `git pull`, `git push`, `quarto render`. Initial setup is
  `uv tool install quartobot` (one line) and a few `quartobot`
  commands.
- **Understand pull requests as a collaboration shape.** A branch, a
  diff, a comment thread, a merge. Most of quartobot's collaborative
  value lives in the PR-review-of-prose pattern — co-authors suggest
  changes on a branch, you discuss in PR comments, the rendered
  preview updates on each push.

If those four boxes tick, you're set. If they don't yet, the sections
below name what to learn for each starting point.

## Coming from Google Docs

You're probably here because Google Docs got you 80% of the way to
collaborative writing, but its citation story is the missing 20%.
Pasting DOIs into the Zotero side panel, watching the bibliography
get out of sync with what's actually cited in prose, the comment
sidebar that doesn't survive an export — you know the friction.

**What you give up:**

- Real-time collaborative cursors. quartobot's collaboration shape
  is asynchronous (PRs and comments), not synchronous (cursors
  meeting in a paragraph). For some teams that's a feature; for
  others it's a real loss.
- The auto-save reflex. You explicitly `git commit` to save a
  version-controlled snapshot. Half-finished sentences in your local
  copy don't propagate to collaborators until you push.
- WYSIWYG editing. Markdown is plain text; the rendered version
  comes from `quarto render`. You can run a live preview locally
  (`quarto preview`) for a similar feel, but the source itself is
  not what the rendered output looks like.

**What you gain:**

- The document **is** the source code. Diffs make sense. Reviewers
  can suggest specific changes via PR — "rewrite this paragraph"
  becomes a diff, not a comment-thread argument.
- Citations live in your prose by DOI/PMID/arXiv, not in a binary
  database synced via a side panel. Paste `@doi:10.1038/...`, and
  the bibliography entry appears on the next render. No "is my
  Zotero up to date?" anxiety.
- Reproducible builds. The PDF a collaborator generates from your
  source is byte-equivalent to the one CI generates. No "the
  formatting broke when I opened it on my laptop" debugging.

**Pre-quartobot lift:** if you're coming straight from Google Docs
with no git or Markdown experience, budget a day to learn both.
Markdown is genuinely small (90% of what you need is in the first
hour of any tutorial); git is the bigger learning curve, but the
subset you need for quartobot is `clone`, `add`, `commit`, `push`,
`pull`, plus the GitHub web UI for PRs. You don't need to learn
rebase, cherry-pick, or any of the harder operations.

A reasonable on-ramp: start with [GitHub Desktop](https://desktop.github.com/)
or [GitKraken](https://www.gitkraken.com/) rather than the command
line for the first week. Once the mental model is in place, the
terminal feels lighter, not heavier.

## Coming from manubot

You're already comfortable with the persistent-identifier citation
pattern. quartobot uses manubot's exact citation key vocabulary
(`@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`,
`@pmcid:`) and reuses `manubot.cite` for the actual resolution
under the hood. Your prose is mostly portable.

**What's the same:**

- Citation keys, exactly. `[@doi:10.1371/journal.pcbi.1007128]` works
  in both worlds.
- The collaboration model — git, PRs, deploys to gh-pages.
- The seven persistent-identifier handlers (`doi`, `pmid`, `arxiv`,
  `isbn`, `url`, `wikidata`, `pmcid`).

**What's different:**

- The rendering layer is Quarto, not the manubot template. You get
  Quarto's richer Markdown extensions, Jupyter / R Markdown
  integration, multi-format output (HTML / PDF / DOCX from one
  source), the visual editor in RStudio if you want it.
- Citation resolution happens via a Quarto pre-render hook, not via
  the `pandoc-manubot-cite` filter. The end result is the same
  rendered bibliography, but the seam is structurally cleaner — no
  pandoc version constraints, no PATH-at-render-time concerns. See
  [Differences from manubot](./differences-from-manubot/) for the
  full mechanical comparison.
- Per-commit `/v/<sha>/` permalinks are opt-in via `quartobot use
  github-ci --with-versioned-snapshots`, not the default. If you
  want the manubot pattern in full, that flag preserves it.
- Caching is the default. `references.json` IS the cache; commit it
  and CI never hits Crossref. (manubot's default is no cache — each
  render re-resolves.)

**Migration path:** point Quarto at your existing manuscript prose,
`quartobot init`, `quartobot use github-ci`, push. Hand-curated
`.bib` entries continue to work alongside the auto-resolved ones.

## Coming from Quarto with a manual references.bib

You already know Quarto. The friction you're solving is the BibTeX
maintenance burden for DOI/PMID-heavy writing — copy the citation
out of Crossref, paste into `.bib`, hope the export was complete,
re-export when the metadata gets fixed upstream.

**What you keep:** everything about your current Quarto setup. Project
structure, formats, themes, the visual editor, your render flow.

**What changes:** one line in `_quarto.yml`:

```yaml
project:
  pre-render: quartobot resolve --from-scan . --output references.json --id-mode citation-key

bibliography:
  - references.bib    # still here — hand-curated entries
  - references.json   # new — auto-resolved entries
```

Now you can write `@doi:10.1038/...` directly in prose and the entry
appears in the bibliography on the next render. Hand-curated entries
in `references.bib` keep working unchanged for the things the
resolver can't reach (preprints not on Crossref, edge cases, custom
citations).

**Pre-quartobot lift:** essentially zero. You're already comfortable
with Quarto; this is a one-line addition.

See [first manuscript in 15 minutes](./first-manuscript/) for the
guided walkthrough; the "existing Quarto project" path in
[choose a path in](./getting-started/) is the minimum-friction option.

## Coming from Zotero

Zotero is excellent for reference management — discovering papers,
organizing collections, syncing across devices, browser-based one-click
capture. None of that is what quartobot does.

The friction Zotero leaves is in the writing workflow itself: pulling
a citation from Zotero into your prose requires the side panel, the
Better BibTeX export, and a sync step every time the export drifts
from what's in the database.

**Honest framing:** quartobot doesn't replace Zotero. You can use both.

- **Zotero** stays your discovery and organization layer. Browser
  capture, PDF library, tag-based collections, syncing.
- **quartobot** handles the citation insertion at writing time. You
  type the DOI inline; the bibliography assembles itself.

If your workflow today is "I want to cite a paper I already found
last week," opening Zotero to grab the citation key still works.
But when you're reading a paper online and want to cite it
immediately, `@doi:` is one fewer round-trip.

**Pre-quartobot lift:** the same Markdown + git + terminal
prerequisites listed at the top of this page. If you've been using
Zotero with LaTeX or Pandoc already, the rest is small.

## Coming from raw LaTeX or Overleaf

LaTeX gives you precise typesetting control; quartobot doesn't compete
on that axis. But if your current pain is collaborative editing
(merging two co-authors' edits in Overleaf), keeping the BibTeX file
maintained, or maintaining the LaTeX-Markdown-PDF translation in your
head, Quarto-plus-quartobot is worth a look.

**What you give up:**

- Direct control over the typesetting at the LaTeX-macro level. You
  can still drop in raw LaTeX for math and custom commands in PDF
  output, but the document body is Markdown, not `\section{}`.
- The Overleaf editor's live PDF preview. Quarto has a similar
  feature (`quarto preview`), but it's a local-machine thing, not a
  hosted-editor thing.

**What you gain:**

- The same source renders to HTML, PDF, and DOCX. No more separate
  TeX and Word versions for journals that ask for both.
- Collaborative editing via git and PRs. No more "my co-author broke
  the build by editing the references file while I was writing the
  intro."
- Automatic citation resolution from DOIs and PMIDs. No more
  hand-maintained BibTeX entries.

**Pre-quartobot lift:** you already know LaTeX, which means you
understand the build-time-rendering model. Learning Markdown is
genuinely fast — Quarto's [Authoring](https://quarto.org/docs/authoring/markdown-basics.html)
page is enough for most. Learning git takes longer, but Overleaf's
git integration probably exposed you to the basics already.

## When quartobot isn't for you

A few honest signals that another tool may fit better:

- You write predominantly without citations (a novel, a poem, a
  newsletter). quartobot's primary value is citation resolution; if
  you don't cite, you're paying setup cost for nothing.
- Your collaborators won't use git, and you don't have authority to
  change that. The PR-review-of-prose model is load-bearing for the
  collaboration value; without it, you're just writing in Markdown
  alone, which Quarto + a personal bib file already does.
- You need real-time synchronous editing more than you need
  reproducibility. Google Docs / Notion / Quip / Word-Online win on
  that axis and always will.

## See also

- [First manuscript in 15 minutes](./first-manuscript/) — the
  canonical guided walkthrough, with all the prerequisites assumed.
- [Choose a path in](./getting-started/) — three minimum-friction
  paths for "new manuscript," "existing Quarto project," and "I just
  want auto-resolved citations."
- [Differences from manubot](./differences-from-manubot/) — the
  detailed mechanical comparison for users porting from manubot.

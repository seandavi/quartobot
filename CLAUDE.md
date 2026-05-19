# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## quartobot

Manubot's manuscript-as-software pattern, implemented natively for the Quarto ecosystem.

**Status:** v0.1 work in flight. The Python CLI (`quartobot scan/validate/resolve/init`) is the load-bearing artifact, paired with manuscript and book templates and a reusable CI workflow. Settled 2026-05-14 on the pre-render hook architecture in [`docs/citation-pipeline.md`](docs/citation-pipeline.md): `_quarto.yml` declares `project.pre-render: quartobot resolve …`, no Lua filter, no `_extensions/`, no `quarto add` step.

## Directory layout

- `src/quartobot/` — the Python CLI. Commands: `scan`, `validate`, `resolve`, `init`. The `resolve` command runs as a Quarto pre-render hook from `_quarto.yml` and is the load-bearing surface for citation resolution.
- `template/` — `quartobot-manuscript` GitHub template (Quarto + pre-render hook wiring + CI for permalinks, banners, PR previews). Will eventually be promoted to a standalone template repo.
- `template-book/` — book variant of the same template.
- `examples/minimal/` — smallest end-to-end demo of the pre-render hook on its own, without the template's CI/banner machinery.
- `examples/book-minimal/` — same, on Quarto's book project type.
- `actions/` — composite GitHub Actions (`setup-quartobot`, `render-manuscript`) used by the reusable workflow.
- `paper/` — eventual home for `paper.md`, the JOSS submission (~1000 words). Voice guide for this file lives in the "Writing in Sean Davis's voice" section below.
- `docs/` — design docs (`citation-pipeline.md`, `prior-art.md`, `publication-plan.md`, `conversation-notes.md`). Read before non-trivial design changes.
- `site/` — the documentation site, built with [Astro](https://astro.build) + [Starlight](https://starlight.astro.build). Content lives at `site/src/content/docs/*.md(x)`; navbar in `site/astro.config.mjs`. Deploys to https://seandavi.github.io/quartobot/ via `.github/workflows/publish-site.yml` on every push to `main` that touches `site/**`. First deploy needs Settings → Pages → Source: GitHub Actions flipped on once.

## Commands

- **CLI install:** `uv tool install git+https://github.com/seandavi/quartobot` (recommended — puts `quartobot` on user PATH, so Quarto's pre-render subprocess finds it without venv-activation). For repo dev: `uv pip install -e .` from a clone.
- **Template adoption:** `gh repo create my-paper --template seandavi/quartobot-manuscript` (template currently lives at `template/` in this repo; promotion to its own repo is part of v0.1).
- **Render the docs site locally:** `cd site && npm install && npm run dev` → http://localhost:4321/quartobot/.
- **Render the minimal example:** `cd examples/minimal && quarto render`. The pre-render hook calls `quartobot resolve` from `_quarto.yml`; `quartobot` must be on PATH (`uv tool install`).
- The Venice hackathon manuscript ([seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript)) runs the CI/permalink/banner half on a live 25-author preprint and is the reference implementation for the template's render workflow.

## Contributing conventions

From `CONTRIBUTING.md`:

- Branches off `main`, named `<handle>/<short-description>` (e.g., `seandavi/version-banner-default`).
- No squash merges by default — preserve history with merge commits.
- CI must pass before merge (no CI exists yet; this kicks in once the template lands).
- Discuss design changes in an issue first — JOSS paper review will want the paper trail.

## What this is

Two artifacts ship together:

1. `quartobot` — a Python CLI. `quartobot resolve` is invoked from Quarto's `project.pre-render:` declaration in `_quarto.yml`, calls `manubot.cite.citekey_to_csl_item` for every persistent-identifier cite key in the project, and writes CSL JSON to `references.json`. Pandoc-citeproc reads that file alongside any hand-curated `references.bib`. `scan`, `validate`, and `init` round out the surface for CI-lint and scaffolding.
2. `quartobot-manuscript` — a GitHub template combining Quarto + the pre-render hook wiring + CI for per-commit permalinks, version banners, and PR previews.

[`docs/citation-pipeline.md`](docs/citation-pipeline.md) is the architecture rationale: the pre-render seam is structurally cleaner than the filter shape v0.1 originally shipped (manubot's pandoc 3.x version check and `pandoc-manubot-cite`'s PATH requirement at render time are both unreachable from the pre-render path), and the seam opens a citation-plugin architecture that the filter form couldn't support.

**Scope:** Not limited to manuscripts. Quarto covers websites, books, posters, slides, dashboards, courseware. The manubot pattern (versioned citations, immutable permalinks, collaborative PRs) applies to all of them. Manuscript first; broader project types are explicit v2+ work.

## Key design decisions (already settled)

- Reuse `manubot.cite` (the Python library — `citekey_to_csl_item`) — do NOT rebuild the resolver. Manubot's seven first-class handlers (`doi`, `pmid`, `arxiv`, `isbn`, `url`, `wikidata`, `pmc`) represent eight years of accumulated bug fixes for source-API quirks. `quartobot resolve` calls the library directly from the pre-render hook; manubot's `pandoc-manubot-cite` is not invoked at any point.
- Bibliography: CSL JSON for auto-resolved entries + hand-curated `.bib` alongside. Both declared in `_quarto.yml`.
- Citation key syntax: manubot's exactly (`@doi:`, `@pmid:`, `@arxiv:`, `@isbn:`, `@url:`, `@wikidata:`, bare DOIs). No new syntax.
- `--id-mode citation-key` on `quartobot resolve` is load-bearing — it writes the CSL `id` as the user's prose key so pandoc-citeproc matches `[@doi:…]` directly. The validate check warns if it's missing from the pre-render line.
- Permalink: `/v/<full-sha>/` per manubot convention.
- Version banner: HTML-only, injected via CI `sed` into a Quarto include file. PDF/DOCX skip via `content-visible`.
- PR previews: sticky comment via `marocchino/sticky-pull-request-comment`, not HTML banners.

## Prior art

See `docs/prior-art.md`. The gap is real and documented. Key references:
- `pandoc-manubot-cite` — already ships in `pip install manubot`
- Quarto Manuscripts — first-party project type since Quarto 1.4
- [manubot/manubot#332](https://github.com/manubot/manubot/issues/332) — Anthony Gitter's 2022 integration request, opened after conversations with Sean Davis. This repo resolves it.

## Publication plan

JOSS first. See `docs/publication-plan.md`. Target co-authors: Anthony Gitter, Daniel Himmelstein, possibly Charles Teague / Mine Çetinkaya-Rundel (Posit/Quarto).

Weekend sequencing: CI template → Quarto extension → manuscript template → JOSS paper. ~4–6 weekends.

## Venice hackathon as proof of concept

[seandavi/2026-venice-spatial-hackathon-manuscript](https://github.com/seandavi/2026-venice-spatial-hackathon-manuscript) already runs the CI / permalink / banner half of the pattern on a live 25-author preprint. That's the source material for the template.

## Open questions

Live design questions: extend vs. fork the first-party Quarto Manuscripts template ([#3](https://github.com/seandavi/quartobot/issues/3)), and bibliography merge semantics for `.bib` + CSL JSON ([#10](https://github.com/seandavi/quartobot/issues/10)). The citation-plugin architecture for deepening manubot's shallow CURIE prefixes (rrid, bioc, clinicaltrials, swhid, etc.) is sketched in `docs/citation-pipeline.md`; first plugins are post-v0.1. Settled: pre-render hook over filter (2026-05-14, see `docs/citation-pipeline.md`); the naming question closed as settled-by-adoption.

---

## Writing in Sean Davis's voice

All user-facing writing in this repo — README, JOSS paper, docs, release notes — should sound like Sean wrote it. This section is based on pre-AI writing samples (2016–2020 institutional strategy documents, grant cover letters, Bioconductor package documentation).

### How he actually writes

**Sentence length varies with the thought.** Some sentences are short. Others carry a full complex argument in one go, with subordinate clauses doing real work. The rhythm is not a formula — it follows what the sentence needs to say. Don't impose artificial brevity.

**Takes positions directly, without preamble.** "We must recognize that while we talk about service and support, such terminology makes an unnatural distinction between 'science' and 'support'." Not: "It is worth noting that the terminology of service and support may potentially create distinctions that could be seen as artificial."

**"That said" is a real connector.** He uses casual transitions inside formal writing. It reads as confident, not sloppy.

**Numbers and specifics are the evidence.** "There are at least 500 investigators who have used CCR high performance computing resources" — not "a large number of investigators." "~50–200 lines" not "a thin layer."

**Double negatives for emphasis.** "valuable and not-insignificant" is a real Sean construction. It acknowledges complexity without hedging.

**Idioms are used naturally.** "all things to all people," "front-and-center," "give-and-take" — he reaches for common idioms when they fit, rather than avoiding them as imprecise.

**Self-aware about clichés.** He'll say a thing, notice it sounds like a cliché, and then defend it: "That sounds trite, but it is an important point." This is more human than pretending the cliché isn't there.

**Institutional and political awareness shows through.** He writes about organizational dynamics, incentives, and trust explicitly, not as background assumptions. This is not boilerplate sensitivity — it's strategic thinking on the page.

**Formal register can drop in context.** Editorial asides, parentheticals, and direct address ("Tom, you may have noticed...") coexist with the more formal sections. Don't flatten everything to one register.

**Informational, not promotional.** Describes what something is and does. Lets methodology and specifics carry the interest. Does not pitch.

### AI patterns to strip before anything leaves this repo

**Vocabulary to delete:**
- pivotal, crucial, vital, key (as an adjective meaning "important"), groundbreaking, transformative
- showcase, highlight (verb used decoratively), underscore, emphasize (as padding)
- landscape (abstract noun), tapestry, ecosystem (when used metaphorically, not technically)
- testament, reminder, marker of
- vibrant, robust (unless measuring something), rich (figurative)
- delve, dive into, explore (as announcements)
- additionally, furthermore, moreover (as sentence openers — just start the next sentence)

**Constructions to rewrite:**
- "serves as / stands as / functions as" → use "is"
- "It's not just X, it's Y" → pick one claim and state it
- "Not only X but also Y" → rewrite as a direct statement
- "In order to" → "To"
- "Due to the fact that" → "Because"
- "At its core / fundamentally / what really matters is" → delete and say the thing
- Trailing -ing phrases that inflate without adding content: "...ensuring that researchers can collaborate effectively" → cut or make it a real sentence
- Em dash overuse — commas and periods do the job
- "challenges and future directions" as a formulaic section heading

**Structure to avoid:**
- Bold header followed immediately by a one-sentence paragraph that just restates the header
- Generic positive conclusion ("The future looks bright", "exciting times ahead", "we look forward to")
- Signposting announcements ("Let's explore", "Here's what you need to know", "Let's dive in")
- Rule of three when two would be more honest
- Any sentence that would appear unchanged in a press release

### JOSS paper specifically

The `paper/paper.md` (~1000 words) should read like a person who built the tool explaining why it exists, not like a grant reviewer summarizing it from the outside.

- Open with the gap, stated directly. One or two sentences. No wind-up.
- Describe what a user actually does: what they type, what happens.
- Cite manubot prominently. Frame this as adoption and extension, not competition.
- The Venice hackathon manuscript is the worked example — name it, link it, say it's a real 25-author preprint with the CI pattern already running. Specifics over vague claims.
- End on what's available now, not a vision statement.

### Voice check

Read the draft aloud. If any sentence sounds like it belongs in a NIH program announcement or a startup pitch deck, rewrite it. The test: would Sean say this in a talk slide note or a direct email? If not, it's not his voice.

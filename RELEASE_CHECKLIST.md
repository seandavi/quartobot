# Release checklist

Things to verify before tagging `vX.Y.Z` and pushing to trigger the
PyPI publish. The list is **grounded in actual failures from prior
releases** — each item is here because it broke once. Update this
document when a new failure mode shows up.

## 1. Code health

Run the same checks CI runs, plus the ones that only matter at release time.

- [ ] **Tests pass.** `uv run pytest`
- [ ] **Ruff lint clean.** `uv run ruff check src tests`
- [ ] **Ruff format clean** — *separately from lint.*
      `uv run ruff format --check src tests`
      <br>*Why separately:* CI runs `ruff format --check` as its own
      step. Local `ruff check` does not include format violations,
      so a clean `ruff check` can still fail CI on format. (v0.3
      lesson.)
- [ ] **Type check clean.** `uv run mypy`

## 2. Package builds

- [ ] **`uv build` succeeds**, producing both wheel and sdist in `dist/`.
- [ ] **`uv run --with twine twine check dist/*` passes** on both
      artifacts. Catches malformed metadata that PyPI would reject.
- [ ] **`dist/` not committed.** Run `rm -rf dist/` before staging.

## 3. Version bump

Three files carry the version number; **all three must match.**

- [ ] `pyproject.toml` — top-level `version = "X.Y.Z"`
- [ ] `src/quartobot/__init__.py` — `__version__ = "X.Y.Z"`
- [ ] `uv.lock` — the `quartobot` package's own version entry (this
      one is easy to miss; it updates automatically the next time `uv
      sync` runs, but committing the bump in the same release commit
      keeps the lockfile consistent on disk)

## 4. CHANGELOG

- [ ] **`Unreleased` section promoted** to a `vX.Y.Z — YYYY-MM-DD`
      section. Don't leave the `Unreleased` header above an empty
      section; either repopulate or remove until the next entry.
- [ ] **Headline paragraph** explaining what changed at a glance —
      one to three sentences a reader can scan without reading the
      whole entry.
- [ ] **Breaking changes called out explicitly.** If a default
      behavior changed (e.g., the lean-default flip in v0.3),
      include a migration sentence pointing at the recovery flag or
      workaround.
- [ ] **Acceptance closures listed.** Each "Closes #N" gets a one-line
      "what was done" reference so the issue can be cross-referenced
      without reopening it.

## 5. Documentation sweep for consistency

The most common source of release-time embarrassment.

- [ ] **No stale repo URLs.**
      `grep -rln "quartobot/quartobot\|quartobot\.github\.io" .` should
      return only intentional references (e.g., redirect-repo
      explanations). After ownership changes, every install command,
      every badge target, every cross-link in docs needs to point at
      the current home. (v0.3 lesson — full sweep needed when the
      repo moved between owners.)
- [ ] **Version numbers in install snippets match the release.** If
      docs say `uv tool install quartobot==0.2.0` anywhere, bump.
- [ ] **CHANGELOG entries reference real PR/issue numbers**, not
      placeholder `#TBD`.
- [ ] **Docs site renders clean locally.** `cd docs-src && quarto
      render`. The Quarto website at `docs-src/_site/` should build
      without errors and without warnings about missing files.
      `publish-docs.yml` runs the same `quarto publish gh-pages`
      step on push to main, so a clean local render is a good
      proxy for the CI publish step. (v0.6.0 lesson — switched
      from Starlight to a Quarto website; the qmd source IS the
      source of truth now, no separate rendered markdown layer.)

## 6. Tag and publish

- [ ] **Tag from `main`, not a branch.** `git checkout main && git
      pull --ff-only && git tag -a vX.Y.Z -m "vX.Y.Z — <one-line>" <SHA>`
- [ ] **Tag references the release commit.** The `git tag` SHA is
      the merge commit of the release PR, not the most recent
      branch HEAD.
- [ ] **Push the tag.** `git push origin vX.Y.Z`. Triggers
      `.github/workflows/publish-pypi.yml`.
- [ ] **Approve the `pypi` environment gate.** The publish workflow
      runs to "waiting" status and pauses for review. Approve in the
      Actions UI; the workflow proceeds. (Without approval the run
      stays "waiting" indefinitely.)
- [ ] **PyPI trusted publisher matches current repo owner.** PyPI's
      trusted-publishing setting names the GitHub `<owner>/<repo>` it
      will accept OIDC tokens from. After any repo transfer, update
      the trusted-publisher in PyPI's project settings before the
      next tag push — otherwise the publish step fails with a token-
      exchange error and the run is cancelled, not failed. (v0.3
      lesson — the repo moved between owners and the next tag's
      publish was cancelled at the gate.)

## 7. Post-release verification

- [ ] **PyPI shows the new version.**
      `curl -s https://pypi.org/pypi/quartobot/json | jq .info.version`
- [ ] **Smoke test the new install.** In a fresh directory:
      ```bash
      uv tool install --upgrade quartobot
      quartobot --version
      ```
      Expect output matching the new tag.
- [ ] **Docs site shows the new version.** Visit the live URL; verify
      the install snippet on the landing page works.
- [ ] **GitHub Release created** (optional but recommended) with the
      CHANGELOG entry copied into the release body. Helps people
      browsing the repo find what changed at a glance.

## Common failure modes and recoveries

| If… | Then… |
|---|---|
| PyPI publish run shows `cancelled` | Trusted-publisher config doesn't match the current repo owner. Fix on PyPI's project settings page (Publishing → trusted publishers). Re-trigger via `gh workflow run publish-pypi.yml --ref vX.Y.Z -F ref=vX.Y.Z`. |
| PyPI publish run shows `waiting` | The `pypi` environment has a required-reviewer gate. Approve in the run's UI. |
| Site links 404 after deploy | Either the `site:` field in `astro.config.mjs` is wrong (it's the absolute-URL base for every page; an org move requires updating it), or page-internal links use `./page/` where they need `../page/`. |
| GitHub Pages 404 on a URL that previously worked | GitHub Pages doesn't redirect on repo transfer. The old URL is permanently dead unless you set up a redirect repo at the old location. |
| Tag pushed but no workflow run | Check the tag matches the pattern in `publish-pypi.yml` (`on: push: tags: ["v*"]`). Tags without `v` prefix won't trigger. |

## Updating this document

When a release goes wrong in a new way, **add the gotcha here.**
Update the relevant checklist item with a one-line "(vX.Y.Z lesson)"
footnote so future-you knows where the rule came from. Each
generation of this list earns its line.

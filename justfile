# quartobot docs build orchestrator.
#
# All docs pages live under docs-src/ as .qmd. Quarto renders the
# whole tree to a static website at docs-src/_site/, then GitHub
# Pages serves it via the publish-docs.yml workflow. quartobot's
# pre-render hook resolves citations on every render — the docs
# site uses quartobot to render its own docs.

# Default: live-reloading preview for local docs work.
default: preview

# Render the Quarto website into docs-src/_site/.
build:
    cd docs-src && quarto render

# Live-reloading preview (Quarto picks up file changes and refreshes
# the browser).
preview:
    cd docs-src && quarto preview

# Remove generated files. The .qmd sources stay in docs-src/.
clean:
    rm -rf docs-src/_site docs-src/_freeze docs-src/.quarto
    rm -f docs-src/references.json docs-src/references.resolved.bib

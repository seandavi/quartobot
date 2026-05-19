#!/usr/bin/env bash
# Demo script for screen-recording quartobot's pre-render hook + render
# in action. Walks scan → resolve → references.json → quarto render →
# the formatted citation in the rendered HTML.
#
# Renders to HTML only (skipping PDF) so the demo stays ~40 seconds —
# PDF takes ~30s extra under TinyTeX on first run. The HTML output
# is enough to show the citation got formatted correctly.
#
# Usage:
#   asciinema rec docs/demo.cast --command 'bash scripts/demo.sh' --overwrite
#
# Re-running is safe: a fresh scratch directory is used each time.
# Prerequisites: quartobot + quarto on PATH.

set -euo pipefail

# Cosmetic pacing for the recording. These delays are dead weight at
# the shell prompt but make the cast watchable. If you're running this
# for a sanity check (not recording), set PAUSE=0.
PAUSE="${PAUSE:-1.2}"

# Fixture: the small sample-paper that lives under docs-src/fixtures/.
# We copy it into a scratch dir so the demo is self-contained and the
# tracked fixture doesn't grow a references.json after a recording.
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
FIXTURE="$REPO_ROOT/docs-src/fixtures/sample-paper"
SCRATCH=$(mktemp -d)
cp -R "$FIXTURE"/* "$SCRATCH/"
cd "$SCRATCH"

# Type-then-pause helper so the cast looks like someone is at a keyboard.
typewriter() {
  local cmd="$1"
  printf '\033[1;32m$\033[0m %s\n' "$cmd"
  sleep "$PAUSE"
}

clear
typewriter "quartobot --version"
quartobot --version
sleep "$PAUSE"
echo

# Step 1: show the manuscript prose with citations in it.
typewriter "head -8 index.qmd"
head -8 index.qmd
sleep "$PAUSE"
echo

# Step 2: scan reports what's there before any network call.
typewriter "quartobot scan ."
quartobot scan .
sleep "$PAUSE"
echo

# Step 3: resolve fetches metadata from Crossref / PubMed / arXiv and
# writes CSL JSON. This is the visible "magic" — the registrar lookup.
typewriter "quartobot resolve --from-scan . --output references.json --id-mode citation-key"
quartobot resolve --from-scan . --output references.json --id-mode citation-key
sleep "$PAUSE"
echo

# Step 4: show the resulting bibliography — real metadata, real titles.
typewriter "head -18 references.json"
head -18 references.json
sleep "$PAUSE"
echo

# Step 5: render the manuscript. The citations get formatted correctly
# because pandoc-citeproc reads references.json (and references.bib).
# --quiet keeps quarto's verbose metadata out of the demo frame.
typewriter "quarto render --to html"
quarto render --to html --quiet 2>&1 || true
printf '  rendered index.html\n'
sleep "$PAUSE"
echo

# Step 6: show what landed on disk.
typewriter "ls -lh index.html"
ls -lh index.html
sleep "$PAUSE"
echo

# Step 7: the payoff frame — the resolved citation, properly formatted,
# in the rendered manuscript.
typewriter "grep -oE 'Wickham[^<]{0,80}' index.html | head -2"
grep -oE 'Wickham[^<]{0,80}' index.html | head -2 || true
sleep "$PAUSE"
echo

# Final beat: what this means for CI.
echo
printf '\033[1;36m# Commit references.json and CI is network-free —\033[0m\n'
printf '\033[1;36m# every machine renders the same bibliography, every time.\033[0m\n'
sleep 3

# Cleanup. The cast file (if any) is in the recording dir, not here.
cd "$REPO_ROOT"
rm -rf "$SCRATCH"

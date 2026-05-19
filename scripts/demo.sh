#!/usr/bin/env bash
# Demo script for screen-recording quartobot's pre-render hook in action.
#
# Designed to run under asciinema (or any screen recorder) and produce a
# ~60-second cast showing the citation-resolution magic without the
# slow-render bits. Skips `quarto render` itself because LaTeX install
# can add 1-2 minutes on first run; the README narrative covers what
# `quarto render` does after the JSON is written.
#
# Usage:
#   asciinema rec docs/demo.cast --command 'bash scripts/demo.sh' --idle-time-limit 2
#
# Then upload the cast to asciinema.org (or commit and embed as an
# <asciinema-player> in site/public/) and update the README + landing
# page to point at the cast URL.
#
# Re-running is safe: a fresh scratch directory is used each time.

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
typewriter "head -25 references.json"
head -25 references.json
sleep "$PAUSE"
echo

# Final beat: what happens next.
echo
printf '\033[1;36m# Now `quarto render` produces the manuscript with formatted citations.\033[0m\n'
printf '\033[1;36m# Commit references.json and CI will skip the network round-trip.\033[0m\n'
sleep 3

# Cleanup. The cast file (if any) is in the recording dir, not here.
cd "$REPO_ROOT"
rm -rf "$SCRATCH"

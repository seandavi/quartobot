# vhs tape for the quartobot README demo. Renders a GIF/MP4 of the
# pre-render hook in action against the sample-paper fixture.
#
# Render with:
#   bash scripts/demo-setup.sh && vhs scripts/demo.tape
#
# The setup script copies the fixture into /tmp/quartobot-demo so vhs
# runs against a scratch directory the demo itself doesn't pollute.
#
# Tape design: ~30s of activity, ~3s tail card. Optimized for visual
# legibility on social-media autoplay (no audio, short, big text).

Output docs/demo.gif

# Visual chrome
Set Theme "Catppuccin Mocha"
Set FontSize 18
Set Width 1200
Set Height 700
Set Padding 24
Set Shell "bash"

# Start fresh in the scratch dir.
Type "cd /tmp/quartobot-demo && clear" Enter
Sleep 800ms

# Show what quartobot is.
Type "quartobot --version" Sleep 300ms Enter
Sleep 1500ms

# 1. Show the manuscript prose — citations live inline.
Type "head -8 index.qmd" Sleep 300ms Enter
Sleep 3500ms

# 2. quartobot scan reports what's there before any network call.
Type "quartobot scan ." Sleep 300ms Enter
Sleep 3500ms

# 3. quartobot resolve fetches the metadata from Crossref / PubMed /
#    arXiv and writes references.json. This is the "magic" frame.
Type "quartobot resolve --from-scan . --output references.json --id-mode citation-key" Sleep 300ms Enter
Sleep 5500ms

# 4. Show the resulting CSL JSON — real titles, real authors.
Type "head -25 references.json" Sleep 300ms Enter
Sleep 4500ms

# Final beat: what happens next in the rendering loop.
Type "# Then quarto render produces the manuscript." Sleep 200ms Enter
Sleep 800ms
Type "# Commit references.json and CI is network-free." Sleep 200ms Enter
Sleep 3000ms

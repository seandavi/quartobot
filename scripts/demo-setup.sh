#!/usr/bin/env bash
# Set up /tmp/quartobot-demo as a scratch copy of the sample-paper
# fixture so scripts/demo.tape can run against a clean directory.
# Idempotent: re-running just re-seeds the scratch.

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
FIXTURE="$REPO_ROOT/docs-src/fixtures/sample-paper"
SCRATCH="/tmp/quartobot-demo"

if [ ! -d "$FIXTURE" ]; then
  echo "fixture not found: $FIXTURE" >&2
  exit 1
fi

rm -rf "$SCRATCH"
mkdir -p "$SCRATCH"
cp -R "$FIXTURE"/. "$SCRATCH/"

echo "scratch ready at $SCRATCH"
ls "$SCRATCH"

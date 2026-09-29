#!/usr/bin/env bash
# Copy a figure from the docling cache into the vault so a note can embed it.
# Usage: _tools/pick_figure.sh <citekey> <fig-file-in-cache> [new-name]
# The file lands at Attachments/<citekey>/<citekey>-<new-name or fig-file>.
# Prefixing with the citekey keeps names unique vault-wide, so ![[<name>]] embeds resolve.
set -euo pipefail
cd "$(dirname "$0")/.."
key=$1; fig=$2; name=${3:-$fig}
cp ".cache/docling/$key/figs/$fig" "Attachments/$key/$key-$name"
echo "![[${key}-${name}]]"

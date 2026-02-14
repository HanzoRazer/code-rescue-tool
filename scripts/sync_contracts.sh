#!/usr/bin/env bash
set -euo pipefail

# Sync contracts from upstream code-analysis-tool repo
# Usage: ./scripts/sync_contracts.sh [ref]
#   ref: branch or tag (default: main)

REF="${1:-main}"
BASE="https://raw.githubusercontent.com/HanzoRazer/code-analysis-tool/${REF}"

echo "Syncing contracts from upstream ref: ${REF}"

curl -fsSL "$BASE/schemas/run_result.schema.json" -o contracts/run_result.schema.json
echo "  [OK] contracts/run_result.schema.json"

echo ""
echo "Synced. Review diff, commit, push:"
echo "  git diff contracts/"
echo "  git add contracts/ && git commit -m 'chore(contracts): sync from upstream'"

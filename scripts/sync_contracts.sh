#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   UPSTREAM_REF=v1.0.0 ./scripts/sync_contracts.sh
#   ./scripts/sync_contracts.sh   (defaults to main)

OWNER="HanzoRazer"
REPO="code-analysis-tool"
UPSTREAM_REF="${UPSTREAM_REF:-main}"

BASE="https://raw.githubusercontent.com/${OWNER}/${REPO}/${UPSTREAM_REF}"

echo "Syncing contracts from ${OWNER}/${REPO}@${UPSTREAM_REF}..."

curl -fsSL \
  "${BASE}/schemas/run_result.schema.json" \
  -o contracts/run_result.schema.json

echo ""
echo "✔ Synced contracts/run_result.schema.json"
echo ""
echo "Next steps:"
echo "  1. git diff contracts/run_result.schema.json"
echo "  2. git commit -am \"chore(contracts): sync from ${OWNER}/${REPO}@${UPSTREAM_REF}\""
echo "  3. git push"

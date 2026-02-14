#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   UPSTREAM_REF=v1.0.0 ./scripts/sync_contracts.sh
#   ./scripts/sync_contracts.sh   (defaults to main)
#
# Optional:
#   CHECK_RULE_REGISTRY=0 ./scripts/sync_contracts.sh   (skip rule registry sync)

OWNER="HanzoRazer"
REPO="code-analysis-tool"
UPSTREAM_REF="${UPSTREAM_REF:-main}"
CHECK_RULE_REGISTRY="${CHECK_RULE_REGISTRY:-1}"

BASE="https://raw.githubusercontent.com/${OWNER}/${REPO}/${UPSTREAM_REF}"

echo "Syncing contracts from ${OWNER}/${REPO}@${UPSTREAM_REF}..."

curl -fsSL \
  "${BASE}/schemas/run_result.schema.json" \
  -o contracts/run_result.schema.json
echo "✔ Synced contracts/run_result.schema.json"

if [[ "${CHECK_RULE_REGISTRY}" != "0" && "${CHECK_RULE_REGISTRY}" != "false" && "${CHECK_RULE_REGISTRY}" != "False" ]]; then
  curl -fsSL \
    "${BASE}/docs/rule_registry.json" \
    -o contracts/rule_registry.json
  echo "✔ Synced contracts/rule_registry.json"
else
  echo "↪ Skipped rule registry sync (CHECK_RULE_REGISTRY=0)"
fi

echo ""
echo "Next steps:"
echo "  1. git diff contracts/run_result.schema.json"
echo "     git diff contracts/rule_registry.json || true"
echo "  2. git commit -am \"chore(contracts): sync from ${OWNER}/${REPO}@${UPSTREAM_REF}\""
echo "  3. git push"

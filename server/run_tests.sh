#!/usr/bin/env bash
# Run all WS tests. No live DB or API keys needed.
# Usage:
#   ./run_tests.sh          → all tests
#   ./run_tests.sh ws4      → only WS-4
#   ./run_tests.sh ws4 ws7  → WS-4 + WS-7

set -e
cd "$(dirname "$0")"

if [ $# -eq 0 ]; then
  uv run pytest tests/ -v --tb=short
else
  FILES=""
  for ws in "$@"; do
    FILES="$FILES tests/test_${ws}_*.py"
  done
  uv run pytest $FILES -v --tb=short
fi

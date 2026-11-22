#!/usr/bin/env bash
# Runs backend + frontend tests, stores JUnit XML in results/, writes results/SUMMARY.md
# and refreshes the test table in README.md. Uses only the project venv / local node_modules.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/results"

cd "$ROOT/backend"
[ -d .venv ] || uv venv -q .venv
uv sync -q
.venv/bin/pytest -q --junitxml="$ROOT/results/backend-junit.xml"; BE=$?

cd "$ROOT/frontend"
[ -d node_modules ] || npm ci --silent
npx vitest run; FE=$?

"$ROOT/backend/.venv/bin/python" "$ROOT/scripts/summarize.py" "$ROOT"
exit $(( BE || FE ))

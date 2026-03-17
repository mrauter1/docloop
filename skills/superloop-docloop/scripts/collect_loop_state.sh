#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

echo "== git status =="
git status --short || true

echo
echo "== superloop tasks (if present) =="
if [ -d .superloop/tasks ]; then
  find .superloop/tasks -maxdepth 3 -type d | sed -n '1,120p'
else
  echo "(none)"
fi

echo
echo "== recent run logs =="
find . -type f \( -name 'run_log.md' -o -name 'progress.txt' -o -name 'raw_phase_log.md' \) | sed -n '1,120p'

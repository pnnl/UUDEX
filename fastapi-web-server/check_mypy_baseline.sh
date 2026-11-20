#!/usr/bin/env bash
# Runs mypy on src and fails when the error count exceeds mypy-baseline.txt.
# Run from fastapi-web-server/ with the dev install available to poetry.
set -euo pipefail

main() {
  local here baseline_file baseline output rc=0 summary count

  here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  baseline_file="$here/mypy-baseline.txt"
  [[ -r "$baseline_file" ]] || { echo "error: cannot read $baseline_file" >&2; exit 1; }
  baseline=$(<"$baseline_file")
  [[ "$baseline" =~ ^[0-9]+$ ]] || { echo "error: $baseline_file must hold one integer" >&2; exit 1; }

  # mypy exits 1 when it reports errors, which is the normal case here; the
  # count below decides pass or fail. Any other status is a crash (2) or worse.
  output=$(poetry run mypy src 2>&1) || rc=$?
  printf '%s\n' "$output"
  if [[ "$rc" -gt 1 ]]; then
    echo "error: mypy exited with status $rc" >&2
    exit 1
  fi

  summary=$(printf '%s\n' "$output" | tail -n 1)
  if [[ "$summary" == Success:* ]]; then
    count=0
  elif [[ "$summary" =~ ^Found\ ([0-9]+)\ errors?\ in ]]; then
    count=${BASH_REMATCH[1]}
  else
    echo "error: no mypy summary line found; last line was: $summary" >&2
    exit 1
  fi

  echo "mypy errors: $count (baseline: $baseline)"
  if (( count > baseline )); then
    echo "error: $((count - baseline)) new mypy error(s) over the baseline" >&2
    exit 1
  fi
  if (( count < baseline )); then
    echo "The count is below the baseline: lower mypy-baseline.txt to $count."
  fi
}

main "$@"

#!/usr/bin/env bash
# docsearch — convenience wrapper that finds the right Python to use.
#
# Resolution order:
#   1. $DOCSEARCH_PYTHON (explicit override)
#   2. Active virtual env (VIRTUAL_ENV set)
#   3. python3 on PATH

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -n "${DOCSEARCH_PYTHON:-}" ]]; then
    exec "$DOCSEARCH_PYTHON" "$SCRIPT_DIR/docsearch.py" "$@"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
    exec "$VIRTUAL_ENV/bin/python3" "$SCRIPT_DIR/docsearch.py" "$@"
else
    exec python3 "$SCRIPT_DIR/docsearch.py" "$@"
fi

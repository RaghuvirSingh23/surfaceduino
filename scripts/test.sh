#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONPATH="$repo_dir/python" python3 -m unittest discover -s "$repo_dir/tests" -v

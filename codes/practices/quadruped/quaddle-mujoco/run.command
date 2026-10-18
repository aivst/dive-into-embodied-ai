#!/bin/zsh
set -eu
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  print -u2 "请先在本目录执行：uv venv --python 3.12 .venv"
  print -u2 "然后执行：uv pip sync --python .venv/bin/python requirements.lock"
  exit 1
fi
exec .venv/bin/python launch.py "$@"

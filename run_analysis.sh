#!/bin/bash
# TradingAgents Claude-native wrapper
# 用法: ./run_analysis.sh LI

unset CLAUDECODE
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TICKER="${1:-LI}"
PHASE="${2:-full}"

if [ "$PHASE" != "full" ]; then
  echo "[warn] phase 参数已废弃，当前统一走 Claude 原生 /deep-analysis 全流程。" >&2
fi

PROMPT="$(python3 - "$TICKER" "$SCRIPT_DIR" <<'PY'
from pathlib import Path
import sys

ticker = sys.argv[1]
repo_root = Path(sys.argv[2])
template_path = repo_root / 'prompts' / 'deep-analysis.md'
text = template_path.read_text(encoding='utf-8')
print(text.replace('$ARGUMENTS', ticker))
PY
)"

cd "$SCRIPT_DIR"
claude -p --dangerously-skip-permissions "$PROMPT"

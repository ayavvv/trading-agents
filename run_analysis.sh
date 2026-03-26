#!/bin/bash
# TradingAgents 多智能体分析 — 入口脚本
# 用法: ./run_analysis.sh LI [full|analysts-only|debate-only]
# OpenClaw cron 或手动调用

unset CLAUDECODE
export PATH="/usr/local/bin:/opt/homebrew/bin:$HOME/.local/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TICKER="${1:-LI}"
PHASE="${2:-full}"

cd "$SCRIPT_DIR"
.venv/bin/python3 orchestrator.py \
  --ticker "$TICKER" \
  --config config.json \
  --phase "$PHASE"

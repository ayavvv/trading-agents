#!/usr/bin/env python3
"""交易后复盘 — 分析决策质量，存入各角色的 BM25 记忆。"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from memory.bm25_search import FinancialMemory


def call_claude(prompt: str, model: str = "sonnet") -> str:
    """调用 claude -p 进行反思分析。"""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    result = subprocess.run(
        ["claude", "-p", "--model", model,
         "--dangerously-skip-permissions", prompt],
        capture_output=True, text=True, timeout=180, env=env,
    )
    return result.stdout.strip()


def reflect_on_trade(state_file: str, outcome: str, model: str = "sonnet"):
    """基于交易结果进行复盘。

    Args:
        state_file: 之前运行生成的 *_state.json 路径
        outcome: 交易结果描述，如 "持有LI，价格从18.08涨至20.50，收益+13.4%"
        model: 用于反思的模型
    """
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)

    ticker = state["ticker"]
    date = state["date"]
    final_decision = state.get("final_decision", "")
    reports_summary = ""
    for name, report in state.get("reports", {}).items():
        reports_summary += f"\n[{name}]: {report[:300]}...\n"

    # 需要反思的角色
    roles = {
        "bull": "多头研究员",
        "bear": "空头研究员",
        "trader": "交易员",
        "judge": "研究经理",
        "portfolio": "投组经理",
    }

    for role_key, role_name in roles.items():
        print(f"  反思: {role_name}...", file=sys.stderr)

        prompt = f"""你是一个交易复盘分析师。请评估以下交易中 "{role_name}" 的表现。

## 交易信息
- 标的: {ticker}
- 分析日期: {date}
- 最终决策: {final_decision[:500]}

## 分析师报告摘要
{reports_summary[:1000]}

## 实际交易结果
{outcome}

请分析：
1. {role_name}的判断是否正确？哪些分析点与实际结果一致？
2. 有哪些错误判断？为什么会犯这些错误？
3. 下次遇到类似情景，{role_name}应该如何改进？

用 2-3 句话总结关键教训。中文输出。"""

        reflection = call_claude(prompt, model)

        # 构建情景描述
        situation = (
            f"{ticker} on {date}. "
            f"Decision: {final_decision[:200]}. "
            f"Outcome: {outcome}"
        )

        # 存入记忆
        mem = FinancialMemory(str(ROOT / "memory" / f"{role_key}.json"))
        mem.add(situation, reflection)
        print(f"  {role_name} 反思已存入记忆 ({mem.size()} 条)", file=sys.stderr)

    print(f"\n复盘完成！5 个角色的反思已存入各自记忆文件。", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="TradingAgents 交易复盘")
    parser.add_argument("--state", required=True, help="state.json 文件路径")
    parser.add_argument("--outcome", required=True, help="交易结果描述")
    parser.add_argument("--model", default="sonnet", help="反思用模型")
    args = parser.parse_args()

    if not os.path.exists(args.state):
        print(f"错误: 文件不存在 {args.state}", file=sys.stderr)
        sys.exit(1)

    reflect_on_trade(args.state, args.outcome, args.model)


if __name__ == "__main__":
    main()

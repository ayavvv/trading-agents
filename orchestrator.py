#!/usr/bin/env python3
"""TradingAgents 编排器 — 替代 LangGraph，用 claude -p 驱动多智能体分析。"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from data.fetcher import build_data_package
from data.formatter import (
    format_for_market_analyst,
    format_for_sentiment_analyst,
    format_for_news_analyst,
    format_for_fundamentals_analyst,
    combine_reports,
    format_debate_context,
    format_risk_context,
)


def load_prompt(name: str) -> str:
    """加载 prompt 文件。"""
    path = ROOT / "prompts" / f"{name}.txt"
    return path.read_text(encoding="utf-8")


def call_claude(model: str, system_prompt: str, user_message: str, timeout: int = 300) -> str:
    """调用 claude -p，返回输出文本。"""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    cmd = [
        "claude", "-p",
        "--model", model,
        "--dangerously-skip-permissions",
        "--append-system-prompt", system_prompt,
        user_message,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout or 300,
            env=env,
        )
        if result.returncode != 0:
            print(f"  [警告] claude 返回码 {result.returncode}: {result.stderr[:200]}", file=sys.stderr)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"  [超时] claude -p 超过 {timeout}s", file=sys.stderr)
        return "[分析超时，未能完成]"
    except FileNotFoundError:
        print("  [错误] claude 命令未找到，请确认已安装 Claude Code CLI", file=sys.stderr)
        sys.exit(1)


def get_futu_positions() -> str:
    """获取 Futu 实盘持仓（复用现有脚本）。"""
    try:
        result = subprocess.run(
            [sys.executable, os.path.expanduser("~/.openclaw/workspace/futu_positions.py")],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def load_memories(role: str, query: str) -> list:
    """从 BM25 记忆中检索相关历史。"""
    memory_file = ROOT / "memory" / f"{role}.json"
    if not memory_file.exists():
        return []
    try:
        from memory.bm25_search import FinancialMemory
        mem = FinancialMemory(str(memory_file))
        return mem.search(query, top_k=2)
    except Exception:
        return []


def run_analysts(data: dict, positions: str, model: str) -> dict:
    """Phase 1: 4 个分析师并行执行。"""
    print("\n━━━ Phase 1: 分析师团队 ━━━", file=sys.stderr)

    analyst_configs = {
        "market": {
            "prompt": "market_analyst",
            "data": format_for_market_analyst(data, positions),
        },
        "sentiment": {
            "prompt": "sentiment_analyst",
            "data": format_for_sentiment_analyst(data),
        },
        "news": {
            "prompt": "news_analyst",
            "data": format_for_news_analyst(data),
        },
        "fundamentals": {
            "prompt": "fundamentals_analyst",
            "data": format_for_fundamentals_analyst(data),
        },
    }

    reports = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {}
        for name, cfg in analyst_configs.items():
            print(f"  [{name}] 启动分析...", file=sys.stderr)
            future = pool.submit(
                call_claude, model, load_prompt(cfg["prompt"]), cfg["data"]
            )
            future_map[future] = name

        for future in as_completed(future_map):
            name = future_map[future]
            try:
                reports[name] = future.result()
                print(f"  [{name}] 完成 ✓", file=sys.stderr)
            except Exception as e:
                reports[name] = f"[分析失败: {e}]"
                print(f"  [{name}] 失败 ✗: {e}", file=sys.stderr)

    return reports


def run_research_debate(all_reports: str, config: dict, model: str, deep_model: str) -> tuple:
    """Phase 2: 多空辩论 + 研究经理裁决。"""
    print("\n━━━ Phase 2: 多空研究辩论 ━━━", file=sys.stderr)

    max_rounds = config.get("max_debate_rounds", 1)
    debate_history = []
    bull_memories = load_memories("bull", all_reports[:500])
    bear_memories = load_memories("bear", all_reports[:500])

    for r in range(max_rounds):
        print(f"  [辩论第 {r+1}/{max_rounds} 轮]", file=sys.stderr)

        # Bull
        bull_ctx = format_debate_context(all_reports, debate_history, bull_memories)
        print(f"    多头研究员...", file=sys.stderr)
        bull_arg = call_claude(model, load_prompt("bull_researcher"), bull_ctx)
        debate_history.append(f"**多头研究员**: {bull_arg}")
        print(f"    多头研究员 ✓", file=sys.stderr)

        # Bear
        bear_ctx = format_debate_context(all_reports, debate_history, bear_memories)
        print(f"    空头研究员...", file=sys.stderr)
        bear_arg = call_claude(model, load_prompt("bear_researcher"), bear_ctx)
        debate_history.append(f"**空头研究员**: {bear_arg}")
        print(f"    空头研究员 ✓", file=sys.stderr)

    # Research Manager judges
    print(f"  研究经理裁决 (使用 {deep_model})...", file=sys.stderr)
    judge_memories = load_memories("judge", all_reports[:500])
    judge_ctx = format_debate_context(all_reports, debate_history, judge_memories)
    investment_plan = call_claude(deep_model, load_prompt("research_manager"), judge_ctx)
    print(f"  研究经理裁决 ✓", file=sys.stderr)

    return debate_history, investment_plan


def run_trader(all_reports: str, investment_plan: str, positions: str, model: str) -> str:
    """Phase 3: 交易员提案。"""
    print("\n━━━ Phase 3: 交易员 ━━━", file=sys.stderr)

    trader_memories = load_memories("trader", all_reports[:500])
    ctx_parts = [
        all_reports,
        "\n---\n",
        "## 研究经理的投资计划\n",
        investment_plan,
    ]
    if positions:
        ctx_parts.extend(["\n## 当前持仓\n", positions])
    if trader_memories:
        ctx_parts.append("\n## 过去类似交易的经验教训\n")
        for mem in trader_memories:
            ctx_parts.append(f"- {mem.get('situation', '')[:200]}")
            ctx_parts.append(f"  {mem.get('reflection', '')[:200]}\n")

    print(f"  交易员制定提案...", file=sys.stderr)
    proposal = call_claude(model, load_prompt("trader"), "\n".join(ctx_parts))
    print(f"  交易员提案 ✓", file=sys.stderr)
    return proposal


def run_risk_debate(all_reports: str, trade_proposal: str, positions: str,
                    config: dict, model: str, deep_model: str) -> tuple:
    """Phase 4: 风控辩论 + 投组经理最终决策。"""
    print("\n━━━ Phase 4: 风控辩论 ━━━", file=sys.stderr)

    max_rounds = config.get("max_risk_discuss_rounds", 1)
    risk_history = []

    debaters = [
        ("aggressive_debater", "激进派"),
        ("conservative_debater", "保守派"),
        ("neutral_debater", "中立派"),
    ]

    for r in range(max_rounds):
        print(f"  [辩论第 {r+1}/{max_rounds} 轮]", file=sys.stderr)
        for prompt_name, label in debaters:
            ctx = format_risk_context(all_reports, trade_proposal, risk_history, positions=positions)
            print(f"    {label}...", file=sys.stderr)
            response = call_claude(model, load_prompt(prompt_name), ctx)
            risk_history.append(f"**{label}**: {response}")
            print(f"    {label} ✓", file=sys.stderr)

    # Portfolio Manager final decision
    print(f"  投组经理最终决策 (使用 {deep_model})...", file=sys.stderr)
    pm_memories = load_memories("portfolio", all_reports[:500])
    pm_ctx = format_risk_context(
        all_reports, trade_proposal, risk_history,
        memories=pm_memories, positions=positions,
    )
    final_decision = call_claude(deep_model, load_prompt("portfolio_manager"), pm_ctx)
    print(f"  投组经理最终决策 ✓", file=sys.stderr)

    return risk_history, final_decision


def save_results(ticker: str, date_str: str, state: dict):
    """保存运行结果。"""
    results_dir = ROOT / "results" / ticker
    results_dir.mkdir(parents=True, exist_ok=True)

    # 保存完整状态
    state_file = results_dir / f"{date_str}_state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)

    # 保存最终决策
    decision_file = results_dir / f"{date_str}_decision.md"
    with open(decision_file, "w", encoding="utf-8") as f:
        f.write(f"# {ticker} 交易决策 ({date_str})\n\n")
        f.write(state.get("final_decision", "无决策"))

    print(f"\n结果已保存: {state_file}", file=sys.stderr)


def run_analysis(ticker: str, config: dict, phase: str = "full"):
    """运行完整分析流程。"""
    start_time = time.time()
    date_str = datetime.now().strftime("%Y-%m-%d")
    analyst_model = config.get("analyst_model", "sonnet")
    deep_model = config.get("deep_think_model", "opus")

    print(f"\n{'='*60}", file=sys.stderr)
    print(f"  TradingAgents 分析: {ticker} ({date_str})", file=sys.stderr)
    print(f"  分析师模型: {analyst_model} | 深度模型: {deep_model}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    # Phase 0: 数据预取
    print("\n━━━ Phase 0: 数据预取 ━━━", file=sys.stderr)
    data = build_data_package(ticker, config)
    positions = get_futu_positions()

    # Phase 1: 分析师
    reports = run_analysts(data, positions, analyst_model)
    all_reports = combine_reports(reports)

    if phase == "analysts-only":
        print("\n" + all_reports)
        return

    # Phase 2: 多空辩论
    debate_history, investment_plan = run_research_debate(
        all_reports, config, analyst_model, deep_model
    )

    if phase == "debate-only":
        print("\n## 投资计划\n")
        print(investment_plan)
        return

    # Phase 3: 交易员
    trade_proposal = run_trader(all_reports, investment_plan, positions, analyst_model)

    # Phase 4: 风控辩论 + 最终决策
    risk_history, final_decision = run_risk_debate(
        all_reports, trade_proposal, positions, config, analyst_model, deep_model
    )

    elapsed = time.time() - start_time

    # 保存结果
    state = {
        "ticker": ticker,
        "date": date_str,
        "config": config,
        "reports": reports,
        "debate_history": debate_history,
        "investment_plan": investment_plan,
        "trade_proposal": trade_proposal,
        "risk_history": risk_history,
        "final_decision": final_decision,
        "elapsed_seconds": round(elapsed, 1),
        "llm_calls": {
            "analysts": 4,
            "debate": 2 * config.get("max_debate_rounds", 1),
            "research_manager": 1,
            "trader": 1,
            "risk_debate": 3 * config.get("max_risk_discuss_rounds", 1),
            "portfolio_manager": 1,
        },
    }
    save_results(ticker, date_str, state)

    # 输出最终决策
    print(final_decision)

    total_calls = sum(state["llm_calls"].values())
    print(f"\n[统计] 总耗时: {elapsed:.0f}s | LLM调用: {total_calls}次 | "
          f"模型: {analyst_model}+{deep_model}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="TradingAgents 多智能体分析")
    parser.add_argument("--ticker", required=True, help="股票代码，如 LI")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--phase", default="full",
                        choices=["full", "analysts-only", "debate-only"],
                        help="运行阶段")
    args = parser.parse_args()

    # 加载配置
    if args.config and os.path.exists(args.config):
        with open(args.config) as f:
            config = json.load(f)
    else:
        config = {
            "data_lookback_days": 30,
            "max_debate_rounds": 1,
            "max_risk_discuss_rounds": 1,
            "analyst_model": "sonnet",
            "deep_think_model": "sonnet",
            "indicators": [
                "rsi_14", "macd", "macdh", "macds",
                "close_20_sma", "close_50_sma", "close_200_sma",
                "boll_ub", "boll_lb",
            ],
        }

    run_analysis(args.ticker, config, args.phase)


if __name__ == "__main__":
    main()

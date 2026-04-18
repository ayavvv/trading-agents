#!/usr/bin/env python3
"""TradingAgents support utilities for Claude-native multi-agent runs."""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from data.fetcher import build_data_package
from data.formatter import (
    format_for_market_analyst,
    format_for_sentiment_analyst,
    format_for_news_analyst,
    format_for_fundamentals_analyst,
)

DEFAULT_CONFIG = {
    "data_lookback_days": 30,
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "analyst_model": "sonnet",
    "deep_think_model": "opus",
    "indicators": [
        "rsi_14",
        "macd",
        "macdh",
        "macds",
        "close_20_sma",
        "close_50_sma",
        "close_200_sma",
        "boll_ub",
        "boll_lb",
        "atr_14",
    ],
}

ROLE_LABELS = {
    "bull": "多头研究员",
    "bear": "空头研究员",
    "trader": "交易员",
    "judge": "研究经理",
    "portfolio": "投组经理",
}


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    path = Path(config_path) if config_path else ROOT / "config.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            config.update(json.load(f))
    return config


def get_futu_positions() -> str:
    try:
        result = subprocess.run(
            [sys.executable, os.path.expanduser("~/.openclaw/workspace/futu_positions.py")],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def load_memories(role: str, query: str) -> List[Dict[str, Any]]:
    memory_file = ROOT / "memory" / f"{role}.json"
    if not memory_file.exists():
        return []
    try:
        from memory.bm25_search import FinancialMemory

        mem = FinancialMemory(str(memory_file))
        return mem.search(query, top_k=2)
    except Exception:
        return []


def build_memory_query(symbol: str, data: Dict[str, Any]) -> str:
    fundamentals = data.get("fundamentals", {})
    news_titles = [item.get("title", "") for item in data.get("news", [])[:5] if item.get("title")]
    return "\n".join(
        [
            symbol,
            fundamentals.get("shortName", ""),
            fundamentals.get("sector", ""),
            fundamentals.get("industry", ""),
            str(fundamentals.get("marketCap", "")),
            str(fundamentals.get("revenueGrowth", "")),
            str(fundamentals.get("earningsGrowth", "")),
            *news_titles,
        ]
    )


def format_memory_brief(role: str, memories: List[Dict[str, Any]]) -> str:
    label = ROLE_LABELS[role]
    lines = [f"# {label} 历史经验\n"]
    if not memories:
        lines.append("暂无相关历史记忆。")
        return "\n".join(lines)

    for index, mem in enumerate(memories, 1):
        situation = (mem.get("situation") or "").strip()
        reflection = (mem.get("reflection") or "").strip()
        lines.extend(
            [
                f"## 案例 {index}",
                f"- 情景: {situation[:400] or 'N/A'}",
                f"- 反思: {reflection[:400] or 'N/A'}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_llm_calls(config: Dict[str, Any]) -> Dict[str, int]:
    max_debate_rounds = config.get("max_debate_rounds", 1)
    max_risk_discuss_rounds = config.get("max_risk_discuss_rounds", 1)
    return {
        "analysts": 4,
        "debate": 2 * max_debate_rounds,
        "research_manager": 1,
        "trader": 1,
        "risk_debate": 3 * max_risk_discuss_rounds,
        "portfolio_manager": 1,
    }


def prepare_run(ticker: str, config_path: Optional[str] = None) -> Path:
    config = load_config(config_path)
    now = datetime.now()
    ticker = ticker.upper()
    date_str = now.strftime("%Y-%m-%d")
    run_id = now.strftime("%Y%m%d-%H%M%S")

    results_dir = ROOT / "results" / ticker
    run_dir = results_dir / "runs" / run_id
    inputs_dir = run_dir / "inputs"
    memory_dir = run_dir / "memory"

    print(f"[prepare] 获取 {ticker} 数据...", file=sys.stderr)
    data = build_data_package(ticker, config)
    positions = get_futu_positions()
    memory_query = build_memory_query(ticker, data)

    input_payloads = {
        "market": format_for_market_analyst(data, positions),
        "sentiment": format_for_sentiment_analyst(data),
        "news": format_for_news_analyst(data),
        "fundamentals": format_for_fundamentals_analyst(data),
    }

    input_paths = {}
    for name, content in input_payloads.items():
        path = inputs_dir / f"{name}.txt"
        write_text(path, content)
        input_paths[name] = str(path)

    positions_path = run_dir / "positions.txt"
    write_text(positions_path, positions or "当前无持仓数据。\n")

    memory_paths = {}
    for role in ROLE_LABELS:
        path = memory_dir / f"{role}.txt"
        write_text(path, format_memory_brief(role, load_memories(role, memory_query)))
        memory_paths[role] = str(path)

    manifest_path = run_dir / "manifest.json"
    manifest = {
        "ticker": ticker,
        "date": date_str,
        "run_id": run_id,
        "created_at": now.isoformat(timespec="seconds"),
        "config": config,
        "paths": {
            "run_dir": str(run_dir),
            "manifest": str(manifest_path),
            "inputs": input_paths,
            "positions": str(positions_path),
            "memories": memory_paths,
            "scratch_state": str(run_dir / "final_state.json"),
            "output_state": str(results_dir / f"{date_str}_state.json"),
            "output_decision": str(results_dir / f"{date_str}_decision.md"),
        },
    }
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(f"[prepare] manifest 已生成: {manifest_path}", file=sys.stderr)
    print(str(manifest_path))
    return manifest_path


def persist_results(manifest_path: str, state_json_path: str) -> Dict[str, str]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(state_json_path, "r", encoding="utf-8") as f:
        raw_state = json.load(f)

    config = manifest.get("config", {})
    final_state = {
        "ticker": manifest["ticker"],
        "date": manifest["date"],
        "run_id": manifest["run_id"],
        "manifest_path": manifest["paths"]["manifest"],
        "config": config,
        "reports": raw_state.get("reports", {}),
        "debate_history": raw_state.get("debate_history", []),
        "investment_plan": raw_state.get("investment_plan", ""),
        "trade_proposal": raw_state.get("trade_proposal", ""),
        "risk_history": raw_state.get("risk_history", []),
        "final_decision": raw_state.get("final_decision", ""),
        "elapsed_seconds": raw_state.get("elapsed_seconds"),
        "llm_calls": raw_state.get("llm_calls", build_llm_calls(config)),
    }

    for key, value in raw_state.items():
        if key not in final_state:
            final_state[key] = value

    output_state = Path(manifest["paths"]["output_state"])
    output_decision = Path(manifest["paths"]["output_decision"])
    write_text(output_state, json.dumps(final_state, ensure_ascii=False, indent=2) + "\n")

    final_decision = final_state.get("final_decision", "").strip()
    if final_decision.startswith("# "):
        decision_content = final_decision + ("\n" if not final_decision.endswith("\n") else "")
    else:
        decision_content = f"# {manifest['ticker']} 交易决策 ({manifest['date']})\n\n{final_decision}\n"
    write_text(output_decision, decision_content)

    result = {
        "state": str(output_state),
        "decision": str(output_decision),
    }
    print(json.dumps(result, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="TradingAgents Claude-native support utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Prepare deterministic inputs for /deep-analysis")
    prepare_parser.add_argument("--ticker", required=True, help="股票代码，如 LI")
    prepare_parser.add_argument("--config", default=None, help="配置文件路径")

    persist_parser = subparsers.add_parser("persist", help="Persist Claude-generated final state")
    persist_parser.add_argument("--manifest", required=True, help="manifest.json 路径")
    persist_parser.add_argument("--state-json", required=True, help="Claude 生成的 final_state.json 路径")

    args = parser.parse_args()

    if args.command == "prepare":
        prepare_run(args.ticker, args.config)
    elif args.command == "persist":
        persist_results(args.manifest, args.state_json)


if __name__ == "__main__":
    main()

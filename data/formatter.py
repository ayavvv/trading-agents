#!/usr/bin/env python3
"""将数据包格式化为各分析师可读的文本。"""
import json


def format_for_market_analyst(data: dict, positions: str = "") -> str:
    """格式化市场/技术分析数据。"""
    parts = [
        f"# {data['symbol']} 市场数据 ({data['fetch_date']})\n",
        "## OHLCV 价格数据（近期）\n",
        "```csv",
        data["ohlcv"],
        "```\n",
        "## 技术指标（最新值）\n",
    ]
    for k, v in data["indicators"].items():
        parts.append(f"- {k}: {v}")

    if positions:
        parts.extend(["\n## 当前持仓\n", positions])

    return "\n".join(parts)


def format_for_sentiment_analyst(data: dict) -> str:
    """格式化情绪/新闻数据供情绪分析师使用。"""
    parts = [
        f"# {data['symbol']} 舆情与情绪数据 ({data['fetch_date']})\n",
        "## 近期新闻\n",
    ]
    for i, item in enumerate(data["news"], 1):
        title = item.get("title", "无标题")
        pub = item.get("publisher", "")
        date = item.get("date", "")
        parts.append(f"{i}. [{date}] {title} — {pub}")

    parts.extend([
        "\n## 内幕交易记录\n",
        data["insider_transactions"],
    ])

    return "\n".join(parts)


def format_for_news_analyst(data: dict) -> str:
    """格式化新闻数据供新闻分析师使用。"""
    parts = [
        f"# {data['symbol']} 新闻与宏观数据 ({data['fetch_date']})\n",
        "## 公司近期新闻\n",
    ]
    for i, item in enumerate(data["news"], 1):
        title = item.get("title", "无标题")
        pub = item.get("publisher", "")
        date = item.get("date", "")
        parts.append(f"{i}. [{date}] {title} — {pub}")

    parts.extend([
        "\n## 内幕交易\n",
        data["insider_transactions"],
        "\n## 基本面快照（供宏观背景参考）\n",
        f"- 行业: {data['fundamentals'].get('sector', 'N/A')} / {data['fundamentals'].get('industry', 'N/A')}",
        f"- 市值: {data['fundamentals'].get('marketCap', 'N/A')}",
        f"- Beta: {data['fundamentals'].get('beta', 'N/A')}",
    ])

    return "\n".join(parts)


def format_for_fundamentals_analyst(data: dict) -> str:
    """格式化基本面数据。"""
    parts = [
        f"# {data['symbol']} 基本面数据 ({data['fetch_date']})\n",
        "## 公司概览与关键指标\n",
    ]
    for k, v in data["fundamentals"].items():
        parts.append(f"- {k}: {v}")

    stmts = data["financial_statements"]
    if stmts.get("balance_sheet") and stmts["balance_sheet"] != "N/A":
        parts.extend(["\n## 资产负债表（近4季度）\n", "```", stmts["balance_sheet"], "```"])
    if stmts.get("cashflow") and stmts["cashflow"] != "N/A":
        parts.extend(["\n## 现金流量表（近4季度）\n", "```", stmts["cashflow"], "```"])
    if stmts.get("income_statement") and stmts["income_statement"] != "N/A":
        parts.extend(["\n## 利润表（近4季度）\n", "```", stmts["income_statement"], "```"])

    return "\n".join(parts)


def combine_reports(reports: dict) -> str:
    """合并所有分析师报告为一个完整文本。"""
    parts = ["# 分析师团队报告汇总\n"]
    labels = {
        "market": "市场/技术分析报告",
        "sentiment": "舆情/情绪分析报告",
        "news": "新闻/宏观分析报告",
        "fundamentals": "基本面分析报告",
    }
    for key, label in labels.items():
        if key in reports:
            parts.extend([
                f"\n{'='*60}",
                f"## {label}",
                f"{'='*60}\n",
                reports[key],
            ])
    return "\n".join(parts)


def format_debate_context(all_reports: str, debate_history: list, memories: list = None) -> str:
    """格式化辩论上下文。"""
    parts = [all_reports, "\n---\n"]

    if debate_history:
        parts.append("## 辩论历史\n")
        for entry in debate_history:
            parts.append(entry + "\n")

    if memories:
        parts.append("\n## 历史相似情景的经验教训\n")
        for mem in memories:
            parts.append(f"- 情景: {mem.get('situation', '')[:200]}")
            parts.append(f"  反思: {mem.get('reflection', '')[:200]}\n")

    return "\n".join(parts)


def format_risk_context(all_reports: str, trade_proposal: str, risk_history: list,
                        memories: list = None, positions: str = "") -> str:
    """格式化风控辩论上下文。"""
    parts = [
        all_reports,
        "\n---\n",
        "## 交易员提案\n",
        trade_proposal,
    ]

    if positions:
        parts.extend(["\n## 当前持仓\n", positions])

    if risk_history:
        parts.append("\n## 风控辩论历史\n")
        for entry in risk_history:
            parts.append(entry + "\n")

    if memories:
        parts.append("\n## 历史经验教训\n")
        for mem in memories:
            parts.append(f"- {mem.get('situation', '')[:200]}")
            parts.append(f"  {mem.get('reflection', '')[:200]}\n")

    return "\n".join(parts)

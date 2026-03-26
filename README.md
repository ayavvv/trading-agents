# TradingAgents for Claude Code

多智能体交易决策框架 — 基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 架构，移植为 Claude Code 原生实现。

## 架构

用 Python 编排器 + `claude -p` 替代 LangGraph/LangChain，12 个专业角色协作完成深度分析：

```
Phase 0: 数据预取 (yfinance + stockstats)
    ↓
Phase 1: 4 分析师并行 → 市场/情绪/新闻/基本面报告
    ↓
Phase 2: 多空辩论 → Bull vs Bear (N轮) → 研究经理裁决
    ↓
Phase 3: 交易员提案
    ↓
Phase 4: 风控辩论 → 激进/保守/中立 (N轮) → 投组经理最终决策
    ↓
输出: Buy / Overweight / Hold / Underweight / Sell
```

## 快速开始

```bash
# 安装
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 完整分析
./run_analysis.sh LI

# 仅分析师报告
./run_analysis.sh LI analysts-only

# 指定配置
.venv/bin/python3 orchestrator.py --ticker YINN --config config.json
```

## 前置条件

- Python 3.9+
- [Claude Code CLI](https://claude.ai/claude-code) (`claude -p`)

## 文件结构

```
├── orchestrator.py          # 核心编排器
├── config.json              # 配置 (标的、辩论轮数、模型)
├── run_analysis.sh          # Shell 入口
├── data/
│   ├── fetcher.py           # yfinance 数据获取
│   ├── indicators.py        # stockstats 技术指标
│   └── formatter.py         # 数据格式化
├── prompts/                 # 12 个角色的 system prompt
├── memory/
│   └── bm25_search.py       # BM25 记忆检索
├── reflect.py               # 交易后复盘
└── results/                 # 运行结果 (gitignored)
```

## vs 原版 TradingAgents

| | 原版 | 本项目 |
|---|---|---|
| 编排 | LangGraph StateGraph | Python subprocess |
| LLM | OpenAI/Anthropic/Google (LangChain) | Claude Code CLI |
| 数据获取 | LLM tool-calling 循环 | 预取全部数据 |
| 每次调用数 | ~21 | **12** |
| 依赖 | LangGraph + LangChain + 多 SDK | yfinance + stockstats + rank-bm25 |

## 交易后复盘

```bash
.venv/bin/python3 reflect.py \
  --state results/LI/2026-03-26_state.json \
  --outcome "持有LI，价格从18.08涨至20.50，收益+13.4%"
```

复盘结果存入 BM25 记忆，下次分析同标的时自动检索历史经验教训。

## License

MIT

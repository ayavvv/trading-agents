# TradingAgents for Claude Code

多智能体交易决策框架 — 基于 [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) 架构，移植为 Claude Code 原生实现。

## 架构

用仓库内 `prompts/deep-analysis.md` 作为权威流程模板，结合 `claude -p` 和确定性 `prepare` / `persist` 辅助脚本完成 12 个专业角色协作的深度分析：

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

# 完整分析（脚本入口）
./run_analysis.sh LI

# 预处理（生成 manifest / inputs / memories）
.venv/bin/python3 orchestrator.py prepare --ticker LI --config config.json

# 持久化 Claude 产出的 final_state.json
.venv/bin/python3 orchestrator.py persist --manifest results/LI/runs/<run_id>/manifest.json --state-json results/LI/runs/<run_id>/final_state.json
```

## 前置条件

- Python 3.9+
- [Claude Code CLI](https://claude.ai/claude-code) (`claude -p`)

## 文件结构

```
├── orchestrator.py          # prepare / persist 确定性辅助脚本
├── config.json              # 配置 (标的、辩论轮数、模型)
├── run_analysis.sh          # Shell 入口（读取仓库内 deep-analysis 模板）
├── data/
│   ├── fetcher.py           # yfinance 数据获取
│   ├── indicators.py        # stockstats 技术指标
│   └── formatter.py         # 数据格式化
├── prompts/                 # 12 个角色 prompt + deep-analysis 权威模板
├── memory/
│   └── bm25_search.py       # BM25 记忆检索
├── reflect.py               # 交易后复盘
└── results/                 # 运行结果 (gitignored)
```

## vs 原版 TradingAgents

| | 原版 | 本项目 |
|---|---|---|
| 编排 | LangGraph StateGraph | Claude Code 原生多 agent + prepare/persist |
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

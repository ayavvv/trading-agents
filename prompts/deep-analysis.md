深度分析股票 $ARGUMENTS，使用 Claude Code 原生多 agent 能力完成全流程，不要使用项目自身的 Python/subprocess 多 agent 编排。

## 总原则

- **Claude Code 是唯一编排层**：并行分析师、并行风控、顺序辩论都由你通过 Agent tool 完成。
- **Python 只做确定性辅助**：数据预取、输入 bundle、BM25 记忆、结果落盘。
- **不要调用** `orchestrator.py` 里旧的多 agent 运行逻辑；只允许使用它的 `prepare` / `persist` 子命令。
- 所有子 agent 都注明：**纯研究任务，只输出报告，不要写入任何文件。**
- 除非用户明确要求，否则最终只展示投组经理最终决策，并简要说明结果文件保存位置。

## Phase 0: 预处理 + 读取运行清单

1. 先用 Bash 运行：
```bash
cd ~/.openclaw/workspace/trading-agents && .venv/bin/python3 orchestrator.py prepare --ticker "$ARGUMENTS" --config config.json
```

2. 从命令输出中拿到 `manifest.json` 路径。

3. 读取以下内容：
- `manifest.json`
- `manifest.paths.inputs.market`
- `manifest.paths.inputs.sentiment`
- `manifest.paths.inputs.news`
- `manifest.paths.inputs.fundamentals`
- `manifest.paths.positions`
- `manifest.paths.memories.bull`
- `manifest.paths.memories.bear`
- `manifest.paths.memories.trader`
- `manifest.paths.memories.judge`
- `manifest.paths.memories.portfolio`

4. 从 `manifest.config` 读取并严格遵循这些运行参数：
- `analyst_model`：4 个分析师、多头研究员、空头研究员、交易员、风控 agent 默认使用该模型；若缺失则用 `sonnet`
- `deep_think_model`：研究经理、投组经理默认使用该模型；若缺失则用 `opus`
- `max_debate_rounds`：多空辩论轮数；若缺失则按 1 轮执行
- `max_risk_discuss_rounds`：风控讨论轮数；若缺失则按 1 轮执行

5. 还要读取角色 prompt 文件，尽量沿用本地既有角色卡：
- `~/.openclaw/workspace/trading-agents/prompts/market_analyst.txt`
- `~/.openclaw/workspace/trading-agents/prompts/sentiment_analyst.txt`
- `~/.openclaw/workspace/trading-agents/prompts/news_analyst.txt`
- `~/.openclaw/workspace/trading-agents/prompts/fundamentals_analyst.txt`
- `~/.openclaw/workspace/trading-agents/prompts/bull_researcher.txt`
- `~/.openclaw/workspace/trading-agents/prompts/bear_researcher.txt`
- `~/.openclaw/workspace/trading-agents/prompts/research_manager.txt`
- `~/.openclaw/workspace/trading-agents/prompts/trader.txt`
- `~/.openclaw/workspace/trading-agents/prompts/aggressive_debater.txt`
- `~/.openclaw/workspace/trading-agents/prompts/conservative_debater.txt`
- `~/.openclaw/workspace/trading-agents/prompts/neutral_debater.txt`
- `~/.openclaw/workspace/trading-agents/prompts/portfolio_manager.txt`

## Phase 1: 4 个分析师并行

用 **并行 Agent** 启动 4 个分析师。每个 agent：
- 读取对应 prompt 文件和对应 input bundle
- 模型优先使用 `manifest.config.analyst_model`；若缺失则用 `sonnet`
- 严格按角色定位输出中文报告
- 这是纯研究任务，只返回最终报告，不要写文件

角色映射：
1. 市场/技术分析师 → `market_analyst.txt` + `manifest.paths.inputs.market`
2. 舆情/情绪分析师 → `sentiment_analyst.txt` + `manifest.paths.inputs.sentiment`
3. 新闻/宏观分析师 → `news_analyst.txt` + `manifest.paths.inputs.news`
4. 基本面分析师 → `fundamentals_analyst.txt` + `manifest.paths.inputs.fundamentals`

收齐后，整理出一份 **分析师摘要**，只提炼：
- 关键数据
- 明确结论
- 主要风险
- 重要价位/触发条件

不要把四篇全文原样塞给下游 agent。

## Phase 2: 多空研究辩论（顺序）

按 `manifest.config.max_debate_rounds` 执行多空辩论；若缺失则按 1 轮执行。每一轮都按以下顺序：

1. **多头研究员**
   - 使用 `bull_researcher.txt`
   - 模型优先使用 `manifest.config.analyst_model`；若缺失则用 `sonnet`
   - 输入：分析师摘要 + 历史多空辩论上下文（若有） + `manifest.paths.memories.bull`
   - 输出：鲜明的看多论证，引用数据，主动反驳潜在空头观点

2. **空头研究员**
   - 使用 `bear_researcher.txt`
   - 模型优先使用 `manifest.config.analyst_model`；若缺失则用 `sonnet`
   - 输入：分析师摘要 + 当前轮多头论点 + 历史多空辩论上下文（若有） + `manifest.paths.memories.bear`
   - 输出：逐条反驳多头，指出脆弱假设与过度乐观之处

完成全部轮次后，再启动：

3. **研究经理**
   - 使用 `research_manager.txt`
   - 模型：优先使用 `manifest.config.deep_think_model`；若缺失则用 `opus`
   - 输入：分析师摘要 + 全部多头论点 + 全部空头论点 + `manifest.paths.memories.judge`
   - 输出：明确的 Buy / Sell / Hold 结论，以及具体投资计划（入场、仓位、止损、止盈、时间框架）

## Phase 3: 交易员提案（顺序）

启动 **交易员** agent：
- 使用 `trader.txt`
- 模型优先使用 `manifest.config.analyst_model`；若缺失则用 `sonnet`
- 输入：分析师摘要 + 研究经理投资计划 + 当前持仓 + `manifest.paths.memories.trader`
- 输出：具体交易提案，含执行细节、仓位、止损止盈、风险回报比、触发条件
- 末尾必须包含：`最终交易提案: BUY/HOLD/SELL`

## Phase 4: 风控讨论 + 投组经理裁决

按 `manifest.config.max_risk_discuss_rounds` 执行风控讨论；若缺失则按 1 轮执行。每一轮都：

1. 用 **并行 Agent** 同时启动：
   - 激进派 → `aggressive_debater.txt`
   - 保守派 → `conservative_debater.txt`
   - 中立派 → `neutral_debater.txt`

   输入统一为：分析师摘要 + 研究经理投资计划 + 交易员提案 + 当前持仓 + 历史风控观点（若有）。

   约束：
   - 模型优先使用 `manifest.config.analyst_model`；若缺失则用 `sonnet`
   - 中文
   - 每个风控观点尽量控制在 500 字以内
   - 只返回最终观点，不写文件

完成全部轮次后，再启动：

2. **投组经理**
   - 使用 `portfolio_manager.txt`
   - 模型：优先使用 `manifest.config.deep_think_model`；若缺失则用 `opus`
   - 输入：分析师摘要 + 研究经理投资计划 + 交易员提案 + 全部风控观点 + `manifest.paths.memories.portfolio`
   - 输出格式必须包含：
     - **评级**：Buy / Overweight / Hold / Underweight / Sell
     - **执行摘要**：表格形式（仓位、止损、目标价、时间框架、强制退出条件）
     - **投资论题**：综合裁决理由，引用各方论点

## Phase 5: 写结构化 state 并落盘

整理出一个 JSON 对象，至少包含这些字段；不要省略空字段，也不要用 `null` 代替必填内容：

```json
{
  "reports": {
    "market": "...",
    "sentiment": "...",
    "news": "...",
    "fundamentals": "..."
  },
  "analyst_summary": "...",
  "debate_history": [
    "**多头研究员**: ...",
    "**空头研究员**: ..."
  ],
  "investment_plan": "...",
  "trade_proposal": "...",
  "risk_history": [
    "**激进派**: ...",
    "**保守派**: ...",
    "**中立派**: ..."
  ],
  "final_decision": "..."
}
```

然后：
1. 写入前自检：`reports.market`、`reports.sentiment`、`reports.news`、`reports.fundamentals`、`analyst_summary`、`investment_plan`、`trade_proposal`、`risk_history`、`final_decision` 都必须非空
2. 把 JSON 写到 `manifest.paths.scratch_state`
3. 用 Bash 运行：
```bash
cd ~/.openclaw/workspace/trading-agents && .venv/bin/python3 orchestrator.py persist --manifest "<manifest_path>" --state-json "<manifest.paths.scratch_state>"
```

## 最终输出

- 主要向用户展示 **投组经理最终决策**。
- 另外简短补一句：结果已保存到 `manifest.paths.output_state` 和 `manifest.paths.output_decision`。
- 不要把全部中间报告一次性倒给用户，除非用户明确要求展开。

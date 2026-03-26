#!/usr/bin/env python3
"""BM25 金融情景记忆系统 — 移植自 TradingAgents 的 FinancialSituationMemory。"""
import json
import os
import re


class FinancialMemory:
    """基于 BM25 的金融情景记忆检索。

    存储格式: JSON 数组，每个元素 {"situation": "...", "reflection": "..."}
    检索方式: BM25Okapi 词法匹配，无需 embedding API
    """

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.entries = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.entries = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.entries = []

    def _tokenize(self, text: str) -> list:
        """简单分词：小写化 + 提取单词。"""
        return re.findall(r'\b\w+\b', text.lower())

    def search(self, query: str, top_k: int = 2) -> list:
        """检索最相似的历史情景。

        Returns:
            list of dict: [{"situation": ..., "reflection": ..., "score": ...}]
        """
        if not self.entries:
            return []

        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            return []

        corpus = [e["situation"] for e in self.entries]
        tokenized_corpus = [self._tokenize(doc) for doc in corpus]

        if not any(tokenized_corpus):
            return []

        bm25 = BM25Okapi(tokenized_corpus)
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        scores = bm25.get_scores(query_tokens)

        # 按分数降序排列，取 top_k
        ranked = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )[:top_k]

        results = []
        for idx in ranked:
            if scores[idx] > 0:
                results.append({
                    "situation": self.entries[idx]["situation"],
                    "reflection": self.entries[idx]["reflection"],
                    "score": round(float(scores[idx]), 4),
                })

        return results

    def add(self, situation: str, reflection: str):
        """添加新的经验记录。"""
        self.entries.append({
            "situation": situation,
            "reflection": reflection,
        })
        self._save()

    def _save(self):
        """持久化到 JSON 文件。"""
        os.makedirs(os.path.dirname(self.filepath) or ".", exist_ok=True)
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def size(self) -> int:
        return len(self.entries)

    def prune(self, max_entries: int = 500):
        """保留最新的 max_entries 条记录。"""
        if len(self.entries) > max_entries:
            self.entries = self.entries[-max_entries:]
            self._save()


if __name__ == "__main__":
    # 测试
    import tempfile
    path = tempfile.mktemp(suffix=".json")
    mem = FinancialMemory(path)

    # 添加示例记忆
    mem.add(
        "LI stock RSI oversold at 28, MACD bearish crossover, price below 200 SMA",
        "Bought too early on RSI oversold signal. Should have waited for MACD confirmation."
    )
    mem.add(
        "TSLA high P/E ratio, strong revenue growth, EV market expanding",
        "Growth stocks can sustain high valuations in bull markets. Don't short on valuation alone."
    )
    mem.add(
        "SPY at all time high, VIX below 15, market breadth narrowing",
        "Low VIX with narrowing breadth often precedes correction. Reduce position size."
    )

    print(f"Memory size: {mem.size()}")

    # 检索
    results = mem.search("LI stock RSI is 54, close to 200 SMA resistance", top_k=2)
    print(f"\nSearch results ({len(results)}):")
    for r in results:
        print(f"  Score: {r['score']}")
        print(f"  Situation: {r['situation'][:80]}")
        print(f"  Reflection: {r['reflection'][:80]}")
        print()

    os.unlink(path)
    print("Test passed!")

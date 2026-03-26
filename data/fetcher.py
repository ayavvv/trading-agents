#!/usr/bin/env python3
"""从 yfinance 预取股票全部数据，返回结构化数据包。"""
import sys
import json
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

from data.indicators import calculate_indicators


def fetch_stock_data(symbol: str, lookback_days: int = 30) -> pd.DataFrame:
    """获取 OHLCV 数据。"""
    ticker = yf.Ticker(symbol)
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    df = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    return df


def fetch_fundamentals(symbol: str) -> dict:
    """获取公司基本面信息。"""
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    # 提取关键财务指标
    keys = [
        "shortName", "sector", "industry", "marketCap", "enterpriseValue",
        "trailingPE", "forwardPE", "priceToBook", "priceToSalesTrailing12Months",
        "profitMargins", "operatingMargins", "grossMargins",
        "returnOnAssets", "returnOnEquity", "revenueGrowth", "earningsGrowth",
        "totalRevenue", "totalDebt", "totalCash", "freeCashflow",
        "dividendYield", "beta", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
        "fiftyDayAverage", "twoHundredDayAverage",
        "targetMeanPrice", "recommendationKey", "numberOfAnalystOpinions",
    ]
    return {k: info.get(k) for k in keys if info.get(k) is not None}


def fetch_financial_statements(symbol: str) -> dict:
    """获取三大财务报表（最近4个季度）。"""
    ticker = yf.Ticker(symbol)
    result = {}
    try:
        bs = ticker.quarterly_balance_sheet
        if bs is not None and not bs.empty:
            result["balance_sheet"] = bs.iloc[:, :4].to_string()
    except Exception:
        result["balance_sheet"] = "N/A"

    try:
        cf = ticker.quarterly_cashflow
        if cf is not None and not cf.empty:
            result["cashflow"] = cf.iloc[:, :4].to_string()
    except Exception:
        result["cashflow"] = "N/A"

    try:
        inc = ticker.quarterly_income_stmt
        if inc is not None and not inc.empty:
            result["income_statement"] = inc.iloc[:, :4].to_string()
    except Exception:
        result["income_statement"] = "N/A"

    return result


def fetch_news(symbol: str, max_items: int = 15) -> list:
    """获取近期新闻。"""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news or []
    except Exception as e:
        print(f"  [警告] 新闻获取失败: {e}", file=sys.stderr)
        return []
    results = []
    for item in news[:max_items]:
        entry = {}
        if "title" in item:
            entry["title"] = item["title"]
        elif "content" in item and isinstance(item["content"], dict):
            entry["title"] = item["content"].get("title", "")
        if "link" in item:
            entry["link"] = item["link"]
        if "publisher" in item:
            entry["publisher"] = item["publisher"]
        elif "content" in item and isinstance(item["content"], dict):
            provider = item["content"].get("provider", {})
            entry["publisher"] = provider.get("displayName", "")
        if "providerPublishTime" in item:
            entry["date"] = datetime.fromtimestamp(item["providerPublishTime"]).strftime("%Y-%m-%d")
        elif "content" in item and isinstance(item["content"], dict):
            entry["date"] = item["content"].get("pubDate", "")[:10]
        if entry.get("title"):
            results.append(entry)
    return results


def fetch_insider_transactions(symbol: str) -> str:
    """获取内幕交易记录。"""
    try:
        ticker = yf.Ticker(symbol)
        insider = ticker.insider_transactions
        if insider is not None and not insider.empty:
            return insider.head(10).to_string()
    except Exception:
        pass
    return "N/A"


def build_data_package(symbol: str, config: dict) -> dict:
    """构建完整数据包，供分析师使用。"""
    lookback = config.get("data_lookback_days", 30)
    indicator_list = config.get("indicators", [
        "rsi_14", "macd", "macdh", "macds",
        "close_20_sma", "close_50_sma", "close_200_sma",
        "boll_ub", "boll_lb",
    ])

    print(f"[数据层] 正在获取 {symbol} 数据...", file=sys.stderr)

    ohlcv = fetch_stock_data(symbol, lookback)
    indicators = calculate_indicators(symbol, indicator_list)
    fundamentals = fetch_fundamentals(symbol)
    statements = fetch_financial_statements(symbol)
    news = fetch_news(symbol)
    insider = fetch_insider_transactions(symbol)

    package = {
        "symbol": symbol,
        "fetch_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "ohlcv": ohlcv.to_csv() if not ohlcv.empty else "N/A",
        "indicators": indicators,
        "fundamentals": fundamentals,
        "financial_statements": statements,
        "news": news,
        "insider_transactions": insider,
    }

    print(f"[数据层] {symbol} 数据获取完成: OHLCV {len(ohlcv)}条, 新闻 {len(news)}条", file=sys.stderr)
    return package


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "LI"
    config = {}
    pkg = build_data_package(symbol, config)
    # 输出摘要
    print(f"=== {pkg['symbol']} 数据包 ({pkg['fetch_date']}) ===")
    print(f"OHLCV 行数: {pkg['ohlcv'].count(chr(10))}")
    print(f"技术指标: {json.dumps(pkg['indicators'], indent=2)}")
    print(f"基本面字段: {list(pkg['fundamentals'].keys())}")
    print(f"财报: {list(pkg['financial_statements'].keys())}")
    print(f"新闻条数: {len(pkg['news'])}")
    print(f"内幕交易: {'有' if pkg['insider_transactions'] != 'N/A' else '无'}")

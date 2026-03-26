#!/usr/bin/env python3
"""使用 stockstats 计算技术指标。"""
import sys
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
from stockstats import wrap


def calculate_indicators(symbol: str, indicator_list: list, lookback_years: int = 2) -> dict:
    """计算指定技术指标的最新值。

    Args:
        symbol: 股票代码
        indicator_list: stockstats 指标名称列表，如 ["rsi_14", "macd", "close_50_sma"]
        lookback_years: 获取历史数据的年数（需要足够长以计算长周期均线）

    Returns:
        dict: {指标名: 最新值}
    """
    end = datetime.now()
    start = end - timedelta(days=lookback_years * 365)

    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"))
    except Exception as e:
        return {ind: f"Error: {e}" for ind in indicator_list}

    if df.empty:
        return {ind: "N/A" for ind in indicator_list}

    # stockstats 需要小写列名
    df.columns = [c.lower() for c in df.columns]
    df = df.reset_index()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    elif "Date" in df.columns:
        df["date"] = pd.to_datetime(df["Date"])

    stock_df = wrap(df)

    results = {}
    for indicator in indicator_list:
        try:
            series = stock_df[indicator]
            val = series.iloc[-1]
            if pd.isna(val):
                results[indicator] = "N/A"
            else:
                results[indicator] = round(float(val), 4)
        except Exception:
            results[indicator] = "N/A"

    return results


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "LI"
    indicators = [
        "rsi_14", "macd", "macdh", "macds",
        "close_20_sma", "close_50_sma", "close_200_sma",
        "boll_ub", "boll_lb", "atr_14",
    ]
    result = calculate_indicators(symbol, indicators)
    for k, v in result.items():
        print(f"  {k}: {v}")

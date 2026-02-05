import os
import pandas as pd
from typing import List
from datetime import datetime, timedelta
import utils.config as config


def check_stock_against_benchmark(
    df_stock: pd.DataFrame,
    symbol: str,
    df_benchmark: pd.DataFrame,
    day: int = 5,
    date_col: str = 'trade_date'
) -> None:
    """
    以基准股票的 trade_date 作为交易日历，检查目标股票最近day个交易日是否连续。
    
    参数：
        df_stock: 目标股票的 DataFrame
        symbol: 目标股票代码（用于输出）
        df_benchmark: 基准股票的 DataFrame（视为完整交易日历）
        date_col: 日期列名，默认 'trade_date'
    """
    # 统一转为 datetime 并排序
    df_stock = df_stock.copy()
    df_benchmark = df_benchmark.copy()
    
    df_stock[date_col] = pd.to_datetime(df_stock[date_col])
    df_benchmark[date_col] = pd.to_datetime(df_benchmark[date_col])
    
    df_stock = df_stock.sort_values(date_col).reset_index(drop=True)
    df_benchmark = df_benchmark.sort_values(date_col).reset_index(drop=True)

    # 构建基准交易日历（去重、升序）
    calendar = df_benchmark[date_col].drop_duplicates().reset_index(drop=True)

    if len(df_stock) < day:
        print(f"股票 {symbol} 数据不足 {day} 条")
        return

    # 取目标股票最后day个日期
    last_day = df_stock[date_col].iloc[-day:].reset_index(drop=True)
    latest_date = last_day.iloc[-1]

    # 检查最新日期是否在基准日历中
    if latest_date not in calendar.values:
        print(f"股票 {symbol} 的最新日期 {latest_date.strftime('%Y-%m-%d')} 不在基准交易日历中")
        return

    # 找到 latest_date 在基准日历中的索引
    idx = calendar[calendar == latest_date].index[0]
    if idx < day - 1:
        print(f"股票 {symbol}：基准日历中无法向前回溯day个交易日（当前仅到索引 {idx}）")
        return

    # 获取基准日历中应有的最后day个交易日
    expected_day = calendar.iloc[idx - (day - 1) : idx + 1].reset_index(drop=True)  # 共day天

    # 转为集合比较
    set_actual = set(last_day)
    set_expected = set(expected_day)

    if set_actual != set_expected:
        missing = sorted(set_expected - set_actual)
        extra = sorted(set_actual - set_expected)
        messages = []
        if missing:
            messages.append(f"缺失: {[d.strftime('%Y-%m-%d') for d in missing]}")
        if extra:
            messages.append(f"多余: {[d.strftime('%Y-%m-%d') for d in extra]}")
        print(f"股票 {symbol}：" + "; ".join(messages))


def load_market(code, mtype):
    """读取数据（如存在）"""
    path = config.default_data_path(code, mtype)
    if os.path.exists(path):
        return pd.read_csv(
            path,
            parse_dates=["trade_date"],
        )
    return pd.DataFrame()

def run(df_benchmark, code, mtype):
    """执行完整流程"""
    df_stock = load_market(code, mtype)
    check_stock_against_benchmark(df_stock, code, df_benchmark, 15)

df_benchmark = load_market("000001", "1")
stock_codes = config.get_codes_from_local()
for code in stock_codes:
    run(df_benchmark, code, "1")

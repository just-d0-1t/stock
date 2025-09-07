#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: update_and_plot.py
@author: vanilla
@date: 2025-09-07
@desc: 更新指定股票数据。
"""

import argparse
import os
import pandas as pd
from datetime import datetime, timedelta
import mplfinance as mpf
from stock_analyzer import StockAnalyzer  # 你之前实现的类
from plot import plot_kline


WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")


def update_stock_data(stock_code, start_date, data_path=None):
    today = datetime.today().date()
#    today = datetime.strptime("2025-09-05", "%Y-%m-%d").date()

    if data_path is None:
        data_path = f"{WORK_DIR}/data/{stock_code}_data.csv"

    if not os.path.exists(data_path):
        # 历史文件不存在 → 默认取一年数据
        if start_date is None:
            start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        analyzer = StockAnalyzer(stock_code, start_date, data_path)
        df = analyzer.run()
    else:
        # 历史文件存在 → 检查是否需要更新
        history = pd.read_csv(
            data_path,
            parse_dates=["trade_date"],
            dtype={"stock_code": str}  # ⭐ 保证股票代码是字符串
        )
        history.sort_values("trade_date", inplace=True)
        last_date = history["trade_date"].iloc[-1].date()

        if last_date >= today:
            # 已有今天 → 删除后更新今天
            # history = history[history["trade_date"].dt.date < today]
            # history.to_csv(data_path, index=False)
            start_date = today.strftime("%Y-%m-%d")
            analyzer = StockAnalyzer(stock_code, start_date, data_path)
            df = analyzer.run()
        else:
            # 有缺口 → 从最后日期的下一天开始追加
            start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            analyzer = StockAnalyzer(stock_code, start_date, data_path)
            df = analyzer.run()

    return df


def update_and_plot(stock_code, date, data_path=None):
    """模块化函数：更新数据并绘制图表"""
    df = update_stock_data(stock_code, date, data_path)

    # 绘制近3月、半年、一年图表
    plot_kline(df, stock_code, 90)
    plot_kline(df, stock_code, 180)
    plot_kline(df, stock_code, 365)

    return df


# 支持命令行直接调用
if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='下载股票数据')

    # 添加命令行参数
    parser.add_argument('-c', '--code', required=True,
                        help='股票代码，例如: 000001.SZ')
    parser.add_argument('-d', '--date',
                        help='日期，格式: YYYY-MM-DD，默认为今天')
    parser.add_argument('-p', '--path',
                        help='数据文件保存位置，默认为./stock_data.csv')

    # 解析参数
    args = parser.parse_args()
    code = args.code
    date = args.date
    path = args.path
    update_and_plot(code, date, path)

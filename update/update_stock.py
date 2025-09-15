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
import utils.config as config
import pandas as pd
from datetime import datetime, timedelta
import mplfinance as mpf
from update.fetch_stock_data import StockAnalyzer  # 你之前实现的类


def update(stock_code, start_date, end_date=None, data_path=None, ktype=1):
    today = datetime.today().date()
#    today = datetime.strptime("2025-09-05", "%Y-%m-%d").date()

    if data_path is None:
        data_path = config.default_data_path(stock_code, ktype)

    if not os.path.exists(data_path):
        # 历史文件不存在 → 默认取两年数据
        if start_date is None:
            start_date = (today - timedelta(days=730)).strftime("%Y-%m-%d")
        analyzer = StockAnalyzer(stock_code, start_date, end_date, data_path, ktype)
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

        days = 0
        # 周线更新近7天数据
        if ktype == 2:
            days = 7
        if ktype == 3:
            days = 31
        if start_date is None:
            start_date = (last_date - timedelta(days=days)).strftime("%Y-%m-%d")
        analyzer = StockAnalyzer(stock_code, start_date, end_date, data_path, ktype)
        df = analyzer.run()

    return df


# 支持命令行直接调用
if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='下载股票数据')

    # 添加命令行参数
    parser.add_argument('-c', '--code', required=True,
                        help='股票代码，例如: 000001.SZ')
    parser.add_argument('-s', '--start_date',
                        help='开始日期，格式: YYYY-MM-DD，默认为今天')
    parser.add_argument('-e', '--end_date',
                        help='结束日期，格式: YYYY-MM-DD，默认为今天')
    parser.add_argument('-p', '--path',
                        help='数据文件保存位置，默认为./stock_ktype_data.csv')
    parser.add_argument('-k', '--ktype',
                        type=int,
                        default=1,
                        help='k线类型')

    # 解析参数
    args = parser.parse_args()
    code = args.code
    start_date = args.start_date
    end_date = args.end_date
    path = args.path
    ktype = args.ktype
    update(code, start_date, end_date, path, ktype)

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
from update.fetch_market import MarketAnalyzer


def update(code, start_date, end_date=None, data_path=None, typ=1, fetch_from="local"):
    today = datetime.today().date()

    if data_path is None:
        data_path = config.default_data_path(code, typ)

    if not os.path.exists(data_path):
        # 历史文件不存在 → 默认取五年数据
        print(data_path)
        if start_date is None:
            start_date = (today - timedelta(days=1825)).strftime("%Y-%m-%d")
        # 之前没有历史数据，需要从远程获取（ths 已显式指定则保留）
        if fetch_from == "local":
            fetch_from = "remote"
    else:
        # 历史文件存在 → 从最后一天起增量拉取
        history = pd.read_csv(data_path, parse_dates=["trade_date"])
        last_date = history["trade_date"].max()
        if start_date is None:
            start_date = last_date.strftime("%Y-%m-%d")

    analyzer = MarketAnalyzer(code, start_date, end_date, data_path, typ, fetch_from)
    return analyzer.run()


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
                        help='数据文件保存位置，默认为./stock_type_data.csv')
    parser.add_argument('-t', '--typ',
                        type=int,
                        default=1,
                        help='代码类型 1:股票 2:指数 3.基金')
    parser.add_argument('-f', '--fetch_from', default="local",
                        help='数据源，remote|ths|local（见 update/sources 注册表）')

    # 解析参数
    args = parser.parse_args()
    code = args.code
    start_date = args.start_date
    end_date = args.end_date
    path = args.path
    typ = args.typ
    fetch_from = args.fetch_from
    update(code, start_date, end_date, path, typ, fetch_from)

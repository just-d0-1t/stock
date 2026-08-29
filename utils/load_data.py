#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
读取单只股票的行情数据（不涉及个股 info 信息）。

市值/成交额等个股信息过滤已前移到 predict 之前的阶段
（见 filter/info_filter.py），predict 链路不再依赖 *_info.csv。
"""

import os
import pandas as pd
import utils.config as config


def load_stock_data(code, path, typ=1):
    """读取行情数据文件，返回 {"code": code, "records": df}；文件缺失或数据不足返回 None"""
    data_file = config.default_data_path(code, typ)
    if path:
        data_file = path

    if not os.path.exists(data_file):
        return None

    df_data = pd.read_csv(data_file, parse_dates=["trade_date"])
    df_data = df_data.sort_values("trade_date").reset_index(drop=True)

    if len(df_data) < 2:
        return None  # 数据不足两天

    return {
        "code": code,
        "records": df_data,
    }
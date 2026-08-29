#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
加载行情数据并按 end_date 截取。

注意：市值/成交额等个股信息过滤已前移到 predict 之前的阶段
（见 filter/info_filter.py），此处只负责行情数据本身。
"""

import pandas as pd
from utils.load_data import load_stock_data


def load_stock(code, path, end_date, typ=1):
    """加载行情数据，截取到指定日期（含）。

    :return: (True, {"code": code, "records": df}) 或 (False, 失败原因)
    """
    stock = load_stock_data(code, path, typ)
    if stock is None:
        return False, "股票数据无法加载"

    records = stock["records"]

    # 截取到指定 end_date 的数据
    try:
        if end_date and isinstance(end_date, str):
            end_date = pd.to_datetime(end_date).date()
            records = records[records["trade_date"].dt.date <= end_date]
            if records.empty:
                return False, f"没有找到 {end_date} 及以前的交易数据"
    except Exception as e:
        return False, f"  加载股票数据出错，无法定位到指定日期: {e}"

    records = records.copy()
    records.sort_values("trade_date", inplace=True)
    stock["records"] = records

    return True, stock
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
加载股票信息，进行初步的条件筛选
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.load_info import load_stock_data


TARGET_MARKET_CAP = 0  # 500亿，单位为元


def reload_data(records, tuning):
    # ✅ 生成副本，避免 SettingWithCopyWarning
    records = records.copy()
    records.sort_values("trade_date", inplace=True)
    return records


"""
加载股票数据
根据市值等条件，过滤掉不满足的股票
对数据进行预处理(股票信息层面)
"""
def load_stock(stock_code, tuning, path, end_date, ktype=1):
    stock = load_stock_data(stock_code, path, ktype)
    if stock is None:
        return False, "股票信息无法加载"

    tuning = tuning.split(",") if tuning else []

    # 条件1：市值大于 500亿
    market = TARGET_MARKET_CAP
    if tuning and len(tuning) > 0:
        market = int(tuning[0])

    if stock["market_cap"] < market:
        return False, f"股票市值小于 {TARGET_MARKET_CAP} 元"

    # ==========================================
    # 🔹 截取到指定 end_date 的数据
    # ==========================================
    records = stock["records"]

    # 将 end_date 转为 datetime.date 对象
    try:
        if end_date and isinstance(end_date, str):
            end_date = pd.to_datetime(end_date).date()
        
            # 过滤：取从最早到 end_date（含） 的记录
            records = records[records["trade_date"].dt.date <= end_date]
    
            if records.empty:
                return False, f"没有找到 {end_date} 及以前的交易数据"
    except Exception as e:
        return False, f"  加载股票数据出错，无法定位到指定日期: {e}"

    records = reload_data(records, tuning)

    # 二次处理数据
    stock["records"] = records

    return True, stock

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: fish_tub.py
@author: vanilla
@date: 2025-09-05
@desc: 股票回测策略脚本，支持多买卖策略组合和调试模式。
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.load_info import load_stock_data


def is_rising(arr):
    """
    判断指标是否转强
    返回: bool
    """
    return arr[-1] == max(arr) and len(set(arr)) > 1

def is_continuous_rising(arr):
    """
    判断数据是否持续上涨
    返回: bool
    """
    # 检查连续递增
    for i in range(1, len(arr)):
        if arr[i] < arr[i-1]:
            return False
    return True


def pretreatment(stock, operate, tuning, debug):
    # ✅ 生成副本，避免 SettingWithCopyWarning
    records = stock["records"]
    records = records.copy()

    # 解析策略参数
    period = 3  # 数据范围: 几天

    # 判断 MA20 斜率是否递增
    def data_processing(idx):
        row = records.iloc[idx]

        if idx >= period - 1:
            if records.iloc[idx]["kdj_signal"] == "golden_cross" or records.iloc[idx-1]["kdj_signal"] == "golden_cross":
                records.loc[idx, "recent_kdj_gold"] = "golden_cross"
            else:
                records.loc[idx, "recent_kdj_gold"] = "no_cross"
        else:
            records.loc[idx, "recent_kdj_gold"] = "no_cross"

        # ===================
        # 60日趋势判断
        # ===================
        if idx >= 59:
            close_60 = records["close"].iloc[idx - 59: idx + 1].values
            # 方案1（线性拟合斜率）
            x = np.arange(len(close_60))
            slope = np.polyfit(x, close_60, 1)[0]
            records.loc[idx, "trend_up_60"] = slope > 0
            # 方案2（简化判断）：末价大于首价
            # records.loc[idx, "trend_up_60"] = close_60[-1] > close_60[0]
        else:
            records.loc[idx, "trend_up_60"] = False

        # 判断 MA20 斜率是否递增
        if idx >= period - 1:
            ma20_recent = records["ma20"].iloc[idx - period + 1: idx + 1].values
            if not np.isnan(ma20_recent).any():
                records.loc[idx, "ma20_rising"] = is_continuous_rising(ma20_recent)

    if operate == "back_test":
        for idx in range(len(records)):
            data_processing(idx)
    if operate == "buy" or operate == "sell":
        data_processing(len(records) - 1)

    stock["records"] = records


# ==========================
# 卖出策略
# ==========================
def buy(r, status, debug=False):
    desc = "策略：KDJ出现金叉"
    if debug: print("[debug] buy_strategy_kdj", r)
    return (
        r["recent_kdj_gold"] == "golden_cross"
    #    and r["ma20_rising"]
        and r["close"] > r["open"]
    #    and r["trend_up_60"]  # ✅ 新增趋势过滤
    ), desc


# ==========================
# 卖出策略
# ==========================
def ma20(r, status, desc, debug=False):
    # if r["ma20_rising"] and r["close"] > r["ma20"]:
    #     return False, ""
    return True, desc

def sell(r, status, debug=False):
    if debug: print("[debug] sell_strategy_4", status["days"], r["trade_date"])
    if r["close"] < r["ma5"]:
    #     return True, "跌破ma5"
        return ma20(r, status, "跌破ma5", debug)
    if ((r["open"] - r["close"]) / r["open"]) > 0.03:
        return True, "单日跌超3%"
    #     return ma20(r, status, "单日跌超3%", debug)
    # if len(status["record"]) == 2 and status["record"][1]["close"] < status["record"][1]["open"]:
    #     return True, "买入第二日即下跌"
    return False, ""

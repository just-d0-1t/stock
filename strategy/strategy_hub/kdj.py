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

            macd_recent = records["MACD"].iloc[idx - period + 1: idx + 1].values
            if not np.isnan(macd_recent).any():
                records.loc[idx, "macd_rising"] = is_rising(macd_recent)
        else:
            records.loc[idx, "recent_kdj_gold"] = "no_cross"
            records.loc[idx, "macd_rising"] = False

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
    desc = "策略：KDJ出现金叉，MACD转强"
    if debug: print("[debug] buy_strategy_kdj", r)
    # cond_macd_pos = r["DIF"] >= 0
    return r["recent_kdj_gold"] == "golden_cross" and r["macd_rising"] and r["close"] > r["open"], desc


# ==========================
# 卖出策略
# ==========================
def sell(r, status, debug=False):
    if debug: print("[debug] sell_strategy_4", status["days"], r["trade_time"])
    if r["close"] < r["ma5"]:
        return True, "跌破ma5"
    if ((r["open"] - r["close"]) / r["open"]) > 0.03:
        return True, "单日跌超3%"
    if len(status["record"]) == 2 and status["record"][1]["close"] < status["record"][1]["open"]:
        return True, "买入第二日即下跌"
    return False, ""

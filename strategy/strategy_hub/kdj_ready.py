#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: fish_tub.py
@author: vanilla
@date: 2025-09-05
@desc: 股票回测策略脚本，支持多买卖策略组合和调试模式。
"""

import os
import numpy as np


def is_slope_increasing(arr):
    """
    判断斜率是否递增（趋势加速）
    """
    slopes = np.diff(arr)  # 相邻天数差分
    return all(slopes[i] >= slopes[i-1] for i in range(1, len(slopes)))


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


# ==========================
# 买入策略
# ==========================
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
            k_recent = records["K"].iloc[idx - period + 1: idx + 1].values
            d_recent = records["D"].iloc[idx - period + 1: idx + 1].values
            if all(x < y for x, y in zip(k_recent, d_recent)):
                kd_recent = [x - y for x, y in zip(k_recent, d_recent)]
                records.loc[idx, "cross_ready"] = is_continuous_rising(kd_recent)
                records.loc[idx, "cross_ready"] = records.loc[idx, "cross_ready"] and k_recent[-1] >= k_recent[-2]
            else:
                records.loc[idx, "cross_ready"] = False

    if operate == "back_test":
        for idx in range(len(records)):
            data_processing(idx)
    if operate == "buy" or operate == "sell":
        data_processing(len(records) - 1)

    stock["records"] = records


"""
KDJ即将出现金叉
"""
def buy(r, status, debug=False):
    desc = "策略：KDJ即将出现金叉"
    if debug: print("[debug] buy_strategy_kdj_ready", r)
    return r["cross_ready"], desc


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

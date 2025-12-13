#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: fish_tub.py
@author: vanilla
@date: 2025-09-05
@desc: 鱼盆模型。
"""

import os
import numpy as np


def is_slope_increasing(arr):
    """
    判断斜率是否递增（趋势加速）
    """
    slopes = np.diff(arr)  # 相邻天数差分
    return all(slopes[i] >= slopes[i-1] for i in range(1, len(slopes)))


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
            ma20_recent = records["ma20"].iloc[idx - period + 1: idx + 1].values
            if not np.isnan(ma20_recent).any():
                records.loc[idx, "ma20_slope_up"] = is_slope_increasing(ma20_recent)
                records.loc[idx, "ma20_rising"] = is_rising(ma20_recent)

    if operate == "back_test":
        for idx in range(len(records)):
            data_processing(idx)
    if operate == "buy" or operate == "sell":
        data_processing(len(records) - 1)

    stock["records"] = records


def buy(r, status, debug=False):
    desc = "策略: 鱼盆模型，超过ma20买入"
    if debug: print("[debug] buy_strategy_ma20", r)
    return r["first_above_ma20"] == "y" and r["close"] > r["open"] and r["ma20_slope_up"], desc

def sell(r, status, debug=False):
    desc = "策略：跌破ma20 卖出"
    if debug: print("[debug] sell_strategy_1", r["trade_date"], r["close"], r["ma20"])
    return r["close"] < r["ma20"], desc

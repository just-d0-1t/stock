#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: hydroplaning.py
@author: vanilla
@date: 2025-09-05
@desc: 水漂模型, 基于鱼盆模型的改进，减少回调区间对收益的影响。
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from .util.load_info import load_stock_data


WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
TARGET_MARKET_CAP = 500e8  # 500亿，单位为元


def is_ma20_slope_increasing(ma20_recent):
    """
    判断 MA 斜率是否递增（趋势加速）
    """
    slopes = np.diff(ma20_recent)  # 相邻天数差分
    return all(slopes[i] >= slopes[i-1] for i in range(1, len(slopes)))


def is_ma20_continuous_rising(ma20_recent):
    """
    判断 MA 最近 period 个交易日是否持续上涨（绝对值递增）
    df: 包含 'ma' 列的 DataFrame，按日期升序排列
    period: 最近多少天
    返回: bool
    """
    # 检查连续递增
    for i in range(1, len(ma20_recent)):
        if ma20_recent[i] < ma20_recent[i-1]:
            return False

    return True


def reload_data(records, tuning):
    records.sort_values("trade_date", inplace=True)

    # 策略调优
    period = 3 # 数据范围: 几天
    if tuning:
        period = int(tuning[0])

    for idx in range(len(records)):
        # 判断涨跌
        row = records.iloc[idx]
        if idx >= 1:
            records.at[idx, "is_raise"] = row["close"] > row["open"]

        # 判断 MA20 斜率是否递增
        if idx >= period - 1:
            ma20_recent = records["ma20"].iloc[idx - period + 1: idx + 1].values
            if not np.isnan(ma20_recent).any():
                records.at[idx, "ma20_slope_up"] = is_ma20_slope_increasing(ma20_recent)
                records.at[idx, "ma20_rising"] = is_ma20_continuous_rising(ma20_recent)

    return records


"""
加载股票数据
根据市值等条件，过滤掉不满足的股票
对数据进行预处理
"""
def load_stock(stock_code, tuning, path):
    stock = load_stock_data(stock_code, path)
    if stock is None:
        return False, "股票信息无法加载"

    tuning = tuning.split(",") if tuning else []

    # 条件1：市值大于 500亿
    market = TARGET_MARKET_CAP
    if tuning and len(tuning) > 1:
        market = int(tuning[1])

    if stock["market_cap"] < market:
        return False, f"股票市值小于 {TARGET_MARKET_CAP} 元"

    # 二次处理数据
    stock["records"] = reload_data(stock["records"], tuning)

    return True, stock


# ==========================
# 买入策略
# ==========================
"""
水漂模型基础买入策略
当前处于鱼盆模型周期，且股价高于ma5
"""
def buy_strategy_1(r, status, debug=False):
    desc = "策略1 : 当前处于鱼盆模型周期，且股价高于ma5" 
    if debug: print("[debug] buy_strategy_1", r, status)
    return "fish_tub" in status and status["fish_tub"] and r["is_raise"] and r["close"] >= r["ma5"], desc


"""
策略2 : 首次超过ma20, 当日涨，斜率为正, 且ma20处于加速上升 
"""
def buy_strategy_2(r, status, debug=False):
    desc = "策略2: 首次超过ma20, 当日涨，斜率为正, 且ma20处于加速上升"
    # 重置状态
    if r['close'] < r['ma20']:
        status["fish_tub"] = False
    if debug: print("[debug] buy_strategy_2", r, status)
    if r["first_above_ma20"] == "y" and r["ma20_rising"] and r["ma20_slope_up"] and r["is_raise"]:
        # 标记鱼盆周期
        status["fish_tub"] = True
        return True, desc

    return False, desc


"""
策略3 : 首次超过ma20, 当日涨，ma20处于加速上升 
"""
def buy_strategy_3(r, status, debug=False):
    desc = "策略3 : 首次超过ma20, 当日涨，ma20处于加速上升"
    if debug: print("[debug] buy_strategy_1", r, status)
    # 重置状态
    if r['close'] < r['ma20']:
        status["fish_tub"] = False
    if r["first_above_ma20"] == "y" and r["ma20_slope_up"] and r["is_raise"]:
        # 标记鱼盆周期
        status["fish_tub"] = True
        return True, desc

    return False, desc


BUY_STRATEGIES = {
    "1": buy_strategy_1,
    "2": buy_strategy_2,
    "3": buy_strategy_3,
}


# ==========================
# 卖出策略
# ==========================
"""
水漂模型基础策略
"""
def sell_strategy_1(r, status, debug=False):
    desc = "策略1: 水漂模型基础策略，当处于鱼盆周期时，若跌破ma5，且ma5斜率远大于ma20的时候，则卖出"
    if debug: print("[debug] sell_strategy_1", r, status)
    recent_record = status["record"]
    if len(status["record"]) >= 5:
        recent_record = status["record"][-5:]
    ma5_slope = recent_record[-1]["ma5"] - recent_record[0]["ma5"]
    ma20_slope = recent_record[-1]["ma20"] - recent_record[0]["ma20"]
    ma5_faster_than_ma20 = ma5_slope / ma20_slope > 2 

    if ma5_faster_than_ma20 and "fish_tub" in status and status["fish_tub"] and r["close"] < r["ma5"]:
        # 如果直接跌穿了ma20，重置状态
        if r['close'] < r['ma20']:
            status["fish_tub"] = False
        return True, desc
    return False, desc


"""
鱼盆卖出策略
"""
def sell_strategy_2(r, status, debug=False):
    desc = "策略2：跌破ma20 卖出"
    if debug: print("[debug] sell_strategy_2", r["trade_time"], r["close"], r["ma20"])
    if r["close"] < r["ma20"]:
        # 退出鱼盆周期
        status["fish_tub"] = False
        return True, desc
    return False, desc


"""
保守型，很不错的策略
"""
def sell_strategy_3(r, status, debug=False):
    desc = "策略3：如果买入五日后, 涨幅过小，卖出，鱼儿未上钩"
    if len(status["record"]) == 5:
        if debug: print("[debug] sell_strategy_3", r["trade_time"], status["record"])
        can_sell = all(day["change_pct"] <= 0.5 for day in status["record"][1:])
        small_gain = (status["record"][-1]["close"] - status["record"][0]["close"]) / status["record"][0]["close"] < 0.01
        if can_sell or small_gain:
            status["fish_tub"] = False
            return True, desc
    return False, desc


"""
中性偏激进型策略
"""
def sell_strategy_4(r, status, debug=False):
    desc = "策略4：如果买入第二日就跌, 卖出，鱼儿未上钩"
    if debug: print("[debug] sell_strategy_4", r["trade_time"], status["record"])
    if len(status["record"]) == 2 and status["record"][1]["close"] < status["record"][1]["open"]:
        status["fish_tub"] = False
        return True, desc
    return False, desc


SELL_STRATEGIES = {
    "1": sell_strategy_1,
    "2": sell_strategy_2,
    "3": sell_strategy_3,
    "4": sell_strategy_4,
}

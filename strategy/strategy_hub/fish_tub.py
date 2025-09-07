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

from .util.load_info import load_stock_data


WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
TARGET_MARKET_CAP = 500e8  # 500亿，单位为元


def is_ma20_slope_increasing(ma20_recent):
    """
    判断 MA20 斜率是否递增（趋势加速）
    """
    slopes = np.diff(ma20_recent)  # 相邻天数差分
    return all(slopes[i] >= slopes[i-1] for i in range(1, len(slopes)))


def is_ma20_continuous_rising(ma20_recent):
    """
    判断 MA20 最近 period 个交易日是否持续上涨（绝对值递增）
    df: 包含 'ma20' 列的 DataFrame，按日期升序排列
    period: 最近多少天
    返回: bool
    """
    # 检查连续递增
    for i in range(1, len(ma20_recent)):
        if ma20_recent[i] <= ma20_recent[i-1]:
            return False
    return True


def first_above_ma20(r):
    """
    判断股价是否超过了ma20
    """
    return r["first_above_ma20"] == "y"


def reload_data(records, tuning):
    records.sort_values("trade_date", inplace=True)

    # 策略调优
    period = 3 # 数据范围: 几天
    if tuning:
        period = int(tuning[0])

    # 判断 MA20 斜率是否递增
    for idx in range(len(records)):
        row = records.iloc[idx]
        if idx >= 1:
            records.at[idx, "is_raise"] = row["close"] > row["open"]

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
        market = tuning[1]

    if stock["market_cap"] < market:
        return False, f"股票市值小于 {TARGET_MARKET_CAP} 元"

    # 二次处理数据
    stock["records"] = reload_data(stock["records"], tuning)

    return True, stock


# ==========================
# 买入策略
# ==========================
"""
策略1比策略3更加激进，ma20斜率未转正时就买入，
具体还要看大盘的走势，底部冲高，或者牛市时，可以大胆买入。
"""
def buy_strategy_1(r, status, debug=False):
    desc = "策略1: 首次超过ma20, 当日涨，且ma20处于加速上升"
    if debug: print("[debug] buy_strategy_1", r)
    return first_above_ma20(r) and r["ma20_slope_up"] and r["is_raise"], desc


def buy_strategy_2(r, status, debug=False):
    desc = "策略2: 首次超过ma20，当日涨"
    if debug: print("[debug] buy_strategy_2", r)
    return first_above_ma20(r) and r["is_raise"], desc


"""
非常稳健的买入策略，
熊市时主要策略
"""
def buy_strategy_3(r, status, debug=False):
    desc = "策略3: 首次超过ma20, 当日涨，斜率为正, 且ma20处于加速上升"
    if debug: print("[debug] buy_strategy_3", r)
    return first_above_ma20(r) and r["ma20_rising"] and r["ma20_slope_up"] and r["is_raise"], desc


BUY_STRATEGIES = {
    "1": buy_strategy_1,
    "2": buy_strategy_2,
    "3": buy_strategy_3,
}


# ==========================
# 卖出策略
# ==========================
"""
基础策略
"""
def sell_strategy_1(r, status, debug=False):
    desc = "策略1：跌破ma20 卖出"
    if debug: print("[debug] sell_strategy_1", r["trade_time"], r["close"], r["ma20"])
    return r["close"] < r["ma20"], desc


def sell_strategy_2(r, status, debug=False):
    desc = "策略2：开始跌就卖出"
    if debug: print("[debug] sell_strategy_2", r["trade_time"], r["close"], r["open"])
    return r["close"] < r["open"], desc


def sell_strategy_3(r, status, debug=False):
    desc = "策略3：收益率达到3%，就卖出"
    if debug: print("[debug] sell_strategy_3", r["trade_time"], r["close"], status["buy"])
    return ((r["close"] - status["buy"]) / status["buy"]) > 0.03, desc


def sell_strategy_4(r, status, debug=False):
    desc = "策略4：持股超过7天，就卖出"
    if debug: print("[debug] sell_strategy_4", status["days"], r["trade_time"])
    return status["days"] >= 7, desc


def sell_strategy_5(r, status, debug=False):
    desc = "策略5：跌幅超过1%，卖出"
    if debug: print("[debug] sell_strategy_5", r["trade_time"], r["close"], r["open"])
    return ((r["open"] - r["close"]) / r["open"]) > 0.01 or r["close"] < r["ma20"], desc


"""
中性偏激进，要具体分析，如果整体收益很小就要尽快撤出
"""
def sell_strategy_6(r, status, debug=False):
    desc = "策略6：跌幅超过2%，卖出"
    if debug: print("[debug] sell_strategy_6", r["trade_time"], r["close"], r["open"])
    return ((r["open"] - r["close"]) / r["open"]) > 0.02, desc


def sell_strategy_7(r, status, debug=False):
    desc = "策略7：大涨5%以上，卖出"
    if debug: print("[debug] sell_strategy_7", r["trade_time"], r["close"], r["open"])
    return ((r["close"] - r["open"]) / r["open"]) > 0.05, desc


"""
保守型，很不错的策略
"""
def sell_strategy_8(r, status, debug=False):
    desc = "策略8：如果买入五日后, 涨幅过小，卖出，鱼儿未上钩"
    if len(status["record"]) == 5:
        if debug: print("[debug] sell_strategy_8", r["trade_time"], status["record"])
        can_sell = all(day["change_pct"] <= 0.5 for day in status["record"][1:])
        small_gain = (status["record"][-1]["close"] - status["record"][0]["close"]) / status["record"][0]["close"] < 0.01
        return can_sell or small_gain, desc
    return False, desc


"""
中性偏激进型策略
"""
def sell_strategy_9(r, status, debug=False):
    desc = "策略9：如果买入第二日就跌, 卖出，鱼儿未上钩"
    if debug: print("[debug] sell_strategy_9", r["trade_time"], status["record"])
    return len(status["record"]) == 2 and status["record"][1]["close"] < status["record"][1]["open"], desc


def sell_strategy_a(r, status, debug=False):
    desc = "策略a：如果连跌三天，卖出，资本跑走了，韭菜废物"
    lst = status["record"]
    if len(lst) > 3:
        for i in range(3, len(lst)):
            if all(lst[j]['close'] <= lst[j]['open'] for j in [i, i-1, i-2]):
                if debug: print("[debug] sell_strategy_a", r["trade_time"])
                return True, desc
    return False, desc


def sell_strategy_b(r, status, debug=False):
    desc = "策略b：4天滑动窗口，如果4天未涨，鱼儿未上钩，或资本跑了，卖出"
    lst = status["record"]
    windows = 4
    if len(lst) > windows:
        for i in range(windows, len(lst)):
            if lst[i]['close'] - lst[i-windows]['open'] < 0.01:
                if debug: print("[debug] sell_strategy_b", r["trade_time"])
                return True, desc
    return False, desc


SELL_STRATEGIES = {
    "1": sell_strategy_1,
    "2": sell_strategy_2,
    "3": sell_strategy_3,
    "4": sell_strategy_4,
    "5": sell_strategy_5,
    "6": sell_strategy_6,
    "7": sell_strategy_7,
    "8": sell_strategy_8,
    "9": sell_strategy_9,
    "a": sell_strategy_a,
    "b": sell_strategy_b,
}

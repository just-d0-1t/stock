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


# ==========================
# 买入策略
# ==========================
import numpy as np
import pandas as pd

# ✅ 解析参数字符串，例如 "prev=5,volumn_amplify=2"
def parse_tuning(tuning_str: str):
    result = {}
    if not tuning_str:
        return result
    for item in tuning_str.split(","):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        v = v.strip()
        # 尝试转成数字
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        result[k.strip()] = v
    return result


def pretreatment(stock, operate, tuning, debug):
    """股票数据预处理，用于策略分析前的数据准备。"""
    records = stock["records"].copy()

    # ✅ 默认参数（支持tuning覆盖）
    tuning = parse_tuning(tuning)
    period = tuning.get("prev", 5)
    volumn_amplify = tuning.get("volumn_amplify", 2)
    volumn_period = tuning.get("volumn_period", 20)
    price_period = tuning.get("price_period", 60)
    volumn_slope = tuning.get("volumn_slope", 0.3)

    # ✅ 预先创建列，避免 SettingWithCopy 警告
    records["price_top3"] = False
    records["volume_breakout"] = False
    records["volume_spike_buy"] = False

    if debug:
        print("period ", period)
        print("volumn_amplify ", volumn_amplify)
        print("volumn_period ", volumn_period)
        print("price_period ", price_period)
        print("volumn_slope ", volumn_slope)

    def data_processing(idx):
        """单条数据处理逻辑"""
        row = records.iloc[idx]

        # === 判断是否为最近 price_period 天内的最高3个收盘价之一 ===
        if idx >= price_period - 1:
            recent_closes = records["close"].iloc[idx - price_period + 1: idx + 1].values
            top3_min = np.sort(recent_closes)[-3] if len(recent_closes) >= 3 else recent_closes.max()
            records.loc[idx, "price_top3"] = row["close"] >= top3_min

        # === 判断成交量突破（放量） ===
        if idx >= volumn_period + 1:
            max_vol = records["volume"].iloc[idx - volumn_period - 1: idx - 1].max() * volumn_amplify
            curr_vol, prev_vol = records["volume"].iloc[idx], records["volume"].iloc[idx - 1]
            cond_volumn_slope = ( abs(curr_vol - prev_vol) / max(curr_vol, prev_vol) ) < volumn_slope
            records.loc[idx, "volume_breakout"] = curr_vol > max_vol and prev_vol > max_vol and cond_volumn_slope

        # === 若未放量，再判断近3日中是否有2日放量 ===
        if not records.loc[idx, "volume_breakout"] and idx >= volumn_period + 2:
            max_vol = records["volume"].iloc[idx - volumn_period - 2: idx - 2].max() * volumn_amplify
            recent3 = records["volume"].iloc[idx - 2: idx + 1].values
            cond_head_tail = (recent3[0] > max_vol and recent3[-1] > max_vol)
            cond_volumn_slope = ( abs(recent3[0] - recent3[1]) / max(recent3[0], recent3[1]) ) < volumn_slope
            records.loc[idx, "volume_breakout"] = cond_head_tail and cond_volumn_slope 

    # ✅ 调度模式：批量 or 单点处理
    if operate == "back_test":
        for idx in range(len(records)):
            data_processing(idx)
    elif operate in ("buy", "sell"):
        data_processing(len(records) - 1)

    stock["records"] = records


def buy(r, status, debug=False):
    """
    策略：成交量连续两天 > 前五天均值 * 2，且前五天波动不大，当日收盘 > 开盘
    依赖字段：records 中已由 reload_data 计算并写入 'volume_spike_buy'
    """
    desc = "策略：放量识别"
    if debug: print("[debug] buy_strategy_volume_spike", r)
    # r 可能是 pandas Series，使用 get 以防 KeyError
    # cond_1 = bool(r.get("volume_spike_buy", False))
    cond_1 = r["close"] > r["open"]
    cond_2 = bool(r.get("volume_breakout", False))
    cond_3 = bool(r.get("price_top3", False))
    if debug:
        print(desc, " ", cond_1)
        print(desc, " ", cond_2)
        print(desc, " ", cond_3)
    return cond_1 and cond_2 and cond_3, desc


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

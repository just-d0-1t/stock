#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: volume_pullback.py
@author: vanilla
@date: 2026-08-27
@desc: 放量回缩策略
"""

import numpy as np
import pandas as pd


# ==========================
# 参数解析
# ==========================

def parse_tuning(tuning_str: str):
    """解析参数字符串，例如：volume_period=5,volume_base_period=10,volume_amplify=1.5"""
    result = {}
    if not tuning_str:
        return result

    for item in tuning_str.split(","):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        v = v.strip()
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        result[k.strip()] = v

    return result


def calculate_normalized_slope(series):
    """
    计算归一化线性回归斜率。

    slope = 线性回归斜率 / 序列平均值
    """
    series = pd.Series(series).dropna()
    if len(series) < 2:
        return np.nan

    mean_value = series.mean()
    if mean_value == 0:
        return np.nan

    x = np.arange(len(series))
    y = series.values
    slope = np.polyfit(x, y, 1)[0]

    return slope / mean_value


# ==========================
# 数据预处理
# ==========================

def pretreatment(stock, operate, tuning, debug):
    """股票数据预处理。"""
    records = stock["records"].copy()
    tuning = parse_tuning(tuning)

    ma_period = tuning.get("ma_period", 3)
    volume_period = tuning.get("volume_period", 3)
    volume_base_period = tuning.get("volume_base_period", 7)
    volume_amplify = tuning.get("volume_amplify", 1.7)
    volume_ma5_slope = tuning.get("volume_ma5_slope", 0.01)
    price_ma5_slope = tuning.get("price_ma5_slope", 0.003)
    rise = tuning.get("rise", 0.005)

    # 初始化字段
    records["volume_ma5"] = np.nan
    records["volume_amplify_ratio"] = np.nan
    records["volume_ma5_slope"] = np.nan
    records["price_ma5_slope"] = np.nan

    records["volume_amplify_ok"] = False
    records["volume_ma5_slope_ok"] = False
    records["price_ma5_slope_ok"] = False
    records["yesterday_rise"] = False
    records["volume_shrink"] = False

    if debug:
        print("ma_period:", ma_period)
        print("volume_period:", volume_period)
        print("volume_base_period:", volume_base_period)
        print("volume_amplify:", volume_amplify)
        print("volume_ma5_slope:", volume_ma5_slope)
        print("price_ma5_slope:", price_ma5_slope)
        print("rise:", rise)

    # 计算成交额MA5
    records["volume_ma5"] = records["volume"].rolling(window=ma_period).mean()

    def data_processing(idx):
        """处理单个交易日，当前idx为T，趋势判断不包含当天。"""
        required_days = volume_period + volume_base_period
        if idx < required_days:
            return

        # 最近N天，不含当天：T-N ~ T-1
        recent_volume = records["volume"].iloc[idx - volume_period:idx]

        # 前M天：T-N-M ~ T-N-1
        base_volume = records["volume"].iloc[
            idx - volume_period - volume_base_period:idx - volume_period
        ]

        if len(recent_volume) != volume_period or len(base_volume) != volume_base_period:
            return

        # 1. 最近N天整体放量
        recent_volume_mean = recent_volume.mean()
        base_volume_mean = base_volume.mean()

        if base_volume_mean > 0:
            amplify_ratio = recent_volume_mean / base_volume_mean
            records.loc[records.index[idx], "volume_amplify_ratio"] = amplify_ratio
            records.loc[records.index[idx], "volume_amplify_ok"] = amplify_ratio >= volume_amplify

        # 2. 最近N天成交额MA5斜率
        recent_volume_ma5 = records["volume_ma5"].iloc[idx - volume_period:idx]
        volume_slope = calculate_normalized_slope(recent_volume_ma5)

        if not pd.isna(volume_slope):
            records.loc[records.index[idx], "volume_ma5_slope"] = volume_slope
            records.loc[records.index[idx], "volume_ma5_slope_ok"] = volume_slope >= volume_ma5_slope

        # 3. 最近N天价格MA5斜率
        # 直接使用已有的records["ma5"]
        recent_price_ma5 = records["ma5"].iloc[idx - volume_period:idx]
        price_slope = calculate_normalized_slope(recent_price_ma5)

        if not pd.isna(price_slope):
            records.loc[records.index[idx], "price_ma5_slope"] = price_slope
            records.loc[records.index[idx], "price_ma5_slope_ok"] = price_slope >= price_ma5_slope

        # 4. 昨天必须上涨
        if idx >= 1:
            yesterday = records.iloc[idx - 1]
            records.loc[records.index[idx], "yesterday_rise"] = yesterday["close"] > yesterday["open"]

        # 5. 当天成交额 < 前一天
        if idx >= 1:
            current_volume = records["volume"].iloc[idx]
            previous_volume = records["volume"].iloc[idx - 1]
            records.loc[records.index[idx], "volume_shrink"] = current_volume < previous_volume

    # 调度
    if operate == "back_test":
        for idx in range(len(records)):
            data_processing(idx)
    elif operate in ("buy", "sell"):
        data_processing(len(records) - 1)

    stock["records"] = records


# ==========================
# 买入策略
# ==========================

def buy(r, status, debug=False):
    """
    放量回缩买入策略。

    1. 最近N天整体成交额明显放量；
    2. 最近N天成交额MA5斜率向上；
    3. 最近N天价格MA5斜率向上；
    4. 昨天上涨；
    5. 当天下跌；
    6. 当天成交额小于昨天。
    """
    desc = "策略：放量回缩"

    if debug:
        print("[debug] buy_strategy_volume_pullback")
        print("close:", r["close"])
        print("open:", r["open"])
        print("volume:", r["volume"])
        print("volume_ma5:", r.get("volume_ma5"))
        print("volume_amplify_ratio:", r.get("volume_amplify_ratio"))
        print("volume_ma5_slope:", r.get("volume_ma5_slope"))
        print("price_ma5_slope:", r.get("price_ma5_slope"))

    # 当天下跌
    cond_1 = r["close"] < r["open"]

    # 最近N天整体放量
    cond_2 = bool(r.get("volume_amplify_ok", False))

    # 成交额MA5趋势向上
    cond_3 = bool(r.get("volume_ma5_slope_ok", False))

    # 价格MA5趋势向上
    cond_4 = bool(r.get("price_ma5_slope_ok", False))

    # 昨天上涨
    cond_5 = bool(r.get("yesterday_rise", False))

    # 当天缩量
    cond_6 = bool(r.get("volume_shrink", False))

    if debug:
        print(desc, "当天跌:", cond_1)
        print(desc, "最近N天整体放量:", cond_2)
        print(desc, "成交额MA5趋势向上:", cond_3)
        print(desc, "价格MA5趋势向上:", cond_4)
        print(desc, "昨天上涨:", cond_5)
        print(desc, "当天缩量:", cond_6)

    result = cond_1 and cond_2 and cond_3 and cond_4 and cond_5 and cond_6

    if result:
        return True, desc

    return False, ""


# ==========================
# 卖出策略
# ==========================

def sell(r, status, debug=False):
    """
    买入后的第二个交易日：

    如果盘中最高价相对买入价上涨达到0.5%，则卖出。
    """
    if debug:
        print("[debug] sell_strategy_volume_pullback")
        print("status:", status)
        print("current close:", r["close"])
        print("current high:", r["high"])

    if len(status["record"]) != 2:
        return False, ""

    r0 = status["record"][0]

    rise = (r["high"] - r0["close"]) / r0["close"]

    if rise >= 0.01:
        r["close"] = r0["close"] * 1.01
        return True, "买入第二天上涨达到0.5%，卖出"

    return True, ""

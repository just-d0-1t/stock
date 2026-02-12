#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: long_trend_pullback_reversal.py
@author: vanilla
@desc: 长期趋势回调反转策略
"""

import numpy as np


# ======================================================
# 工具函数
# ======================================================

def calc_slope(arr):
    """
    使用线性回归计算斜率
    """
    if len(arr) < 2 or np.isnan(arr).any():
        return np.nan
    x = np.arange(len(arr))
    k, _ = np.polyfit(x, arr, 1)
    return k


# ======================================================
# 预处理函数
# ======================================================

def pretreatment(stock, operate, tuning=None, debug=False):
    """
    预处理阶段完成所有“计算型条件”，buy 中只判断状态

    tuning 参数示例：
    {
        "ma_diff_ratio_limit": 0.10,     # 条件3：MA20/MA120 距离比例
        "hist_diff_ratio_limit": 0.30    # 条件4：历史最大距离
    }
    """
    records = stock["records"].copy()

    # ---- 参数 ----
    ma_diff_ratio_limit = 0.05
    hist_diff_ratio_limit = 0.20
    pullback_cycle = 60
    if tuning:
        ma_diff_ratio_limit = tuning.get("ma_diff_ratio_limit", ma_diff_ratio_limit)
        hist_diff_ratio_limit = tuning.get("hist_diff_ratio_limit", hist_diff_ratio_limit)

    # ==================================================
    # 1️⃣ 计算 MA120
    # ==================================================
    records["ma120"] = records["close"].rolling(
        window=120, min_periods=120
    ).mean()

    # ==================================================
    # 2️⃣ 计算斜率
    # ==================================================
    for i in range(len(records)):
        # MA120 近100日斜率
        if i >= 120 + pullback_cycle:
            records.loc[i, "ma120_slope_100"] = calc_slope(
                records["ma120"].iloc[i - 99: i + 1].values
            )
        else:
            records.loc[i, "ma120_slope_100"] = np.nan

        # MA20 近30日斜率
        if i >= pullback_cycle:
            records.loc[i, "ma10_slope_cycle"] = calc_slope(
                records["ma10"].iloc[i - pullback_cycle: i + 1].values
            )
        else:
            records.loc[i, "ma10_slope_cycle"] = np.nan

        # MA20 近5日斜率
        if i >= 4:
            records.loc[i, "ma10_slope_5"] = calc_slope(
                records["ma10"].iloc[i - 4: i + 1].values
            )
        else:
            records.loc[i, "ma10_slope_5"] = np.nan

    # ==================================================
    # 3️⃣ 条件3：MA20 / MA120 距离状态（参数化）
    # ==================================================
    records["ma10_ma120_diff"] = records["ma10"] - records["ma120"]
    records["ma10_ma120_diff_ratio"] = (
        records["ma10_ma120_diff"].abs() / records["ma120"]
    )

    # 近3日是否全部收盘价 > MA120
    records["close_above_ma120_3d"] = (
        records["close"] > records["ma120"]
    ).rolling(window=3, min_periods=3).sum() == 3

    records["cond3_ok"] = (
        (records["ma10_ma120_diff_ratio"] < ma_diff_ratio_limit) &
        (
            # MA20 在 MA120 上方
            (records["ma10_ma120_diff"] >= 0) |
            # MA20 在 MA120 下方，但价格已连续3天站上
            (
                (records["ma10_ma120_diff"] < 0) &
                (records["close_above_ma120_3d"])
            )
        )
    )

    # ==================================================
    # 4️⃣ 条件4：历史强势基因（近100日）
    # ==================================================
    records["ma10_ma120_diff_ratio_pos"] = (
        (records["ma10"] - records["ma120"]) / records["ma120"]
    )

    records["hist_strong_flag"] = False

    for i in range(len(records)):
        if i >= 99:
            hist_max = records["ma10_ma120_diff_ratio_pos"].iloc[i - 99: i + 1].max()
            records.loc[i, "hist_strong_flag"] = hist_max >= hist_diff_ratio_limit

    stock["records"] = records


# ======================================================
# 买入策略
# ======================================================

def buy(r, status=None, debug=False):
    """
    长期趋势回调反转策略（判定版）
    """
    desc = "长期趋势回调反转策略"
    idx = r.name

    if idx < 220:
        return False, "数据不足"

    cond1 = r["ma120_slope_100"] > 0
    cond2 = (r["ma10_slope_cycle"] < 0) and (r["ma10_slope_5"] > 0)
    cond3 = bool(r["cond3_ok"])
    cond4 = bool(r["hist_strong_flag"])

    if debug:
        print(
            f"[DEBUG] {r['trade_time']}",
            f"c1={cond1}",
            f"c2={cond2}",
            f"c3={cond3}",
            f"c4={cond4}",
            f"diff_ratio={r['ma10_ma120_diff_ratio']:.2%}"
        )

    return cond1 and cond2 and cond3 and cond4, desc


# ======================================================
# 卖出策略
# ======================================================

def sell(r, status=None, debug=False):
    """
    跌破 MA20 卖出
    """
    desc = "跌破MA20卖出"
    return r["close"] < r["ma10"], desc


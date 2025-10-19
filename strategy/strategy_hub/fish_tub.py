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


TARGET_MARKET_CAP = 500e8  # 500亿，单位为元


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


def is_rising(arr):
    """
    判断指标是否转强
    返回: bool
    """
    return arr[-1] == max(arr) and len(set(arr)) > 1


def reload_data(records, tuning):
    records.sort_values("trade_date", inplace=True)

    # 策略调优
    period = 3 # 数据范围: 几天
    if tuning:
        period = int(tuning[0])

    # 判断 MA20 斜率是否递增
    for idx in range(len(records)):
        row = records.iloc[idx]
        records.at[idx, "is_raise"] = row["close"] > row["open"]
        if idx >= 1:
            if records.iloc[idx]["kdj_signal"] == "golden_cross" or  records.iloc[idx-1]["kdj_signal"] == "golden_cross":
                records.at[idx, "recent_kdj_gold"] = "golden_cross"

        if idx >= period - 1:
            ma20_recent = records["ma20"].iloc[idx - period + 1: idx + 1].values
            if not np.isnan(ma20_recent).any():
                records.at[idx, "ma20_slope_up"] = is_slope_increasing(ma20_recent)
                records.at[idx, "ma20_rising"] = is_rising(ma20_recent)
            macd_recent = records["MACD"].iloc[idx - period + 1: idx + 1].values
            if not np.isnan(macd_recent).any():
                records.at[idx, "macd_rising"] = is_rising(macd_recent)

            k_recent = records["K"].iloc[idx - period + 1: idx + 1].values
            d_recent = records["D"].iloc[idx - period + 1: idx + 1].values
            if all(x < y for x, y in zip(k_recent, d_recent)):
                kd_recent = [x - y for x, y in zip(k_recent, d_recent)]
                records.at[idx, "cross_ready"] = is_continuous_rising(kd_recent)
                records.at[idx, "cross_ready"] = records.at[idx, "cross_ready"] and k_recent[-1] >= k_recent[-2]
            else:
                records.at[idx, "cross_ready"] = False
            window_start = max(0, idx - 59)
            recent_closes = records["close"].iloc[window_start: idx+1].values
            top3_values = sorted(recent_closes, reverse=True)[:3]
            records.at[idx, "price_top3"] = records["close"].iloc[idx] >= min(top3_values)
        else:
            records.at[idx, "price_top3"] = False

        if idx >= 21:
            max_vol_20 = records["volume"].iloc[idx-21: idx-1].max() * 1.5
            records.at[idx, "volume_breakout"] = records["volume"].iloc[idx] > max_vol_20 and records["volume"].iloc[idx-1] > max_vol_20
        else:
            records.at[idx, "volume_breakout"] = False
    
# ---------------------------
# 在 reload_data 的循环内部（比如在处理完其他指标后），添加以下代码：
# ---------------------------
            # 成交量突增策略判定（需要前 5 天数据：t-4,t-3,t-2,t-1,t）
            # 我们把结果写入列 "volume_spike_buy"
            # 规则：
            #  - t-1 和 t 的成交量都 > mean(t-4,t-3,t-2) * 2
            #  - 前三天成交量的相对偏差 (std/mean) < 0.4 （可调）
            #  - 当天收盘价 > 开盘价
        # if idx >= 6:
        #     try:
        #         prev3 = records["volume"].iloc[idx-6: idx-1].values  # t-4, t-3, t-2
        #         if len(prev3) == 5 and not np.isnan(prev3).any():
        #             mean_prev3 = prev3.mean()
        #             cv_prev3 = prev3.std(ddof=0) / mean_prev3 if mean_prev3 > 0 else np.inf

        #             vol_t_1 = records["volume"].iloc[idx-1]  # 昨天
        #             vol_t = records["volume"].iloc[idx]      # 今天

        #             cond_vol = (vol_t_1 > 2 * mean_prev3) and (vol_t > 2 * mean_prev3)
        #             cond_cv = cv_prev3 < 0.4  # 三天成交量偏差不能太大（阈值可调）
        #             cond_price = row["close"] > row["open"]

        #             records.at[idx, "volume_spike_buy"] = bool(cond_vol and cond_cv and cond_price)
        #         else:
        #             records.at[idx, "volume_spike_buy"] = False
        #     except Exception:
        #         # 任何异常都视为不满足条件
        #         records.at[idx, "volume_spike_buy"] = False
        # else:
        #     records.at[idx, "volume_spike_buy"] = False

        # === 连续放量策略（2~3天） ===
        if idx >= 7:
            try:
                # 前5天成交量（用于均值和波动）
                prev5 = records["volume"].iloc[idx-7: idx-2].values
                # 最近3天成交量（候选观察期）
                recent3 = records["volume"].iloc[idx-2: idx+1].values

                if (
                    len(prev5) == 5 and len(recent3) == 3
                    and not np.isnan(prev5).any()
                    and not np.isnan(recent3).any()
                ):
                    mean_prev5 = prev5.mean()
                    cv_prev5 = prev5.std(ddof=0) / mean_prev5 if mean_prev5 > 0 else np.inf

                    mean_recent3 = recent3.mean()
                    cv_recent3 = recent3.std(ddof=0) / mean_recent3 if mean_recent3 > 0 else np.inf

                    # 1️⃣ 连续三天中至少两天放量 > 前5天均量 × 2
                    cond_vol_3d = np.sum(recent3 > 2 * mean_prev5) >= 2

                    # 2️⃣ 最近三天的波动不大（平稳放量）
                    cond_cv_recent3 = cv_recent3 < 0.3  # 可调阈值

                    # 3️⃣ 前五天成交量波动不大（基准期稳定）
                    cond_cv_prev5 = cv_prev5 < 0.3

                    # 4️⃣ 当天为阳线（价格确认）
                    cond_price = row["close"] > row["open"]

                    records.at[idx, "volume_spike_buy"] = bool(
                        cond_vol_3d and cond_cv_recent3 and cond_cv_prev5 and cond_price
                    )
                else:
                    records.at[idx, "volume_spike_buy"] = False

            except Exception:
                records.at[idx, "volume_spike_buy"] = False
        else:
            records.at[idx, "volume_spike_buy"] = False


    return records


"""
加载股票数据
根据市值等条件，过滤掉不满足的股票
对数据进行预处理
"""
def load_stock(stock_code, tuning, path, ktype=1):
    stock = load_stock_data(stock_code, path, ktype)
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
策略1: 首次超过ma20，当日涨
"""
def buy_strategy_1(r, status, debug=False):
    desc = "策略1: 基础策略，首次超过ma20，当日涨"
    if debug: print("[debug] buy_strategy_1", r)
    return r["first_above_ma20"] == "y" and r["is_raise"], desc


"""
策略2: 当日涨，且ma20处于加速上升
"""
def buy_strategy_2(r, status, debug=False):
    desc = "策略2: 当日涨，且ma20处于加速上升"
    if debug: print("[debug] buy_strategy_2", r)
    return r["ma20_slope_up"] and r["is_raise"], desc


"""
策略3：当日涨，斜率为正, 且ma20处于加速上升
"""
def buy_strategy_3(r, status, debug=False):
    desc = "策略3: 当日涨，斜率为正, 且ma20处于加速上升"
    if debug: print("[debug] buy_strategy_3", r)
    return r["ma20_rising"] and r["ma20_slope_up"] and r["is_raise"], desc


"""
即将突破ma20的股票
"""
def buy_strategy_4(r, status, debug=False):
    desc = "策略4: 即将突破ma20的股票"
    if debug: print("[debug] buy_strategy_4", r)

    close_to_ma20 = r["ma20"] > r["close"] and ((r["ma20"] - r["close"]) / r["close"]) < 0.02

    return close_to_ma20 and r["is_raise"], desc


"""
KDJ出现金叉，MACD转强
"""
def buy_strategy_5(r, status, debug=False):
    desc = "策略5：KDJ出现金叉，MACD转强"
    if debug: print("[debug] buy_strategy_5", r)
    return r["recent_kdj_gold"] == "golden_cross" and r["macd_rising"] and r["is_raise"], desc


"""
KDJ出现金叉，MACD转强
"""
def buy_strategy_6(r, status, debug=False):
    desc = "策略6：KDJ即将出现金叉"
    if debug: print("[debug] buy_strategy_6", r)
    return r["cross_ready"], desc


"""
MACD 处于零轴以上
"""
def buy_strategy_c1(r, status, debug=False):
    desc = "策略6：MACD快线处于零轴以上"
    if debug: print("[debug] buy_strategy_c1", r)
    return r["DIF"] >= 0, desc


# ---------------------------
# 在 BUY_STRATEGIES 的函数组里，新增策略函数（放到现有 buy_strategy_* 定义的后面）
# ---------------------------
def buy_strategy_volume_spike(r, status, debug=False):
    """
    策略7：成交量连续两天 > 前五天均值 * 2，且前五天波动不大，当日收盘 > 开盘
    依赖字段：records 中已由 reload_data 计算并写入 'volume_spike_buy'
    """
    desc = "策略7：成交量连续两天背离（> 前五天均值*2）且前五天波动小，当日收盘大于开盘"
    if debug: print("[debug] buy_strategy_volume_spike", r)
    # r 可能是 pandas Series，使用 get 以防 KeyError
    return bool(r.get("volume_spike_buy", False)), desc


def buy_strategy_volume_breakout(r, status, debug=False):
    desc = "策略8：量能突破（当日成交量超过近20交易日最高量x1.5）"
    if debug: print("[debug] buy_strategy_volume_breakout", r)
    return bool(r.get("volume_breakout", False)), desc


def buy_strategy_price_top3(r, status, debug=False):
    desc = "策略9：价格强势（收盘价为近3个月Top3）"
    if debug: print("[debug] buy_strategy_price_top3", r)
    return bool(r.get("price_top3", False)), desc


BUY_STRATEGIES = {
    "c1": buy_strategy_c1,
    "1": buy_strategy_1,
    "2": buy_strategy_2,
    "3": buy_strategy_3,
    "4": buy_strategy_4,
    "5": buy_strategy_5,
    "6": buy_strategy_6,
    "7": buy_strategy_volume_spike,
    "8": buy_strategy_volume_breakout,  # 新增：量能突破
    "9": buy_strategy_price_top3,       # 新增：价格Top3
}


# ==========================
# 卖出策略
# ==========================
"""
带c打头的策略是条件策略，不单独作为售卖策略，
是其他策略的补充，组合使用
"""
def sell_strategy_c1(r, status, debug=False):
    desc = "条件1：ma20上升"
    if debug: print("[debug] sell_strategy_c1", r)
    return r["ma20_rising"], desc


def sell_strategy_c2(r, status, debug=False):
    desc = "条件2：ma20下降"
    if debug: print("[debug] sell_strategy_c1", r)
    return not r["ma20_rising"], desc


"""
基础策略
"""
def sell_strategy_1(r, status, debug=False):
    desc = "策略1：跌破ma20 卖出"
    if debug: print("[debug] sell_strategy_1", r["trade_time"], r["close"], r["ma20"])
    return r["close"] < r["ma20"], desc


def sell_strategy_2(r, status, debug=False):
    desc = "策略2：KDJ死叉"
    if debug: print("[debug] sell_strategy_2", r)
    return r["kdj_signal"] == "death_cross", desc


def sell_strategy_3(r, status, debug=False):
    desc = "策略3：MACD死叉"
    if debug: print("[debug] sell_strategy_3", r)
    return r["macd_signal"] == "death_cross", desc


def sell_strategy_4(r, status, debug=False):
    desc = "策略4：持股超过7天，就卖出"
    if debug: print("[debug] sell_strategy_4", status["days"], r["trade_time"])
    return len(status["record"]) >= 7, desc


def sell_strategy_5(r, status, debug=False):
    desc = "策略5: 跌破ma5卖出"
    if debug: print("[debug] sell_strategy_5", r)
    return r["close"] < r["ma5"], desc


def sell_strategy_6(r, status, debug=False):
    desc = "策略6：跌破ma10卖出"
    if debug: print("[debug] sell_strategy_7", r)
    return r["close"] < r["ma10"], desc


"""
中性偏激进，要具体分析，如果整体收益很小就要尽快撤出
"""
def sell_strategy_7(r, status, debug=False):
    desc = "策略7：跌幅超过2%，卖出"
    if debug: print("[debug] sell_strategy_6", r["trade_time"], r["close"], r["open"])
    return ((r["open"] - r["close"]) / r["open"]) > 0.02, desc


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


def sell_strategy_c(r, status, debug=False):
    desc = "策略c：短线策略，第二天直接卖出"
    if debug: print(r, status)
    ok = len(status["record"]) == 2
    return ok, desc


SELL_STRATEGIES = {
    "c1": sell_strategy_c1,
    "c2": sell_strategy_c2,
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
    "c": sell_strategy_c,
}

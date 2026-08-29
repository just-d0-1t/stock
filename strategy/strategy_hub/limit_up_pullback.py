#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: limit_up_pullback.py
@author: vanilla
@date: 2026-08-29
@desc: 涨停回调再启动策略。

策略故事：
  曾经大热的股票（连续涨停）被洗盘（大幅回调）后，再次出现涨停启动时买入。

逻辑（对每个交易日 i 倒查，在 pretreatment 中完成）：
  1. 当天（索引 i）涨停，且是“重新拉伸”段的第一个涨停日；
  2. 倒查前 period 个交易日（并要求至少 min_history 天历史），
     窗口内存在一段 >= min_streak 天的连续涨停（事件A）；
  3. 该涨停段结束后，股价从段内最高价回撤 >= pullback_pct（事件B，洗盘）；
  4. 同时满足 1/2/3 → buy_signal = True。

买入后跌破 MA5 卖出。
"""

import numpy as np
from utils.parse import parse_tuning

def pretreatment(stock, operate, tuning, debug):
    """
    预处理：遍历 records，对每个交易日 i —— 若当天涨停，则倒查前 period 个
    交易日，判断窗口内是否曾经存在“连续涨停 → 大幅回调（洗盘）”的完整事件，
    存在则当天发出买入信号。

    参数（-t 传入）：
      period:          回看窗口（默认 100）
      pullback_period: 回调周期（默认 20）
      min_history:     评估前至少需要的历史交易日数（默认 30）
      min_streak:      连续涨停最少天数（默认 2）
      pullback_pct:    回调幅度阈值（默认 0.20，即 20%）
      limit_up_pct:    涨停判定阈值（默认 0.098，即 9.8%）
      peak_window:     涨停段结束后 N 天内最高价仍视为回调起点（默认 3）
    """
    records = stock["records"]
    tuning = parse_tuning(tuning)

    period = tuning.get("period", 100)
    pullback_period = tuning.get("pullback_period", 20)
    min_history = tuning.get("min_history", 30)
    min_streak = tuning.get("min_streak", 2)
    pullback_pct = tuning.get("pullback_pct", 0.20)
    limit_up_pct = tuning.get("limit_up_pct", 0.098)
    peak_window = tuning.get("peak_window", 3)

    if debug:
        print("period:", period)
        print("min_history:", min_history)
        print("min_streak:", min_streak)
        print("pullback_pct:", pullback_pct)
        print("limit_up_pct:", limit_up_pct)
        print("peak_window:", peak_window)

    n = len(records)
    close = records["close"].to_numpy(dtype=float)
    pre_close = records["pre_close"].to_numpy(dtype=float)
    high = records["high"].to_numpy(dtype=float)
    low = records["low"].to_numpy(dtype=float)

    # ---- 当天是否涨停 ----
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = (close - pre_close) / pre_close
    limit_up = (pre_close > 0) & (pct >= limit_up_pct)

    # ---- 找出所有 >= min_streak 天的连续涨停段，并记录每根K线所在段的起点 ----
    segments = []
    run_start = np.arange(n)
    i = 0
    while i < n:
        if limit_up[i]:
            j = i
            while j + 1 < n and limit_up[j + 1]:
                j += 1
            if j - i + 1 >= min_streak:
                segments.append((i, j))
            run_start[i: j + 1] = i
            i = j + 1
        else:
            i += 1

    def find_firing_segment(idx):
        """
        倒查 idx 之前 period 天内，是否存在“连续涨停 → 大幅回调（洗盘）”的完整事件。
        只使用 idx 之前的数据（无未来函数）。命中返回 (start, end)，否则 None。
        """
        if idx < min_history:
            return None
        win_start = max(0, idx - period)
        for s, e in reversed(segments):       # 从最近的段往前查（存在性语义）
            if e < win_start:
                break                         # 更早的段已超出回看窗口
            if e >= idx:
                continue                      # 当天仍处于该段中（当前启动段），跳过
            if idx - e <= pullback_period:
                break                         # 回调周期不能太短，不然洗盘不干净
            # 回调起点：段内最高价，并计入段后 peak_window 天内的最高价（只用到 idx-1）
            peak = high[s: e + 1].max()
            if e + 1 < idx and peak_window > 0:
                peak = max(peak, high[e + 1: min(e + 1 + peak_window, idx)].max())
            # 回调终点：昨天为止的股价，相比之前连续涨停已经下跌20%以上；
            trough = close[idx-1]
            if trough <= peak * (1 - pullback_pct):
                return (s, e)
        return None

    # ---- 初始化输出字段 ----
    last_streak_days = np.zeros(n, dtype=int)
    buy_signal = np.zeros(n, dtype=bool)

    def analyze(idx):
        if limit_up[idx]:
            seg = find_firing_segment(idx)
            if seg is not None:
                last_streak_days[idx] = seg[1] - seg[0] + 1
                buy_signal[idx] = True

    # ---- 调度模式：back_test 全量 / buy、sell 仅最后一天 ----
    if operate == "back_test":
        for idx in range(n):
            analyze(idx)
    elif operate == "buy":
        analyze(n - 1)

    records["limit_up"] = limit_up
    records["last_streak_days"] = last_streak_days
    records["buy_signal"] = buy_signal
    stock["records"] = records

def buy(r, status=None, debug=False):
    """
    当天涨停，且前期完成“连续涨停 → 大幅回调”，则买入。
    """
    desc = "策略：涨停回调再启动"
    if debug:
        print("[debug] buy_strategy_limit_up_pullback")
        print("limit_up:", r.get("limit_up"))
        print("last_streak_days:", r.get("last_streak_days"))
        print("buy_signal:", r.get("buy_signal"))
    return bool(r.get("buy_signal", False)), desc

def sell(r, status=None, debug=False):
    """
    跌破 MA5 卖出。
    """
    desc = "跌破MA5卖出"
    if debug:
        print("[debug] sell_strategy_limit_up_pullback", r["trade_date"], r["close"], r.get("ma5"))
    return r["close"] < r["ma5"], desc

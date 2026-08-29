#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: fetch_market.py
@author: vanilla
@date: 2025-09-05
@desc: 行情数据拉取、指标计算与落盘。

MarketAnalyzer 只负责“拉取新数据 → 合并历史 → 增量计算指标 → 保存 CSV”。
数据从哪里拉取由数据源注册表决定：-f/--fetch_from 传入名称
（remote | ths | local，见 update/sources/__init__.py）。
新增数据源不需要改动本文件。
"""

import os
import numpy as np
import pandas as pd
import utils.config as config
from update.sources import create_source


def compute_kdj(all_df, new_start_idx, n=9, k_smooth=3, d_smooth=3):
    """
    增量计算 KDJ，确保结果与全量计算一致
    :param all_df: 完整 DataFrame（已排序去重）
    :param new_start_idx: 需要更新指标的起始索引（含重叠部分）
    :param n: RSV 周期
    """
    if new_start_idx >= len(all_df):
        return

    # === 1. 确定计算窗口 ===
    # 预热窗口长度：经验值 3*n（可调整）
    warmup = max(n * 3, 50)  # 至少 50 行保证 EWM 收敛
    calc_start = max(0, new_start_idx - warmup)

    # 提取计算子集
    calc_df = all_df.iloc[calc_start:].copy()

    # === 2. 全量计算 KDJ（在子集上）===
    low_min = calc_df['low'].rolling(window=n, min_periods=1).min()
    high_max = calc_df['high'].rolling(window=n, min_periods=1).max()
    rsv = (calc_df['close'] - low_min) / (high_max - low_min) * 100
    calc_df['rsv'] = rsv.fillna(0)  # 处理除零或 NaN

    # K 和 D 使用 EWM
    calc_df['K'] = calc_df['rsv'].ewm(alpha=1/k_smooth, adjust=False).mean()
    calc_df['D'] = calc_df['K'].ewm(alpha=1/d_smooth, adjust=False).mean()
    calc_df['J'] = 3 * calc_df['K'] - 2 * calc_df['D']

    # === 3. 只将“需要更新的部分”写回 all_df ===
    # 从 new_start_idx 开始的所有行都需要更新（包括重叠部分）
    update_indices = all_df.index[new_start_idx:]
    update_slice = calc_df.loc[update_indices]

    for col in ['K', 'D', 'J']:
        all_df.loc[update_indices, col] = update_slice[col].values

    # === 4. 更新信号（保留历史，只重算 new_start_idx 之后）===
    if 'kdj_signal' not in all_df.columns:
        all_df['kdj_signal'] = 'no_cross'
    all_df.loc[new_start_idx:, 'kdj_signal'] = 'no_cross'  # 初始化

    for i in range(new_start_idx, len(all_df)):
        if i == 0:
            continue
        k_prev, d_prev = all_df.at[i-1, 'K'], all_df.at[i-1, 'D']
        k_curr, d_curr = all_df.at[i, 'K'], all_df.at[i, 'D']
        if k_prev < d_prev and k_curr > d_curr:
            all_df.at[i, 'kdj_signal'] = 'golden_cross'
        elif k_prev > d_prev and k_curr < d_curr:
            all_df.at[i, 'kdj_signal'] = 'death_cross'



class MarketAnalyzer:
    """
    从指定数据源获取日线数据，维护本地 CSV（含 MA/KDJ 等指标）。

    数据源通过 fetch_from 指定（见 update/sources.SOURCE_REGISTRY），
    例如：remote(adata/akshare) | ths(同花顺) | local(本地快照)。
    """

    def __init__(self, code: str, start_date: str, end_date: str = None,
                 data_path: str = None, typ: int = 1, fetch_from: str = "remote",
                 source_kwargs: dict = None):
        """
        :param code: 股票代码，例如 '002747'
        :param start_date: 起始日期，例如 '2025-08-01'
        :param end_date: 结束日期（默认由数据源决定）
        :param data_path: 股票数据存放路径（CSV 文件），若未指定则默认生成
        :param typ: 1.股票；2.指数；3.基金
        :param fetch_from: 数据源名称（remote | ths | local，见 update.sources）
        :param source_kwargs: 透传给数据源构造函数的额外参数，如
            {"snapshot_path": "..."}（local 源）
        """
        self.code = code
        self.start_date = start_date
        self.end_date = end_date
        self.typ = typ
        self.source = create_source(fetch_from, typ=typ, **(source_kwargs or {}))
        if data_path:
            self.data_path = data_path
        else:
            self.data_path = config.default_data_path(self.code, self.typ)

    def load_history(self):
        """读取历史数据（如存在）"""
        if os.path.exists(self.data_path):
            return pd.read_csv(
                self.data_path,
                parse_dates=["trade_date"],
            )
        return pd.DataFrame()

    def ma(self, all_df, period, new_start_idx):
        """
        增量计算 MA 指标
        :param all_df: 完整 DataFrame（含历史+新数据）
        :param period: MA 周期，如 5, 10, 20
        :param new_start_idx: 新数据在 all_df 中的起始索引
        """
        period = str(period)
        win = int(period)
        col_ma = f"ma{period}"
        col_above = f"above_ma{period}"
        col_first_above = f"first_above_ma{period}"
        col_first_under = f"first_under_ma{period}"

        # === 1. 计算 MA（只需从 new_start_idx - win + 1 开始算，但为安全取更早一点）
        start_calc = max(0, new_start_idx - win)
        subset = all_df.iloc[start_calc:].copy()
        subset[col_ma] = subset["close"].rolling(window=win, min_periods=win).mean()

        # 将计算结果写回 all_df
        all_df.loc[subset.index, col_ma] = subset[col_ma]

        # === 2. 计算 above_ma
        mask = (all_df[col_ma] > 0) & (all_df["close"] > all_df[col_ma])
        all_df[col_above] = np.where(mask, "y", "n")

        # === 3. 计算 first_above_ma 和 first_under_ma（只需从 new_start_idx 开始检查）
        # 初始化为 "n"
        all_df[col_first_above] = "n"
        all_df[col_first_under] = "n"

        for i in range(new_start_idx, len(all_df)):
            if all_df.at[i, col_above] == "y":
                if i == 0 or all_df.at[i-1, col_above] == "n":
                    all_df.at[i, col_first_above] = "y"
            else:
                if i > 0 and all_df.at[i-1, col_above] == "y":
                    all_df.at[i, col_first_under] = "y"
        # ===== 计算 ma =====
        all_df["ma" + period] = all_df["close"].rolling(window=win, min_periods=win).mean().fillna(0)

        # ===== 收盘价是否超过 ma =====
        all_df["above_ma" + period] = all_df.apply(
            lambda row: "y" if row["ma" + period] > 0 and row["close"] > row["ma" + period] else "n",
            axis=1
        )

        # ===== 是否首次突破 ma =====
        first_flags = []
        for i in range(len(all_df)):
            if all_df.loc[i, "above_ma" + period] == "y":
                if i == 0:
                    first_flags.append("n")
                elif all_df.loc[i-1, "above_ma" + period] == "n":
                    first_flags.append("y")
                else:
                    first_flags.append("n")
            else:
                first_flags.append("n")
        all_df["first_above_ma" + period] = first_flags

        # ===== 是否首次跌破 ma =====
        first_under_flags = []
        for i in range(len(all_df)):
            if all_df.loc[i, "above_ma" + period] == "n":
                if i == 0:
                    first_under_flags.append("n")
                elif all_df.loc[i-1, "above_ma" + period] == "y":
                    first_under_flags.append("y")
                else:
                    first_under_flags.append("n")
            else:
                first_under_flags.append("n")
        all_df["first_under_ma" + period] = first_under_flags

    def compute_indicators(self, df: pd.DataFrame, history_df: pd.DataFrame):
        if df.empty:
            return history_df

        # ===== 统一日期和股票代码类型 =====
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
        if not history_df.empty:
            history_df["trade_date"] = pd.to_datetime(history_df["trade_date"])

        # ===== 合并历史与新数据（去重） =====
        all_df = pd.concat([history_df, df]).drop_duplicates(
            subset=["trade_date"], keep="last"
        ).sort_values("trade_date").reset_index(drop=True)

        # 前复权数据源（如同花顺）段首行没有昨收，用合并后的前一日收盘补齐
        if "pre_close" in all_df.columns:
            all_df["pre_close"] = all_df["pre_close"].fillna(all_df["close"].shift(1))
        else:
            all_df["pre_close"] = all_df["close"].shift(1)

        # ✅ 在你的前提下，这是安全的
        new_start_idx = len(all_df) - len(df)

        # 安全兜底（理论上不会触发，但防御性编程）
        if new_start_idx < 0:
            new_start_idx = 0

        # 增量计算（实际会重算 [new_start_idx:]）
        self.ma(all_df, 5, new_start_idx)
        self.ma(all_df, 10, new_start_idx)
        self.ma(all_df, 20, new_start_idx)
        compute_kdj(all_df, new_start_idx)

        return all_df

    def save_data(self, df: pd.DataFrame):
        """以追加方式写入 CSV，并保持股票代码为字符串"""
        # 写入 CSV
        df.to_csv(self.data_path, index=False, mode="w", encoding="utf-8-sig")

    def run(self):
        """执行完整流程：拉取新数据 → 合并历史 → 增量计算指标 → 保存 CSV"""
        """各渠道需要提供的基础数据 trade_date, open, close, high, low, volume, amount, pre_close"""
        print(f"获取股票 {self.code} 自 {self.start_date} 起的数据（数据源: {self.source.name}）...")
        new_data = self.source.fetch_daily(
            code=self.code,
            start_date=self.start_date,
            end_date=self.end_date,
        )

        if new_data is None or new_data.empty:
            print(f"⚠️ 股票 {self.code} new_data 是空的 DataFrame")
            return new_data
        history_data = self.load_history()

        all_data = self.compute_indicators(new_data, history_data)
        self.save_data(all_data)

        print(f"分析完成，数据已保存到 {self.data_path}")
        return all_data

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
import utils.indicator as indicator
from update.sources import create_source


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
        indicator.ma(all_df, 5, new_start_idx)
        indicator.ma(all_df, 10, new_start_idx)
        indicator.ma(all_df, 20, new_start_idx)
        indicator.compute_kdj(all_df, new_start_idx)

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

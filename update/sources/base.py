#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据源统一接口：新增数据源只需实现 DailySource，并在
update/sources/__init__.py 的 SOURCE_REGISTRY 中登记即可被使用。
"""

from abc import ABC, abstractmethod


class DailySource(ABC):
    """日线行情数据源接口。"""

    #: 数据源名称（注册键，打印/日志用）
    name = "base"

    @abstractmethod
    def fetch_daily(self, code, start_date=None, end_date=None):
        """
        获取单只标的的日线行情。

        :param code: 股票代码，如 "603007"（是否带市场后缀由数据源决定）
        :param start_date / end_date: "YYYY-MM-DD"，None 表示不限制/到最新
        :return: DataFrame，至少包含列
            trade_date, open, close, high, low, volume, amount
            （pre_close 可缺省，MarketAnalyzer.compute_indicators 会补齐）
        """
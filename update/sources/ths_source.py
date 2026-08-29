#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
同花顺（THS）数据源：封装 update.sources.ths_api.ThsClient，
把接口响应统一为存储结构（trade_date/open/close/high/low/volume/amount/pre_close）。
"""

from datetime import datetime

from update.sources.ths_api import ThsClient
from update.sources.base import DailySource


class ThsSource(DailySource):
    """同花顺行情 API 数据源（前复权日线）。"""

    name = "ths"

    def __init__(self, typ=1, token=None):
        self.typ = typ
        self.token = token

    def fetch_daily(self, code, start_date=None, end_date=None):
        """仅支持 A 股（typ=1）；自动补全市场后缀，如 603007 -> 603007.SH"""
        if self.typ not in (1, "1"):
            raise ValueError(f"同花顺行情 API 暂仅支持股票(typ=1)，当前 typ={self.typ}")
        end_date = end_date or datetime.today().strftime("%Y-%m-%d")
        client = ThsClient(token=self.token)
        return client.fetch_daily(
            code=code,
            start_date=start_date,
            end_date=end_date,
        )
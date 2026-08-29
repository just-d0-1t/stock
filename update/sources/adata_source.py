#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
adata / akshare 数据源（原 MarketAnalyzer.fetch_market_data）。
  - 股票 typ=1：adata.stock.market.get_market
  - ETF   typ=2：akshare.fund_etf_hist_em（前复权）
"""

import pandas as pd
from datetime import datetime
import adata
import akshare as ak

from update.sources.base import DailySource


class AdataSource(DailySource):
    """adata / akshare 远程数据源（默认 remote）。"""

    name = "remote"

    def __init__(self, typ=1):
        self.typ = typ

    def fetch_daily(self, code, start_date=None, end_date=None):
        """获取交易数据"""
        res_df = pd.DataFrame()
        if self.typ in (1, "1"):
            # 股票类型
            res_df = adata.stock.market.get_market(
                stock_code=code,
                start_date=start_date,
                end_date=end_date,
            )
        elif self.typ in (2, "2"):
            # ETF 基金类型（akshare 的字段为中文列名，由上游统一清洗）
            start = start_date.replace("-", "") if start_date else "19900101"
            today = datetime.today().strftime("%Y%m%d")
            end = end_date.replace("-", "") if end_date else today
            print(start, end)
            res_df = ak.fund_etf_hist_em(
                symbol=code,
                start_date=start,
                end_date=end,
                adjust="qfq",
            )
        else:
            raise ValueError(f"不支持的代码类型: typ={self.typ}")
        return res_df
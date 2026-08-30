#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: ths_api.py
@author: vanilla
@date: 2026-08-29
@desc: 同花顺（THS）金融数据 API 客户端。

对接接口：
  GET https://fuyao.aicubes.cn/api/a-share/prices/historical
      ?thscode=603007.SH&interval=1d&start=<epoch_ms>&end=<epoch_ms>&adjust=forward
  GET https://fuyao.aicubes.cn/api/fund/market/historical   (基金/ETF，仅四参数)
      ?thscode=510300.SH&interval=1d&start=<epoch_ms>&end=<epoch_ms>

调用方式：
  1. 设置环境变量 THS_TOKEN（作为 X-api-key 请求头）；
  2. client = ThsClient()
  3. df = client.fetch_daily("603007", start_date="2025-08-01", end_date="2026-08-29")

返回的 DataFrame 列与 update/fetch_market.py 的存储结构一致：
  trade_date, open, close, high, low, volume, amount, pre_close
  - volume / amount 为接口原始数值（未做换算，保持与接口一致）；
  - pre_close 由段内前一日收盘价推算，段首行为 NaN，
    由 MarketAnalyzer.compute_indicators 合并历史后补齐。
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone

# 股票代码前缀 -> 市场后缀
exchange_suffix = {
    "00": ".SZ",
    "15": ".SZ",  # 深市 ETF（159xxx）
    "20": ".SZ",
    "30": ".SZ",
    "43": ".BJ",
    "51": ".SH",  # 沪市 ETF（51xxxx）
    "56": ".SH",  # 沪市 ETF（56xxxx）
    "58": ".SH",  # 沪市 ETF（58xxxx，含科创板 588）
    "60": ".SH",
    "68": ".SH",
    "83": ".BJ",
    "87": ".BJ",
    "90": ".SH",
    "92": ".BJ",
}


def compile_exchange_by_stock_code(stock_code):
    """根据股票代码补全市场后缀，如 603007 -> 603007.SH"""
    prefix = stock_code[0:2]
    if prefix in exchange_suffix:
        return stock_code + exchange_suffix[prefix]
    return stock_code


def get_exchange_by_stock_code(stock_code):
    """根据股票代码返回交易所缩写，如 603007 -> SH；未知返回 XX"""
    prefix = stock_code[0:2]
    if prefix not in exchange_suffix:
        print(f"⚠️ 股票代码 {stock_code} 不在已知交易所中")
        return "XX"
    return exchange_suffix[prefix][1:]


def date_to_ms(date_str):
    """YYYY-MM-DD -> 毫秒时间戳（北京时间零点，与接口示例一致）。

    接口按北京时间解释日期：示例 2021-01-01 -> 1609430400000（北京 00:00）。
    """
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone(timedelta(hours=8)))
    return int(dt.timestamp() * 1000)


def now_ms():
    """当前时间（UTC）-> 毫秒时间戳"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def ms_to_date(ms):
    """毫秒时间戳 -> 北京时间日期（datetime.date）"""
    return datetime.fromtimestamp(ms / 1000, tz=timezone(timedelta(hours=8))).date()


class ThsClient:
    """同花顺行情数据客户端（A股 + ETF 基金）"""

    BASE_URL = "https://fuyao.aicubes.cn/api/a-share/prices/historical"
    FUND_BASE_URL = "https://fuyao.aicubes.cn/api/fund/market/historical"

    def __init__(self, token=None, timeout=10):
        self.token = token or os.environ.get("THS_TOKEN", "")
        if not self.token:
            raise ValueError("缺少 THS_TOKEN 环境变量（同花顺 API 的 X-api-key）")
        self.timeout = timeout

    def _request_historical(self, url, code, start_date, end_date,
                            start_ms, end_ms, interval, extra_params=None):
        """
        通用历史行情请求：统一处理参数编码、X-api-key 头部与响应解析。

        :param url: 接口地址（A 股或基金）
        :param code: 代码，可带或不带市场后缀，如 "603007" / "510300"
        :param start_date / end_date: "YYYY-MM-DD"，优先于 start_ms / end_ms
        :param start_ms / end_ms: 毫秒时间戳
        :param interval: K 线周期，固定 "1d"
        :param extra_params: 额外查询参数（如 A 股的 adjust），None 则不加
        """
        thscode = compile_exchange_by_stock_code(code)
        if start_date is not None:
            start_ms = date_to_ms(start_date)
        if end_date is not None:
            end_ms = date_to_ms(end_date)
        if start_ms is None:
            raise ValueError("必须指定 start_date 或 start_ms")
        if end_ms is None:
            end_ms = now_ms()

        params = {
            "thscode": thscode,
            "interval": interval,
            "start": start_ms,
            "end": end_ms,
        }
        if extra_params:
            params.update(extra_params)
        headers = {"X-api-key": self.token}
        resp = requests.get(url, params=params, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        return self._parse_payload(resp.json())

    def fetch_daily(self, code, start_date=None, end_date=None,
                    start_ms=None, end_ms=None, interval="1d", adjust="forward"):
        """
        获取单只股票日线行情（默认前复权）。

        :param code: 股票代码，可带或不带市场后缀，如 "603007" / "603007.SH"
        :param start_date / end_date: "YYYY-MM-DD"，优先于 start_ms / end_ms
        :param start_ms / end_ms: 毫秒时间戳
        :param interval: K 线周期，固定 "1d"
        :param adjust: 复权方式，固定 "forward"（前复权）
        """
        return self._request_historical(
            self.BASE_URL, code, start_date, end_date, start_ms, end_ms,
            interval, extra_params={"adjust": adjust},
        )

    def fetch_fund_daily(self, code, start_date=None, end_date=None,
                         start_ms=None, end_ms=None, interval="1d"):
        """
        获取 ETF 基金日线行情。

        基金接口仅 thscode/interval/start/end 四个参数，无 adjust 字段；
        响应结构假定与 A 股接口一致（code/data/item + date_ms/open_price 等）。

        :param code: 基金代码，可带或不带市场后缀，如 "510300" / "510300.SH"
        :param start_date / end_date: "YYYY-MM-DD"，优先于 start_ms / end_ms
        :param start_ms / end_ms: 毫秒时间戳
        :param interval: K 线周期，固定 "1d"
        """
        return self._request_historical(
            self.FUND_BASE_URL, code, start_date, end_date, start_ms, end_ms,
            interval,
        )

    def _parse_payload(self, payload):
        """接口响应 -> 存储结构 DataFrame"""
        if payload.get("code") != 0:
            raise RuntimeError(
                f"同花顺接口返回错误: code={payload.get('code')}, message={payload.get('message')}"
            )
        items = (payload.get("data") or {}).get("item") or []
        rows = []
        for item in items:
            rows.append({
                "trade_date": pd.Timestamp(ms_to_date(item["date_ms"])),
                "open": float(item["open_price"]),
                "close": float(item["close_price"]),
                "high": float(item["high_price"]),
                "low": float(item["low_price"]),
                "volume": float(item["volume"]),
                "amount": float(item["turnover"]),
            })
        df = pd.DataFrame(rows, columns=[
            "trade_date", "open", "close", "high", "low", "volume", "amount",
        ])
        if df.empty:
            return df
        df = df.sort_values("trade_date").reset_index(drop=True)
        # 段内推算昨收；段首行留空，由上游合并历史后补齐
        df["pre_close"] = df["close"].shift(1)
        return df


if __name__ == "__main__":
    print(compile_exchange_by_stock_code("200039"))
    print(get_exchange_by_stock_code("200039"))

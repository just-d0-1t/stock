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
import argparse
from datetime import datetime, timedelta
from glob import glob

from utils.load_info import load_stock_data
import utils.config as config


TARGET_MARKET_CAP = 500e8  # 500亿，单位为元


def market_cap_handler(stock, args):
    # 首先检查 args 是否是字典
    if not isinstance(args, dict):
        return False, f"market_cap_handler: args should be dict, got {type(args)}"
    
    # 安全地获取值，避免 KeyError
    above = args.get("above")
    under = args.get("under")
    
    # 检查市值条件
    if above is not None and stock.get("market_cap") is not None:
        if stock["market_cap"] < above:
            return False, f"market_cap {stock['market_cap']} under above limit {above}"
    
    if under is not None and stock.get("market_cap") is not None:
        if stock["market_cap"] > under:
            return False, f"market_cap {stock['market_cap']} exceed under limit {under}"
    
    return True, ""


def market_handler(stock, args):
    # 首先检查 args 是否是字典
    if not isinstance(args, dict):
        return False, f"market_handler: args should be dict, got {type(args)}"
    
    # 安全地获取值，避免 KeyError
    above = args.get("above")
    under = args.get("under")

    records = stock["records"]
    if len(records) <= 0:
        return False, f"market records is null"

    close = records.iloc[-1]["close"]

    # 检查市值条件
    if above is not None and close <= above:
        return False, f"market {close} under above limit {above}"
    
    if under is not None and close >= under:
        return False, f"market {close} exceed under limit {under}"

    return True, ""
    

filter_handler = {
    "market_cap": market_cap_handler,
    "market": market_handler,
}


def cond_init():
    return {
        "market_cap": {
            "above": TARGET_MARKET_CAP,
            "under": None,
        }
    }


def filter_stock(stock, cond=None):
    if stock is None:
        return False, "stock is empty"

    if cond is None:
        cond = cond_init()

    for c, args in cond.items():
        ok, desc = filter_handler[c](stock, args)
        if not ok:
            return False, desc

    return True, ""


def main(code, output, above, under):
    cond = {
        "market_cap": {
            "above": above if above is not None else TARGET_MARKET_CAP,
            "under": under,
        }
    }

    stock_codes = []
    if code == "all":
        stock_codes = config.get_codes_from_local()
    else:
        stock_codes = code.split(",")
    # 2. 遍历股票，更新数据并生成图表
    for code in stock_codes:
        stock = load_stock_data(code, None)
        if stock is None:
            continue
        ok, desc = filter_stock(stock, cond)
        if output == "hit":
            if ok:
                print(stock["stock_name"], code)
            continue
        if output == "miss":
            if not ok:
                print(stock["stock_name"], code, desc)
            continue
        print(stock["stock_name"], code, ok, desc)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='并发更新所有股票数据')
    parser.add_argument('-c', '--code', type=str, help='股票列表')
    parser.add_argument('-a', '--above', type=int, help='市值下限')
    parser.add_argument('-u', '--under', type=int, help='市值上限')
    parser.add_argument('-o', '--output', type=str, default="", help='输出类型')
    args = parser.parse_args()
    main(args.code, args.output, args.above, args.under)

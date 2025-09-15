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
from glob import glob

from utils.load_info import load_stock_data


WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径
TARGET_MARKET_CAP = 200e8  # 500亿，单位为元


"""
加载股票数据
根据市值等条件，过滤掉不满足的股票
对数据进行预处理
"""
def load_stock(stock_code):
    stock = load_stock_data(stock_code, None)
    if stock is None:
        return False, "股票信息无法加载"


    # 条件1：市值大于 500亿
    market = TARGET_MARKET_CAP

    if stock["market_cap"] < market:
        return

    print(stock["stock_name"], code)



def get_codes_from_local():
    print("从本地获取A股股票代码...")
    stock_codes = []
    info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
    stock_codes = [os.path.basename(f).split("_")[0] for f in info_files]
    return stock_codes


stock_codes = []
stock_codes = get_codes_from_local()
# 2. 遍历股票，更新数据并生成图表
for idx, code in enumerate(stock_codes, start=1):
    load_stock(code)



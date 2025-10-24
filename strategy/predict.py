#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: backtest.py
@author: vanilla
@date: 2025-09-05
@desc: 股票回测策略脚本，支持多买卖策略组合和调试模式。
"""

import argparse
import os
import re
import sys
import pandas as pd
import numpy as np

from glob import glob
from datetime import datetime, timedelta
from strategy.load_stock import load_stock

# 注册策略
import strategy.strategy_hub.fish_tub as fish_tub
import strategy.strategy_hub.kdj as kdj
import strategy.strategy_hub.kdj_ready as kdj_ready
import strategy.strategy_hub.volumn_detect as volumn_detect
mapping = {
    "kdj": kdj,
    "kdj_ready": kdj_ready,
    "fish_tub": fish_tub,
    "volumn_detect": volumn_detect,
}

strategy = None

WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径


def get_strategy(mode: str):
    """根据命令行参数选择策略模块"""
    if mode not in mapping:
        raise ValueError(f"未知环境: {env}，仅支持 {list(mapping.keys())}")
    return mapping[mode]


def buy(r, status, debug=False):
    return strategy.buy(r, status, debug)


def sell(r, status, debug=False):
    return strategy.sell(r, status, debug)


def backtesting(records, debug):
    fund = 10000

    # 股票持有状态
    status = {
        "hold": False,
        "buy": 0,
        "base": fund,
        "fund": fund,
        "lose": 0,
        "win": 0,
        "hand": 0,
        "days": 0,
        "record": [],
        "operations": [],
    }

    operation = {}
    for idx, r in records.iterrows():
        # 忽略掉初始一些脏数据
        if idx < 21:
            continue

        if not status["hold"]:
            ok, desc = buy(r, status, debug)
            if ok:
                status["should_buy"] = True
                status["record"].append(r)
                operation["operator"] = "买入"
                operation["strategy"] = desc
                # 可买入手数，100的整数倍
                status["hand"] = int(status["fund"] / r["close"] / 100) * 100
                # 持仓，扣除手续费
                capital = r["close"] * status["hand"]
                status["fund"] = status["fund"] - capital
                status["buy"] = r["close"]
                if capital * 0.00026 < 5:
                    status["fund"] = status["fund"] - 5
                else:
                    status["fund"] = status["fund"] - capital * 0.00026
                operation["trade_time"] = r["trade_time"] 
                operation["hand"] = status["hand"]
                operation["price"] = r["close"]
                operation["capital"] = capital
                operation["cash_flow"] = status["fund"]
                operation["rate"] = 0
                status["operations"].append(operation)
                operation = {}
                status["hold"] = True

        else:
            status["days"] = status["days"] + 1
            status["record"].append(r)
            ok, desc = sell(r, status, debug)
            if ok:
                status["hold"] = False
                status["days"] = 0
                capital = status["hand"] * r["close"]
                status["fund"] = status["fund"] + capital
                if capital * 0.00026 < 5:
                    status["fund"] = status["fund"] - 5
                else:
                    status["fund"] = status["fund"] - capital * 0.00026
                rate = (r["close"] - status["buy"]) * 100.0 / status["buy"]
                if rate >= 0:
                    status["win"] = status["win"] + 1
                else:
                    status["lose"] = status["lose"] + 1
                operation["operator"] = "卖出"
                operation["trade_time"] = r["trade_time"] 
                operation["hand"] = status["hand"]
                operation["price"] = r["close"]
                operation["capital"] = 0
                operation["cash_flow"] = status["fund"]
                operation["strategy"] = desc
                operation["rate"] = rate
                status["operations"].append(operation)
                operation = {}
                status["hand"] = 0
                status["record"] = []

    return status


def back_test(code, records, path, mode, debug):
    status = backtesting(records, debug)

    for op in status["operations"]:
        print("操作 ", op["operator"])
        print("日期 ", op["trade_time"])
        print("股份 ", op["hand"], " 手")
        print("股价 ", op["price"])
        print("涨跌 %.2f%%" % (op["rate"]))
        print("持仓 ", op["capital"])
        print("现金 ", op["cash_flow"])
        print("策略 ", op["strategy"])
        if op["operator"] == "买入":
            print()
        else:
            print()
            print()
            print()

    capital = 0
    if len(status["operations"]) > 0:
        capital = status["operations"][-1]["capital"]

    print("============================")
    print("股票代码: %s\n量化策略: %s\n数据路径: %s" % (code, mode, path))
    print("涨跌: ", (status["fund"] + capital - status["base"]) * 100.0 / status["base"], "%")
    print("胜率: 总计 %d 轮操作, 取胜 %d 轮" % (status["win"] + status["lose"], status["win"]))
    print("============================")
    print()


def predict_buy(records, debug):
    r = records.iloc[-1]
    status = {}
    ok, desc = buy(r, status, debug)
    return ok, desc, r["trade_time"]


def excute(code, ktype, operate, mode, tuning, cond, path, date, debug):
    global strategy
    strategy = get_strategy(mode) 

    if path is None:
        path = f"{WORK_DIR}/data/{code}_{ktype}_data.csv"

    # 加载股票信息
    ok, stock = load_stock(code, cond, path, date, ktype)
    if not ok:
        msg = stock
        if debug: print(stock)
        return False

    # 数据预处理
    strategy.pretreatment(stock, operate, tuning, debug)
    records = stock["records"]

    # 回测
    if operate == "back_test":
        back_test(code, records, path, mode, debug)

    if operate == "buy":
        ok, desc, trade_time = predict_buy(records, debug)
        if ok:
            close = records.iloc[-1]["close"]
            print(f"推荐买入股票 %s, 代码 %s, 日期 %s, 最新股价 %s" % (stock["stock_name"], stock["stock_code"], trade_time, close))
            print(desc)


def get_codes_from_file(path):
    print("指定文件股票代码...")
    # 假设文件名是 data.txt
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 去掉每行的换行符
    lines = [line.strip() for line in lines]
    return lines


def predict(code, ktype, operate, mode, tuning, cond, path, target_date, debug, progress_callback=None):
    codes = []
    print("testing  ", mode)
    if code == "all":
        info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
        codes = [os.path.basename(f).split("_")[0] for f in info_files]
    elif "file" in code:
        file = code.split(",")[1]
        codes = get_codes_from_file(file)
    else:
        codes = code.split(",")

    idx = 1
    count = len(codes)
    for code in codes:
        # 🔹 新增：可选的回调函数
        if progress_callback:
            progress_callback(idx, count, code)

        idx = idx + 1
        try:
            excute(
                code,
                ktype,
                operate,
                mode,
                tuning,
                cond,
                path,
                target_date,
                debug
            )
        except Exception as e:
            print(f"⚠️ 股票 {code} 处理失败: {e}")



# ==========================
# 支持命令行直接调用
# ==========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='股票策略回测')

    parser.add_argument('-c', '--code', required=True, help='股票代码，例如: 000001.SZ')
    parser.add_argument('-k', '--ktype', type=int, default=1, help='k线类型，例如: 1,2,3')
    parser.add_argument('-m', '--mode', help='量化策略，例如: fish_tub')
    parser.add_argument('-o', '--operate', help='预测买入|预测卖出|回测')
    parser.add_argument('-t', '--tuning', help='股票过滤')
    parser.add_argument('-s', '--stock_cond', help='量化策略调优')
    parser.add_argument('-p', '--path', help='数据文件保存位置')
    parser.add_argument('-q', '--date', help='指定查询日期')
    parser.add_argument('-d', '--debug', help='调试模式')

    args = parser.parse_args()

    predict(
        args.code,
        args.ktype,
        args.operate,
        args.mode,
        args.tuning,
        args.stock_cond,
        args.path,
        args.date,
        args.debug,
    )


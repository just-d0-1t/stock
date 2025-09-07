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
import pandas as pd
import numpy as np
import strategy_hub.fish_tub as fish_tub
from glob import glob
from datetime import datetime, timedelta


strategy = None

WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径


def get_strategy(mode: str):
    """根据命令行参数选择策略模块"""
    mapping = {
        "fish_tub": fish_tub,
    }
    if mode not in mapping:
        raise ValueError(f"未知环境: {env}，仅支持 {list(mapping.keys())}")
    return mapping[mode]


# ==========================
# 执行策略函数
# ==========================
def buy(r, status, debug=False):
    for sid in status["buy_strategy"]:
        if sid in strategy.BUY_STRATEGIES:
            hit, desc = strategy.BUY_STRATEGIES[sid](r, status, debug)
            if hit:
                return True, desc
    return False, ""


def sell(r, status, debug=False):
    for sid in status["sell_strategy"]:
        if sid in strategy.SELL_STRATEGIES:
            hit, desc = strategy.SELL_STRATEGIES[sid](r, status, debug)
            if hit:
                return True, desc
    return False, ""


def backtesting(records, buy_strategy, sell_strategy, debug):
    fund = 10000

    # 股票持有状态
    status = {
        "sell_strategy": sell_strategy,
        "buy_strategy": buy_strategy,
        "should_buy": False,
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
        if idx < 21:
            continue

        if status["should_buy"]:
            # 可买入手数，100的整数倍
            status["hand"] = int(status["fund"] / r["open"] / 100) * 100
            # 持仓，扣除手续费
            capital = r["open"] * status["hand"]
            status["fund"] = status["fund"] - capital
            status["buy"] = r["open"]
            if capital * 0.00026 < 5:
                status["fund"] = status["fund"] - 5
            else:
                status["fund"] = status["fund"] - capital * 0.00026
            operation["trade_time"] = r["trade_time"] 
            operation["hand"] = status["hand"]
            operation["price"] = r["open"]
            operation["capital"] = capital
            operation["cash_flow"] = status["fund"]
            operation["rate"] = 0
            status["operations"].append(operation)
            operation = {}
            status["should_buy"] = False
            status["hold"] = True

        if not status["hold"]:
            ok, desc = buy(r, status, debug)
            if ok:
                status["should_buy"] = True
                status["record"].append(r)
                operation["trggier"] = r["trade_time"]
                operation["operator"] = "买入"
                operation["strategy"] = desc

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


def back_test(records, buy_strategy, sell_strategy, path, debug):
    status = backtesting(records, buy_strategy, sell_strategy, debug)

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

    print("============================")
    print("股票代码: %s\n量化策略: %s\n买入策略: %s\n卖出策略: %s\n数据路径: %s" % (code, mode, buy_strategy, sell_strategy, path))
    print("涨跌: ", (status["fund"] - status["base"]) * 100.0 / status["base"], "%")
    print("胜率: 总计 %d 轮操作, 取胜 %d 轮" % (status["win"] + status["lose"], status["win"]))
    print("============================")
    print()


def predict_buy(records, buy_strategy, sell_strategy, debug):
    r = records.iloc[-1]
    status = {
        "buy_strategy": buy_strategy,
    }
    ok, desc = buy(r, status, debug)
    return ok, desc, r["trade_time"]



def get_last_trading_days(today=None, n=2):
    """
    获取最近 n 个交易日（跳过周末）
    """
    if today is None:
        today = datetime.today().date()

    trading_days = []
    cur = today

    while len(trading_days) < n:
        cur -= timedelta(days=1)
        if cur.weekday() < 5:  # 0=Mon ... 4=Fri
            trading_days.append(cur)

    return trading_days


def is_last_two_trading_days(last_operation):
    """
    判断最后一次操作是否在上两个交易日
    """
    if not last_operation or "trade_time" not in last_operation:
        return False

    trade_time = datetime.strptime(last_operation["trade_time"], "%Y-%m-%d %H:%M:%S").date()
    today = datetime.today().date()

    last_two = get_last_trading_days(today, n=1)
    return trade_time in last_two


def predict_sell(records, buy_strategy, sell_strategy, debug):
    status = backtesting(records, buy_strategy, sell_strategy, debug)

    if len(status["operations"]) == 0:
        return False, ""

    last_operation = status["operations"][-1]

    if last_operation["operator"] == "卖出" and is_last_two_trading_days(last_operation):
        return True, last_operation["strategy"], last_operation["trade_time"]

    return False, "", ""
        

def excute(stock_code, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, debug):
    global strategy
    strategy = get_strategy(mode) 

    if path is None:
        path = f"{WORK_DIR}/data/{stock_code}_data.csv"

    # 加载股票信息
    ok, stock = strategy.load_stock(stock_code, mode_tuning, path)
    if not ok:
        msg = stock
        if debug: print(stock)
        return False

    records = stock["records"]
    buy_strategy = buy_strategy.split(",") if buy_strategy else []
    sell_strategy = sell_strategy.split(",") if sell_strategy else []

    # 回测
    if operate == "back_test":
        back_test(records, buy_strategy, sell_strategy, path, debug)

    if operate == "predict_buy":
        ok, desc, trade_time = predict_buy(records, buy_strategy, sell_strategy, debug)
        if ok:
            print(f"推荐买入股票 %s, 代码 %s, 日期 %s" % (stock["stock_name"], stock["stock_code"], trade_time))
            print(desc)
            print()

    if operate == "predict_sell":
        ok, desc, trade_time = predict_sell(records, buy_strategy, sell_strategy, debug)
        if ok:
            print(f"推荐卖出股票 %s, 代码 %s, 日期 %s" % (stock["stock_name"], stock["stock_code"], trade_time))
            print(desc)
            print()


def predict(stock_code, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, debug):
    stock_codes = []
    if stock_code == "all":
        info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
        stock_codes = [os.path.basename(f).split("_")[0] for f in info_files]
    else:
        stock_codes = stock_code.split(",")

    for code in stock_codes:
        excute(code, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, debug)


# ==========================
# 支持命令行直接调用
# ==========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='股票策略回测')

    parser.add_argument('-c', '--code', required=True, help='股票代码，例如: 000001.SZ')
    parser.add_argument('-m', '--mode', help='量化策略，例如: fish_tub')
    parser.add_argument('-o', '--operate', help='预测买入|预测卖出|回测')
    parser.add_argument('-t', '--tuning', help='量化策略调优')
    parser.add_argument('-b', '--buy', help='买入策略，例如: 1,2')
    parser.add_argument('-s', '--sell', help='卖出策略，例如: 1,6,7')
    parser.add_argument('-p', '--path', help='数据文件保存位置')
    parser.add_argument('-d', '--debug', help='调试模式')

    args = parser.parse_args()
    code = args.code
    operate = args.operate
    mode = args.mode
    mode_tuning = args.tuning
    buy_strategy = args.buy
    sell_strategy = args.sell
    path = args.path
    debug = args.debug

    predict(code, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, debug)


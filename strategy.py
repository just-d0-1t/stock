#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: strategy.py
@author: vanilla
@date: 2025-09-05
@desc: 股票回测策略脚本，支持多买卖策略组合和调试模式。
"""

import argparse
import os
import pandas as pd
import numpy as np
import strategy_hub.fish_tub as fish_tub


strategy = None

file_path = os.path.abspath(__file__)
dir_path = os.path.dirname(file_path)


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
                print(desc)
                return True
    return False


def sell(r, status, debug=False):
    for sid in status["sell_strategy"]:
        if sid in strategy.SELL_STRATEGIES:
            hit, desc = strategy.SELL_STRATEGIES[sid](r, status, debug)
            if hit:
                print(desc)
                return True
    return False


def excute(stock_code, mode, mode_tuning, buy_strategy, sell_strategy, path, debug):
    global strategy
    strategy = get_strategy(mode) 

    if path is None:
        path = dir_path + f"/data/{stock_code}_data.csv"

    records = strategy.load_data(stock_code, mode_tuning, path)

    fund = 10000

    # 股票持有状态
    status = {
        "sell_strategy": sell_strategy,
        "buy_strategy": buy_strategy,
        "should_buy": False,
        "hold": False,
        "buy": 0,
        "fund": fund,
        "lose": 0,
        "win": 0,
        "hand": 0,
        "days": 0,
        "record": []
    }
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
            print("日期 ", r["trade_time"])
            print("买入 ", status["hand"], " 手")
            print("股价 ", r["open"])
            print("持仓 ", capital)
            print("现金 ", status["fund"])
            status["should_buy"] = False
            status["hold"] = True
            print()

        if not status["hold"]:
            if buy(r, status, debug):
                status["should_buy"] = True
                status["record"].append(r)

        else:
            status["days"] = status["days"] + 1
            status["record"].append(r)
            if sell(r, status, debug):
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
                print("日期 ", r["trade_time"])
                print("卖出 ", status["hand"], " 手")
                print("股价 ", r["close"])
                print("涨跌 %.2f%%" % (rate))
                print("现金 ", status["fund"])
                status["hand"] = 0
                status["record"] = []
                print("\n\n")
    print("============================")
    print("股票代码: %s\n量化策略: %s\n买入策略: %s\n卖出策略: %s\n数据路径: %s" % (code, mode, buy_strategy, sell_strategy, path))
    print("涨跌: ", (status["fund"] - fund) * 100.0 / fund, "%")
    print("胜率: 总计 %d 轮操作, 取胜 %d 轮" % (status["win"] + status["lose"], status["win"]))
    print("============================")
    print()


# ==========================
# 支持命令行直接调用
# ==========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='股票策略回测')

    parser.add_argument('-c', '--code', required=True, help='股票代码，例如: 000001.SZ')
    parser.add_argument('-m', '--mode', help='量化策略，例如: fish_tub')
    parser.add_argument('-t', '--tuning', help='量化策略调优')
    parser.add_argument('-b', '--buy', help='买入策略，例如: 1,2')
    parser.add_argument('-s', '--sell', help='卖出策略，例如: 1,6,7')
    parser.add_argument('-p', '--path', help='数据文件保存位置')
    parser.add_argument('-d', '--debug', help='调试模式')

    args = parser.parse_args()
    code = args.code
    mode = args.mode
    mode_tuning = args.tuning
    buy_strategy = args.buy.split(",") if args.buy else []
    sell_strategy = args.sell.split(",") if args.sell else []
    path = args.path
    debug = args.debug

    excute(code, mode, mode_tuning, buy_strategy, sell_strategy, path, debug)


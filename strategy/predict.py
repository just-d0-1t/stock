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

from glob import glob
from datetime import datetime, timedelta

# 注册策略
import strategy.strategy_hub.fish_tub as fish_tub
mapping = {
    "fish_tub": fish_tub,
}

strategy = None

WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径


def get_strategy(mode: str):
    """根据命令行参数选择策略模块"""
    if mode not in mapping:
        raise ValueError(f"未知环境: {env}，仅支持 {list(mapping.keys())}")
    return mapping[mode]


# ==========================
# 执行策略函数
# ==========================
def eval_strategy(expr, r, status, strategies, debug=False):
    """
    递归解析表达式，支持:
    - "," 表示 OR
    - "+" 表示 AND
    """
    expr = expr.strip()

    # 优先级: AND (+) > OR (,)
    if "," in expr:  # 先处理 OR
        parts = expr.split(",")
        for part in parts:
            hit, desc = eval_strategy(part, r, status, strategies, debug)
            if hit:
                return hit, desc
        return False, ""

    if "+" in expr:  # 处理 AND
        parts = expr.split("+")
        results = []
        descs = []
        for part in parts:
            hit, desc = eval_strategy(part, r, status, strategies, debug)
            results.append(hit)
            descs.append(desc)
        return all(results), " AND ".join([d for h, d in zip(results, descs) if h])

    # 基础情况: 单个策略编号
    sid = expr
    if sid in strategies:
        return strategies[sid](r, status, debug)
    else:
        if debug:
            print(f"未知策略: {sid}")
        return False, ""

def buy(r, status, debug=False):
    return eval_strategy(status["buy_strategy"], r, status, strategy.BUY_STRATEGIES, debug)


def sell(r, status, debug=False):
    return eval_strategy(status["sell_strategy"], r, status, strategy.SELL_STRATEGIES, debug)


def backtesting(records, buy_strategy, sell_strategy, debug):
    fund = 10000

    # 股票持有状态
    status = {
        "sell_strategy": sell_strategy,
        "buy_strategy": buy_strategy,
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

        # # 隔日早盘买入的逻辑
        # if status["should_buy"]:
        #     # 可买入手数，100的整数倍
        #     status["hand"] = int(status["fund"] / r["open"] / 100) * 100
        #     # 持仓，扣除手续费
        #     capital = r["open"] * status["hand"]
        #     status["fund"] = status["fund"] - capital
        #     status["buy"] = r["open"]
        #     if capital * 0.00026 < 5:
        #         status["fund"] = status["fund"] - 5
        #     else:
        #         status["fund"] = status["fund"] - capital * 0.00026
        #     operation["trade_time"] = r["trade_time"] 
        #     operation["hand"] = status["hand"]
        #     operation["price"] = r["open"]
        #     operation["capital"] = capital
        #     operation["cash_flow"] = status["fund"]
        #     operation["rate"] = 0
        #     status["operations"].append(operation)
        #     operation = {}
        #     status["should_buy"] = False
        #     status["hold"] = True

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


def back_test(code, records, buy_strategy, sell_strategy, path, debug):
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

    capital = 0
    if len(status["operations"]) > 0:
        capital = status["operations"][-1]["capital"]

    print("============================")
    print("股票代码: %s\n量化策略: %s\n买入策略: %s\n卖出策略: %s\n数据路径: %s" % (code, mode, buy_strategy, sell_strategy, path))
    print("涨跌: ", (status["fund"] + capital - status["base"]) * 100.0 / status["base"], "%")
    print("胜率: 总计 %d 轮操作, 取胜 %d 轮" % (status["win"] + status["lose"], status["win"]))
    print("============================")
    print()


def predict_buy(records, buy_strategy, sell_strategy, target_date, debug):
    r = records.iloc[-1]

    if target_date:
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        rs = records[records["trade_date"].dt.date == target_date]
        if len(rs) == 0:
            return False, "无匹配的日期", target_date
        r = rs.iloc[0]

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
        

def excute(stock_code, ktype, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, target_date, debug):
    global strategy
    strategy = get_strategy(mode) 

    if path is None:
        path = f"{WORK_DIR}/data/{stock_code}_{ktype}_data.csv"

    # 加载股票信息
    ok, stock = strategy.load_stock(stock_code, mode_tuning, path, ktype)
    if not ok:
        msg = stock
        if debug: print(stock)
        return False

    records = stock["records"]
    buy_strategy = buy_strategy
    sell_strategy = sell_strategy

    # 回测
    if operate == "back_test":
        if buy_strategy is None or sell_strategy is None:
            print(f"回测必须指定买入策略{buy_strategy}，和卖出策略{sell_strategy}") 
            return
        back_test(stock_code, records, buy_strategy, sell_strategy, path, debug)

    if operate == "buy":
        if buy_strategy is None:
            print(f"预测买入必须指定买入策略{buy_strategy}") 
            return
        ok, desc, trade_time = predict_buy(records, buy_strategy, sell_strategy, target_date, debug)
        if ok:
            print(f"推荐买入股票 %s, 代码 %s, 日期 %s" % (stock["stock_name"], stock["stock_code"], trade_time))
            print(desc)
            print()

    if operate == "sell":
        if buy_strategy is None:
            print(f"预测卖出必须指定卖出策略{sell_strategy}") 
            return
        ok, desc, trade_time = predict_sell(records, buy_strategy, sell_strategy, debug)
        if ok:
            print(f"推荐卖出股票 %s, 代码 %s, 日期 %s" % (stock["stock_name"], stock["stock_code"], trade_time))
            print(desc)
            print()


def get_codes_from_file(path):
    print("指定文件股票代码...")
    # 假设文件名是 data.txt
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 去掉每行的换行符
    lines = [line.strip() for line in lines]
    return lines


def predict(stock_code, ktype, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, target_date, debug):
    stock_codes = []
    if stock_code == "all":
        info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
        stock_codes = [os.path.basename(f).split("_")[0] for f in info_files]
    elif "file" in stock_code:
        file = stock_code.split(",")[1]
        stock_codes = get_codes_from_file(file)
    else:
        stock_codes = stock_code.split(",")

    for code in stock_codes:
        excute(code, ktype, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, target_date, debug)


# ==========================
# 支持命令行直接调用
# ==========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='股票策略回测')

    parser.add_argument('-c', '--code', required=True, help='股票代码，例如: 000001.SZ')
    parser.add_argument('-k', '--ktype', type=int, default=1, help='k线类型，例如: 1,2,3')
    parser.add_argument('-m', '--mode', help='量化策略，例如: fish_tub')
    parser.add_argument('-o', '--operate', help='预测买入|预测卖出|回测')
    parser.add_argument('-t', '--tuning', help='量化策略调优')
    parser.add_argument('-b', '--buy', help='买入策略，例如: 1,2')
    parser.add_argument('-s', '--sell', help='卖出策略，例如: 1,6,7')
    parser.add_argument('-p', '--path', help='数据文件保存位置')
    parser.add_argument('-q', '--date', help='指定查询日期')
    parser.add_argument('-d', '--debug', help='调试模式')

    args = parser.parse_args()
    code = args.code
    ktype = args.ktype
    operate = args.operate
    mode = args.mode
    mode_tuning = args.tuning
    buy_strategy = args.buy
    sell_strategy = args.sell
    path = args.path
    target_date = args.date
    debug = args.debug

    predict(code, ktype, operate, mode, mode_tuning, buy_strategy, sell_strategy, path, target_date, debug)


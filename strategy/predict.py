#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: backtest.py
@author: vanilla
@date: 2025-09-05
@desc: 股票回测策略脚本，线程/窗口安全，支持多买卖策略组合、调试模式、前端日志回调。
"""

import os
import re
import pickle
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
import strategy.strategy_hub.volumn_break as volumn_break
import strategy.strategy_hub.low_volumn_pullback as low_volumn_pullback
import strategy.strategy_hub.ma120_pullback as ma120_pullback

mapping = {
    "kdj": kdj,
    "kdj_ready": kdj_ready,
    "fish_tub": fish_tub,
    "volumn_detect": volumn_detect,
    "volumn_break": volumn_break,
    "low_volumn_pullback": low_volumn_pullback,
    "ma120_pullback": ma120_pullback,
}

WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径

# ===============================
# Predictor 类
# ===============================
class Predictor:
    def __init__(self, mode, log_callback=None, stop_flag=None):
        if mode not in mapping:
            raise ValueError(f"未知策略: {mode}, 支持: {list(mapping.keys())}")
        self.strategy_module = mapping[mode]
        self.log = log_callback or print
        self.stop_flag = stop_flag

    # -------------------- 内部 buy/sell 调用 --------------------
    def buy(self, r, status, debug=False):
        return self.strategy_module.buy(r, status, debug)

    def sell(self, r, status, debug=False):
        return self.strategy_module.sell(r, status, debug)

    # -------------------- 回测函数 --------------------
    def backtesting(self, records, debug=False):
        fund = 10000
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
            if self.stop_flag and self.stop_flag.is_set():
                self.log(">>> 用户终止任务")
                return status

            if idx < 21:
                continue

            if not status["hold"]:
                ok, desc = self.buy(r, status, debug)
                if ok:
                    status["should_buy"] = True
                    status["record"].append(r)
                    operation["operator"] = "买入"
                    operation["strategy"] = desc
                    status["hand"] = int(status["fund"] / r["close"] / 100) * 100
                    capital = r["close"] * status["hand"]
                    status["fund"] -= capital
                    status["fund"] -= min(capital * 0.00026, 5)
                    status["buy"] = r["close"]
                    operation["trade_date"] = r["trade_date"]
                    operation["hand"] = status["hand"]
                    operation["price"] = r["close"]
                    operation["capital"] = capital
                    operation["cash_flow"] = status["fund"]
                    operation["rate"] = 0
                    status["operations"].append(operation)
                    operation = {}
                    status["hold"] = True

            else:
                status["days"] += 1
                status["record"].append(r)
                ok, desc = self.sell(r, status, debug)
                if ok:
                    status["hold"] = False
                    status["days"] = 0
                    capital = status["hand"] * r["close"]
                    status["fund"] += capital
                    status["fund"] -= min(capital * 0.00026, 5)
                    rate = (r["close"] - status["buy"]) * 100.0 / status["buy"]
                    if rate >= 0:
                        status["win"] += 1
                    else:
                        status["lose"] += 1
                    operation["operator"] = "卖出"
                    operation["trade_date"] = r["trade_date"]
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

    # -------------------- 执行股票任务 --------------------
    def excute(self, code, ktype, operate, tuning, cond, path, target_date, debug=False):
        # 加载股票数据
        ok, stock = load_stock(code, cond, path, target_date, ktype)
        if not ok:
            if debug:
                self.log(f"⚠️ 股票 {code} 数据加载失败: {stock}")
            return False, ""

        # 数据预处理
        self.strategy_module.pretreatment(stock, operate, tuning, debug)
        records = stock["records"]

        if operate == "back_test":
            status = self.backtesting(records, debug)
            # 输出操作日志
            for op in status["operations"]:
                op_str = (
                    f"操作 {op['operator']}\n"
                    f"日期 {op['trade_date']}\n"
                    f"股份 {op['hand']} 手\n"
                    f"股价 {op['price']}\n"
                    f"涨跌 {op['rate']:.2f}%\n"
                    f"持仓 {op['capital']}\n"
                    f"现金 {op['cash_flow']}\n"
                    f"策略 {op['strategy']}\n\n"
                )
                self.log(op_str)
            capital = status["operations"][-1]["capital"] if status["operations"] else 0
            summary = (
                f"========= summary ===========\n"
                f"代码: {code}\n"
                f"名称: {stock['name']}\n"
                f"量化策略: {self.strategy_module.__name__}\n"
                f"数据路径: {path}\n"
                f"涨跌: {(status['fund'] + capital - status['base']) * 100.0 / status['base']:.2f}%\n"
                f"胜率: 总计 {status['win'] + status['lose']} 轮操作, 取胜 {status['win']} 轮\n"
                f"============================\n"
            )
            self.log(summary)
            return True, summary

        elif operate == "buy":
            r = records.iloc[-1]
            ok, desc = self.buy(r, {}, debug)
            if ok:
                close = r["close"]
                market = round(stock['market_cap'] / 10000 / 10000, 2)
                amount = round(stock['amount'] / 10000 / 10000, 2)
                rise = round((close - r["open"]) * 100 / r["open"], 2)
                res = f"推荐买入股票 {stock['name']}, 代码 {stock['code']}, 日期 {r['trade_date']}, 最新股价 {close}, 市值 {market} 亿, 昨日成交额 {amount} 亿, 当日涨幅 {rise}% \n{desc}\n"
                self.log(res)
                return True, res

        return False, ""

    # -------------------- 主 predict 函数 --------------------
    def predict(self, code, ktype, operate, tuning="", cond=None, path=None, target_date=None, debug=False, cache=False, progress_callback=None):
        codes = []
        if code == "all":
            info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
            codes = [os.path.basename(f).split("_")[0] for f in info_files]
        elif "file" in code:
            file = code.split(",")[1]
            codes = self.get_codes_from_file(file)
        else:
            codes = code.split(",")

        total = len(codes)
        results = []

        for idx, c in enumerate(codes, start=1):
            if self.stop_flag and self.stop_flag.is_set():
                self.log(">>> 用户终止任务")
                break

            if progress_callback:
                progress_callback(idx, total, c)

            ok, res = self.excute(c, ktype, operate, tuning, cond, path, target_date, debug)
            if ok and res:
                results.append(res)

        return results

    @staticmethod
    def get_codes_from_file(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines()]
        return lines

# ===============================
# 命令行支持
# ===============================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="股票策略回测")

    parser.add_argument("-c", "--code", required=True)
    parser.add_argument("-k", "--ktype", type=int, default=1)
    parser.add_argument("-m", "--mode", required=True)
    parser.add_argument("-o", "--operate", required=True)
    parser.add_argument("-t", "--tuning", default="")
    parser.add_argument("-s", "--stock_cond", default="")
    parser.add_argument("-p", "--path")
    parser.add_argument("-q", "--date")
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-u", "--use_cache", type=bool, default=False)

    args = parser.parse_args()

    predictor = Predictor(args.mode)
    predictor.predict(args.code, args.ktype, args.operate, args.tuning, args.stock_cond, args.path, args.date, args.debug, args.use_cache)


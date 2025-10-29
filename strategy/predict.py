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

    result_str = ""

    for op in status["operations"]:
        op_str = f"""操作 {op["operator"]}
日期 {op["trade_time"]}
股份 {op["hand"]} 手
股价 {op["price"]}
涨跌 {op["rate"]:.2f}%
持仓 {op["capital"]}
现金 {op["cash_flow"]}
策略 {op["strategy"]}
"""
        if op["operator"] == "买入":
            op_str += "\n"
        else:
            op_str += "\n\n\n"
        
        print(op_str, end="")
        result_str += op_str

    capital = 0
    if len(status["operations"]) > 0:
        capital = status["operations"][-1]["capital"]

    summary = f"""============================
股票代码: {code}
量化策略: {mode}
数据路径: {path}
涨跌: {(status["fund"] + capital - status["base"]) * 100.0 / status["base"]}%
胜率: 总计 {status["win"] + status["lose"]} 轮操作, 取胜 {status["win"]} 轮
============================

"""
    print(summary, end="")
    result_str += summary
    
    return result_str


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
        return False, ""

    # 数据预处理
    strategy.pretreatment(stock, operate, tuning, debug)
    records = stock["records"]

    # 回测
    if operate == "back_test":
        res = back_test(code, records, path, mode, debug)
        return True, res

    if operate == "buy":
        ok, desc, trade_time = predict_buy(records, debug)
        if ok:
            close = records.iloc[-1]["close"]
            res = f"推荐买入股票 %s, 代码 %s, 日期 %s, 最新股价 %s\n%s\n" % (stock["stock_name"], stock["stock_code"], trade_time, close, desc)
            print(res)
            return True, res

    return False, ""


def get_codes_from_file(path):
    print("指定文件股票代码...")
    # 假设文件名是 data.txt
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 去掉每行的换行符
    lines = [line.strip() for line in lines]
    return lines


def predict(code, ktype, operate, mode, tuning, cond, path, target_date, debug, cache, progress_callback=None, stop_flag=None):
    # 生成缓存文件名
    cache_base = os.path.join(DATA_DIR, "cache")
    cache_filename = generate_cache_filename(code, ktype, operate, mode, tuning, cond, path, target_date)
    cache_filepath = os.path.join(cache_base, cache_filename)
    
    # 如果cache为真且缓存文件存在，则读取缓存
    if operate == "buy" and cache and os.path.exists(cache_filepath):
        try:
            with open(cache_filepath, 'r', encoding="utf-8") as f:
                cached_results = f.read()
            print(f"📁 从缓存读取结果: {cached_results}")
            return cached_results, cache_filepath
        except Exception as e:
            print(f"⚠️ 读取缓存失败: {e}")
    
    codes = []
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
    results = []
    for code in codes:
        if progress_callback:
            progress_callback(idx, count, code)
        idx = idx + 1

        if stop_flag and stop_flag.is_set():
            print(">>> 用户终止任务")
            return

        try:
            ok, res = excute(
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
            if ok:
                results.append(res)
        except Exception as e:
            print(f"⚠️ 股票 {code} 处理失败: {e}")
            return None, cache_filepath

    if operate == "buy":
        try:
            os.makedirs(cache_base, exist_ok=True)
            with open(cache_filepath, 'w', encoding='utf-8') as f:
                for result in results:
                    f.write(str(result) + '\n')
            print(f"💾 结果已缓存到: {cache_filename}")
        except Exception as e:
            print(f"⚠️ 缓存保存失败: {e}")
            return None, cache_filepath

    return results, cache_filepath

def generate_cache_filename(code, ktype, operate, mode, tuning, cond, path, target_date):
    """生成缓存文件名"""
    # 如果日期为空，使用上一个工作日
    if not target_date:
        target_date = get_previous_workday()
    
    # 根据参数组合生成文件名
    params = {
        'code': code,
        'ktype': ktype,
        'operate': operate,
        'mode': mode,
        'tuning': tuning,
        'cond': cond,
        'path': os.path.basename(path) if path else '',
        'date': target_date
    }
    
    # 创建文件名哈希或直接拼接关键参数
    filename_parts = []
    for key, value in params.items():
        if value:  # 只包含非空参数
            # 简化参数值，避免文件名过长
            simplified_value = str(value).replace('/', '_').replace('\\', '_')[:20]
            filename_parts.append(f"{key}_{simplified_value}")
    
    filename = "_".join(filename_parts) + ".pkl"
    return filename

def get_previous_workday():
    """获取上一个工作日"""
    today = datetime.now()
    # 简单的实现，假设工作日是周一到周五
    if today.weekday() == 0:  # 周一
        previous_day = today - timedelta(days=3)  # 上周五
    else:
        previous_day = today - timedelta(days=1)
    
    return previous_day.strftime("%Y%m%d")


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
    parser.add_argument('-u', '--use_cache', type=bool, default=False, help='use cache')

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
        args.use_cache,
    )


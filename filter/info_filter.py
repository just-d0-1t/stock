#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
按个股信息（市值/成交额）筛选股票，输出代码清单，供 predict 前使用。

市值 = 上一交易日收盘价 × 最新流通A股股本（list_a_shares）。
predict 本身不再做市值/成交额过滤，只消费这里产出的代码清单：

  python filter/info_filter.py --market 10000000000 --out data/filtered.code
  python strategy/predict.py -c "file,data/filtered.code" -m limit_up_pullback -o buy
"""

import argparse
import glob
import os
import pandas as pd
import utils.config as config


def load_latest_info(code, typ="1"):
    """读取个股信息文件，返回按 change_date 排序后的最新一行；缺失返回 None"""
    path = config.default_info_path(code, typ)
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, parse_dates=["list_date", "change_date"], dtype={"recent_kdj_gold": str})
    return df.sort_values("change_date").iloc[-1]


def market_cap(code, typ="1"):
    """上一交易日收盘价 × 最新流通A股股本（元）"""
    info = load_latest_info(code, typ)
    data_path = config.default_data_path(code, typ)
    if info is None or "list_a_shares" not in info or not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path, usecols=["close"])
    if len(df) < 2:
        return None
    return df["close"].iloc[-2] * info["list_a_shares"]


def last_amount(code, typ="1"):
    """上一交易日成交额（元）"""
    data_path = config.default_data_path(code, typ)
    if not os.path.exists(data_path):
        return None
    df = pd.read_csv(data_path, usecols=["amount"])
    if len(df) < 2:
        return None
    return df["amount"].iloc[-2]


def filter_codes(market=0, amount=0, typ="1"):
    """按市值/成交额过滤，返回满足条件的代码清单"""
    info_files = glob.glob(os.path.join(config.DATA_DIR, f"*_{typ}_info.csv"))
    codes = []
    for f in info_files:
        code = os.path.basename(f).split("_")[0]
        mc = market_cap(code, typ)
        if mc is None or mc < market:
            continue
        if amount > 0:
            amt = last_amount(code, typ)
            if amt is None or amt < amount:
                continue
        codes.append(code)
    return sorted(codes)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="按市值/成交额筛选股票代码（predict 前置）")
    parser.add_argument("--market", type=float, default=0, help="最低市值（元），如 1e10 表示 100 亿")
    parser.add_argument("--amount", type=float, default=0, help="最低成交额（元）")
    parser.add_argument("-t", "--typ", default="1", help="数据类型 1:股票")
    parser.add_argument("-o", "--out", default="data/filtered.code", help="输出代码清单文件")
    args = parser.parse_args()

    codes = filter_codes(args.market, args.amount, args.typ)
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(codes))
    print(f"筛选出 {len(codes)} 只股票，已写入 {args.out}")
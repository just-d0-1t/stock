#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: all_stock_market.py
@author: vanilla
@date: 2025-09-08
@desc: 更新所有股票数据。
"""

import adata
from update_and_plot import update_and_plot
from update_stock import update
import time
import os
from glob import glob
import argparse


WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")
DATA_DIR = f"{WORK_DIR}/data"  # 本地数据路径


def get_codes_from_local():
    print("从本地获取A股股票代码...")
    stock_codes = []
    info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
    stock_codes = [os.path.basename(f).split("_")[0] for f in info_files]
    return stock_codes


def get_codes_from_remote():
    print("获取所有A股股票代码...")
    res_df = adata.stock.info.all_code()

    # 过滤掉没有上市日期的股票（可选）
    res_df = res_df[res_df['list_date'].notna()]
    stock_codes = res_df['stock_code'].tolist()
    return stock_codes


def get_codes_from_file(path):
    print("指定文件股票代码...")
    # 假设文件名是 data.txt
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # 去掉每行的换行符
    lines = [line.strip() for line in lines]
    return lines
    

def update_codes(fetch, ktype, path, update_only, delay):
    stock_codes = []
    if fetch == 'remote':
        stock_codes = get_codes_from_remote()
    elif fetch == 'file':
        stock_codes = get_codes_from_file(path)
    else:
        stock_codes = get_codes_from_local()
        
    # 1. 获取所有大A股票代码
    print(f"共获取 {len(stock_codes)} 只股票")

    if delay is None:
        delay = 1

    # 2. 遍历股票，更新数据并生成图表
    for idx, code in enumerate(stock_codes, start=1):
        try:
            time.sleep(delay)  # 1秒延时
            print(f"\n[{idx}/{len(stock_codes)}] 正在处理股票: {code}")
            if update_only:
                update(code, None, None, ktype)
            else:
                update_and_plot(code, None, None, ktype)  # 使用默认历史文件路径
            # 为防止接口请求过快，可加延时
        except Exception as e:
            print(f"⚠️ 股票 {code} 处理失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='更新所有股票数据')
    parser.add_argument('-f', '--fetch', required=True, help='指定数据源，local|remote')
    parser.add_argument('-p', '--path', help='指定数据文件')
    parser.add_argument('-k', '--ktype', type=int, default=1, help='k线类型')
    parser.add_argument('-d', '--delay', type=float, help='指定延迟')
    parser.add_argument('-u', '--update', help='仅更新数据')
    args = parser.parse_args()
    update_codes(args.fetch, args.ktype, args.path, args.update, args.delay)


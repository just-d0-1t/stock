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
    

def update(fetch):
    stock_codes = []
    if fetch == 'remote':
        stock_codes = get_codes_from_remote()
    else:
        stock_codes = get_codes_from_local()
        
    # 1. 获取所有大A股票代码
    print(f"共获取 {len(stock_codes)} 只股票")

    # 2. 遍历股票，更新数据并生成图表
    for idx, code in enumerate(stock_codes, start=1):
        try:
            print(f"\n[{idx}/{len(stock_codes)}] 正在处理股票: {code}")
            update_and_plot(code, None)  # 使用默认历史文件路径
            # 为防止接口请求过快，可加延时
            time.sleep(1)  # 1秒延时
        except Exception as e:
            print(f"⚠️ 股票 {code} 处理失败: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='更新所有股票数据')
    parser.add_argument('-f', '--fetch', required=True, help='指定数据源，local|remote')
    args = parser.parse_args()
    update(args.fetch)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: all_stock_market_concurrent.py
@author: vanilla
@date: 2025-09-12
@desc: 并发更新所有股票数据，支持控制并发数。
"""

import adata
from update.plot_stock import plot
from update.update_stock import update
import time
import os
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import utils.config as config



def get_codes_from_remote():
    res_df = adata.stock.info.all_code()
    res_df = res_df[res_df['list_date'].notna()]  # 过滤未上市股票
    return res_df['stock_code'].tolist()


def get_codes_from_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def process_code(code, idx, total, ktype, update_only, delay):
    """单只股票处理逻辑"""
    try:
        if delay:
            time.sleep(delay)
        print(f"\n[{idx}/{total}] 正在处理股票: {code}")
        update(code, None, None, None, ktype)
        if not update_only:
            plot(code, ktype, 90)
            plot(code, ktype, 365)
            plot(code, ktype, 730)
        return f"✅ {code} 成功"
    except Exception as e:
        return f"⚠️ 股票 {code} 处理失败: {e}"


def update_codes(fetch, ktype, path, update_only, delay, workers):
    if fetch == 'remote':
        print("获取所有A股股票代码...")
        stock_codes = get_codes_from_remote()
    elif fetch == 'file':
        print(f"指定文件股票代码: {path}")
        stock_codes = get_codes_from_file(path)
    else:
        print("从本地获取A股股票代码...")
        stock_codes = config.get_codes_from_local()

    print(f"共获取 {len(stock_codes)} 只股票")

    # 并发执行
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_code = {
            executor.submit(process_code, code, idx, len(stock_codes), ktype, update_only, delay): code
            for idx, code in enumerate(stock_codes, start=1)
        }
        for future in as_completed(future_to_code):
            result = future.result()
            print(result)
            results.append(result)

    print("\n处理完成！")
    print(f"成功 {sum('✅' in r for r in results)} 只，失败 {sum('⚠️' in r for r in results)} 只。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='并发更新所有股票数据')
    parser.add_argument('-f', '--fetch', required=True, help='指定数据源，local|remote|file')
    parser.add_argument('-p', '--path', help='指定数据文件')
    parser.add_argument('-k', '--ktype', type=int, default=1, help='k线类型')
    parser.add_argument('-d', '--delay', type=float, default=0, help='请求间延迟（秒）')
    parser.add_argument('-u', '--update', action='store_true', help='仅更新数据，不生成图表')
    parser.add_argument('-w', '--workers', type=int, default=5, help='并发线程数')
    args = parser.parse_args()

    update_codes(args.fetch, args.ktype, args.path, args.update, args.delay, args.workers)


#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: plot.py
@author: vanilla
@date: 2025-09-07
@desc: 绘制股票K线图。
"""

import argparse
import os
import pandas as pd
from datetime import datetime, timedelta
import mplfinance as mpf

SAVE_DIR = "/usr/local/openresty/nginx/html/download/"
WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)


def plot_kline(df, stock_code, ktype, period_days, end_date = None, save_dir=SAVE_DIR):
    """
    绘制股票K线图 + MA20 + 量比（A股风格：涨红跌绿）
    df: DataFrame，必须包含 open, high, low, close, volume, trade_date, volume_ratio
    period_days: int，最近多少天绘制
    """
    ensure_dir(save_dir)

    # 计算起始日期
    if end_date:
        end_date = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end_date = df["trade_date"].max()
    start_date = end_date - timedelta(days=period_days)

    # 选取绘图区间
    # df_period = df[df["trade_date"] >= start_date].copy()
    df_period = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)].copy()
    df_period.set_index("trade_date", inplace=True)

    # K线需要的数据
    ohlc = df_period[["open", "high", "low", "close", "volume"]]

    # A股风格：涨红跌绿
    mc = mpf.make_marketcolors(
        up='red',
        down='green',
        edge='inherit',
        wick='inherit',
        volume='inherit'
    )
    style = mpf.make_mpf_style(marketcolors=mc)

    # 量比曲线（右轴，线条更细）
    add_plots = [
        mpf.make_addplot(
            df_period["volume_ratio"],
            panel=1,
            color='blue',
            width=0.8,        # 线条更细
            secondary_y=True  # 右边Y轴
        )
    ]

    # 输出路径
    save_path = os.path.join(save_dir, f"{stock_code}_{ktype}_kline_{period_days}d.png")

    # 绘制并保存（高分辨率）
    mpf.plot(
        ohlc,
        type='candle',
        mav=(5,10,20),
        volume=True,
        style=style,
        title=f"{stock_code} 近{period_days}日 K线 + MA20 + 量比",
        figsize=(12, 8),
        addplot=add_plots,
        panel_ratios=(3, 1),
        savefig=dict(fname=save_path, dpi=300, bbox_inches="tight")  # 高分辨率保存
    )

    print(f"✅ 已保存高清图表: {save_path}")


def load_data(stock_code, data_path=None):
    if not os.path.exists(data_path):
        return None

    df = pd.read_csv(
        data_path,
        parse_dates=["trade_date"],
        dtype={"stock_code": str}  # ⭐ 保证股票代码是字符串
    )
    df.sort_values("trade_date", inplace=True)

    return df


def plot(stock_code, period, end_date, path, save_dir):
    if path is None:
        path = f"{WORK_DIR}/data/{stock_code}_data.csv"

    df = load_data(stock_code, path)
    if df is None:
        print("未读取到数据!!!")

    if save_dir is None:
        save_dir = SAVE_DIR

    plot_kline(df, stock_code, period, end_date, save_dir)


# 支持命令行直接调用
if __name__ == "__main__":
    # 创建参数解析器
    parser = argparse.ArgumentParser(description='绘制股票K线')

    # 添加命令行参数
    parser.add_argument('-c', '--code', required=True,
                        help='股票代码，例如: 000001.SZ')
    parser.add_argument('-k', '--ktype', required=True, type=int,
                        help='k线类型')
    parser.add_argument('-e', '--end',
                        help='终点日期，格式: YYYY-MM-DD，默认为今天')
    parser.add_argument('-d', '--days', required=True,
                        type=int,
                        help='绘制天数')
    parser.add_argument('-p', '--path',
                        help='绘制天数')
    parser.add_argument('-s', '--save',
                        help='数据文件保存位置')

    # 解析参数
    args = parser.parse_args()
    plot(args.code, arsg.ktype, args.days, args.end, args.path, args.save)

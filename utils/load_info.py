import os
import pandas as pd
import utils.config as config


def load_stock_data(code, path, ktype=1):
    """读取单只股票的 info 和 data 文件，计算市值"""
    info_file = config.default_info_path(code, ktype)
    data_file = config.default_data_path(code, ktype)
    if path:
        data_file = path

    if not os.path.exists(info_file) or not os.path.exists(data_file):
        return None

    # 读取 info
    df_info = pd.read_csv(
        info_file,
        parse_dates=["list_date", "change_date"],
        dtype={
            "recent_kdj_gold": str
        }
    )
    # 获取最新股本记录
    latest_info = df_info.sort_values("change_date").iloc[-1]

    # 读取 data
    df_data = pd.read_csv(data_file, parse_dates=["trade_date"])
    df_data = df_data.sort_values("trade_date").reset_index(drop=True)

    if len(df_data) < 2:
        return None  # 数据不足两天

    # 计算市值（上一日收盘价 * 最新流通A股股本）
    prev_close = df_data.loc[len(df_data)-2, "close"]
    amount = df_data.loc[len(df_data)-2, "amount"]
    market_cap = prev_close * latest_info["list_a_shares"]

    return {
        "code": code,
        "name": df_info.iloc[-1]["short_name"],
        "info": df_info,
        "exchange": latest_info["exchange"],
        "market_cap": market_cap,
        "records": df_data,
        "amount": amount,
    }

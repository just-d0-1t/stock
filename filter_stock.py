import os
import pandas as pd
from glob import glob

DATA_DIR = "./data"  # 本地数据路径
TARGET_MARKET_CAP = 500e8  # 500亿，单位为元

def load_stock(stock_code):
    """读取单只股票的 info 和 data 文件，计算市值"""
    info_file = os.path.join(DATA_DIR, f"{stock_code}_info.csv")
    data_file = os.path.join(DATA_DIR, f"{stock_code}_data.csv")

    if not os.path.exists(info_file) or not os.path.exists(data_file):
        return None

    # 读取 info
    df_info = pd.read_csv(info_file, parse_dates=["list_date", "change_date"], dtype={"stock_code": str})
    # 获取最新股本记录
    latest_info = df_info.sort_values("change_date").iloc[-1]

    # 读取 data
    df_data = pd.read_csv(data_file, parse_dates=["trade_date"], dtype={"stock_code": str})
    df_data = df_data.sort_values("trade_date").reset_index(drop=True)

    if len(df_data) < 2:
        return None  # 数据不足两天

    # 计算市值（上一日收盘价 * 最新流通A股股本）
    prev_close = df_data.loc[len(df_data)-2, "close"]
    market_cap = prev_close * latest_info["list_a_shares"]

    return {
        "stock_code": stock_code,
        "short_name": latest_info["short_name"],
        "exchange": latest_info["exchange"],
        "market_cap": market_cap,
        "data": df_data
    }

def is_first_cross_ma20(df):
#    """判断前两个交易日是否收盘价首次超过 MA20"""
#    df_recent = df.tail(2)
#    crosses = df_recent["close"] > df_recent["ma20"]
#    # 首次突破：前一天没有突破，当前突破
#    return crosses.iloc[-1] and not crosses.iloc[-2]
    """
    判断最近两个交易日，是否满足：
    - 前一天 first_above_ma20 == 'y'
    - 当日收盘价继续在 MA20 之上
    """
    if df.empty or len(df) < 2:
        return False

    df_recent = df.tail(2)
    prev_row = df_recent.iloc[0]

    return prev_row.get("first_above_ma20", "").lower() == "y"

def main():
    # 获取所有 info 文件对应的股票代码
    info_files = glob(os.path.join(DATA_DIR, "*_info.csv"))
    stock_codes = [os.path.basename(f).split("_")[0] for f in info_files]

    target_stocks = []

    for code in stock_codes:
        stock = load_stock(code)
        if stock is None:
            continue

        # 条件1：市值大于 500亿
        if stock["market_cap"] < TARGET_MARKET_CAP:
            continue

        # 条件2：前两个交易日收盘价首次超过 MA20
        df_data = stock["data"]
        if len(df_data) >= 2 and is_first_cross_ma20(df_data):
            target_stocks.append({
                "stock_code": stock["stock_code"],
                "short_name": stock["short_name"],
                "exchange": stock["exchange"],
                "market_cap": stock["market_cap"]
            })

    # 输出结果
    result_df = pd.DataFrame(target_stocks)
    print("符合条件的股票：")
    print(result_df)

if __name__ == "__main__":
    main()


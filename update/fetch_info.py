import adata
import pandas as pd
import time
import argparse
import os
import utils.config as config

def save_data(df: pd.DataFrame, data_path):
    """以覆盖方式写入 CSV，并保持股票代码为字符串"""
    # 确保 stock_code 列为字符串
    df["stock_code"] = df["stock_code"].astype(str)
    # 创建目录
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    # 写入 CSV，覆盖写入
    df.to_csv(data_path, index=False, mode="w", encoding="utf-8-sig")

def fetch():
    # 1. 获取所有大A股票代码
    print("获取所有A股股票代码...")
    try:
        res_df = adata.stock.info.all_code()
        # 过滤掉没有上市日期的股票（可选）
        res_df = res_df[res_df['list_date'].notna()]
    except Exception as e:
        print(f"获取股票失败: {e}")
        return

    if res_df.empty:
        print("未获取到任何股票数据。")
        return

    # 确保 stock_code 是字符串类型
    res_df["stock_code"] = res_df["stock_code"].astype(str)

    total = len(res_df)
    print(f"共获取 {total} 只股票，开始逐个保存...")

    for idx, row in res_df.iterrows():
        stock_code = row["stock_code"]
        try:
            # 构造单只股票的 DataFrame（一行）
            single_df = pd.DataFrame([row])
            # 获取存储路径
            data_path = config.get_default_info_path(stock_code)
            # 保存
            save_data(single_df, data_path)
            if (idx + 1) % 50 == 0 or idx + 1 == total:
                print(f"已保存 {idx + 1}/{total} 只股票...")
        except Exception as e:
            print(f"保存股票 {stock_code} 失败: {e}")
            continue

    print("所有股票信息保存完成。")

if __name__ == "__main__":
    fetch()

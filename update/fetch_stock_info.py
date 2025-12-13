import adata
import pandas as pd
import time
import argparse
import os
import utils.config as config
from concurrent.futures import ThreadPoolExecutor, as_completed



def save_data(df: pd.DataFrame, data_path):
    """以追加方式写入 CSV，并保持股票代码为字符串"""
    # 确保 stock_code 列为字符串
    df["stock_code"] = df["stock_code"].astype(str)
    # 创建目录
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    # 写入 CSV，覆盖写入
    df.to_csv(data_path, index=False, mode="w", encoding="utf-8-sig")


def fetch_stock(code, stock_info, idx, total, delay=1):
    print(f"\n[{idx}/{total}] 正在处理股票: {code}")

    if delay != 0:
        time.sleep(delay)

    try:
        # 获取股票历史股本/流通股数据
        df_shares = adata.stock.info.get_stock_shares(stock_code=code, is_history=False)

        if df_shares.empty:
            return f"⚠️ 股票 {code} 没有历史股本数据，跳过"

        # 去掉 df_shares 中重复的 stock_code 列
        if "stock_code" in df_shares.columns:
            df_shares = df_shares.drop(columns=["stock_code"])

        # 获取res_df中对应股票的信息
        # 将stock_info扩展为与df_shares行数相同
        stock_info_df = pd.DataFrame([stock_info] * len(df_shares)).reset_index(drop=True)

        # 合并数据
        df_combined = pd.concat([stock_info_df.reset_index(drop=True), df_shares.reset_index(drop=True)], axis=1)

        # 保存
        path = config.default_info_path(code, "1")
        save_data(df_combined, path)
        return f"✅ {code} 成功"
    except Exception as e:
        return f"⚠️ 股票 {code} 处理失败: {e}"


def fetch(workers, delay=1):
    # 1. 获取所有大A股票代码
    print("获取所有A股股票代码...")
    try:
        res_df = adata.stock.info.all_code()
        # 过滤掉没有上市日期的股票（可选）
        res_df = res_df[res_df['list_date'].notna()]
        stock_codes = res_df['stock_code'].tolist()
        print(f"共获取 {len(stock_codes)} 只股票")
    except Exception as e:
        print(f"获取股票失败")
        return

    # 并发执行
    results = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_code = {
            executor.submit(fetch_stock, code, res_df[res_df["stock_code"] == code].iloc[0], idx, len(stock_codes), delay): code
            for idx, code in enumerate(stock_codes, start=1)
        }
        for future in as_completed(future_to_code):
            result = future.result()
            print(result)
            results.append(result)

    print(f"成功 {sum('✅' in r for r in results)} 只，失败 {sum('⚠️' in r for r in results)} 只。")

    #for idx, code in  enumerate(stock_codes, start=1):
    #    print(fetch_stock(code, res_df[res_df["stock_code"] == code].iloc[0], idx, len(stock_codes), delay))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='并发更新所有股票数据')
    parser.add_argument('-w', '--workers', type=int, default=5, help='并发线程数')
    parser.add_argument('-d', '--delay', type=int, default=1, help='获取股票延迟')
    args = parser.parse_args()

    fetch(args.workers, args.delay)

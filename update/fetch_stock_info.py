import adata
import pandas as pd
import time
import os


WORK_DIR = os.environ.get("STOCK_WORK_DIR", ".")


def save_data(df: pd.DataFrame, data_path):
    """以追加方式写入 CSV，并保持股票代码为字符串"""
    # 确保 stock_code 列为字符串
    df["stock_code"] = df["stock_code"].astype(str)
    # 创建目录
    os.makedirs(os.path.dirname(data_path), exist_ok=True)
    # 写入 CSV，覆盖写入
    df.to_csv(data_path, index=False, mode="w", encoding="utf-8-sig")


def main():
    # 1. 获取所有大A股票代码
    print("获取所有A股股票代码...")
    res_df = adata.stock.info.all_code()

    # 过滤掉没有上市日期的股票（可选）
    res_df = res_df[res_df['list_date'].notna()]

    stock_codes = res_df['stock_code'].tolist()
    print(f"共获取 {len(stock_codes)} 只股票")

    # 2. 遍历股票，更新数据并生成文件
    for idx, code in enumerate(stock_codes, start=1):
        try:
            print(f"\n[{idx}/{len(stock_codes)}] 正在处理股票: {code}")

            # 获取股票历史股本/流通股数据
            df_shares = adata.stock.info.get_stock_shares(stock_code=code, is_history=True)

            if df_shares.empty:
                print(f"⚠️ 股票 {code} 没有历史股本数据，跳过")
                continue

            # 去掉 df_shares 中重复的 stock_code 列
            if "stock_code" in df_shares.columns:
                df_shares = df_shares.drop(columns=["stock_code"])

            # 获取res_df中对应股票的信息
            stock_info = res_df[res_df["stock_code"] == code].iloc[0]
            # 将stock_info扩展为与df_shares行数相同
            stock_info_df = pd.DataFrame([stock_info] * len(df_shares)).reset_index(drop=True)

            # 合并数据
            df_combined = pd.concat([stock_info_df.reset_index(drop=True), df_shares.reset_index(drop=True)], axis=1)

            # 保存
            path = f"{WORK_DIR}/{code}_info.csv"
            save_data(df_combined, path)

            # 防止接口请求过快
            time.sleep(0.3)

        except Exception as e:
            print(f"⚠️ 股票 {code} 处理失败: {e}")


if __name__ == "__main__":
    main()


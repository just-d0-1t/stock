import adata
from update_and_plot import update_and_plot
import time

def main():
    # 1. 获取所有大A股票代码
    print("获取所有A股股票代码...")
    res_df = adata.stock.info.all_code()

    # 过滤掉没有上市日期的股票（可选）
    res_df = res_df[res_df['list_date'].notna()]

    stock_codes = res_df['stock_code'].tolist()
    print(f"共获取 {len(stock_codes)} 只股票")

    # 2. 遍历股票，更新数据并生成图表
    for idx, code in enumerate(stock_codes, start=1):
        try:
            print(f"\n[{idx}/{len(stock_codes)}] 正在处理股票: {code}")
            update_and_plot(code)  # 使用默认历史文件路径
            # 为防止接口请求过快，可加延时
            time.sleep(1)  # 1秒延时
        except Exception as e:
            print(f"⚠️ 股票 {code} 处理失败: {e}")

if __name__ == "__main__":
    main()


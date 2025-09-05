import os
import pandas as pd
import adata
from datetime import datetime

class StockAnalyzer:
    def __init__(self, stock_code: str, start_date: str, data_path: str = None):
        """
        :param stock_code: 股票代码，例如 '002747'
        :param start_date: 起始日期，例如 '2025-08-01'
        :param data_path: 股票数据存放路径（CSV 文件），若未指定则默认生成
        """
        self.stock_code = stock_code
        self.start_date = start_date
        if data_path:
            self.data_path = data_path
        else:
            self.data_path = f"./data/{self.stock_code}_data.csv"

    def fetch_market_data(self):
        """获取交易数据"""
        res_df = adata.stock.market.get_market(
            stock_code=self.stock_code,
            k_type=1,
            start_date=self.start_date
        )
        return res_df

    def load_history(self):
        # """读取历史数据（如存在）"""
        # if os.path.exists(self.data_path):
        #     return pd.read_csv(self.data_path, parse_dates=["trade_date"])
        # return pd.DataFrame()
        """读取历史数据（如存在）"""
        if os.path.exists(self.data_path):
            return pd.read_csv(
                self.data_path,
                parse_dates=["trade_date"],
                dtype={"stock_code": str}  # ⭐ 保证股票代码是字符串
            )
        return pd.DataFrame()

    def compute_indicators(self, df: pd.DataFrame, history_df: pd.DataFrame):
        """计算指标：ma20, above_ma20, first_above_ma20, volume_ratio"""
    
        # ===== 统一日期和股票代码类型 =====
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            df["stock_code"] = df["stock_code"].astype(str)
        if not history_df.empty:
            history_df["trade_date"] = pd.to_datetime(history_df["trade_date"])
            history_df["stock_code"] = history_df["stock_code"].astype(str)
    
        # ===== 合并历史与新数据（去重） =====
        all_df = pd.concat([history_df, df]).drop_duplicates(
            subset=["trade_date"], keep="last"
        ).sort_values("trade_date").reset_index(drop=True)
    
        # ===== 计算 ma20 =====
        all_df["ma20"] = all_df["close"].rolling(window=20, min_periods=20).mean().fillna(0)
    
        # ===== 收盘价是否超过 ma20 =====
        all_df["above_ma20"] = all_df.apply(
            lambda row: "y" if row["ma20"] > 0 and row["close"] > row["ma20"] else "n",
            axis=1
        )
    
        # ===== 是否首次突破 ma20 =====
        first_flags = []
        for i in range(len(all_df)):
            if all_df.loc[i, "above_ma20"] == "y":
                if i == 0 or all_df.loc[i-1, "above_ma20"] == "n":
                    first_flags.append("y")
                else:
                    first_flags.append("n")
            else:
                first_flags.append("n")
        all_df["first_above_ma20"] = first_flags
    
        # ===== 计算量比（过去5日平均） =====
        vr_list = []
        for i in range(len(all_df)):
            today_vol = all_df.loc[i, "volume"]
            past_vols = all_df.loc[max(0, i-5):i-1, "volume"]
            if len(past_vols) > 0:
                avg_vol = past_vols.mean()
                vr_list.append(today_vol / avg_vol if avg_vol > 0 else 0)
            else:
                vr_list.append(0)
        all_df["volume_ratio"] = vr_list
    
        return all_df
    
    def save_data(self, df: pd.DataFrame):
        """以追加方式写入 CSV，并保持股票代码为字符串"""
        # 确保 stock_code 列为字符串
        df["stock_code"] = df["stock_code"].astype(str)
        # 写入 CSV
        df.to_csv(self.data_path, index=False, mode="w", encoding="utf-8-sig")

    def run(self):
        """执行完整流程"""
        print(f"获取股票 {self.stock_code} 自 {self.start_date} 起的数据...")
        new_data = self.fetch_market_data()
        history_data = self.load_history()

        all_data = self.compute_indicators(new_data, history_data)
        self.save_data(all_data)

        print(f"分析完成，数据已保存到 {self.data_path}")
        return all_data


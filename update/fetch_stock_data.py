import os
import pandas as pd
import adata
from datetime import datetime
import numpy as np

def compute_kdj(df, n=9, k_smooth=3, d_smooth=3):
    """
    计算KDJ指标，并标注金叉和死叉
    df: DataFrame，必须包含 high, low, close
    n: RSV周期，常用9
    k_smooth: K平滑周期，常用3
    d_smooth: D平滑周期，常用3
    """
    # 1. 计算RSV
    low_min = df['low'].rolling(n, min_periods=1).min()
    high_max = df['high'].rolling(n, min_periods=1).max()
    df['rsv'] = (df['close'] - low_min) / (high_max - low_min) * 100

    # 2. 计算K、D
    df['K'] = df['rsv'].ewm(alpha=1/k_smooth, adjust=False).mean()
    df['D'] = df['K'].ewm(alpha=1/d_smooth, adjust=False).mean()

    # 3. 计算J
    df['J'] = 3 * df['K'] - 2 * df['D']

    # 4. 标注金叉/死叉
    df['kdj_signal'] = ''
    for i in range(1, len(df)):
        if df['K'].iloc[i-1] < df['D'].iloc[i-1] and df['K'].iloc[i] > df['D'].iloc[i]:
            df.at[i, 'kdj_signal'] = 'golden_cross'  # 金叉
        elif df['K'].iloc[i-1] > df['D'].iloc[i-1] and df['K'].iloc[i] < df['D'].iloc[i]:
            df.at[i, 'kdj_signal'] = 'death_cross'   # 死叉
        else:
            df.at[i, 'kdj_signal'] = 'no_cross'   # 死叉
            

    df.drop(['rsv'], axis=1, inplace=True)

    return df


def compute_macd(df, short=12, long=26, signal=9):
    """
    计算MACD指标，并标注金叉和死叉
    df: DataFrame，必须包含 close 列
    short: 短期EMA周期，常用12
    long: 长期EMA周期，常用26
    signal: DEA平滑周期，常用9
    """
    # 1. 计算EMA
    df['ema_short'] = df['close'].ewm(span=short, adjust=False).mean()
    df['ema_long'] = df['close'].ewm(span=long, adjust=False).mean()

    # 2. DIF
    df['DIF'] = df['ema_short'] - df['ema_long']

    # 3. DEA（信号线）
    df['DEA'] = df['DIF'].ewm(span=signal, adjust=False).mean()

    # 4. MACD（柱状图）
    df['MACD'] = 2 * (df['DIF'] - df['DEA'])

    # 5. 标注金叉/死叉
    df['macd_signal'] = ''
    for i in range(1, len(df)):
        if df['DIF'].iloc[i-1] < df['DEA'].iloc[i-1] and df['DIF'].iloc[i] > df['DEA'].iloc[i]:
            df.at[i, 'macd_signal'] = 'golden_cross'  # 金叉
        elif df['DIF'].iloc[i-1] > df['DEA'].iloc[i-1] and df['DIF'].iloc[i] < df['DEA'].iloc[i]:
            df.at[i, 'macd_signal'] = 'death_cross'   # 死叉
        else:
            df.at[i, 'macd_signal'] = 'no_cross'   # 死叉

    if 'mach_signal' in df:
        df.drop(['ema_long', 'ema_short', 'mach_signal'], axis=1, inplace=True)
    else:
        df.drop(['ema_long', 'ema_short'], axis=1, inplace=True)

    return df


class StockAnalyzer:
    def __init__(self, stock_code: str, start_date: str, end_date: str = None, data_path: str = None, ktype: int=1):
        """
        :param stock_code: 股票代码，例如 '002747'
        :param start_date: 起始日期，例如 '2025-08-01'
        :param data_path: 股票数据存放路径（CSV 文件），若未指定则默认生成
        :param ktype: 1.日；2.周；3.月
        """
        self.stock_code = stock_code
        self.start_date = start_date
        self.end_date = end_date
        self.ktype = ktype
        if data_path:
            self.data_path = data_path
        else:
            self.data_path = config.default_data_path(self.stock_code, self.ktype)

    def fetch_market_data(self, ktype=1):
        """获取交易数据"""
        res_df = adata.stock.market.get_market(
            stock_code=self.stock_code,
            k_type=self.ktype,
            start_date=self.start_date,
            end_date=self.end_date,
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

    def ma(self, all_df, period):
        # 偷个懒
        period = str(period)
        win = int(period)

        # ===== 计算 ma =====
        all_df["ma" + period] = all_df["close"].rolling(window=win, min_periods=win).mean().fillna(0)

        # ===== 收盘价是否超过 ma =====
        all_df["above_ma" + period] = all_df.apply(
            lambda row: "y" if row["ma" + period] > 0 and row["close"] > row["ma" + period] else "n",
            axis=1
        )

        # ===== 是否首次突破 ma =====
        first_flags = []
        for i in range(len(all_df)):
            if all_df.loc[i, "above_ma" + period] == "y":
                if i == 0:
                    first_flags.append("n")
                elif all_df.loc[i-1, "above_ma" + period] == "n":
                    first_flags.append("y")
                else:
                    first_flags.append("n")
            else:
                first_flags.append("n")
        all_df["first_above_ma" + period] = first_flags

        # ===== 是否首次跌破 ma =====
        first_under_flags = []
        for i in range(len(all_df)):
            if all_df.loc[i, "above_ma" + period] == "n":
                if i == 0:
                    first_under_flags.append("n")
                elif all_df.loc[i-1, "above_ma" + period] == "y":
                    first_under_flags.append("y")
                else:
                    first_under_flags.append("n")
            else:
                first_under_flags.append("n")
        all_df["first_under_ma" + period] = first_under_flags

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
    
        # ===== 计算 ma5 =====
        self.ma(all_df, 5)

        # ===== 计算 ma10 =====
        self.ma(all_df, 10)

        # ===== 计算 ma20 =====
        self.ma(all_df, 20)
    
        # ===== 计算 kdj =====
        compute_kdj(all_df)
    
        # ===== 计算 macd =====
        compute_macd(all_df)
    
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
        if new_data.empty:
            print(f"⚠️ 股票 {self.stock_code} new_data 是空的 DataFrame")
            return new_data
        history_data = self.load_history()

        all_data = self.compute_indicators(new_data, history_data)
        self.save_data(all_data)

        print(f"分析完成，数据已保存到 {self.data_path}")
        return all_data


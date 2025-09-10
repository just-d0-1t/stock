import pandas as pd
import numpy as np

def compute_kdj(df, n=9, k_smooth=3, d_smooth=3):
    """
    计算KDJ指标，并标注金叉和死叉
    df: DataFrame，必须包含 high, low, close
    n: RSV周期，常用9
    k_smooth: K平滑周期，常用3
    d_smooth: D平滑周期，常用3
    """
    df = df.copy()
    
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
    df['signal'] = ''
    for i in range(1, len(df)):
        if df['K'].iloc[i-1] < df['D'].iloc[i-1] and df['K'].iloc[i] > df['D'].iloc[i]:
            df.at[i, 'signal'] = 'golden_cross'  # 金叉
        elif df['K'].iloc[i-1] > df['D'].iloc[i-1] and df['K'].iloc[i] < df['D'].iloc[i]:
            df.at[i, 'signal'] = 'death_cross'   # 死叉

    return df

# 示例使用
if __name__ == "__main__":
    # 假设你有历史数据CSV
    df = pd.read_csv('stock_data.csv', parse_dates=['trade_date'])
    df_kdj = compute_kdj(df)

    # 输出带信号的前几行
    print(df_kdj[['trade_date', 'close', 'K', 'D', 'J', 'signal']].tail(20))


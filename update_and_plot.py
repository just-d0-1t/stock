import os
import pandas as pd
from datetime import datetime, timedelta
import mplfinance as mpf
from stock_analyzer import StockAnalyzer  # 你之前实现的类

SAVE_DIR = "/usr/local/openresty/nginx/html/download/"

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def update_stock_data(stock_code, data_path=None):
    today = datetime.today().date()

    if data_path is None:
        data_path = f"./data/{stock_code}_data.csv"

    if not os.path.exists(data_path):
        # 历史文件不存在 → 默认取一年数据
        start_date = (today - timedelta(days=365)).strftime("%Y-%m-%d")
        analyzer = StockAnalyzer(stock_code, start_date, data_path)
        df = analyzer.run()
    else:
        # 历史文件存在 → 检查是否需要更新
        history = pd.read_csv(
            data_path,
            parse_dates=["trade_date"],
            dtype={"stock_code": str}  # ⭐ 保证股票代码是字符串
        )
        history.sort_values("trade_date", inplace=True)
        last_date = history["trade_date"].iloc[-1].date()

        if last_date >= today:
            # 已有今天 → 删除后更新今天
            history = history[history["trade_date"].dt.date < today]
            history.to_csv(data_path, index=False)
            start_date = today.strftime("%Y-%m-%d")
            analyzer = StockAnalyzer(stock_code, start_date, data_path)
            df = analyzer.run()
        else:
            # 有缺口 → 从最后日期的下一天开始追加
            start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            analyzer = StockAnalyzer(stock_code, start_date, data_path)
            df = analyzer.run()

    return df

def plot_kline(df, stock_code, period_days, save_dir=SAVE_DIR):
    """
    绘制股票K线图 + MA20 + 量比（A股风格：涨红跌绿）
    df: DataFrame，必须包含 open, high, low, close, volume, trade_date, volume_ratio
    period_days: int，最近多少天绘制
    """
    ensure_dir(save_dir)

    # 计算起始日期
    end_date = df["trade_date"].max()
    start_date = end_date - timedelta(days=period_days)

    # 选取绘图区间
    df_period = df[df["trade_date"] >= start_date].copy()
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

    # 量比曲线（和成交量在同一个panel，但用右轴显示）
    add_plots = [
        mpf.make_addplot(
            df_period["volume_ratio"],
            panel=1,
            color='blue',
            secondary_y=True  # 右边Y轴
        )
    ]

    # 输出路径
    save_path = os.path.join(save_dir, f"{stock_code}_kline_{period_days}d.png")

    # 绘制并保存
    mpf.plot(
        ohlc,
        type='candle',
        mav=(20,),
        volume=True,
        style=style,
        title=f"{stock_code} 近{period_days}日 K线 + MA20 + 量比",
        figsize=(12, 8),
        addplot=add_plots,
        panel_ratios=(3, 1),  # 上面K线占3份
        savefig=save_path
    )

    print(f"✅ 已保存图表: {save_path}")

def update_and_plot(stock_code, data_path=None):
    """模块化函数：更新数据并绘制图表"""
    df = update_stock_data(stock_code, data_path)

    # 绘制近3月、半年、一年图表
    plot_kline(df, stock_code, 90)
    plot_kline(df, stock_code, 180)
    plot_kline(df, stock_code, 365)

    return df

# 支持命令行直接调用
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python update_and_plot.py <股票代码> [历史数据文件路径]")
    else:
        code = sys.argv[1]
        path = sys.argv[2] if len(sys.argv) > 2 else None
        update_and_plot(code, path)

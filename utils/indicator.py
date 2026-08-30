import os
import numpy as np

def ma(all_df, period, new_start_idx=0):
        """
        增量计算 MA 指标
        :param all_df: 完整 DataFrame（含历史+新数据）
        :param period: MA 周期，如 5, 10, 20
        :param new_start_idx: 新数据在 all_df 中的起始索引
        """
        period = str(period)
        win = int(period)
        col_ma = f"ma{period}"
        col_above = f"above_ma{period}"
        col_first_above = f"first_above_ma{period}"
        col_first_under = f"first_under_ma{period}"

        # === 1. 计算 MA（只需从 new_start_idx - win + 1 开始算，但为安全取更早一点）
        start_calc = max(0, new_start_idx - win)
        subset = all_df.iloc[start_calc:].copy()
        subset[col_ma] = subset["close"].rolling(window=win, min_periods=win).mean()

        # 将计算结果写回 all_df
        all_df.loc[subset.index, col_ma] = subset[col_ma]

        # === 2. 计算 above_ma
        mask = (all_df[col_ma] > 0) & (all_df["close"] > all_df[col_ma])
        all_df[col_above] = np.where(mask, "y", "n")

        # === 3. 计算 first_above_ma 和 first_under_ma（只需从 new_start_idx 开始检查）
        # 初始化为 "n"
        all_df[col_first_above] = "n"
        all_df[col_first_under] = "n"

        for i in range(new_start_idx, len(all_df)):
            if all_df.at[i, col_above] == "y":
                if i == 0 or all_df.at[i-1, col_above] == "n":
                    all_df.at[i, col_first_above] = "y"
            else:
                if i > 0 and all_df.at[i-1, col_above] == "y":
                    all_df.at[i, col_first_under] = "y"
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


def compute_kdj(all_df, new_start_idx, n=9, k_smooth=3, d_smooth=3):
    """
    增量计算 KDJ，确保结果与全量计算一致
    :param all_df: 完整 DataFrame（已排序去重）
    :param new_start_idx: 需要更新指标的起始索引（含重叠部分）
    :param n: RSV 周期
    """
    if new_start_idx >= len(all_df):
        return

    # === 1. 确定计算窗口 ===
    # 预热窗口长度：经验值 3*n（可调整）
    warmup = max(n * 3, 50)  # 至少 50 行保证 EWM 收敛
    calc_start = max(0, new_start_idx - warmup)

    # 提取计算子集
    calc_df = all_df.iloc[calc_start:].copy()

    # === 2. 全量计算 KDJ（在子集上）===
    low_min = calc_df['low'].rolling(window=n, min_periods=1).min()
    high_max = calc_df['high'].rolling(window=n, min_periods=1).max()
    rsv = (calc_df['close'] - low_min) / (high_max - low_min) * 100
    calc_df['rsv'] = rsv.fillna(0)  # 处理除零或 NaN

    # K 和 D 使用 EWM
    calc_df['K'] = calc_df['rsv'].ewm(alpha=1/k_smooth, adjust=False).mean()
    calc_df['D'] = calc_df['K'].ewm(alpha=1/d_smooth, adjust=False).mean()
    calc_df['J'] = 3 * calc_df['K'] - 2 * calc_df['D']

    # === 3. 只将“需要更新的部分”写回 all_df ===
    # 从 new_start_idx 开始的所有行都需要更新（包括重叠部分）
    update_indices = all_df.index[new_start_idx:]
    update_slice = calc_df.loc[update_indices]

    for col in ['K', 'D', 'J']:
        all_df.loc[update_indices, col] = update_slice[col].values

    # === 4. 更新信号（保留历史，只重算 new_start_idx 之后）===
    if 'kdj_signal' not in all_df.columns:
        all_df['kdj_signal'] = 'no_cross'
    all_df.loc[new_start_idx:, 'kdj_signal'] = 'no_cross'  # 初始化

    for i in range(new_start_idx, len(all_df)):
        if i == 0:
            continue
        k_prev, d_prev = all_df.at[i-1, 'K'], all_df.at[i-1, 'D']
        k_curr, d_curr = all_df.at[i, 'K'], all_df.at[i, 'D']
        if k_prev < d_prev and k_curr > d_curr:
            all_df.at[i, 'kdj_signal'] = 'golden_cross'
        elif k_prev > d_prev and k_curr < d_curr:
            all_df.at[i, 'kdj_signal'] = 'death_cross'

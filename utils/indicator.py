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

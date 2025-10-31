#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
@file: fish_tub_v2.py
@desc: "缩量回调"买入策略。
"""

import numpy as np

# ✅ 解析参数字符串，例如 "prev=5,volumn_amplify=2"
def parse_tuning(tuning_str: str):
    result = {}
    if not tuning_str:
        return result
    for item in tuning_str.split(","):
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        v = v.strip()
        # 尝试转成数字
        try:
            v = float(v) if "." in v else int(v)
        except ValueError:
            pass
        result[k.strip()] = v
    return result


def calc_slope(values):
    """计算斜率"""
    if len(values) < 2 or np.isnan(values).any():
        return 0
    x = np.arange(len(values))
    # 用线性回归求斜率
    k, _ = np.polyfit(x, values, 1)
    return k


def pretreatment(stock, operate, tuning=None, debug=False):
    """
    在 records 中计算新增指标：10日/20日斜率、10日均量等。
    """
    records = stock["records"].copy()

    # 计算10日斜率（用于温和上行判断）
    def data_processing(i):
        row = records.iloc[i]
        if i >= 9:
            records.loc[i, "ma10_slope"] = calc_slope(records["ma10"].iloc[i - 9: i + 1].values)
            # --- 过去10日数据 ---
            last10 = records.iloc[i - 9: i + 1]
            prev_day = records.iloc[i - 1]
    
            # 1️⃣ 前期爆量
            vol_max = last10["amount"].max()
            vol_min = last10["amount"].min()
            records.loc[i, "volumn_outbreak"] = vol_max >= vol_min * 2
    
            # 2️⃣ 前期有涨停（涨幅 >= 9.8%）
            records.loc[i, "limit_up"] = ((last10["close"] - last10["pre_close"]) / last10["pre_close"] * 100 >= 9.8).any()
    
            # 4️⃣ 当日缩量
            records.loc[i, "volumn_fall"] = (records.loc[i, "amount"] < last10["amount"].mean()) and (records.loc[i, "amount"] < prev_day["amount"])
    
            # 5️⃣ 回调至10日线
            records.loc[i, "close_to_ma10"] = (records.loc[i, "close"] >= records.loc[i, "ma10"]) and (abs(records.loc[i, "close"] - records.loc[i, "ma10"]) / records.loc[i, "ma10"] <= 0.01)
    
            # 6️⃣ 10日线与20日线贴合
            records.loc[i, "ma10_close_to_ma20"] = abs(records.loc[i, "ma20"] - records.loc[i, "ma10"]) / records.loc[i, "ma10"] <= 0.01
    
            # 7️⃣ 10日线温和上行
            records.loc[i, "ma10_slope_up"] = (0 < row.get("ma10_slope", 0) < 0.3)
        else:
            records.loc[i, "ma10_slope"] = np.nan
            records.loc[i, "volumn_outbreak"] = False 
            records.loc[i, "limit_up"] = False
            records.loc[i, "volumn_fall"] = False
            records.loc[i, "close_to_ma10"] = False
            records.loc[i, "ma10_close_to_ma20"] = False
            records.loc[i, "ma10_slope_up"] = False

    # ✅ 调度模式：批量 or 单点处理
    if operate == "back_test":
        for i in range(len(records)):
            data_processing(i)
    elif operate in ("buy", "sell"):
        data_processing(len(records) - 1)

    stock["records"] = records


def buy(r, status=None, debug=False):
    """
    策略逻辑：
    1. 前期爆量（过去10日最高成交额 >= 最低成交额 * 2）
    2. 前期有涨停（过去10日内至少一次涨停）
    3. 当日阴线
    4. 当日缩量（成交额 < 过去10日平均 & 小于昨日成交额）
    5. 回调至10日线（收盘价高于10日线 & 差距<1%）
    6. 10日线和20日线贴合（差距<1%）
    7. 10日线温和上行（斜率 >0 且 <0.3）
    """
    desc = "策略：缩量回调"
    if debug: print("[debug] low_volumn_fallback", r)
    cond1 = r["volumn_outbreak"]
    cond2 = r["limit_up"]
    cond3 = r["close"] < r["open"]
    cond4 = r["volumn_fall"]
    cond5 = r["close_to_ma10"]
    cond6 = r["ma10_close_to_ma20"]
    cond7 = r["ma10_slope_up"]

    all_cond = cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7
    return all_cond, desc


def sell(r, status=None, debug=False):
    """
    卖出条件示例: 持有1－2日，赚2%或者跌破ma10卖出
    """
    cond = r["close"] < r["ma10"]
    desc = "跌破10日线卖出"
    return cond, desc


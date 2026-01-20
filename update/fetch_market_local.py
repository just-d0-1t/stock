import json
import pandas as pd
from datetime import datetime

# ===== 配置区 =====
# 使用当前系统日期（根据你的系统时间）
CURRENT_DATE = datetime.now().date()  # 2026-01-20
TRADE_DATE_STR = CURRENT_DATE.strftime("%Y-%m-%d")          # "2026-01-20"
TRADE_TIME_STR = CURRENT_DATE.strftime("%Y-%m-%d 00:00:00")  # "2026-01-20 00:00:00"

# 如果你希望固定为 2026-01-19（比如这是历史数据），取消注释下面两行：
# TRADE_DATE_STR = "2026-01-19"
# TRADE_TIME_STR = "2026-01-19 00:00:00"

# 字段映射（原始 f 字段 → 目标列名）
FIELD_MAPPING = {
    'f2': 'close',
    'f3': 'change_pct',
    'f4': 'change',
    'f5': 'volume',
    'f6': 'amount',
    'f8': 'turnover_ratio',
    'f12': 'stock_code',
    'f15': 'high',
    'f16': 'low',
    'f17': 'open',
    'f18': 'pre_close'
}

# 需要除以 100 的字段（包括价格、涨跌幅、换手率等）
DIVIDE_100_FIELDS = {'open', 'close', 'high', 'low', 'pre_close', 'change_pct', 'change', 'turnover_ratio'}

# volume 需要乘以 100
MULTIPLY_100_FIELDS = {'volume'}

def parse_concatenated_json(text):
    """手动解析 [{...}][{...}] 格式的拼接 JSON"""
    records = []
    i = 0
    n = len(text)
    
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        if text[i] != '[':
            raise ValueError(f"期望 '['，但在位置 {i} 遇到 '{text[i]}'")
        i += 1
        
        depth = 0
        start = i
        in_string = False
        escape = False
        
        while i < n:
            c = text[i]
            if not escape:
                if c == '\\':
                    escape = True
                elif c == '"':
                    in_string = not in_string
                elif not in_string:
                    if c == '[':
                        depth += 1
                    elif c == ']':
                        if depth == 0:
                            break
                        else:
                            depth -= 1
            else:
                escape = False
            i += 1
        else:
            raise ValueError("未找到匹配的 ']'")
        
        content = text[start:i]
        i += 1
        
        if content.strip() == '':
            continue
        
        json_str = '[' + content + ']'
        try:
            arr = json.loads(json_str)
            if isinstance(arr, list):
                records.extend(arr)
        except json.JSONDecodeError as e:
            print(f"JSON 解析失败: {e}，片段: {json_str[:100]}...")
    
    return records

def load_stock_data(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    records = parse_concatenated_json(content)
    valid_records = [r for r in records if isinstance(r, dict) and 'f12' in r]
    
    if not valid_records:
        print("没有找到有效的股票记录。")
        return {}
    
    df = pd.DataFrame(valid_records)
    
    # 字段映射
    needed_f_fields = [k for k in FIELD_MAPPING if k in df.columns]
    df = df[needed_f_fields].rename(columns=FIELD_MAPPING)

    # 强制转换为数值（处理字符串数字）
    numeric_cols = ['open', 'close', 'high', 'low', 'pre_close', 'change', 'change_pct', 'turnover_ratio', 'volume', 'amount']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # 数值缩放
    for col in DIVIDE_100_FIELDS:
        if col in df.columns:
            df[col] = df[col] / 100.0
    for col in MULTIPLY_100_FIELDS:
        if col in df.columns:
            df[col] = df[col] * 100

    # 添加日期时间字段
    df['trade_date'] = TRADE_DATE_STR
    df['trade_time'] = TRADE_TIME_STR

    # === 指定列顺序 ===
    desired_order = [
        'stock_code',
        'trade_time',
        'trade_date',
        'open',
        'close',
        'high',
        'low',
        'volume',
        'amount',
        'change_pct',
        'change',
        'turnover_ratio',
        'pre_close'
    ]
    # 只保留存在的列
    final_cols = [col for col in desired_order if col in df.columns]
    df = df[final_cols]

    # 按 stock_code 分组返回
    result = {}
    for code, group in df.groupby('stock_code'):
        result[code] = group.reset_index(drop=True)
    return result

if __name__ == "__main__":
    file_path = "/root/stock/data/2026-01-20_all_market.txt.bak"  # 改成你的文件路径
    data = load_stock_data(file_path)
    
    for i, (code, df) in enumerate(data.items()):
        print(f"\n=== 股票 {code} ===")
        print(df)
        if i >= 2:
            break

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

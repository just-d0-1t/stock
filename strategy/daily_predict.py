import os
import sys
import json
import base64
import time
import threading
import requests
from datetime import datetime
from strategy.predict import Predictor  # 引入你的类版本predict

# -------------------------
# 模型配置
# -------------------------
MODELS = [
    "kdj",
    "volumn_detect",
    # 可以继续添加其他模型
]

NOTIFY_URL = os.environ.get("STOCK_NOTIFY_URL", ".")
RESULT_DIR = "/tmp/predict"
os.makedirs(RESULT_DIR, exist_ok=True)

# -------------------------
# 简单加密函数（可自定义）
# -------------------------
def encrypt_path(path: str) -> str:
    """简单加密文件路径"""
    b64 = base64.urlsafe_b64encode(path.encode()).decode()
    return b64

# -------------------------
# 单模型执行函数
# -------------------------
def run_predict(model: str, cond = None):
    """执行单个模型预测任务"""
    predictor = Predictor(model)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{model}_{timestamp}.txt"
    filepath = os.path.join(RESULT_DIR, filename)

    print(f"[*] 开始执行模型: {model}")

    try:
        # 调用predict方法
        result = predictor.predict(
            code="all",
            ktype=1,
            operate="buy",
            tuning="",
            cond=cond,
        )

        # 写入文件
        with open(filepath, "w") as f:
            f.write(json.dumps(result, ensure_ascii=False, indent=2))

        print(f"[+] 模型 {model} 预测完成，结果写入：{filepath}")

        # 加密路径
        encrypted_path = encrypt_path(filepath)

        # 推送通知
        data = {
            "msgtype": "text",
            "text": {
                "content": encrypted_path,
            },
        }
        try:
            resp = requests.post(NOTIFY_URL, json=data, timeout=5)
            print(f"[+] 通知接口响应: {resp.status_code}")
        except Exception as e:
            print(f"[!] 通知接口请求失败: {e}")

    except Exception as e:
        print(f"[x] 模型 {model} 执行失败: {e}")

# -------------------------
# 主入口
# -------------------------
if __name__ == "__main__":
    print(f"=== {datetime.now()} 开始执行每日预测任务 ===")

    threads = []
    cond=None
    for model in MODELS:
        if model == "kdj":
            cond = "50000000000" 
        t = threading.Thread(target=run_predict, args=(model, cond))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    print(f"=== {datetime.now()} 所有模型预测完成 ===")


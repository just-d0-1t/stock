import requests
import gzip
import json
import time
from datetime import datetime, timedelta
import os

# 手动补充数据指令
# curl "http://push2.eastmoney.com/api/qt/clist/get?np=1&fltt=1&invt=2&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2Cm%3A0%2Bt%3A80%2Bf%3A!2%2Cm%3A1%2Bt%3A2%2Bf%3A!2%2Cm%3A1%2Bt%3A23%2Bf%3A!2%2Cm%3A0%2Bt%3A81%2Bs%3A262144%2Bf%3A!2&fields=f12%2Cf13%2Cf14%2Cf1%2Cf2%2Cf4%2Cf3%2Cf152%2Cf5%2Cf6%2Cf7%2Cf15%2Cf18%2Cf16%2Cf17%2Cf10%2Cf8%2Cf9%2Cf20&fid=f20&pn=8&pz=100&po=1&dect=1&ut=fa5fd1943c7b386f172d6893dbfba10b&wbp2u=%7C0%7C1%7C0%7Cweb&_=1662352742788" -vo /tmp/test.dat.gz -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36 Edg/142.0.0.0" -x 127.0.0.1:18888
# gzip -d /tmp/test.dat.gz
# jq -r '.data.diff[] | "\(.f12)\t\(.f14)\t\(.f20)"' /tmp/test.dat

# -----------------------
# 计算日期（14:00 前取昨日）
# -----------------------
now = datetime.now()
if now.hour < 14:
    date_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
else:
    date_str = now.strftime("%Y-%m-%d")

output_file = f"{date_str}.txt"

if os.path.exists(output_file):
    print(f"✅ 文件已存在，直接使用：{output_file}")
    exit(0)

# -----------------------
# 请求配置
# -----------------------
BASE_URL = (
    "http://push2.eastmoney.com/api/qt/clist/get"
    "?np=1&fltt=1&invt=2"
    "&fs=m%3A0%2Bt%3A6%2Bf%3A!2%2C"
    "m%3A0%2Bt%3A80%2Bf%3A!2%2C"
    "m%3A1%2Bt%3A2%2Bf%3A!2%2C"
    "m%3A1%2Bt%3A23%2Bf%3A!2%2C"
    "m%3A0%2Bt%3A81%2Bs%3A262144%2Bf%3A!2"
    "&fields=f12%2Cf13%2Cf14%2Cf20"
    "&fid=f20&pz=100&po=1&dect=1"
    "&ut=fa5fd1943c7b386f172d6893dbfba10b"
    "&wbp2u=%7C0%7C1%7C0%7Cweb"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/142.0.0.0 Safari/537.36"
    ),
}
PROXY = {"http": "http://127.0.0.1:18888", "https": "http://127.0.0.1:18888"}


# -----------------------
# 拉取单页（带重试 + 自动解压）
# -----------------------
def fetch_page(page, retries=6):
    url = f"{BASE_URL}&pn={page}"
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, proxies=PROXY, timeout=10)
            if resp.status_code != 200:
                print(f"⚠️ 第{page}页请求失败({resp.status_code})，重试 {attempt+1}/{retries}")
                time.sleep(2)
                continue

            content = resp.content
            encoding = resp.headers.get("Content-Encoding", "").lower()

            # 根据头部解压
            # if "gzip" in encoding:
            #     content = gzip.decompress(content)
            # elif "br" in encoding:
            #     # brotli压缩格式（需要安装brotli库）
            #     import brotli
            #     content = brotli.decompress(content)
            # elif "deflate" in encoding:
            #     import zlib
            #     content = zlib.decompress(content)

            data = json.loads(content.decode("utf-8", errors="ignore"))
            if "data" not in data or not data["data"].get("diff"):
                print(f"⚠️ 第{page}页数据为空，重试 {attempt+1}/{retries}")
                time.sleep(2)
                continue

            return data["data"]["diff"]

        except Exception as e:
            print(f"⚠️ 第{page}页异常：{e}，重试 {attempt+1}/{retries}")
            time.sleep(2)

    print(f"❌ 第{page}页重试失败，跳过")
    return []


# -----------------------
# 主流程
# -----------------------
all_stocks = []
for page in range(1, 11):
    print(f"📄 正在拉取第 {page} 页...")
    rows = fetch_page(page)
    for item in rows:
        code = item.get("f12")
        name = item.get("f14")
        market_value = item.get("f20")
        if code and name and market_value:
            all_stocks.append(f"{code}\t{name}\t{market_value}")
    time.sleep(5)

# -----------------------
# 写入文件
# -----------------------
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(all_stocks))

print(f"✅ 共获取 {len(all_stocks)} 条股票记录，已写入 {output_file}")

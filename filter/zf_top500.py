import requests
import time
from bs4 import BeautifulSoup
import os
from datetime import date

HEADERS = {
    "Cookie": "searchGuide=sg; __utma=156575163.286450060.1760713645.1760713645.1760713645.1; __utmz=156575163.1760713645.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none);",
    "hexin-v": "Ax9DIgoZiypRb482joLQgF7grnishHMmjdh3GrFsu04VQDFmuVQDdp2oB2jC",
    "Referer": "https://data.10jqka.com.cn/market/zdfph/field/zdf/order/desc/page/2",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36 Edg/141.0.0.0"
}

def fetch_page(page, max_retries=3):
    """抓取并解析单页，最多重试 max_retries 次"""
    url = f"http://data.10jqka.com.cn/market/zdfph/field/zdf5/order/desc/ajax/1/page/{page}/free/1/"

    proxy_env = os.environ.get("STOCK_HTTP_PROXY")
    proxies = {"http": proxy_env, "https": proxy_env} if proxy_env else None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method='get', url=url, headers=HEADERS, proxies=proxies, timeout=10)
            if resp.status_code != 200:
                print(f"⚠️ 第{page}页请求失败（状态码 {resp.status_code}），重试 {attempt}/{max_retries}")
                time.sleep(2)
                continue

            resp.encoding = "gbk"
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            tbody = soup.find("tbody")
            if not tbody:
                print(f"⚠️ 第{page}页无有效数据，重试 {attempt}/{max_retries}")
                time.sleep(2)
                continue

            codes = []
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) >= 2:
                    code = tds[1].get_text(strip=True)
                    if code:
                        codes.append(code)

            if codes:
                print(codes)
                return codes
            else:
                print(f"⚠️ 第{page}页返回空数据，重试 {attempt}/{max_retries}")
                time.sleep(2)
        except Exception as e:
            print(f"❌ 第{page}页抓取异常：{e}，重试 {attempt}/{max_retries}")
            time.sleep(2)
    print(f"❌ 第{page}页最终失败，跳过。")
    return []

def main():
    filename = f"{date.today()}.txt"
    if os.path.exists(filename):
        print(f"✅ 文件已存在：{filename}，跳过抓取。")
        return

    all_codes = []
    for page in range(1, 11):
        print(f"正在抓取第 {page} 页...")
        codes = fetch_page(page)
        print(f"  -> 获取 {len(codes)} 个股票代码")
        all_codes.extend(codes)
        time.sleep(10)

    with open(filename, "w", encoding="utf-8") as f:
        for code in all_codes:
            f.write(code + "\n")

    print(f"✅ 完成，共导出 {len(all_codes)} 个股票代码到 {filename}")

if __name__ == "__main__":
    main()


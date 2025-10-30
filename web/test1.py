import streamlit as st
import threading
import queue
import time
from datetime import date
import re

# 请确保 strategy/predict.py 可被 import
import strategy.predict as backtest

st.set_page_config(page_title="量化回测/预测前端", layout="wide")

# -------------------- session 独立状态 --------------------
if "running" not in st.session_state:
    st.session_state.running = False
if "thread" not in st.session_state:
    st.session_state.thread = None
if "output_queue" not in st.session_state:
    st.session_state.output_queue = queue.Queue()
if "stop_flag" not in st.session_state:
    st.session_state.stop_flag = threading.Event()

# -------------------- 参数输入区 --------------------
st.title("简易量化前端（Streamlit）")
st.markdown("注：股票信息最快于当日18:00更新，预测今日股价请于该时间之后查询。")

col1, col2 = st.columns(2)
with col1:
    operate = st.selectbox("操作", options=["buy", "back_test"], index=0)
    today = date.today()
    target_date = st.date_input("时间（仅 predict 有效）", value=today)
    mode = st.selectbox("量化策略", options=["fish_tub", "kdj", "volumn_detect"], index=2)

    tuning_string = ""
    if mode == "volumn_detect":
        st.markdown("**放量识别策略参数（可选）**")
        volumn_amplify = st.number_input("放量倍数", value=2.0, step=0.1)
        volumn_period = st.number_input("成交量对比周期", value=20, step=1)
        price_period = st.number_input("价格对比周期", value=60, step=1)
        volumn_slope = st.number_input("成交量波动率", value=0.3, step=0.01)
        rise = st.number_input("近5日涨幅", value=0.2, step=0.01)
        tuning_items = [
            f"volumn_amplify={volumn_amplify}",
            f"volumn_period={int(volumn_period)}",
            f"price_period={int(price_period)}",
            f"volumn_slope={volumn_slope}",
            f"rise={rise}",
        ]
        tuning_string = ",".join(tuning_items)
        st.code(tuning_string)
    else:
        tuning_string = st.text_input("其他策略调优（可选）", value="")

with col2:
    st.markdown("**股票筛选**")
    if operate == "back_test":
        code_input = st.text_input("股票代码（回测）", value="", placeholder="例如：600519")
        stock_cond = st.text_input("股票筛选条件（市值，回测忽略）", value="")
    else:
        code_input = st.text_area("股票代码 / all", value="all", height=80)
        stock_cond = st.text_input("市值，示例：1000", value="")

# -------------------- 输出区域 --------------------
log_box = st.empty()
status_slot = st.empty()
progress_bar = st.progress(0)
progress_text = st.empty()

# -------------------- worker 线程 --------------------
def worker_predict(code, operate, mode, tuning, cond, target_date, q: queue.Queue, stop_flag: threading.Event):
    def print_q(txt):
        q.put(("stdout", txt))

    def progress_callback(current, total, code_name):
        q.put(("progress", (current, total, code_name)))

    try:
        date_str = target_date.isoformat() if isinstance(target_date, date) else str(target_date)
        print_q(">>> 开始执行：\n")
        print_q(f"操作={operate}, 策略={mode}, 参数={tuning}, 股票过滤条件={cond}, date={date_str}\n")
        print_q(">>> 输出将实时显示，请耐心等待。\n")

        codes = [code.strip() for code in code.split(",")] if code != "all" else ["all"]

        for idx, c in enumerate(codes, start=1):
            if stop_flag.is_set():
                print_q(">>> 用户终止任务\n")
                return
            backtest.predict(
                c, "1", operate, mode, tuning, cond, None, date_str, None, False,
                progress_callback=progress_callback,
                log_callback=print_q,
                stop_flag=stop_flag  # 传入 stop_flag
            )
            time.sleep(0.1)

        print_q(">>> 后端脚本执行完成。\n")
    except Exception as e:
        print_q(f"⚠️ 后端运行出错：{repr(e)}\n")
    finally:
        q.put((None, None))


# -------------------- 前端按钮逻辑 --------------------
col_btn1, col_btn2 = st.columns([1,1])
with col_btn1:
    if not st.session_state.running:
        if st.button("开始执行"):
            # 检查回测条件
            if operate == "back_test" and (not code_input or "," in code_input):
                st.error("回测操作请输入单一股票代码（例如 600519）。")
            else:
                st.session_state.stop_flag.clear()
                st.session_state.output_queue = queue.Queue()
                t = threading.Thread(
                    target=worker_predict,
                    args=(code_input.strip() or "all",
                          operate, mode, tuning_string, stock_cond.strip() or None,
                          target_date,
                          st.session_state.output_queue,
                          st.session_state.stop_flag),
                )
                t.start()
                st.session_state.thread = t
                st.session_state.running = True
                st.rerun()
    else:
        if st.button("结束执行"):
            st.session_state.stop_flag.set()
            st.session_state.running = False
            st.info("任务终止信号已发送。")
            st.rerun()

# -------------------- 实时日志与进度 --------------------
if st.session_state.running:
    q = st.session_state.output_queue
    log_lines = []

    while True:
        try:
            kind, item = q.get(timeout=0.2)
        except queue.Empty:
            if not st.session_state.thread.is_alive():
                break
            continue

        if kind is None:
            break
        elif kind == "stdout":
            log_lines.append(item)
            log_box.code("".join(log_lines))
        elif kind == "progress":
            cur, total, code_name = item
            ratio = min(cur / total, 1.0)
            progress_bar.progress(ratio)
            progress_text.text(f"当前进度: {cur}/{total} - {code_name}")

    st.session_state.running = False
    status_slot.markdown("<div style='text-align:center'>✅ <b>策略执行完成</b></div>", unsafe_allow_html=True)


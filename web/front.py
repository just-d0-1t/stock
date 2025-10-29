import streamlit as st
import threading
import queue
import sys
import time
from datetime import date, timedelta
import os
import re

# 请确保 backtest.py 在同一目录或可被 import 的路径中
import strategy.predict as backtest

st.set_page_config(page_title="量化回测/预测前端", layout="wide")

# -------------------- stdout/stderr 重定向 --------------------
class QueueStdout:
    def __init__(self, q: queue.Queue):
        self._q = q
    def write(self, txt):
        if txt:
            self._q.put(("stdout", txt))
    def flush(self):
        pass

class QueueStderr:
    def __init__(self, q: queue.Queue):
        self._q = q
    def write(self, txt):
        if txt:
            self._q.put(("stderr", txt))
    def flush(self):
        pass


# -------------------- 参数输入区 --------------------
st.title("简易量化前端（Streamlit）")
st.markdown("注：股票信息最快于当日18:00更新，预测今日股价请于该时间之后查询。")

col1, col2 = st.columns(2)
with col1:
    operate = st.selectbox("操作", options=["buy", "back_test"], index=0)
    today = date.today()
    default_date = today
    target_date = st.date_input("时间（仅 predict 有效）", value=default_date)
    mode = st.selectbox("量化策略", options=["fish_tub", "kdj", "volumn_detect"], index=2,
                        help="fish_tub=鱼盆模型, kdj=kdj金叉, volumn_detect=放量识别")

    # 🔹 策略调优
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
        st.markdown("回测只允许填写一只股票代码（例如：600519）")
        code_input = st.text_input("股票代码（回测）", value="", placeholder="例如：600519")
        stock_cond = st.text_input("股票筛选条件（市值，回测忽略）", value="")
    else:
        st.markdown("预测可输入：逗号分隔的股票代码列表，或填写 `all` 使用全部A股")
        code_input = st.text_area("股票代码 / all", value="all", height=80)
        stock_cond = st.text_input("市值，示例：1000", value="")

# 🔹 提交按钮
with st.form("submit_form"):
    submitted = st.form_submit_button("开始执行")

# -------------------- 日志输出区 --------------------
log_box = st.empty()
status_slot = st.empty()

if "running" not in st.session_state:
    st.session_state.running = False

output_queue = queue.Queue()


# -------------------- worker 线程 --------------------
def worker_predict(code, operate, mode, tuning, cond, path, target_date, debug):
    q = output_queue
    backup_stdout = sys.stdout
    backup_stderr = sys.stderr
    sys.stdout = QueueStdout(q)
    sys.stderr = QueueStderr(q)
    try:
        date_str = target_date.isoformat() if isinstance(target_date, (date,)) else target_date
        print(">>> 开始执行：")
        print(f"操作={operate}, 策略={mode}, 模型调优参数={tuning}, 股票过滤条件={cond}, date={date_str}")
        print(">>> 输出将实时显示，请耐心等待。")

        # 调用核心回测逻辑
        backtest.predict(code, "1", operate, mode, tuning, cond, path, date_str, False, debug)

        print(">>> 后端脚本执行完成。")
    except Exception as e:
        print("⚠️ 后端运行出错：", repr(e))
    finally:
        sys.stdout = backup_stdout
        sys.stderr = backup_stderr
        q.put((None, None))


# -------------------- 前端执行逻辑 --------------------
if submitted:
    if st.session_state.running:
        st.warning("已有任务在运行，请等待其完成。")
    else:
        if operate == "back_test" and (not code_input or "," in code_input):
            st.error("回测操作请输入单一股票代码（例如 600519）。")
        else:
            code_arg = code_input.strip() if code_input else "all"
            path_arg = None
            cond_arg = stock_cond.strip() or None
            tuning_arg = tuning_string or ""
            debug_flag = None

            st.session_state.running = True
            t = threading.Thread(
                target=worker_predict,
                args=(code_arg, operate, mode, tuning_arg, cond_arg, path_arg, target_date, debug_flag),
            )
            t.start()

            log_lines = []
            progress_bar = st.progress(0)
            progress_text = st.empty()

            with st.spinner("任务已启动，正在运行中..."):
                while True:
                    try:
                        kind, item = output_queue.get(timeout=0.2)
                    except queue.Empty:
                        if not t.is_alive() and output_queue.empty():
                            break
                        continue

                    if kind is None:
                        break

                    # 普通日志输出
                    if kind == "stdout":
                        log_lines.append(item)
                        log_box.code("".join(log_lines), language=None)

                    # 进度条更新
                    elif kind == "stderr":
                        m = re.search(r"处理进度 \[ *(\d+) / *(\d+) *\]", item)
                        if m:
                            current, total = int(m.group(1)), int(m.group(2))
                            ratio = min(current / total, 1.0)
                            progress_bar.progress(ratio)
                            progress_text.text(f"当前进度: {current} / {total}")

                # 清理阶段
                while not output_queue.empty():
                    kind, item = output_queue.get()
                    if kind == "stdout" and item:
                        log_lines.append(item)
                log_box.code("".join(log_lines), language=None)
                status_slot.markdown("<div style='text-align:center'>✅ <b>策略执行完成</b></div>", unsafe_allow_html=True)
                progress_bar.progress(1.0)
                progress_text.text("任务完成 ✅")

            st.session_state.running = False
else:
    if not st.session_state.running:
        log_box.info("等待操作：请在上方选择参数并点击【开始执行】。")


# pages/2_loader.py
import streamlit as st
import os
import base64
import json

# 预测结果目录（与 strategy/daily_predict.py 保持一致）
RESULT_DIR = os.path.join(os.environ.get("STOCK_WORK_DIR", "."), "predict")

st.set_page_config(page_title="查看预测文件", layout="wide")
st.title("📁 查看每日预测文件 (Loader)")

# 你提供的解密函数（保持原样）
def decrypt_path(encrypted: str) -> str:
    """解密路径"""
    try:
        path = base64.urlsafe_b64decode(encrypted.encode()).decode()
        return path
    except Exception:
        return None

# 安全校验并返回 realpath（抛 ValueError 以便统一处理）
def resolve_and_validate(token: str) -> str:
    if not token:
        raise ValueError("token 为空")

    real_path = decrypt_path(token)
    if not real_path:
        raise ValueError("解密失败或 token 无效")

    # 规范化为绝对真实路径（解析符号链接、.. 等）
    real_path = os.path.realpath(real_path)
    allowed_base = os.path.realpath(RESULT_DIR)

    # 防止越界：commonpath 必须等于 allowed_base
    try:
        common = os.path.commonpath([allowed_base, real_path])
    except Exception:
        raise ValueError("路径解析异常")

    if common != allowed_base:
        raise ValueError("无权限访问该文件（越权或路径不在允许目录）")

    if not os.path.exists(real_path):
        raise ValueError("文件不存在")
    if not os.path.isfile(real_path):
        raise ValueError("该路径不是文件")

    return real_path

# ---- 页面输入与自动提取 ----
# 优先从 query param 中取 token
query = st.experimental_get_query_params()
qp_token = None
if "token" in query and query["token"]:
    qp_token = query["token"][0]

token_input = st.text_input("Token（加密路径）:", value=qp_token or "")

if st.button("读取并显示文件") or token_input:
    token_to_use = token_input.strip()
    if not token_to_use:
        st.error("请提供 token")
    else:
        try:
            safe_path = resolve_and_validate(token_to_use)
            st.success(f"已验证并读取文件：{safe_path}")

            with open(safe_path, "r", encoding="utf-8") as f:
                content = f.read()

            # 若为 JSON，则优先以 JSON 美化展示
            try:
                data = json.loads(content)
                st.json(data)
            except Exception:
                st.text_area("文件内容", value=content, height=500)
        except ValueError as e:
            st.error(f"验证失败：{e}")
        except Exception as e:
            st.error(f"读取失败：{e}")


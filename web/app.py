import streamlit as st

st.set_page_config(page_title="股票策略系统", layout="wide")

st.title("📊 股票策略分析系统")

st.markdown("""
欢迎使用 **股票策略系统**。  
请选择功能：
- **预测回测**：手动运行模型回测、查看实时日志。
- **查看预测文件**：查看每日14:30自动预测结果。
""")

st.sidebar.success("从左侧导航进入子页面")


"""FundScope Streamlit Application.

MVP Phase 1: Three pages - Fund Research, Portfolio Diagnosis, Strategy Lab.
"""
import streamlit as st

st.set_page_config(
    page_title="FundScope - 基金投资辅助系统",
    page_icon="📊",
    layout="wide",
)

st.title("FundScope 基金投资辅助系统")
st.markdown("""
**数据驱动 + 策略可验证 + 决策可解释**的基金投资辅助系统

请在左侧边栏选择功能页面：
- 📈 **基金研究** - 搜索基金、查看评分、赛道分类
- 📊 **持仓诊断** - 录入持仓、分析集中度、获取建议
- 🧪 **策略验证** - 创建虚拟账户、模拟交易
""")

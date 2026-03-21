"""Portfolio Diagnosis Page - Enter holdings, analyze concentration, get suggestions."""
import streamlit as st
from service.portfolio_service import PortfolioService

st.set_page_config(
    page_title="持仓诊断 - FundScope",
    page_icon="📊",
)

st.title("📊 持仓诊断")
st.markdown("录入持仓，分析集中度、赛道重叠，获取优化建议")

# Initialize service
@st.cache_resource
def get_portfolio_service():
    return PortfolioService()

service = get_portfolio_service()

# Session state for holdings
if "holdings" not in st.session_state:
    st.session_state.holdings = []

# Input form
st.subheader("添加持仓")
col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
with col1:
    fund_code = st.text_input("基金代码", key="input_code", max_chars=6)
with col2:
    fund_name = st.text_input("基金名称", key="input_name")
with col3:
    amount = st.number_input("持仓金额 (元)", min_value=0.0, step=1000.0, key="input_amount")
with col4:
    add_btn = st.button("添加", type="primary", use_container_width=True)

if add_btn and fund_code and fund_name and amount > 0:
    st.session_state.holdings.append({
        "fund_code": fund_code,
        "fund_name": fund_name,
        "amount": amount,
    })
    st.success(f"已添加 {fund_name}")
    st.rerun()

# Display current holdings
if st.session_state.holdings:
    st.subheader("当前持仓")
    total_amount = sum(h["amount"] for h in st.session_state.holdings)

    holdings_data = []
    for h in st.session_state.holdings:
        weight = (h["amount"] / total_amount * 100) if total_amount > 0 else 0
        holdings_data.append({
            "基金代码": h["fund_code"],
            "基金名称": h["fund_name"],
            "金额": f"¥{h['amount']:,.0f}",
            "权重": f"{weight:.1f}%",
        })

    st.table(holdings_data)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("总持仓金额", f"¥{total_amount:,.0f}")
    with col2:
        st.metric("持仓数量", len(st.session_state.holdings))

    # Analyze button
    if st.button("开始诊断", type="primary"):
        with st.spinner("正在分析持仓..."):
            try:
                result = service.get_diagnosis(st.session_state.holdings)

                # Diagnosis results
                st.subheader("诊断结果")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("集中度风险 (HHI)", f"{result['concentration_risk']:.3f}",
                              help="0-1，越高越集中")
                with col2:
                    st.metric("有效持仓数", f"{result['effective_n']:.1f}",
                              help="1/sum(weight²)，衡量真实分散度")
                with col3:
                    defense_status = "✅" if not result["missing_defense"] else "⚠️"
                    st.metric("防守资产", defense_status,
                              help="债券、红利低波等防守型赛道")

                # Sector overlap
                if result["sector_overlap"]:
                    st.warning(f"⚠️ 赛道重叠：{', '.join(result['sector_overlap'])}")
                else:
                    st.success("✅ 无赛道重叠")

                # Style balance
                if result["style_balance"]:
                    st.subheader("赛道分布")
                    st.bar_chart(result["style_balance"])

                # Suggestions
                st.subheader("优化建议")
                for i, suggestion in enumerate(result["suggestions"], 1):
                    st.write(f"{i}. {suggestion}")

            except Exception as e:
                st.error(f"诊断失败：{str(e)}")

    # Clear button
    if st.button("清空持仓"):
        st.session_state.holdings = []
        st.rerun()
else:
    st.info("👈 请添加持仓后开始诊断")

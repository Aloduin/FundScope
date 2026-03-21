"""Fund Research Page - Search funds, view scores and sector classification."""
import streamlit as st
from service.fund_service import FundService

st.set_page_config(
    page_title="基金研究 - FundScope",
    page_icon="📈",
)

st.title("📈 基金研究")
st.markdown("输入基金代码，查看基金信息、评分和赛道分类")

# Initialize service
@st.cache_resource
def get_fund_service():
    return FundService()

service = get_fund_service()

# Search form
col1, col2 = st.columns([3, 1])
with col1:
    fund_code = st.text_input("基金代码", placeholder="例如：000001", max_chars=6)
with col2:
    search_btn = st.button("搜索", type="primary", use_container_width=True)

if search_btn and fund_code:
    with st.spinner(f"正在分析基金 {fund_code}..."):
        try:
            result = service.analyze_fund(fund_code)

            # Fund Info
            st.subheader("基金基本信息")
            info = result["info"]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("基金名称", info.fund_name)
                st.metric("基金类型", info.fund_type)
            with col2:
                st.metric("基金经理", info.manager_name)
                st.metric("任职年限", f"{info.manager_tenure:.1f}年")
            with col3:
                st.metric("基金规模", f"{info.fund_size:.1f}亿元")
                st.metric("管理费率", f"{info.management_fee:.2%}")

            # Sector Classification
            st.subheader("赛道分类")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("主赛道", result["primary_sector"])
            with col2:
                st.metric("分类来源", result["sector_source"])

            if result["sectors"]:
                st.multiselect("全部赛道标签", result["sectors"], default=result["sectors"], disabled=True)

            # Score
            st.subheader("基金评分")
            score = result["score"]
            col1, col2 = st.columns(2)
            with col1:
                st.metric("总分", f"{score.total_score:.1f}", help="0-100 分")
                st.metric("数据完整度", f"{score.data_completeness:.0%}", help="评分可信度")

            with col2:
                # Dimension scores
                dimensions = {
                    "收益": score.return_score,
                    "风险": score.risk_score,
                    "稳定性": score.stability_score,
                    "成本": score.cost_score,
                    "规模": score.size_score,
                    "经理": score.manager_score,
                }

                for dim, val in dimensions.items():
                    if val is not None:
                        st.metric(dim, f"{val:.1f}")
                    else:
                        st.metric(dim, "N/A", help="数据缺失")

            # Metrics
            st.subheader("绩效指标")
            metrics = result["metrics"]
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("年化收益", f"{metrics.annualized_return:.2%}" if metrics.annualized_return else "N/A")
                st.metric("最大回撤", f"{metrics.max_drawdown:.2%}" if metrics.max_drawdown else "N/A")
            with col2:
                st.metric("波动率", f"{metrics.volatility:.2%}" if metrics.volatility else "N/A")
                st.metric("夏普比率", f"{metrics.sharpe_ratio:.2f}" if metrics.sharpe_ratio else "N/A")
            with col3:
                st.metric("胜率", f"{metrics.win_rate:.1%}" if metrics.win_rate else "N/A")
                st.metric("修复因子", f"{metrics.recovery_factor:.2f}" if metrics.recovery_factor else "N/A")

            # Missing dimensions warning
            if score.missing_dimensions:
                st.warning(f"⚠️ 以下维度数据缺失：{', '.join(score.missing_dimensions)}")

        except Exception as e:
            st.error(f"分析失败：{str(e)}")
elif search_btn:
    st.warning("请输入基金代码")
else:
    st.info("👈 请输入基金代码并点击搜索")

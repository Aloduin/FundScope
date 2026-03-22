"""Portfolio Diagnosis Page - Enter holdings, analyze concentration, get suggestions."""
import streamlit as st
from service.portfolio_service import PortfolioService
from infrastructure.importer.csv_importer import CsvImporter

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

# ---------------------------------------------------------------------------
# CSV Import Section
# ---------------------------------------------------------------------------
st.subheader("📂 批量导入持仓（CSV）")

with st.expander("从 CSV 文件导入持仓", expanded=False):
    st.markdown(
        "支持 **支付宝**、**天天基金** 导出格式，以及含 `fund_code / fund_name / amount` 列的标准格式。"
    )
    uploaded_file = st.file_uploader(
        "选择 CSV 文件",
        type=["csv"],
        key="csv_upload",
        help="文件编码自动识别（UTF-8 / GBK / GB18030）",
    )

    if uploaded_file is not None:
        raw_bytes = uploaded_file.read()
        try:
            result = CsvImporter.from_bytes(raw_bytes)
        except Exception as exc:
            st.error(f"解析失败：{exc}")
            result = None

        if result is not None:
            st.caption(f"识别格式：`{result.source_type}`　有效行：{len(result.valid_rows)}　跳过行：{len(result.skipped_rows)}")

            # Warnings
            for w in result.warnings:
                st.warning(w)

            # Preview merged rows
            if result.merged_rows:
                import pandas as _pd
                preview_df = _pd.DataFrame(result.merged_rows)[["fund_code", "fund_name", "amount"]]
                preview_df.columns = ["基金代码", "基金名称", "金额 (元)"]
                preview_df["金额 (元)"] = preview_df["金额 (元)"].map(lambda x: f"{x:,.2f}")
                st.dataframe(preview_df, use_container_width=True)

                if st.button("导入到当前持仓", type="primary", key="btn_import_csv"):
                    imported = 0
                    for row in result.merged_rows:
                        # Avoid duplicates — update amount if code already exists
                        existing = next(
                            (h for h in st.session_state.holdings if h["fund_code"] == row["fund_code"]),
                            None,
                        )
                        if existing is None:
                            st.session_state.holdings.append({
                                "fund_code": row["fund_code"],
                                "fund_name": row["fund_name"],
                                "amount": row["amount"],
                            })
                            imported += 1
                        else:
                            existing["amount"] = row["amount"]
                            existing["fund_name"] = row["fund_name"] or existing["fund_name"]
                            imported += 1
                    st.success(f"已导入 {imported} 条持仓记录")
                    st.rerun()
            else:
                st.info("未解析到有效持仓行。")

            # Skipped rows detail
            if result.skipped_rows:
                with st.expander(f"查看跳过的行（共 {len(result.skipped_rows)} 行）"):
                    for item in result.skipped_rows:
                        st.text(f"原因：{item['reason']}　原始数据：{item['raw_row']}")

st.divider()

# Input form
st.subheader("✏️ 手动添加持仓")
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

    # -----------------------------------------------------------------------
    # Send to Virtual Account Section
    # -----------------------------------------------------------------------
    st.divider()

    # Only show when holdings exist (spec Section 五: 显示条件)
    total_import_amount = sum(h["amount"] for h in st.session_state.holdings)

    with st.expander("📤 发送到虚拟账户", expanded=False):
        st.info("⚠️ 所有持仓将按 NAV=1.0 建仓，仅用于建立模拟起点，不代表真实持仓成本。")

        col_left, col_right = st.columns(2)
        with col_left:
            account_type = st.radio(
                "目标账户类型",
                options=["新建账户", "已有账户"],
                horizontal=True,
                key="va_account_type",
            )

        if account_type == "新建账户":
            new_account_id = st.text_input(
                "账户 ID",
                placeholder="输入新账户 ID",
                key="va_new_account_id",
            )
            min_cash = total_import_amount
            initial_cash_input = st.number_input(
                "初始资金",
                min_value=float(min_cash),
                value=float(min_cash),
                step=10000.0,
                key="va_initial_cash",
            )
            mode = "replace"  # New account always uses replace
        else:
            existing_account_id = st.text_input(
                "账户 ID",
                placeholder="输入已有账户 ID",
                key="va_existing_account_id",
            )
            mode = st.radio(
                "导入模式",
                options=["追加到现有持仓", "替换现有持仓"],
                horizontal=True,
                key="va_import_mode",
            )
            mode = "append" if mode == "追加到现有持仓" else "replace"

        if st.button("确认导入", type="primary", key="btn_import_to_va"):
            from service.simulation_service import SimulationService as SimService

            va_service = SimService()

            # Determine account_id based on type
            if account_type == "新建账户":
                account_id = new_account_id
                initial_cash = initial_cash_input
            else:
                account_id = existing_account_id
                initial_cash = 0.0  # Not used for existing account

            # Validate account_id
            if not account_id or not account_id.strip():
                st.warning("请输入账户 ID")
            else:
                try:
                    result = va_service.import_holdings(
                        holdings=st.session_state.holdings,
                        account_id=account_id,
                        mode=mode,
                        initial_cash=initial_cash,
                        nav=1.0,
                    )

                    st.success(
                        f"✅ 已将 {result['imported_count']} 条持仓导入账户 {account_id}（模式：{mode}）"
                    )
                    st.page_link("pages/3_strategy_lab.py", label="前往策略验证页查看 →")

                except ValueError as e:
                    error_msg = str(e)
                    if "Account not found" in error_msg:
                        st.error(f"未找到账户 {account_id}，请先在策略验证页创建账户")
                    elif "Insufficient cash" in error_msg:
                        account = va_service.get_account(account_id)
                        current_cash = account.cash if account else 0
                        needed = total_import_amount
                        st.error(f"账户余额不足，无法追加导入。当前余额：¥{current_cash:,.0f}，需要：¥{needed:,.0f}")
                    elif "Initial cash" in error_msg:
                        st.error(f"初始资金必须 ≥ 持仓总金额 ¥{total_import_amount:,.0f}")
                    else:
                        st.error(f"导入失败：{error_msg}")
else:
    st.info("👈 请添加持仓后开始诊断")

"""Strategy Lab Page - Create virtual account, execute trades, view positions."""
import streamlit as st
from service.simulation_service import SimulationService
from datetime import date

st.set_page_config(
    page_title="策略验证 - FundScope",
    page_icon="🧪",
)

st.title("🧪 策略验证中心")
st.markdown("创建虚拟账户，执行模拟交易，跟踪持仓收益")

# Initialize service
@st.cache_resource
def get_simulation_service():
    return SimulationService()

service = get_simulation_service()

# Session state
if "current_account" not in st.session_state:
    st.session_state.current_account = None
if "account_id" not in st.session_state:
    st.session_state.account_id = ""

# Create account section
if not st.session_state.current_account:
    st.subheader("创建虚拟账户")
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        account_id = st.text_input("账户 ID", placeholder="例如：my_account_001")
    with col2:
        initial_cash = st.number_input("初始资金 (元)", min_value=1000.0, step=10000.0, value=100000.0)
    with col3:
        if st.button("创建账户", type="primary", use_container_width=True):
            if account_id:
                try:
                    account = service.create_account(account_id, initial_cash)
                    st.session_state.current_account = account
                    st.session_state.account_id = account_id
                    st.success(f"账户 {account_id} 创建成功！")
                    st.rerun()
                except Exception as e:
                    st.error(f"创建失败：{str(e)}")
            else:
                st.warning("请输入账户 ID")
else:
    # Account dashboard
    account = st.session_state.current_account

    # Refresh account data
    account = service.get_account(st.session_state.account_id)
    st.session_state.current_account = account

    st.subheader(f"账户：{account.account_id}")

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("现金余额", f"¥{account.cash:,.0f}")
    with col2:
        st.metric("初始资金", f"¥{account.initial_cash:,.0f}")
    with col3:
        used = account.initial_cash - account.cash
        st.metric("已用资金", f"¥{used:,.0f}")
    with col4:
        st.metric("持仓数量", len(account.positions))

    # Trade form
    st.subheader("执行交易")
    tab_buy, tab_sell = st.tabs(["买入", "卖出"])

    with tab_buy:
        col1, col2, col3, col4 = st.columns([2, 3, 2, 1])
        with col1:
            buy_code = st.text_input("基金代码", key="buy_code", max_chars=6)
        with col2:
            buy_name = st.text_input("基金名称", key="buy_name")
        with col3:
            buy_amount = st.number_input("买入金额 (元)", min_value=100.0, step=1000.0, key="buy_amount")
        with col4:
            nav = st.number_input("成交净值", min_value=0.01, step=0.01, value=1.0, key="buy_nav")

        if st.button("买入", type="primary", key="exec_buy"):
            if buy_code and buy_name and buy_amount > 0:
                try:
                    service.execute_buy(
                        account.account_id,
                        buy_code,
                        buy_name,
                        buy_amount,
                        nav,
                        reason="手动买入"
                    )
                    st.session_state.current_account = service.get_account(account.account_id)
                    st.success(f"买入成功：{buy_amount}元 {buy_name}")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:
                    st.error(f"交易失败：{str(e)}")
            else:
                st.warning("请填写完整交易信息")

    with tab_sell:
        # Get position options
        position_options = {p["fund_code"]: f"{p['fund_name']} ({p['fund_code']})" for p in account.positions}

        if position_options:
            col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
            with col1:
                sell_code = st.selectbox("选择持仓", options=list(position_options.keys()), format_func=lambda x: position_options[x], key="sell_select")
            with col2:
                sell_name = st.text_input("基金名称", key="sell_name", value=position_options.get(sell_code, "").split(" ")[0] if sell_code else "")
            with col3:
                sell_amount = st.number_input("卖出金额 (元)", min_value=100.0, step=1000.0, key="sell_amount")
            with col4:
                sell_nav = st.number_input("成交净值", min_value=0.01, step=0.01, value=1.0, key="sell_nav")

            if st.button("卖出", type="primary", key="exec_sell"):
                if sell_code and sell_name and sell_amount > 0:
                    try:
                        service.execute_sell(
                            account.account_id,
                            sell_code,
                            sell_name,
                            sell_amount,
                            sell_nav,
                            reason="手动卖出"
                        )
                        st.session_state.current_account = service.get_account(account.account_id)
                        st.success(f"卖出成功：{sell_amount}元 {sell_name}")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"交易失败：{str(e)}")
                else:
                    st.warning("请填写完整交易信息")
        else:
            st.info("暂无持仓，请先买入")

    # Positions table
    st.subheader("当前持仓")
    if account.positions:
        positions_data = []
        for p in account.positions:
            positions_data.append({
                "基金代码": p["fund_code"],
                "基金名称": p.get("fund_name", ""),
                "金额": f"¥{p['amount']:,.0f}",
                "份额": f"{p.get('shares', 0):.2f}",
                "成本净值": f"¥{p.get('cost_nav', 1.0):.4f}",
            })
        st.table(positions_data)
    else:
        st.info("暂无持仓")

    # Trade history
    st.subheader("交易记录")
    if account.trades:
        trades_data = []
        for t in reversed(account.trades[-10:]):  # Last 10 trades
            trades_data.append({
                "日期": str(t.trade_date),
                "类型": "买入" if t.action == "BUY" else "卖出",
                "基金代码": t.fund_code,
                "金额": f"¥{t.amount:,.0f}",
                "净值": f"¥{t.nav:.4f}",
                "份额": f"{t.shares:.2f}",
            })
        st.table(trades_data)
    else:
        st.info("暂无交易记录")

    # Switch account button
    if st.button("切换账户"):
        st.session_state.current_account = None
        st.session_state.account_id = ""
        st.rerun()

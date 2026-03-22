"""Strategy Lab Page - Create virtual account, execute trades, view positions."""
import streamlit as st
from service.simulation_service import SimulationService
from service.backtest_service import BacktestService
from datetime import date, timedelta
import plotly.graph_objects as go

st.set_page_config(
    page_title="策略验证 - FundScope",
    page_icon="🧪",
)

st.title("🧪 策略验证中心")
st.markdown("创建虚拟账户，执行模拟交易，跟踪持仓收益")

# Create tabs
tab_account, tab_backtest = st.tabs(["虚拟账户", "策略回测"])

# ========== Virtual Account Tab ==========
with tab_account:
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

# ========== Backtest Tab ==========
with tab_backtest:
    st.subheader("策略回测")
    st.markdown("选择基金和策略，运行历史回测")

    # Initialize backtest service
    @st.cache_resource
    def get_backtest_service():
        return BacktestService()

    backtest_service = get_backtest_service()

    # Input form
    col1, col2 = st.columns(2)
    with col1:
        backtest_fund_code = st.text_input("基金代码", placeholder="例如：000001", max_chars=6, key="bt_fund_code")
    with col2:
        strategy_name = st.selectbox("策略选择", options=["DCA", "MA Timing", "DCA + MA Filter"], key="bt_strategy")

    # Strategy parameters
    st.markdown("**策略参数**")
    if strategy_name == "DCA":
        col1, col2 = st.columns(2)
        with col1:
            dca_invest_amount = st.number_input("每次投资金额 (元)", min_value=1000.0, step=1000.0, value=10000.0, key="bt_dca_amount")
        with col2:
            dca_interval = st.number_input("投资间隔 (天)", min_value=7, step=7, value=20, key="bt_dca_interval")
        strategy_params = {
            "invest_amount": dca_invest_amount,
            "interval_days": dca_interval
        }
    elif strategy_name == "MA Timing":
        col1, col2 = st.columns(2)
        with col1:
            ma_short_window = st.number_input("短期均线 (天)", min_value=3, step=1, value=5, key="bt_ma_short")
        with col2:
            ma_long_window = st.number_input("长期均线 (天)", min_value=10, step=5, value=20, key="bt_ma_long")
        strategy_params = {
            "short_window": ma_short_window,
            "long_window": ma_long_window
        }
    else:  # DCA + MA Filter
        col1, col2, col3 = st.columns(3)
        with col1:
            dca_invest_amount = st.number_input("每次投资金额 (元)", min_value=1000.0, step=1000.0, value=10000.0, key="bt_dca_amount")
        with col2:
            dca_interval = st.number_input("投资间隔 (天)", min_value=7, step=7, value=20, key="bt_dca_interval")
        with col3:
            ma_window = st.number_input("MA 窗口 (天)", min_value=5, step=1, value=20, key="bt_ma_window")
        strategy_params = {
            "invest_amount": dca_invest_amount,
            "interval_days": dca_interval,
            "ma_window": ma_window
        }

    # Date range
    st.markdown("**回测区间**")
    col1, col2 = st.columns(2)
    with col1:
        default_start = date.today() - timedelta(days=365)
        start_date = st.date_input("开始日期", value=default_start, key="bt_start_date")
    with col2:
        end_date = st.date_input("结束日期", value=date.today(), key="bt_end_date")

    # Initial cash
    initial_cash = st.number_input("初始资金 (元)", min_value=10000.0, step=10000.0, value=100000.0, key="bt_initial_cash")

    # Run backtest button
    if st.button("运行回测", type="primary", use_container_width=True):
        if backtest_fund_code:
            if start_date >= end_date:
                st.error("开始日期必须早于结束日期")
            else:
                with st.spinner(f"正在回测基金 {backtest_fund_code}..."):
                    try:
                        result = backtest_service.run_backtest(
                            fund_code=backtest_fund_code,
                            strategy_name=strategy_name,
                            strategy_params=strategy_params,
                            start_date=start_date,
                            end_date=end_date,
                            initial_cash=initial_cash
                        )

                        # Metrics display
                        st.subheader("回测结果")
                        col1, col2, col3, col4, col5 = st.columns(5)
                        with col1:
                            total_return_pct = result.total_return * 100
                            return_color = "green" if total_return_pct >= 0 else "red"
                            col1.metric("总收益", f"{total_return_pct:.2f}%", delta=f"{total_return_pct:+.2f}%" if total_return_pct != 0 else None)
                        with col2:
                            annual_return_pct = result.annualized_return * 100
                            col2.metric("年化收益", f"{annual_return_pct:.2f}%")
                        with col3:
                            max_dd_pct = result.max_drawdown * 100
                            col3.metric("最大回撤", f"-{max_dd_pct:.2f}%", delta=f"{-max_dd_pct:.2f}%" if max_dd_pct > 0 else None, delta_color="inverse")
                        with col4:
                            col4.metric("夏普比率", f"{result.sharpe_ratio:.2f}")
                        with col5:
                            col5.metric("胜率", f"{result.win_rate:.1%}")

                        # Equity curve chart
                        st.subheader("净值曲线")
                        if result.equity_curve:
                            dates = [point[0] for point in result.equity_curve]
                            values = [point[1] for point in result.equity_curve]

                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=dates,
                                y=values,
                                mode='lines',
                                name='账户净值',
                                line=dict(color='blue', width=2)
                            ))

                            fig.update_layout(
                                title='回测期间账户净值变化',
                                xaxis_title='日期',
                                yaxis_title='账户净值 (元)',
                                hovermode='x unified',
                                height=400
                            )

                            st.plotly_chart(fig, use_container_width=True)

                        # Executed trades table
                        st.subheader("交易记录")
                        if result.executed_trades:
                            trades_data = []
                            for t in result.executed_trades:
                                trades_data.append({
                                    "日期": str(t.date),
                                    "类型": "买入" if t.action == "BUY" else "卖出",
                                    "基金代码": t.fund_code,
                                    "金额": f"¥{t.amount:,.0f}",
                                    "净值": f"¥{t.nav:.4f}",
                                    "份额": f"{t.shares:.2f}",
                                    "原因": t.reason
                                })
                            st.table(trades_data)

                            # Trade statistics
                            col1, col2 = st.columns(2)
                            with col1:
                                buy_trades = [t for t in result.executed_trades if t.action == "BUY"]
                                st.metric("买入次数", len(buy_trades))
                            with col2:
                                sell_trades = [t for t in result.executed_trades if t.action == "SELL"]
                                st.metric("卖出次数", len(sell_trades))
                        else:
                            st.info("回测期间无交易执行")

                        # Explanation panel for composite strategy
                        # IMPORTANT: Check result.strategy_name, NOT dropdown value
                        is_composite_result = "MAFilter" in result.strategy_name

                        if is_composite_result:
                            st.divider()
                            with st.expander("📋 信号解释", expanded=False):
                                final_signal_count = len(result.signals)
                                blocked_count = len(result.blocked_signals)

                                col1, col2 = st.columns(2)
                                with col1:
                                    st.metric("最终信号", final_signal_count)
                                with col2:
                                    st.metric("被拦截信号", blocked_count)

                                if blocked_count == 0:
                                    st.success("本次组合策略运行中没有信号被拦截。")
                                else:
                                    st.markdown("**拦截详情：**")
                                    for item in result.blocked_signals:
                                        signal = item.original
                                        st.write(
                                            f"- {signal.date} **{signal.action}** "
                                            f"({item.modifier}) → {item.reason}"
                                        )

                    except Exception as e:
                        st.error(f"回测失败：{str(e)}")
        else:
            st.warning("请输入基金代码")

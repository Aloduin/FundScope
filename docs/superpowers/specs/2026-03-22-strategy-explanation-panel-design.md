# Phase 3B: 策略解释面板 — 设计文档

**日期：** 2026-03-22
**版本：** v1.0
**目标：** 在回测结果中展示被拦截信号，让用户理解组合策略的过滤逻辑。

---

## 一、背景与目标

### 1.1 当前状态

**已有数据流：**
```
UI (策略选择) → BacktestService → BacktestEngine → Strategy → BacktestResult → UI (展示结果)
```

**CompositeStrategy 已实现：**
- `get_blocked_signals()` 返回被拦截信号列表
- 每条记录：`{original: Signal, modifier: str, reason: str}`

**缺失环节：**
1. `BacktestResult` 没有 `blocked_signals` 字段
2. `BacktestService` 不支持创建 CompositeStrategy
3. UI 没有组合策略选项和被拦截信号展示

### 1.2 目标

- 扩展回测结果模型，携带被拦截信号数据
- 在回测 UI 中增加组合策略选项
- 展示信号过滤解释面板

### 1.3 不做的事

- 多策略组合器（通用 UI 组合任意策略）
- RebalancePolicy 接入（Phase 3C）
- 信号修改历史详细 trace（仅展示拦截）

---

## 二、架构变更

### 2.1 数据模型变更

**文件：** `domain/backtest/models.py`

```python
@dataclass
class BacktestResult:
    """Backtest result summary."""
    strategy_name: str
    fund_code: str
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    trade_count: int
    signals: list[Signal] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    executed_trades: list[ExecutedTrade] = field(default_factory=list)
    blocked_signals: list[dict] = field(default_factory=list)  # 新增
```

### 2.2 Engine 变更

**文件：** `domain/backtest/engine.py`

在 `run()` 方法末尾：
```python
# Check if strategy is CompositeStrategy and collect blocked signals
if isinstance(strategy, CompositeStrategy):
    result.blocked_signals = strategy.get_blocked_signals()
```

### 2.3 Service 变更

**文件：** `service/backtest_service.py`

新增策略类型：
```python
def _create_strategy(self, strategy_name: str, params: dict) -> Strategy:
    if strategy_name == "DCA":
        return DCAStrategy(...)
    elif strategy_name == "MA Timing":
        return MAStrategy(...)
    elif strategy_name == "DCA + MA Filter":
        dca = DCAStrategy(
            invest_amount=params.get("invest_amount", 10000),
            invest_interval_days=params.get("interval_days", 20)
        )
        ma_filter = MAFilter(
            window=params.get("ma_window", 20)
        )
        return CompositeStrategy(primary_strategy=dca, modifier=ma_filter)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
```

### 2.4 UI 变更

**文件：** `ui/pages/3_strategy_lab.py`

**策略选择：**
```python
strategy_name = st.selectbox(
    "策略选择",
    options=["DCA", "MA Timing", "DCA + MA Filter"],
    key="bt_strategy"
)
```

**参数配置（仅 DCA + MA Filter 时显示）：**
```python
if strategy_name == "DCA + MA Filter":
    col1, col2, col3 = st.columns(3)
    with col1:
        dca_invest_amount = st.number_input("每次投资金额 (元)", ...)
    with col2:
        dca_interval = st.number_input("投资间隔 (天)", ...)
    with col3:
        ma_window = st.number_input("MA 窗口 (天)", min_value=5, value=20)
```

**结果展示：**
```python
# 信号解释面板（仅当有 blocked_signals 时显示）
if result.blocked_signals:
    with st.expander("📋 信号解释", expanded=False):
        passed_count = len(result.executed_trades)
        blocked_count = len(result.blocked_signals)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("✅ 通过信号", passed_count)
        with col2:
            st.metric("⛔ 被拦截信号", blocked_count)

        if blocked_count > 0:
            st.markdown("**拦截详情：**")
            for item in result.blocked_signals:
                signal = item["original"]
                reason = item["reason"]
                st.write(f"- {signal.date} **{signal.action}** → {reason}")
```

---

## 三、文件变更清单

| 文件 | 动作 |
|---|---|
| `domain/backtest/models.py` | 新增 `blocked_signals` 字段 |
| `domain/backtest/engine.py` | 检测 CompositeStrategy 并获取 blocked_signals |
| `service/backtest_service.py` | 新增 "DCA + MA Filter" 策略创建 |
| `ui/pages/3_strategy_lab.py` | 新增组合策略选项、参数、解释面板 |

---

## 四、测试覆盖

| 测试用例 | 验证点 |
|---|---|
| BacktestResult 默认 blocked_signals 为空 | 新字段默认值 |
| Engine + CompositeStrategy 返回 blocked_signals | 集成正确 |
| BacktestService 创建 "DCA + MA Filter" | 策略实例化正确 |
| UI 展示 blocked_signals | 前端渲染正确 |

---

## 五、使用示例

用户操作流程：
1. 进入策略验证页 → 回测 Tab
2. 选择策略："DCA + MA Filter"
3. 配置参数：每次 10000 元，间隔 20 天，MA 窗口 20 天
4. 运行回测
5. 查看结果，点击 "📋 信号解释" 展开面板
6. 看到被拦截的买入信号及其原因

---

## 六、后续扩展

- Phase 3C: RebalancePolicy 接入
- 更多组合策略选项（MA + 其他过滤器）
- 信号修改历史详细 trace（非仅拦截）
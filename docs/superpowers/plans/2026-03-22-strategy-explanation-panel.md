# Phase 3B: 策略解释面板 Implementation Plan（最终可执行版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测结果中展示组合策略被拦截的信号及原因，让用户理解过滤逻辑，形成 “策略执行 → 结果展示 → 信号解释” 的完整闭环。

**Architecture:**

* 新增 `BlockedSignalTrace` dataclass 作为统一的拦截信号追踪模型
* `Strategy` 基类增加 `get_blocked_signals()` 默认方法，保证 engine 可统一读取
* `CompositeStrategy` 返回 `list[BlockedSignalTrace]`，替代原来的 `list[dict]`
* `BacktestEngine` 不再判断具体策略类型，而是统一通过 `strategy.get_blocked_signals()` 获取解释数据
* `BacktestService` 支持创建 `"DCA + MA Filter"` 组合策略
* `ui/pages/3_strategy_lab.py` 增加组合策略选项、参数区和解释面板

**Scope constraints:**

* 本阶段仅消费 Phase 3A 已实现的过滤型组合策略能力
* 不接入 RebalancePolicy 主流程
* 不做通用多策略组合 UI
* 不做完整信号修改历史，只展示“被拦截信号”

**Phase 3A consistency:**
本计划基于已确定的 Phase 3A 设计：`CompositeStrategy + SignalModifier + MAFilter` 为主流程，`RebalancePolicy` 仅保留接口、不接入主流程。
另外，`ThresholdRebalancePolicy` 的阈值与归一化约束仍作为后续预留，不纳入 Phase 3B 实现范围。

---

## File Structure

```text
domain/backtest/
├── models.py                    # 新增 BlockedSignalTrace；扩展 BacktestResult
└── strategies/
    ├── base.py                  # 新增 get_blocked_signals() 默认方法
    └── composite.py             # 修改返回类型为 list[BlockedSignalTrace]

service/
└── backtest_service.py          # 新增 "DCA + MA Filter" 策略创建

ui/pages/
└── 3_strategy_lab.py            # 新增组合策略选项、参数、解释面板

tests/domain/backtest/
├── test_models.py               # 新增 BlockedSignalTrace 测试
├── test_engine.py               # 新增 engine blocked_signals 测试
└── strategies/
    ├── test_base.py             # 新增 get_blocked_signals() 默认方法测试
    └── test_composite.py        # 修改测试适配新返回类型

tests/service/
└── test_backtest_service.py     # 新增组合策略创建与 blocked_signals 集成测试
```

---

## Task 1: 新增 BlockedSignalTrace dataclass

**Files:**

* Modify: `domain/backtest/models.py`
* Modify: `tests/domain/backtest/test_models.py`

### - [ ] Step 1: 为 BlockedSignalTrace 编写失败测试

将下面测试追加到 `tests/domain/backtest/test_models.py`：

```python
from datetime import date

class TestBlockedSignalTrace:
    """Tests for BlockedSignalTrace dataclass."""

    def test_blocked_signal_trace_creation(self):
        from domain.backtest.models import Signal, BlockedSignalTrace

        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        trace = BlockedSignalTrace(
            original=signal,
            modifier="MAFilter(20, trend_confirm)",
            reason="买入信号被拦截：当前净值低于20日均线"
        )

        assert trace.original == signal
        assert trace.modifier == "MAFilter(20, trend_confirm)"
        assert "买入信号被拦截" in trace.reason

    def test_backtest_result_blocked_signals_default_empty(self):
        from domain.backtest.models import BacktestResult

        result = BacktestResult(
            strategy_name="DCA",
            fund_code="000001",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            total_return=0.10,
            annualized_return=0.10,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            win_rate=0.6,
            trade_count=5,
        )

        assert result.blocked_signals == []
```

### - [ ] Step 2: 运行测试，确认失败

```bash
uv run pytest tests/domain/backtest/test_models.py::TestBlockedSignalTrace -v
```

Expected: FAIL with `cannot import name 'BlockedSignalTrace'`

### - [ ] Step 3: 实现 BlockedSignalTrace

在 `domain/backtest/models.py` 中增加：

```python
from dataclasses import dataclass, field
from datetime import date

@dataclass
class BlockedSignalTrace:
    """Trace record for a blocked signal."""
    original: Signal
    modifier: str
    reason: str
```

### - [ ] Step 4: 扩展 BacktestResult

在 `domain/backtest/models.py` 中为 `BacktestResult` 增加字段：

```python
@dataclass
class BacktestResult:
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
    blocked_signals: list[BlockedSignalTrace] = field(default_factory=list)
```

### - [ ] Step 5: 运行测试，确认通过

```bash
uv run pytest tests/domain/backtest/test_models.py::TestBlockedSignalTrace -v
```

Expected: PASS

### - [ ] Step 6: Commit

```bash
git add domain/backtest/models.py tests/domain/backtest/test_models.py
git commit -m "feat(backtest): add BlockedSignalTrace and extend BacktestResult"
```

---

## Task 2: Strategy 基类新增 get_blocked_signals() 默认方法

**Files:**

* Modify: `domain/backtest/strategies/base.py`
* Modify: `tests/domain/backtest/strategies/test_base.py`

### - [ ] Step 1: 编写失败测试

将下面测试追加到 `tests/domain/backtest/strategies/test_base.py` 的 `TestStrategyInterface` 中：

```python
def test_strategy_default_get_blocked_signals_returns_empty_list(self):
    """Test that default get_blocked_signals returns empty list."""
    from domain.backtest.strategies.base import Strategy

    class MinimalStrategy(Strategy):
        def name(self) -> str:
            return "Minimal"

        def generate_signals(self, nav_history: list[dict]) -> list:
            return []

    strategy = MinimalStrategy()
    assert strategy.get_blocked_signals() == []
```

### - [ ] Step 2: 运行测试，确认失败

```bash
uv run pytest tests/domain/backtest/strategies/test_base.py::TestStrategyInterface::test_strategy_default_get_blocked_signals_returns_empty_list -v
```

Expected: FAIL with `'MinimalStrategy' object has no attribute 'get_blocked_signals'`

### - [ ] Step 3: 在 Strategy 基类中增加默认方法

修改 `domain/backtest/strategies/base.py`：

```python
from abc import ABC, abstractmethod
from domain.backtest.models import Signal, BlockedSignalTrace

class Strategy(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        raise NotImplementedError

    def get_blocked_signals(self) -> list[BlockedSignalTrace]:
        """Default: no blocked signals."""
        return []
```

### - [ ] Step 4: 运行测试，确认通过

```bash
uv run pytest tests/domain/backtest/strategies/test_base.py::TestStrategyInterface::test_strategy_default_get_blocked_signals_returns_empty_list -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/strategies/base.py tests/domain/backtest/strategies/test_base.py
git commit -m "feat(backtest): add default get_blocked_signals() to Strategy"
```

---

## Task 3: CompositeStrategy 改为返回 BlockedSignalTrace 列表

**Files:**

* Modify: `domain/backtest/strategies/composite.py`
* Modify: `tests/domain/backtest/strategies/test_composite.py`

### - [ ] Step 1: 先改测试，切换为属性访问

在 `tests/domain/backtest/strategies/test_composite.py` 中，把原先基于 dict 的断言改为 dataclass 属性访问。

例如：

```python
blocked = composite.get_blocked_signals()
assert len(blocked) == 1
assert blocked[0].original.action == "BUY"
assert "买入信号被拦截" in blocked[0].reason
```

同时把其他相关测试中的：

```python
record["original"]
record["modifier"]
record["reason"]
```

全部替换成：

```python
record.original
record.modifier
record.reason
```

### - [ ] Step 2: 运行测试，确认失败

```bash
uv run pytest tests/domain/backtest/strategies/test_composite.py -v
```

Expected: FAIL with `'dict' object has no attribute 'original'`

### - [ ] Step 3: 修改 CompositeStrategy

更新 `domain/backtest/strategies/composite.py`：

```python
import dataclasses
from domain.backtest.models import Signal, SignalContext, BlockedSignalTrace
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.modifiers.base import SignalModifier

class CompositeStrategy(Strategy):
    def __init__(self, primary_strategy: Strategy, modifier: SignalModifier | None = None):
        self.primary_strategy = primary_strategy
        self.modifier = modifier
        self._blocked_signals: list[BlockedSignalTrace] = []

    def name(self) -> str:
        if self.modifier is None:
            return self.primary_strategy.name()
        return f"{self.primary_strategy.name()}+{self.modifier.name()}"

    def get_blocked_signals(self) -> list[BlockedSignalTrace]:
        return self._blocked_signals.copy()

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        self._blocked_signals = []

        if not nav_history:
            return []

        base_signals = self.primary_strategy.generate_signals(nav_history)

        if self.modifier is None:
            return base_signals

        final_signals = []
        for signal in base_signals:
            context = self._build_context(signal, nav_history)
            result = self.modifier.modify(signal, context)

            if result is not None:
                final_signals.append(result)
            else:
                self._blocked_signals.append(
                    BlockedSignalTrace(
                        original=dataclasses.replace(signal),
                        modifier=self.modifier.name(),
                        reason=self.modifier.explain_block(signal, context),
                    )
                )

        return final_signals
```

### - [ ] Step 4: 运行 CompositeStrategy 全量测试

```bash
uv run pytest tests/domain/backtest/strategies/test_composite.py -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/strategies/composite.py tests/domain/backtest/strategies/test_composite.py
git commit -m "refactor(backtest): CompositeStrategy returns BlockedSignalTrace list"
```

---

## Task 4: BacktestEngine 统一读取 blocked_signals

**Files:**

* Modify: `domain/backtest/engine.py`
* Modify: `tests/domain/backtest/test_engine.py`

### - [ ] Step 1: 编写 engine 侧失败测试

在 `tests/domain/backtest/test_engine.py` 中新增：

```python
from datetime import date, timedelta

class TestBacktestEngineBlockedSignals:
    """Tests for blocked signals in backtest results."""

    def test_engine_with_composite_strategy_returns_blocked_signals(self):
        from domain.backtest.strategies.composite import CompositeStrategy
        from domain.backtest.strategies.dca import DCAStrategy
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        engine = BacktestEngine(initial_cash=100000)

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 - i * 0.01, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        result = engine.run(composite, fund_code="000001", nav_history=nav_history)

        assert len(result.blocked_signals) > 0
        assert result.blocked_signals[0].original.action == "BUY"

    def test_engine_with_composite_strategy_no_blocks(self):
        from domain.backtest.strategies.composite import CompositeStrategy
        from domain.backtest.strategies.dca import DCAStrategy
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        engine = BacktestEngine(initial_cash=100000)

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 + i * 0.01, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        result = engine.run(composite, fund_code="000001", nav_history=nav_history)

        assert result.blocked_signals == []

    def test_engine_with_normal_strategy_empty_blocked_signals(self):
        from domain.backtest.strategies.dca import DCAStrategy

        engine = BacktestEngine(initial_cash=100000)

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 + i * 0.001, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        result = engine.run(dca, fund_code="000001", nav_history=nav_history)

        assert result.blocked_signals == []
```

### - [ ] Step 2: 运行测试，确认失败

```bash
uv run pytest tests/domain/backtest/test_engine.py::TestBacktestEngineBlockedSignals -v
```

Expected: FAIL because `blocked_signals` is missing or always empty

### - [ ] Step 3: 修改 engine 统一采集 blocked_signals

修改 `domain/backtest/engine.py`，在 `run()` 中：

```python
signals = strategy.generate_signals(nav_history)
blocked_signals = strategy.get_blocked_signals()
```

并在构造 `BacktestResult` 时写入：

```python
return BacktestResult(
    strategy_name=strategy.name(),
    fund_code=fund_code,
    start_date=nav_history[0]["date"],
    end_date=nav_history[-1]["date"],
    total_return=total_return,
    annualized_return=annualized_return,
    max_drawdown=max_drawdown,
    sharpe_ratio=sharpe_ratio,
    win_rate=win_rate,
    trade_count=len(executed_trades),
    signals=signals,
    equity_curve=equity_curve,
    executed_trades=executed_trades,
    blocked_signals=blocked_signals,
)
```

> 注意：如果当前 engine 内部变量名仍是 `trades`，应先统一为 `executed_trades`，再做本改动。

### - [ ] Step 4: 运行测试，确认通过

```bash
uv run pytest tests/domain/backtest/test_engine.py::TestBacktestEngineBlockedSignals -v
```

Expected: PASS

### - [ ] Step 5: 跑完整 backtest 测试

```bash
uv run pytest tests/domain/backtest/ -v
```

Expected: All pass

### - [ ] Step 6: Commit

```bash
git add domain/backtest/engine.py tests/domain/backtest/test_engine.py
git commit -m "feat(backtest): engine collects blocked_signals via Strategy interface"
```

---

## Task 5: BacktestService 支持 `"DCA + MA Filter"` 组合策略

**Files:**

* Modify: `service/backtest_service.py`
* Modify: `tests/service/test_backtest_service.py`

### - [ ] Step 1: 编写失败测试

在 `tests/service/test_backtest_service.py` 中新增：

```python
from datetime import date, timedelta
from unittest.mock import patch

def test_service_creates_composite_strategy(self):
    """Test that service creates DCA + MA Filter composite strategy."""
    service = BacktestService()

    strategy = service._create_strategy("DCA + MA Filter", {
        "invest_amount": 10000,
        "interval_days": 20,
        "ma_window": 20,
    })

    assert strategy.name() == "DCA+MAFilter(20, trend_confirm)"

def test_run_backtest_returns_blocked_signals_in_result(self):
    """Test that run_backtest returns blocked_signals in result."""
    service = BacktestService()

    nav_history = []
    for i in range(60):
        d = date(2023, 1, 1) + timedelta(days=i)
        nav_history.append({"date": d, "nav": 1.0 - i * 0.01, "acc_nav": 1.0})

    with patch.object(service.datasource, "get_fund_nav_history", return_value=nav_history):
        result = service.run_backtest(
            fund_code="000001",
            strategy_name="DCA + MA Filter",
            strategy_params={
                "invest_amount": 1000,
                "interval_days": 20,
                "ma_window": 20,
            },
            start_date=date(2023, 1, 1),
            end_date=date(2023, 3, 1),
            initial_cash=100000
        )

    assert len(result.blocked_signals) > 0
    assert result.blocked_signals[0].original.action == "BUY"
```

### - [ ] Step 2: 运行测试，确认失败

```bash
uv run pytest tests/service/test_backtest_service.py::TestBacktestService::test_service_creates_composite_strategy tests/service/test_backtest_service.py::TestBacktestService::test_run_backtest_returns_blocked_signals_in_result -v
```

Expected: FAIL with `Unknown strategy: DCA + MA Filter`

### - [ ] Step 3: 实现组合策略创建

修改 `service/backtest_service.py`：

```python
from domain.backtest.strategies.composite import CompositeStrategy
from domain.backtest.strategies.modifiers.ma_filter import MAFilter
```

并更新 `_create_strategy()`：

```python
def _create_strategy(self, strategy_name: str, params: dict) -> Strategy:
    if strategy_name == "DCA":
        return DCAStrategy(
            invest_amount=params.get("invest_amount", 10000),
            invest_interval_days=params.get("interval_days", 20)
        )
    elif strategy_name == "MA Timing":
        return MAStrategy(
            short_window=params.get("short_window", 5),
            long_window=params.get("long_window", 20)
        )
    elif strategy_name == "DCA + MA Filter":
        dca = DCAStrategy(
            invest_amount=params.get("invest_amount", 10000),
            invest_interval_days=params.get("interval_days", 20),
        )
        ma_filter = MAFilter(
            window=params.get("ma_window", 20)
        )
        return CompositeStrategy(
            primary_strategy=dca,
            modifier=ma_filter,
        )
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")
```

### - [ ] Step 4: 运行测试，确认通过

```bash
uv run pytest tests/service/test_backtest_service.py::TestBacktestService::test_service_creates_composite_strategy tests/service/test_backtest_service.py::TestBacktestService::test_run_backtest_returns_blocked_signals_in_result -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add service/backtest_service.py tests/service/test_backtest_service.py
git commit -m "feat(service): add DCA + MA Filter composite strategy support"
```

---

## Task 6: UI 增加组合策略选项与解释面板

**Files:**

* Modify: `ui/pages/3_strategy_lab.py`

### - [ ] Step 1: 扩展策略下拉框

```python
strategy_name = st.selectbox(
    "策略选择",
    options=["DCA", "MA Timing", "DCA + MA Filter"],
    key="bt_strategy"
)
```

### - [ ] Step 2: 增加 `"DCA + MA Filter"` 参数区

替换原有策略参数逻辑为：

```python
st.markdown("**策略参数**")

if strategy_name == "DCA":
    col1, col2 = st.columns(2)
    with col1:
        dca_invest_amount = st.number_input(
            "每次投资金额 (元)",
            min_value=1000.0,
            step=1000.0,
            value=10000.0,
            key="bt_dca_amount"
        )
    with col2:
        dca_interval = st.number_input(
            "投资间隔 (天)",
            min_value=7,
            step=7,
            value=20,
            key="bt_dca_interval"
        )
    strategy_params = {
        "invest_amount": dca_invest_amount,
        "interval_days": dca_interval,
    }

elif strategy_name == "MA Timing":
    col1, col2 = st.columns(2)
    with col1:
        ma_short_window = st.number_input(
            "短期均线 (天)",
            min_value=3,
            step=1,
            value=5,
            key="bt_ma_short"
        )
    with col2:
        ma_long_window = st.number_input(
            "长期均线 (天)",
            min_value=10,
            step=5,
            value=20,
            key="bt_ma_long"
        )
    strategy_params = {
        "short_window": ma_short_window,
        "long_window": ma_long_window,
    }

elif strategy_name == "DCA + MA Filter":
    col1, col2, col3 = st.columns(3)
    with col1:
        dca_invest_amount = st.number_input(
            "每次投资金额 (元)",
            min_value=1000.0,
            step=1000.0,
            value=10000.0,
            key="bt_dca_amount"
        )
    with col2:
        dca_interval = st.number_input(
            "投资间隔 (天)",
            min_value=7,
            step=7,
            value=20,
            key="bt_dca_interval"
        )
    with col3:
        ma_window = st.number_input(
            "MA 窗口 (天)",
            min_value=5,
            step=1,
            value=20,
            key="bt_ma_window"
        )
    strategy_params = {
        "invest_amount": dca_invest_amount,
        "interval_days": dca_interval,
        "ma_window": ma_window,
    }
```

### - [ ] Step 3: 在结果区域增加解释面板

在回测结果展示区、交易记录区之后增加：

```python
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
```

> 注意：解释面板显示条件要基于 **`result.strategy_name`**，不要仅依赖当前下拉框值，避免用户改动 UI 选择后影响已展示结果。

### - [ ] Step 4: 手工验证 UI

运行：

```bash
uv run streamlit run ui/app.py
```

手工检查：

1. 下拉框出现 `"DCA + MA Filter"`
2. 参数区出现 3 个输入项
3. 运行下跌趋势回测时，解释面板能显示被拦截信号
4. 切换下拉框但不重新运行时，已展示结果仍保持正确解释面板状态

### - [ ] Step 5: Commit

```bash
git add ui/pages/3_strategy_lab.py
git commit -m "feat(ui): add DCA + MA Filter option and explanation panel"
```

---

## Task 7: 全量测试与收尾

### - [ ] Step 1: 跑 backtest 相关测试

```bash
uv run pytest tests/domain/backtest/ tests/service/test_backtest_service.py -v
```

Expected: PASS

### - [ ] Step 2: 跑完整测试套件

```bash
uv run pytest -v
```

Expected: All pass

### - [ ] Step 3: 如有失败，修复并提交

```bash
git add -A
git commit -m "fix: address Phase 3B test failures"
```

### - [ ] Step 4: Push

```bash
git push
```

---

## 验收标准

* [ ] `BlockedSignalTrace` 已落地，`BacktestResult.blocked_signals` 默认空列表
* [ ] `Strategy` 基类默认实现 `get_blocked_signals()`
* [ ] `CompositeStrategy.get_blocked_signals()` 返回 `list[BlockedSignalTrace]`
* [ ] `BacktestEngine` 统一通过 `strategy.get_blocked_signals()` 取解释数据
* [ ] `BacktestService` 支持 `"DCA + MA Filter"`
* [ ] `3_strategy_lab.py` 出现组合策略选项和解释面板
* [ ] 下跌趋势下，`DCA + MA Filter` 能展示被拦截 BUY 信号
* [ ] 普通单策略结果 `blocked_signals == []`
* [ ] 全量测试通过

---

## Summary

| Task                                  | Files Modified                                    | Tests Added/Updated |
| ------------------------------------- | ------------------------------------------------- | ------------------- |
| 1. BlockedSignalTrace                 | `models.py`, `test_models.py`                     | 2                   |
| 2. Strategy base default method       | `base.py`, `test_base.py`                         | 1                   |
| 3. CompositeStrategy typed traces     | `composite.py`, `test_composite.py`               | updated             |
| 4. Engine blocked_signals integration | `engine.py`, `test_engine.py`                     | 3                   |
| 5. Service composite strategy         | `backtest_service.py`, `test_backtest_service.py` | 2                   |
| 6. UI explanation panel               | `3_strategy_lab.py`                               | manual verification |
| 7. Full validation                    | -                                                 | all                 |

**Phase 3B deliverable:**

* `BlockedSignalTrace` dataclass
* Strategy 基类 `get_blocked_signals()` 默认方法
* Engine 统一收集 blocked_signals
* `"DCA + MA Filter"` 组合策略入口
* UI 解释面板

# Phase 3B: 策略解释面板 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在回测结果中展示组合策略拦截的信号及原因，让用户理解过滤逻辑。

**Architecture:** 新增 `BlockedSignalTrace` dataclass 携带拦截数据；Strategy 基类增加 `get_blocked_signals()` 默认方法；Engine 统一调用该接口；BacktestService 支持 "DCA + MA Filter" 组合策略；UI 增加解释面板。

**Tech Stack:** Python 3.13, dataclasses, pytest, Streamlit

---

## File Structure

```text
domain/backtest/
├── models.py                    # 新增 BlockedSignalTrace
└── strategies/
    ├── base.py                  # 新增 get_blocked_signals() 默认方法
    └── composite.py             # 修改返回类型为 list[BlockedSignalTrace]

service/
└── backtest_service.py          # 新增 "DCA + MA Filter" 策略创建

ui/pages/
└── 3_strategy_lab.py            # 新增组合策略选项、参数、解释面板

tests/domain/backtest/
├── test_models.py               # 新增 BlockedSignalTrace 测试
└── strategies/
    └── test_composite.py        # 修改测试适配新返回类型
```

---

## Task 1: 新增 BlockedSignalTrace dataclass

**Files:**
- Modify: `domain/backtest/models.py`
- Modify: `tests/domain/backtest/test_models.py`

### - [ ] Step 1: Write failing tests for BlockedSignalTrace

```python
# tests/domain/backtest/test_models.py - add to existing file

class TestBlockedSignalTrace:
    """Tests for BlockedSignalTrace dataclass."""

    def test_blocked_signal_trace_creation(self):
        from datetime import date
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
        from datetime import date
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

### - [ ] Step 2: Run test to verify it fails

```bash
uv run pytest tests/domain/backtest/test_models.py::TestBlockedSignalTrace -v
```

Expected: FAIL with `cannot import name 'BlockedSignalTrace'`

### - [ ] Step 3: Implement BlockedSignalTrace

```python
# domain/backtest/models.py - add after SignalContext dataclass

@dataclass
class BlockedSignalTrace:
    """Trace record for a blocked signal."""
    original: Signal
    modifier: str
    reason: str
```

### - [ ] Step 4: Extend BacktestResult

```python
# domain/backtest/models.py - add field to BacktestResult

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
    blocked_signals: list[BlockedSignalTrace] = field(default_factory=list)  # 新增
```

### - [ ] Step 5: Run test to verify it passes

```bash
uv run pytest tests/domain/backtest/test_models.py::TestBlockedSignalTrace -v
```

Expected: PASS

### - [ ] Step 6: Commit

```bash
git add domain/backtest/models.py tests/domain/backtest/test_models.py
git commit -m "feat(backtest): add BlockedSignalTrace dataclass and extend BacktestResult"
```

---

## Task 2: Strategy 基类新增 get_blocked_signals() 默认方法

**Files:**
- Modify: `domain/backtest/strategies/base.py`
- Modify: `tests/domain/backtest/strategies/test_base.py`

### - [ ] Step 1: Write failing test for base class method

```python
# tests/domain/backtest/strategies/test_base.py - add to TestStrategyInterface

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

### - [ ] Step 2: Run test to verify it fails

```bash
uv run pytest tests/domain/backtest/strategies/test_base.py::TestStrategyInterface::test_strategy_default_get_blocked_signals_returns_empty_list -v
```

Expected: FAIL with `'Strategy' object has no attribute 'get_blocked_signals'`

### - [ ] Step 3: Implement default method in Strategy base class

```python
# domain/backtest/strategies/base.py - add import at top
from domain.backtest.models import Signal, BlockedSignalTrace

# domain/backtest/strategies/base.py - add method to Strategy class

class Strategy(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    def name(self) -> str:
        """Get strategy name."""
        raise NotImplementedError

    @abstractmethod
    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        """Generate trading signals from NAV history."""
        raise NotImplementedError

    def get_blocked_signals(self) -> list[BlockedSignalTrace]:
        """Return blocked signal traces for explanation panel.

        Default: no blocked signals. Override in CompositeStrategy.
        """
        return []
```

### - [ ] Step 4: Run test to verify it passes

```bash
uv run pytest tests/domain/backtest/strategies/test_base.py::TestStrategyInterface::test_strategy_default_get_blocked_signals_returns_empty_list -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/strategies/base.py tests/domain/backtest/strategies/test_base.py
git commit -m "feat(backtest): add get_blocked_signals() default method to Strategy base class"
```

---

## Task 3: 修改 CompositeStrategy 返回 BlockedSignalTrace 列表

**Files:**
- Modify: `domain/backtest/strategies/composite.py`
- Modify: `tests/domain/backtest/strategies/test_composite.py`

### - [ ] Step 1: Update tests to use attribute access (TDD: test change first)

```python
# tests/domain/backtest/strategies/test_composite.py - update test_blocked_signals_recorded
# Change from dict-style to attribute access:

def test_blocked_signals_recorded(self):
    # ... setup code unchanged ...
    blocked = composite.get_blocked_signals()
    assert len(blocked) == 1
    assert blocked[0].original.action == "BUY"  # attribute access
    assert "买入信号被拦截" in blocked[0].reason  # attribute access
```

### - [ ] Step 2: Run test to verify it fails (dict vs dataclass mismatch)

```bash
uv run pytest tests/domain/backtest/strategies/test_composite.py::TestCompositeStrategy::test_blocked_signals_recorded -v
```

Expected: FAIL with `'dict' object has no attribute 'original'`

### - [ ] Step 3: Update composite.py to use BlockedSignalTrace

```python
# domain/backtest/strategies/composite.py - update imports
import dataclasses
from domain.backtest.models import Signal, SignalContext, BlockedSignalTrace

# domain/backtest/strategies/composite.py - update _blocked_signals type hint
self._blocked_signals: list[BlockedSignalTrace] = []

# domain/backtest/strategies/composite.py - update generate_signals method
# Replace the dict append with BlockedSignalTrace construction:
self._blocked_signals.append(
    BlockedSignalTrace(
        original=dataclasses.replace(signal),
        modifier=self.modifier.name(),
        reason=self.modifier.explain_block(signal, context)
    )
)

# domain/backtest/strategies/composite.py - update get_blocked_signals return type
def get_blocked_signals(self) -> list[BlockedSignalTrace]:
    return self._blocked_signals.copy()
```

### - [ ] Step 4: Run all composite tests to verify they pass

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

## Task 4: 修改 BacktestEngine 统一读取 blocked_signals

**Files:**
- Modify: `domain/backtest/engine.py`
- Modify: `tests/domain/backtest/test_engine.py`

### - [ ] Step 1: Write tests for engine returning blocked_signals

```python
# tests/domain/backtest/test_engine.py - add new test class

class TestBacktestEngineBlockedSignals:
    """Tests for blocked signals in backtest results."""

    def test_engine_with_composite_strategy_returns_blocked_signals(self):
        """Test that engine returns blocked signals from composite strategy."""
        from domain.backtest.strategies.composite import CompositeStrategy
        from domain.backtest.strategies.dca import DCAStrategy
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        from datetime import date, timedelta

        engine = BacktestEngine(initial_cash=100000)

        # Create downtrend NAV history (BUY signals will be blocked)
        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 - i * 0.01, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        result = engine.run(composite, fund_code="000001", nav_history=nav_history)

        # Should have blocked signals due to downtrend
        assert len(result.blocked_signals) > 0
        assert result.blocked_signals[0].original.action == "BUY"

    def test_engine_with_composite_strategy_no_blocks(self):
        """Test that engine returns empty blocked_signals when none are blocked."""
        from domain.backtest.strategies.composite import CompositeStrategy
        from domain.backtest.strategies.dca import DCAStrategy
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        from datetime import date, timedelta

        engine = BacktestEngine(initial_cash=100000)

        # Create uptrend NAV history (BUY signals will pass)
        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 + i * 0.01, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        result = engine.run(composite, fund_code="000001", nav_history=nav_history)

        # No blocked signals in uptrend
        assert result.blocked_signals == []

    def test_engine_with_normal_strategy_empty_blocked_signals(self):
        """Test that normal strategies return empty blocked_signals."""
        from domain.backtest.strategies.dca import DCAStrategy
        from datetime import date, timedelta

        engine = BacktestEngine(initial_cash=100000)

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 + i * 0.001, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        result = engine.run(dca, fund_code="000001", nav_history=nav_history)

        assert result.blocked_signals == []
```

### - [ ] Step 2: Run tests to verify they fail

```bash
uv run pytest tests/domain/backtest/test_engine.py::TestBacktestEngineBlockedSignals -v
```

Expected: FAIL (blocked_signals field missing or empty)

### - [ ] Step 3: Modify engine to collect blocked_signals

```python
# domain/backtest/engine.py - add import at top
from domain.backtest.models import ExecutedTrade, BacktestResult, BlockedSignalTrace

# domain/backtest/engine.py - in run() method, add after line 22 (after generate_signals):
signals = strategy.generate_signals(nav_history)
blocked_signals = strategy.get_blocked_signals()  # Add this line

# domain/backtest/engine.py - update BacktestResult construction (line 124-138):
# NOTE: Use the existing executed_trades variable maintained by the engine.
# If the engine internally uses a different variable name (e.g., 'trades'),
# ensure it is renamed to executed_trades before this change, or use the correct name here.
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
    blocked_signals=blocked_signals,  # Add this line
)
```

### - [ ] Step 4: Run tests to verify they pass

```bash
uv run pytest tests/domain/backtest/test_engine.py::TestBacktestEngineBlockedSignals -v
```

Expected: PASS

### - [ ] Step 5: Run all backtest tests

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

## Task 5: BacktestService 支持 "DCA + MA Filter" 组合策略

**Files:**
- Modify: `service/backtest_service.py`
- Modify: `tests/service/test_backtest_service.py`

### - [ ] Step 1: Write tests for composite strategy creation and end-to-end

```python
# tests/service/test_backtest_service.py - add to existing test class

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
    from unittest.mock import patch
    from datetime import date, timedelta

    service = BacktestService()

    # Create mock NAV history (downtrend)
    nav_history = []
    for i in range(60):
        d = date(2023, 1, 1) + timedelta(days=i)
        nav_history.append({"date": d, "nav": 1.0 - i * 0.01, "acc_nav": 1.0})

    with patch.object(service.datasource, 'get_fund_nav_history', return_value=nav_history):
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

    # Should have blocked signals due to downtrend
    assert len(result.blocked_signals) > 0
    assert result.blocked_signals[0].original.action == "BUY"
```

### - [ ] Step 2: Run tests to verify they fail

```bash
uv run pytest tests/service/test_backtest_service.py::TestBacktestService::test_service_creates_composite_strategy tests/service/test_backtest_service.py::TestBacktestService::test_run_backtest_returns_blocked_signals_in_result -v
```

Expected: FAIL with `Unknown strategy: DCA + MA Filter`

### - [ ] Step 3: Implement composite strategy creation

```python
# service/backtest_service.py - add imports at top
from domain.backtest.strategies.composite import CompositeStrategy
from domain.backtest.strategies.modifiers.ma_filter import MAFilter

# service/backtest_service.py - add to _create_strategy method
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

### - [ ] Step 4: Run tests to verify they pass

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

## Task 6: UI 增加组合策略选项和解释面板

**Files:**
- Modify: `ui/pages/3_strategy_lab.py`

### - [ ] Step 1: Update strategy selectbox options

```python
# ui/pages/3_strategy_lab.py - update strategy_name selectbox (around line 207)
strategy_name = st.selectbox("策略选择", options=["DCA", "MA Timing", "DCA + MA Filter"], key="bt_strategy")
```

### - [ ] Step 2: Add MA window parameter for composite strategy

```python
# ui/pages/3_strategy_lab.py - update strategy parameters section (after line 230)
# Replace the existing strategy params block with:

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
elif strategy_name == "DCA + MA Filter":
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
        "ma_window": ma_window,
    }
```

### - [ ] Step 3: Add explanation panel after backtest results

```python
# ui/pages/3_strategy_lab.py - add after trade statistics section (after line 327)
# IMPORTANT: Check result.strategy_name instead of dropdown value to avoid UI state issues
# when user changes dropdown after running backtest
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

### - [ ] Step 4: Commit

```bash
git add ui/pages/3_strategy_lab.py
git commit -m "feat(ui): add DCA + MA Filter option and explanation panel"
```

---

## Task 7: 运行全量测试

### - [ ] Step 1: Run all tests

```bash
uv run pytest -v
```

Expected: All tests pass

### - [ ] Step 2: Fix any failures if needed

If tests fail, fix them and commit.

### - [ ] Step 3: Final commit and push

```bash
git push
```

---

## Summary

| Task | Files Modified | Tests Added |
|------|----------------|-------------|
| 1. BlockedSignalTrace | models.py, test_models.py | 2 |
| 2. Strategy base method | base.py, test_base.py | 1 |
| 3. CompositeStrategy refactor | composite.py, test_composite.py | 0 (updated) |
| 4. Engine blocked_signals | engine.py, test_engine.py | 3 |
| 5. Service composite strategy | backtest_service.py, test_backtest_service.py | 2 |
| 6. UI explanation panel | 3_strategy_lab.py | 0 |
| 7. Full test suite | - | - |

**Total new tests:** 8
**Phase 3B deliverable:**
- `BlockedSignalTrace` dataclass
- Strategy 基类 `get_blocked_signals()` 方法
- Engine 统一收集 blocked_signals
- "DCA + MA Filter" 组合策略入口
- UI 解释面板
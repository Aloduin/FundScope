# Phase 3A: CompositeStrategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement filter-type composite strategy framework supporting `DCA + MAFilter` combination.

**Architecture:** `CompositeStrategy` wraps a primary `Strategy` and applies a `SignalModifier` to filter/transform signals. `MAFilter` implements `trend_confirm` mode:

* allow `BUY` in uptrend
* allow `SELL` in downtrend

Blocked signals are traced for the future explanation panel.

**Tech Stack:** Python 3.13, dataclasses, abc, pytest

---

## 一、实施前修正说明

本修正版相对上一版，做了以下关键修正：

1. **测试拆分**

   * 原方案把 `SignalModifier`、`MAFilter`、`CompositeStrategy` 都放在同一个 `test_composite.py` 中，容易因为后续 top-level import 导致前序任务提前失败。
   * 修正为拆分：

     * `test_modifiers.py`
     * `test_composite.py`

2. **避免非法日期**

   * 原方案有使用 `date(2023, 6, i)` 且 `i > 30` 的风险。
   * 全部改为 `start_date + timedelta(days=i)` 生成日期。

3. **MAFilter 放行理由与设计文档保持一致**

   * 放行时补充 allow reason，而不是直接返回原 signal。

4. **CompositeStrategy 明确禁止 RebalancePolicy 接入主流程**

   * Phase 3A 只支持 `SignalModifier`
   * `RebalancePolicy` 只保留接口和 stub

---

## 二、File Structure

```text
domain/backtest/
├── models.py                    # ADD: SignalContext dataclass
└── strategies/
    ├── composite.py             # NEW: CompositeStrategy class
    ├── modifiers/
    │   ├── __init__.py          # NEW
    │   ├── base.py              # NEW: SignalModifier ABC
    │   └── ma_filter.py         # NEW: MAFilter
    └── rebalance/
        ├── __init__.py          # NEW
        ├── policy.py            # NEW: RebalancePolicy ABC (stub only)
        └── threshold.py         # NEW: ThresholdRebalancePolicy (stub only)

tests/domain/backtest/
├── test_models.py               # MODIFY: add SignalContext tests
└── strategies/
    ├── test_modifiers.py        # NEW
    └── test_composite.py        # NEW
```

---

## Task 1: Add `SignalContext` to `models.py`

### Files

* Modify: `domain/backtest/models.py`
* Modify: `tests/domain/backtest/test_models.py`

### - [ ] Step 1: Write failing tests for `SignalContext`

```python
# tests/domain/backtest/test_models.py - add to existing file

class TestSignalContext:
    """Tests for SignalContext dataclass."""

    def test_signal_context_creation(self):
        from datetime import date
        from domain.backtest.models import SignalContext

        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.05,
            indicators={
                "ma_window": 20,
                "ma_value": 1.03,
                "trend_relation": "above",
                "ma_available": True,
            }
        )

        assert context.date == date(2023, 6, 15)
        assert context.current_nav == 1.05
        assert context.indicators["ma_window"] == 20
        assert context.indicators["trend_relation"] == "above"

    def test_signal_context_allows_none_in_indicators(self):
        from datetime import date
        from domain.backtest.models import SignalContext

        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.05,
            indicators={
                "ma_value": None,
                "ma_available": False,
            }
        )

        assert context.indicators["ma_value"] is None
        assert context.indicators["ma_available"] is False
```

### - [ ] Step 2: Run test to verify it fails

```bash
uv run pytest tests/domain/backtest/test_models.py::TestSignalContext -v
```

Expected: FAIL with `cannot import name 'SignalContext'`

### - [ ] Step 3: Implement `SignalContext`

```python
# domain/backtest/models.py - add after Signal class

@dataclass
class SignalContext:
    """Context information for signal modification."""
    date: date
    current_nav: float
    indicators: dict[str, float | str | bool | None]
```

### - [ ] Step 4: Run test to verify it passes

```bash
uv run pytest tests/domain/backtest/test_models.py::TestSignalContext -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/models.py tests/domain/backtest/test_models.py
git commit -m "feat(backtest): add SignalContext dataclass"
```

---

## Task 2: Create `SignalModifier` Abstract Base Class

### Files

* Create: `domain/backtest/strategies/modifiers/__init__.py`
* Create: `domain/backtest/strategies/modifiers/base.py`
* Create: `tests/domain/backtest/strategies/test_modifiers.py`

### - [ ] Step 1: Write failing tests for `SignalModifier`

```python
# tests/domain/backtest/strategies/test_modifiers.py
import pytest


class TestSignalModifierABC:
    """Tests for SignalModifier abstract base class."""

    def test_signal_modifier_is_abstract(self):
        from domain.backtest.strategies.modifiers.base import SignalModifier

        with pytest.raises(TypeError):
            SignalModifier()

    def test_signal_modifier_has_required_methods(self):
        from domain.backtest.strategies.modifiers.base import SignalModifier

        class ConcreteModifier(SignalModifier):
            def name(self) -> str:
                return "TestModifier"

            def modify(self, signal, context):
                return signal

            def explain_block(self, signal, context):
                return "test reason"

        modifier = ConcreteModifier()
        assert modifier.name() == "TestModifier"
```

### - [ ] Step 2: Run test to verify it fails

```bash
uv run pytest tests/domain/backtest/strategies/test_modifiers.py::TestSignalModifierABC -v
```

Expected: FAIL with `cannot import name 'SignalModifier'`

### - [ ] Step 3: Implement `SignalModifier`

```python
# domain/backtest/strategies/modifiers/__init__.py
"""Signal modifiers for composite strategies."""
from domain.backtest.strategies.modifiers.base import SignalModifier

__all__ = ["SignalModifier"]
```

```python
# domain/backtest/strategies/modifiers/base.py
"""Abstract base class for signal modifiers."""
from abc import ABC, abstractmethod
from domain.backtest.models import Signal, SignalContext


class SignalModifier(ABC):
    """Abstract base class for signal modifiers that filter or transform signals."""

    @abstractmethod
    def name(self) -> str:
        """Get modifier name for display."""
        raise NotImplementedError

    @abstractmethod
    def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
        """Return modified signal, or None to block."""
        raise NotImplementedError

    @abstractmethod
    def explain_block(self, signal: Signal, context: SignalContext) -> str:
        """Explain why signal was blocked."""
        raise NotImplementedError
```

### - [ ] Step 4: Run test to verify it passes

```bash
uv run pytest tests/domain/backtest/strategies/test_modifiers.py::TestSignalModifierABC -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/strategies/modifiers/ tests/domain/backtest/strategies/test_modifiers.py
git commit -m "feat(backtest): add SignalModifier abstract base class"
```

---

## Task 3: Implement `MAFilter`

### Files

* Create: `domain/backtest/strategies/modifiers/ma_filter.py`
* Modify: `tests/domain/backtest/strategies/test_modifiers.py`

### - [ ] Step 1: Add failing tests for `MAFilter`

```python
# tests/domain/backtest/strategies/test_modifiers.py - append to file
from datetime import date
from domain.backtest.models import Signal, SignalContext


class TestMAFilter:
    """Tests for MAFilter signal modifier."""

    def test_mafilter_name_format(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20, filter_mode="trend_confirm")
        assert ma_filter.name() == "MAFilter(20, trend_confirm)"

    def test_mafilter_default_params(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter()
        assert ma_filter.window == 20
        assert ma_filter.filter_mode == "trend_confirm"

    def test_mafilter_invalid_filter_mode_raises(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        with pytest.raises(NotImplementedError):
            MAFilter(window=20, filter_mode="unsupported_mode")

    def test_mafilter_buy_above_ma_passes(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.05,
            indicators={"trend_relation": "above", "ma_available": True, "ma_value": 1.03, "ma_window": 20}
        )
        result = ma_filter.modify(signal, context)
        assert result is not None
        assert result.action == "BUY"
        assert "上涨趋势确认" in result.reason

    def test_mafilter_buy_below_ma_blocked(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=0.95,
            indicators={"trend_relation": "below", "ma_available": True, "ma_window": 20}
        )
        assert ma_filter.modify(signal, context) is None

    def test_mafilter_sell_below_ma_passes(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="SELL",
            confidence=0.7,
            reason="test sell"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=0.95,
            indicators={"trend_relation": "below", "ma_available": True, "ma_value": 1.03, "ma_window": 20}
        )
        result = ma_filter.modify(signal, context)
        assert result is not None
        assert result.action == "SELL"
        assert "下跌趋势确认" in result.reason

    def test_mafilter_sell_above_ma_blocked(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="SELL",
            confidence=0.7,
            reason="test sell"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.05,
            indicators={"trend_relation": "above", "ma_available": True, "ma_window": 20}
        )
        assert ma_filter.modify(signal, context) is None

    def test_mafilter_equal_blocked(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.00,
            indicators={"trend_relation": "equal", "ma_available": True}
        )
        assert ma_filter.modify(signal, context) is None
        assert "趋势不明确" in ma_filter.explain_block(signal, context)

    def test_mafilter_hold_and_rebalance_always_pass(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)

        for action in ("HOLD", "REBALANCE"):
            signal = Signal(
                date=date(2023, 6, 15),
                fund_code="000001",
                action=action,
                confidence=0.7,
                reason="test"
            )
            context = SignalContext(
                date=date(2023, 6, 15),
                current_nav=0.95,
                indicators={"trend_relation": "below", "ma_available": True}
            )
            assert ma_filter.modify(signal, context) is not None

    def test_mafilter_unknown_trend_passes(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.00,
            indicators={"trend_relation": "unknown", "ma_available": False}
        )
        assert ma_filter.modify(signal, context) is not None

    def test_mafilter_explain_block_messages(self):
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter

        ma_filter = MAFilter(window=20)

        buy_signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test"
        )
        buy_context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=0.95,
            indicators={"trend_relation": "below", "ma_available": True, "ma_window": 20}
        )
        assert "买入信号被拦截" in ma_filter.explain_block(buy_signal, buy_context)

        sell_signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="SELL",
            confidence=0.7,
            reason="test"
        )
        sell_context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.05,
            indicators={"trend_relation": "above", "ma_available": True, "ma_window": 20}
        )
        assert "卖出信号被拦截" in ma_filter.explain_block(sell_signal, sell_context)
```

### - [ ] Step 2: Run test to verify it fails

```bash
uv run pytest tests/domain/backtest/strategies/test_modifiers.py::TestMAFilter -v
```

Expected: FAIL with `cannot import name 'MAFilter'`

### - [ ] Step 3: Implement `MAFilter`

```python
# domain/backtest/strategies/modifiers/ma_filter.py
"""Moving Average filter for signal modification."""
import dataclasses
from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.modifiers.base import SignalModifier


class MAFilter(SignalModifier):
    """Moving Average filter that blocks signals against the trend."""

    def __init__(self, window: int = 20, filter_mode: str = "trend_confirm"):
        self.window = window
        self.filter_mode = filter_mode
        if filter_mode != "trend_confirm":
            raise NotImplementedError(f"filter_mode={filter_mode} not supported in Phase 3A")

    def name(self) -> str:
        return f"MAFilter({self.window}, {self.filter_mode})"

    def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
        trend = context.indicators.get("trend_relation", "unknown")
        ma_value = context.indicators.get("ma_value")
        window = context.indicators.get("ma_window", self.window)

        if signal.action in ("HOLD", "REBALANCE"):
            return signal

        if trend == "unknown":
            return signal

        if signal.action == "BUY":
            if trend == "above":
                return dataclasses.replace(
                    signal,
                    reason=f"{signal.reason}（上涨趋势确认，MA{window}={ma_value:.4f}）"
                )
            return None

        if signal.action == "SELL":
            if trend == "below":
                return dataclasses.replace(
                    signal,
                    reason=f"{signal.reason}（下跌趋势确认，MA{window}={ma_value:.4f}）"
                )
            return None

        return signal

    def explain_block(self, signal: Signal, context: SignalContext) -> str:
        trend = context.indicators.get("trend_relation", "unknown")
        window = context.indicators.get("ma_window", self.window)

        if signal.action == "BUY":
            if trend == "below":
                return f"买入信号被拦截：当前净值低于{window}日均线"
            if trend == "equal":
                return "信号被拦截：当前净值等于均线，趋势不明确"

        if signal.action == "SELL":
            if trend == "above":
                return f"卖出信号被拦截：当前净值高于{window}日均线"
            if trend == "equal":
                return "信号被拦截：当前净值等于均线，趋势不明确"

        return "信号被拦截：未知原因"
```

### - [ ] Step 4: Run test to verify it passes

```bash
uv run pytest tests/domain/backtest/strategies/test_modifiers.py::TestMAFilter -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/strategies/modifiers/ma_filter.py tests/domain/backtest/strategies/test_modifiers.py
git commit -m "feat(backtest): implement MAFilter with trend_confirm mode"
```

---

## Task 4: Create `RebalancePolicy` Stub (Not for Main Flow)

### Files

* Create: `domain/backtest/strategies/rebalance/__init__.py`
* Create: `domain/backtest/strategies/rebalance/policy.py`
* Create: `domain/backtest/strategies/rebalance/threshold.py`

### - [ ] Step 1: Create stub classes

```python
# domain/backtest/strategies/rebalance/__init__.py
"""Rebalance policies for composite strategies."""
from domain.backtest.strategies.rebalance.policy import RebalancePolicy
from domain.backtest.strategies.rebalance.threshold import ThresholdRebalancePolicy

__all__ = ["RebalancePolicy", "ThresholdRebalancePolicy"]
```

```python
# domain/backtest/strategies/rebalance/policy.py
"""Abstract base class for rebalance policies."""
from abc import ABC, abstractmethod
from domain.backtest.models import Signal, SignalContext


class RebalancePolicy(ABC):
    """Phase 3A: interface only, not integrated into main backtest flow."""

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def rebalance(
        self,
        current_positions: list[dict],
        target_weights: dict[str, float],
        context: SignalContext
    ) -> list[Signal]:
        raise NotImplementedError
```

```python
# domain/backtest/strategies/rebalance/threshold.py
"""Threshold-based rebalance policy."""
from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.rebalance.policy import RebalancePolicy


class ThresholdRebalancePolicy(RebalancePolicy):
    """Stub only for Phase 3A."""

    def __init__(self, threshold: float = 0.05, mode: str = "threshold"):
        self.threshold = threshold
        self.mode = mode
        if mode != "threshold":
            raise NotImplementedError(f"mode={mode} not supported in Phase 3A")

    def name(self) -> str:
        return f"ThresholdRebalance({self.threshold:.0%})"

    def rebalance(
        self,
        current_positions: list[dict],
        target_weights: dict[str, float],
        context: SignalContext
    ) -> list[Signal]:
        return []
```

### - [ ] Step 2: Commit

```bash
git add domain/backtest/strategies/rebalance/
git commit -m "feat(backtest): add RebalancePolicy stub (not integrated)"
```

---

## Task 5: Implement `CompositeStrategy`

### Files

* Create: `domain/backtest/strategies/composite.py`
* Create: `tests/domain/backtest/strategies/test_composite.py`

### - [ ] Step 1: Write failing tests for `CompositeStrategy`

```python
# tests/domain/backtest/strategies/test_composite.py
from datetime import date, timedelta
import pytest

from domain.backtest.models import Signal
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.strategies.modifiers.ma_filter import MAFilter


def generate_mock_nav_history(start_date: date, periods: int = 60) -> list[dict]:
    nav_history = []
    nav = 1.0
    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        nav = nav * 1.001
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })
    return nav_history


class MockStrategy(Strategy):
    def __init__(self, signals: list[Signal]):
        self._signals = signals

    def name(self) -> str:
        return "MockStrategy"

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        return self._signals


class TestCompositeStrategy:
    def test_name_without_modifier(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=None)
        assert composite.name() == "DCA"

    def test_name_with_modifier(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter(window=20))
        assert composite.name() == "DCA+MAFilter(20, trend_confirm)"

    def test_empty_nav_history_returns_empty(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter())
        assert composite.generate_signals([]) == []

    def test_without_modifier_passthrough(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        nav_history = generate_mock_nav_history(date(2023, 1, 1), periods=60)
        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)

        composite = CompositeStrategy(primary_strategy=dca, modifier=None)
        assert composite.generate_signals(nav_history) == dca.generate_signals(nav_history)

    def test_blocked_signals_initially_empty(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter())
        assert composite.get_blocked_signals() == []

    def test_blocked_signals_recorded(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        signal = Signal(
            date=date(2023, 2, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        mock = MockStrategy([signal])

        nav_history = []
        for i in range(40):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 - i * 0.005, "acc_nav": 1.0})

        composite = CompositeStrategy(primary_strategy=mock, modifier=MAFilter(window=20))
        signals = composite.generate_signals(nav_history)

        assert signals == []
        blocked = composite.get_blocked_signals()
        assert len(blocked) == 1
        assert blocked[0]["original"].action == "BUY"
        assert "买入信号被拦截" in blocked[0]["reason"]

    def test_blocked_signals_cleared_each_run(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        signal = Signal(
            date=date(2023, 2, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        mock = MockStrategy([signal])

        nav_history = []
        for i in range(40):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 - i * 0.005, "acc_nav": 1.0})

        composite = CompositeStrategy(primary_strategy=mock, modifier=MAFilter(window=20))
        composite.generate_signals(nav_history)
        assert len(composite.get_blocked_signals()) == 1

        composite.generate_signals(nav_history)
        assert len(composite.get_blocked_signals()) == 1

    def test_dca_uptrend_buy_passes(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 + i * 0.01, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter(window=20))
        signals = composite.generate_signals(nav_history)

        assert len(signals) >= 2
        assert all(s.action == "BUY" for s in signals)

    def test_dca_downtrend_buy_blocked(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 - i * 0.01, "acc_nav": 1.0})

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter(window=20))
        signals = composite.generate_signals(nav_history)

        assert len(signals) == 0
        assert len(composite.get_blocked_signals()) >= 2

    def test_insufficient_data_allows_signal(self):
        from domain.backtest.strategies.composite import CompositeStrategy

        nav_history = generate_mock_nav_history(date(2023, 1, 1), periods=15)
        dca = DCAStrategy(invest_amount=1000, invest_interval_days=10)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter(window=20))

        signals = composite.generate_signals(nav_history)
        assert len(signals) >= 1

    def test_rebalance_policy_rejected(self):
        from domain.backtest.strategies.composite import CompositeStrategy
        from domain.backtest.strategies.rebalance.threshold import ThresholdRebalancePolicy

        dca = DCAStrategy(invest_amount=1000)
        with pytest.raises(NotImplementedError):
            CompositeStrategy(
                primary_strategy=dca,
                modifier=ThresholdRebalancePolicy()  # type: ignore[arg-type]
            )
```

### - [ ] Step 2: Run test to verify it fails

```bash
uv run pytest tests/domain/backtest/strategies/test_composite.py -v
```

Expected: FAIL with `cannot import name 'CompositeStrategy'`

### - [ ] Step 3: Implement `CompositeStrategy`

```python
# domain/backtest/strategies/composite.py
"""Composite strategy that combines a primary strategy with a signal modifier."""
import dataclasses

from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.modifiers.base import SignalModifier
from domain.backtest.strategies.modifiers.ma_filter import MAFilter
from domain.backtest.strategies.rebalance.policy import RebalancePolicy


class CompositeStrategy(Strategy):
    """Phase 3A: only supports primary strategy + SignalModifier."""

    def __init__(
        self,
        primary_strategy: Strategy,
        modifier: SignalModifier | None = None
    ):
        self.primary_strategy = primary_strategy
        self.modifier = modifier
        self._blocked_signals: list[dict] = []

        if isinstance(modifier, RebalancePolicy):
            raise NotImplementedError(
                "RebalancePolicy is not supported in Phase 3A. "
                "Use SignalModifier (e.g., MAFilter) instead."
            )

    def name(self) -> str:
        if self.modifier is None:
            return self.primary_strategy.name()
        return f"{self.primary_strategy.name()}+{self.modifier.name()}"

    def get_blocked_signals(self) -> list[dict]:
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
            context = self._build_context(signal.date, nav_history)
            result = self.modifier.modify(signal, context)
            if result is None:
                self._blocked_signals.append({
                    "original": dataclasses.replace(signal),
                    "modifier": self.modifier.name(),
                    "reason": self.modifier.explain_block(signal, context)
                })
            else:
                final_signals.append(result)

        return final_signals

    def _build_context(self, as_of_date, nav_history: list[dict]) -> SignalContext:
        records_before = [r for r in nav_history if r["date"] <= as_of_date]
        if not records_before:
            raise ValueError(f"No NAV data found on or before signal date {as_of_date}")

        record = records_before[-1]
        indicators: dict[str, float | str | bool | None] = {}

        if isinstance(self.modifier, MAFilter):
            window = self.modifier.window

            if len(records_before) < window:
                indicators = {
                    "ma_window": window,
                    "ma_value": None,
                    "trend_relation": "unknown",
                    "ma_available": False,
                }
            else:
                window_records = records_before[-window:]
                ma_value = sum(r["nav"] for r in window_records) / window
                current_nav = record["nav"]

                if abs(current_nav - ma_value) < 1e-9:
                    trend_relation = "equal"
                elif current_nav > ma_value:
                    trend_relation = "above"
                else:
                    trend_relation = "below"

                indicators = {
                    "ma_window": window,
                    "ma_value": ma_value,
                    "trend_relation": trend_relation,
                    "ma_available": True,
                }

        return SignalContext(
            date=as_of_date,
            current_nav=record["nav"],
            indicators=indicators
        )
```

### - [ ] Step 4: Run test to verify it passes

```bash
uv run pytest tests/domain/backtest/strategies/test_composite.py -v
```

Expected: PASS

### - [ ] Step 5: Commit

```bash
git add domain/backtest/strategies/composite.py tests/domain/backtest/strategies/test_composite.py
git commit -m "feat(backtest): implement CompositeStrategy with MAFilter support"
```

---

## Task 6: Run Full Test Suite

### - [ ] Step 1: Run all backtest tests

```bash
uv run pytest tests/domain/backtest/ -v
```

Expected: All tests pass

### - [ ] Step 2: Run full test suite

```bash
uv run pytest
```

Expected: All tests pass

### - [ ] Step 3: Commit if fixes were needed

```bash
git add -A
git commit -m "fix: address composite strategy test failures"
```

---

## 三、Summary

| Task                    | Files Created | Files Modified | Tests Added |
| ----------------------- | ------------: | -------------: | ----------: |
| 1. SignalContext        |             0 |              2 |           2 |
| 2. SignalModifier ABC   |             2 |              0 |           2 |
| 3. MAFilter             |             1 |              1 |         10+ |
| 4. RebalancePolicy stub |             3 |              0 |           0 |
| 5. CompositeStrategy    |             1 |              1 |         10+ |
| 6. Test suite           |             0 |              0 |           0 |

**Total new files:** 7
**Total modified files:** 4
**Phase 3A deliverable:**

* `SignalContext`
* `SignalModifier`
* `MAFilter`
* `CompositeStrategy`
* `RebalancePolicy` stub only


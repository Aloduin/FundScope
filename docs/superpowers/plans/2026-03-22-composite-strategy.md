# Phase 3A: CompositeStrategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement filter-type composite strategy framework supporting DCA + MA Filter combination.

**Architecture:** CompositeStrategy wraps a primary Strategy and applies a SignalModifier to filter/transform signals. MAFilter implements trend_confirm mode (allow BUY in uptrend, allow SELL in downtrend). Blocked signals are traced for Phase 3B explanation panel.

**Tech Stack:** Python 3.13, dataclasses, abc, pytest

---

## File Structure

```
domain/backtest/
├── models.py                    # ADD: SignalContext dataclass
└── strategies/
    ├── composite.py             # NEW: CompositeStrategy class
    ├── modifiers/
    │   ├── __init__.py          # NEW: module init
    │   ├── base.py              # NEW: SignalModifier ABC
    │   └── ma_filter.py         # NEW: MAFilter implementation
    └── rebalance/
        ├── __init__.py          # NEW: module init
        ├── policy.py            # NEW: RebalancePolicy ABC (stub)
        └── threshold.py         # NEW: ThresholdRebalancePolicy (stub)

tests/domain/backtest/strategies/
└── test_composite.py            # NEW: comprehensive tests
```

---

## Task 1: Add SignalContext to models.py

**Files:**
- Modify: `domain/backtest/models.py`
- Test: `tests/domain/backtest/test_models.py`

- [ ] **Step 1: Write the failing test for SignalContext**

```python
# tests/domain/backtest/test_models.py - add to existing file

class TestSignalContext:
    """Tests for SignalContext dataclass."""

    def test_signal_context_creation(self):
        from domain.backtest.models import SignalContext
        from datetime import date

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
        from domain.backtest.models import SignalContext
        from datetime import date

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

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/backtest/test_models.py::TestSignalContext -v`
Expected: FAIL with "cannot import name 'SignalContext'"

- [ ] **Step 3: Add SignalContext dataclass to models.py**

```python
# domain/backtest/models.py - add after Signal class

@dataclass
class SignalContext:
    """Context information for signal modification."""
    date: date
    current_nav: float
    indicators: dict[str, float | str | bool | None]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/backtest/test_models.py::TestSignalContext -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/backtest/models.py tests/domain/backtest/test_models.py
git commit -m "feat(backtest): add SignalContext dataclass"
```

---

## Task 2: Create SignalModifier Abstract Base Class

**Files:**
- Create: `domain/backtest/strategies/modifiers/__init__.py`
- Create: `domain/backtest/strategies/modifiers/base.py`
- Test: `tests/domain/backtest/strategies/test_composite.py`

- [ ] **Step 1: Write the failing test for SignalModifier ABC**

```python
# tests/domain/backtest/strategies/test_composite.py - new file

"""Tests for composite strategy and modifiers."""
import pytest
from abc import ABC
from datetime import date, timedelta
from domain.backtest.strategies.modifiers.base import SignalModifier


def generate_mock_nav_history(start_date: date, periods: int = 252) -> list[dict]:
    """Generate mock NAV history for testing."""
    nav_history = []
    nav = 1.0
    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        nav = nav * (1 + 0.0005 + (hash(str(i)) % 100 - 50) / 10000)
        nav_history.append({"date": current_date, "nav": nav, "acc_nav": nav})
    return nav_history


class TestSignalModifierABC:
    """Tests for SignalModifier abstract base class."""

    def test_signal_modifier_is_abstract(self):
        """SignalModifier should be abstract and not instantiable directly."""
        with pytest.raises(TypeError):
            SignalModifier()

    def test_signal_modifier_has_required_methods(self):
        """SignalModifier should define name, modify, explain_block methods."""
        from domain.backtest.models import SignalContext
        from datetime import date

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

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/backtest/strategies/test_composite.py::TestSignalModifierABC -v`
Expected: FAIL with "cannot import name 'SignalModifier'"

- [ ] **Step 3: Create modifiers directory and base.py**

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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/backtest/strategies/test_composite.py::TestSignalModifierABC -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/backtest/strategies/modifiers/ tests/domain/backtest/strategies/test_composite.py
git commit -m "feat(backtest): add SignalModifier abstract base class"
```

---

## Task 3: Implement MAFilter

**Files:**
- Create: `domain/backtest/strategies/modifiers/ma_filter.py`
- Modify: `tests/domain/backtest/strategies/test_composite.py`

- [ ] **Step 1: Write the failing tests for MAFilter**

```python
# tests/domain/backtest/strategies/test_composite.py
# 在 TestSignalModifierABC 类后面添加以下代码
# 注意：导入放在类方法内部，避免前序任务提前失败

class TestMAFilter:
    """Tests for MAFilter signal modifier."""

    def test_mafilter_name_format(self):
        """MAFilter name should include window and mode."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter(window=20, filter_mode="trend_confirm")
        assert ma_filter.name() == "MAFilter(20, trend_confirm)"

    def test_mafilter_default_params(self):
        """MAFilter should have default window=20 and filter_mode='trend_confirm'."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter()
        assert ma_filter.window == 20
        assert ma_filter.filter_mode == "trend_confirm"

    def test_mafilter_invalid_filter_mode_raises(self):
        """MAFilter should raise NotImplementedError for unsupported filter_mode."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        with pytest.raises(NotImplementedError):
            MAFilter(window=20, filter_mode="unsupported_mode")

    def test_mafilter_buy_above_ma_passes(self):
        """BUY signal above MA should pass with updated reason."""
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
        assert "上涨趋势" in result.reason  # 放行时应补充 allow reason

    def test_mafilter_buy_below_ma_blocked(self):
        """BUY signal below MA should be blocked."""
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
            indicators={"trend_relation": "below", "ma_available": True}
        )
        result = ma_filter.modify(signal, context)
        assert result is None

    def test_mafilter_sell_below_ma_passes(self):
        """SELL signal below MA should pass with updated reason."""
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
        assert "下跌趋势" in result.reason  # 放行时应补充 allow reason

    def test_mafilter_sell_above_ma_blocked(self):
        """SELL signal above MA should be blocked."""
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
            indicators={"trend_relation": "above", "ma_available": True}
        )
        result = ma_filter.modify(signal, context)
        assert result is None

    def test_mafilter_buy_equal_ma_blocked(self):
        """BUY signal equal to MA should be blocked."""
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
        result = ma_filter.modify(signal, context)
        assert result is None

    def test_mafilter_sell_equal_ma_blocked(self):
        """SELL signal equal to MA should be blocked."""
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
            current_nav=1.00,
            indicators={"trend_relation": "equal", "ma_available": True}
        )
        result = ma_filter.modify(signal, context)
        assert result is None

    def test_mafilter_hold_always_passes(self):
        """HOLD signal should always pass regardless of trend."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="HOLD",
            confidence=0.7,
            reason="test hold"
        )
        # Test with below trend
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=0.95,
            indicators={"trend_relation": "below", "ma_available": True}
        )
        result = ma_filter.modify(signal, context)
        assert result is not None

    def test_mafilter_rebalance_always_passes(self):
        """REBALANCE signal should always pass regardless of trend."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="REBALANCE",
            confidence=0.7,
            reason="test rebalance"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=0.95,
            indicators={"trend_relation": "below", "ma_available": True}
        )
        result = ma_filter.modify(signal, context)
        assert result is not None

    def test_mafilter_unknown_trend_passes(self):
        """Signal with unknown trend (insufficient data) should pass."""
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
        result = ma_filter.modify(signal, context)
        assert result is not None

    def test_mafilter_explain_block_buy_below(self):
        """explain_block should return Chinese message for BUY below MA."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=0.95,
            indicators={"trend_relation": "below", "ma_available": True, "ma_window": 20}
        )
        explanation = ma_filter.explain_block(signal, context)
        assert "买入信号被拦截" in explanation
        assert "20日均线" in explanation

    def test_mafilter_explain_block_sell_above(self):
        """explain_block should return Chinese message for SELL above MA."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="SELL",
            confidence=0.7,
            reason="test"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.05,
            indicators={"trend_relation": "above", "ma_available": True, "ma_window": 20}
        )
        explanation = ma_filter.explain_block(signal, context)
        assert "卖出信号被拦截" in explanation
        assert "20日均线" in explanation

    def test_mafilter_explain_block_equal(self):
        """explain_block should return message for equal to MA."""
        from domain.backtest.strategies.modifiers.ma_filter import MAFilter
        ma_filter = MAFilter(window=20)
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test"
        )
        context = SignalContext(
            date=date(2023, 6, 15),
            current_nav=1.00,
            indicators={"trend_relation": "equal", "ma_available": True}
        )
        explanation = ma_filter.explain_block(signal, context)
        assert "趋势不明确" in explanation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/backtest/strategies/test_composite.py::TestMAFilter -v`
Expected: FAIL with "cannot import name 'MAFilter'"

- [ ] **Step 3: Implement MAFilter**

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
        """Return modifier name in format 'MAFilter(window, mode)'."""
        return f"MAFilter({self.window}, {self.filter_mode})"

    def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
        """Return modified signal with allow reason, or None to block."""
        trend = context.indicators.get("trend_relation", "unknown")
        ma_value = context.indicators.get("ma_value")
        window = context.indicators.get("ma_window", self.window)

        # HOLD and REBALANCE always pass (no reason modification needed)
        if signal.action in ("HOLD", "REBALANCE"):
            return signal

        # Unknown trend (insufficient data) - allow by default
        if trend == "unknown":
            return signal

        # BUY: allow only in uptrend (above MA)
        if signal.action == "BUY":
            if trend == "above":
                # 补充 allow reason
                return dataclasses.replace(
                    signal,
                    reason=f"{signal.reason}（上涨趋势确认，MA{window}={ma_value:.4f}）"
                )
            return None  # Block BUY in downtrend or equal

        # SELL: allow only in downtrend (below MA)
        if signal.action == "SELL":
            if trend == "below":
                # 补充 allow reason
                return dataclasses.replace(
                    signal,
                    reason=f"{signal.reason}（下跌趋势确认，MA{window}={ma_value:.4f}）"
                )
            return None  # Block SELL in uptrend or equal

        # Unknown action - allow by default
        return signal

    def explain_block(self, signal: Signal, context: SignalContext) -> str:
        """Explain why signal was blocked."""
        trend = context.indicators.get("trend_relation", "unknown")
        window = context.indicators.get("ma_window", self.window)

        if signal.action == "BUY":
            if trend == "below":
                return f"买入信号被拦截：当前净值低于{window}日均线"
            elif trend == "equal":
                return "信号被拦截：当前净值等于均线，趋势不明确"

        if signal.action == "SELL":
            if trend == "above":
                return f"卖出信号被拦截：当前净值高于{window}日均线"
            elif trend == "equal":
                return "信号被拦截：当前净值等于均线，趋势不明确"

        return f"信号被拦截：未知原因"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/backtest/strategies/test_composite.py::TestMAFilter -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add domain/backtest/strategies/modifiers/ma_filter.py tests/domain/backtest/strategies/test_composite.py
git commit -m "feat(backtest): implement MAFilter with trend_confirm mode"
```

---

## Task 4: Create RebalancePolicy Stub (Not for Main Flow)

**Files:**
- Create: `domain/backtest/strategies/rebalance/__init__.py`
- Create: `domain/backtest/strategies/rebalance/policy.py`
- Create: `domain/backtest/strategies/rebalance/threshold.py`

- [ ] **Step 1: Create RebalancePolicy ABC and ThresholdRebalancePolicy stub**

```python
# domain/backtest/strategies/rebalance/__init__.py
"""Rebalance policies for composite strategies."""
from domain.backtest.strategies.rebalance.policy import RebalancePolicy

__all__ = ["RebalancePolicy"]
```

```python
# domain/backtest/strategies/rebalance/policy.py
"""Abstract base class for rebalance policies."""
from abc import ABC, abstractmethod
from domain.backtest.models import Signal, SignalContext


class RebalancePolicy(ABC):
    """Abstract base class for rebalance policies.

    Phase 3A: Interface only, not integrated into main backtest flow.
    """

    @abstractmethod
    def name(self) -> str:
        """Get policy name for display."""
        raise NotImplementedError

    @abstractmethod
    def rebalance(
        self,
        current_positions: list[dict],  # [{fund_code, weight}, ...]
        target_weights: dict[str, float],  # {fund_code: target_weight}
        context: SignalContext
    ) -> list[Signal]:
        """Generate rebalance signals based on position drift."""
        raise NotImplementedError
```

```python
# domain/backtest/strategies/rebalance/threshold.py
"""Threshold-based rebalance policy."""
from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.rebalance.policy import RebalancePolicy


class ThresholdRebalancePolicy(RebalancePolicy):
    """Rebalance policy that triggers when position drift exceeds threshold.

    Phase 3A: Stub implementation only, not integrated into main backtest flow.
    """

    def __init__(self, threshold: float = 0.05, mode: str = "threshold"):
        self.threshold = threshold
        self.mode = mode
        if mode != "threshold":
            raise NotImplementedError(f"mode={mode} not supported in Phase 3A")

    def name(self) -> str:
        """Return policy name."""
        return f"ThresholdRebalance({self.threshold:.0%})"

    def rebalance(
        self,
        current_positions: list[dict],
        target_weights: dict[str, float],
        context: SignalContext
    ) -> list[Signal]:
        """Generate rebalance signals when drift exceeds threshold.

        Phase 3A: Placeholder implementation.
        Full implementation requires engine-level portfolio state support.
        """
        # Stub: return empty list
        # Real implementation would compare current vs target weights
        # and generate BUY/SELL signals for positions exceeding threshold
        return []
```

- [ ] **Step 2: Commit**

```bash
git add domain/backtest/strategies/rebalance/
git commit -m "feat(backtest): add RebalancePolicy stub (not integrated)"
```

---

## Task 5: Implement CompositeStrategy

**Files:**
- Create: `domain/backtest/strategies/composite.py`
- Modify: `tests/domain/backtest/strategies/test_composite.py`

- [ ] **Step 1: Write the failing tests for CompositeStrategy**

```python
# tests/domain/backtest/strategies/test_composite.py - add after TestMAFilter

from domain.backtest.strategies.composite import CompositeStrategy
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.strategies.base import Strategy


class MockStrategy(Strategy):
    """Mock strategy for testing that returns predefined signals."""

    def __init__(self, signals: list[Signal]):
        self._signals = signals

    def name(self) -> str:
        return "MockStrategy"

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        return self._signals


class TestCompositeStrategy:
    """Tests for CompositeStrategy."""

    # --- Basic tests ---

    def test_composite_name_without_modifier(self):
        """CompositeStrategy name should be primary name when no modifier."""
        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=None)
        assert composite.name() == "DCA"

    def test_composite_name_with_modifier(self):
        """CompositeStrategy name should combine primary and modifier names."""
        dca = DCAStrategy(invest_amount=1000)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)
        assert composite.name() == "DCA+MAFilter(20, trend_confirm)"

    def test_composite_empty_nav_history(self):
        """CompositeStrategy should return empty list for empty nav_history."""
        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter())
        signals = composite.generate_signals([])
        assert signals == []

    def test_composite_without_modifier_passthrough(self):
        """CompositeStrategy without modifier should pass through signals unchanged."""
        from datetime import timedelta

        # Create mock nav history
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=None)

        dca_signals = dca.generate_signals(nav_history)
        composite_signals = composite.generate_signals(nav_history)

        assert len(composite_signals) == len(dca_signals)
        for cs, ds in zip(composite_signals, dca_signals):
            assert cs.date == ds.date
            assert cs.action == ds.action

    # --- Blocked signals tracking ---

    def test_get_blocked_signals_empty_initially(self):
        """get_blocked_signals should return empty list before generate_signals."""
        dca = DCAStrategy(invest_amount=1000)
        composite = CompositeStrategy(primary_strategy=dca, modifier=MAFilter())
        assert composite.get_blocked_signals() == []

    def test_get_blocked_signals_records_blocked(self):
        """get_blocked_signals should return blocked signal records."""
        # Create mock strategy that returns a BUY signal
        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test"
        )
        mock_strategy = MockStrategy([signal])

        # Create context where BUY will be blocked (below MA)
        nav_history = [{"date": date(2023, 6, 15), "nav": 0.95}]

        # Use a filter that blocks BUY below MA
        ma_filter = MAFilter(window=20)

        # For this test, we need CompositeStrategy to build context
        # We'll test the full flow with sufficient nav_history
        nav_history_long = generate_mock_nav_history(date(2023, 1, 1), periods=180)
        # Make nav decline to create "below MA" scenario
        for i, record in enumerate(nav_history_long):
            record["nav"] = 1.0 - (i * 0.001)  # Declining trend

        mock_strategy_decline = MockStrategy([Signal(
            date=nav_history_long[-1]["date"],
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy in decline"
        )])

        composite = CompositeStrategy(primary_strategy=mock_strategy_decline, modifier=ma_filter)
        signals = composite.generate_signals(nav_history_long)

        # The BUY should be blocked
        blocked = composite.get_blocked_signals()
        assert len(blocked) == 1
        assert blocked[0]["original"].action == "BUY"
        assert "买入信号被拦截" in blocked[0]["reason"]

    def test_blocked_signals_cleared_on_new_generate(self):
        """_blocked_signals should be cleared at start of each generate_signals."""
        signal1 = Signal(date=date(2023, 6, 15), fund_code="000001", action="BUY", confidence=0.7, reason="test1")
        signal2 = Signal(date=date(2023, 6, 16), fund_code="000001", action="BUY", confidence=0.7, reason="test2")

        mock_strategy = MockStrategy([signal1])
        composite = CompositeStrategy(primary_strategy=mock_strategy, modifier=MAFilter())

        # First call with declining nav (will block) - use generate_mock_nav_history to avoid invalid dates
        nav_decline = generate_mock_nav_history(date(2023, 1, 1), periods=60)
        for i, record in enumerate(nav_decline):
            record["nav"] = 1.0 - i * 0.005  # Declining trend
        composite.generate_signals(nav_decline)
        assert len(composite.get_blocked_signals()) == 1

        # Second call - should clear previous blocked signals
        mock_strategy._signals = [signal2]
        composite.generate_signals(nav_decline)
        assert len(composite.get_blocked_signals()) == 1  # Not 2

    # --- DCA + MAFilter integration tests ---

    def test_rebalance_policy_blocked_in_phase3a(self):
        """CompositeStrategy should reject RebalancePolicy in Phase 3A."""
        from domain.backtest.strategies.rebalance.threshold import ThresholdRebalancePolicy

        dca = DCAStrategy(invest_amount=1000)
        rebalance_policy = ThresholdRebalancePolicy(threshold=0.05)

        with pytest.raises(NotImplementedError, match="RebalancePolicy is not supported"):
            CompositeStrategy(primary_strategy=dca, modifier=rebalance_policy)

    def test_dca_mafilter_uptrend_buy_passes(self):
        """DCA BUY in uptrend should pass through MAFilter."""
        # Create uptrend nav history
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)
        # Make nav rise to create "above MA" scenario
        for i, record in enumerate(nav_history):
            record["nav"] = 1.0 + (i * 0.005)  # Rising trend

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        signals = composite.generate_signals(nav_history)

        # All DCA signals should pass in uptrend
        assert len(signals) >= 2
        for signal in signals:
            assert signal.action == "BUY"

    def test_dca_mafilter_downtrend_buy_blocked(self):
        """DCA BUY in downtrend should be blocked by MAFilter."""
        # Create downtrend nav history
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)
        # Make nav decline to create "below MA" scenario
        for i, record in enumerate(nav_history):
            record["nav"] = 1.0 - (i * 0.005)  # Declining trend

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        signals = composite.generate_signals(nav_history)

        # All BUY signals should be blocked in downtrend
        assert len(signals) == 0
        assert len(composite.get_blocked_signals()) >= 2

    def test_composite_insufficient_nav_data_passes(self):
        """Signals should pass when nav history is insufficient for MA calculation."""
        # Create short nav history (< window=20)
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=15)

        dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

        signals = composite.generate_signals(nav_history)

        # Should pass through (insufficient data = unknown trend = allow)
        assert len(signals) >= 1

    def test_multiple_signals_blocked_accumulates(self):
        """_blocked_signals should accumulate multiple blocked signals."""
        # Create multiple BUY signals that will be blocked
        signals = [
            Signal(date=date(2023, 1, 10), fund_code="000001", action="BUY", confidence=0.7, reason="buy1"),
            Signal(date=date(2023, 1, 20), fund_code="000001", action="BUY", confidence=0.7, reason="buy2"),
            Signal(date=date(2023, 1, 30), fund_code="000001", action="BUY", confidence=0.7, reason="buy3"),
        ]
        mock_strategy = MockStrategy(signals)

        # Declining nav history - use generate_mock_nav_history to avoid invalid dates
        nav_history = generate_mock_nav_history(date(2023, 1, 1), periods=60)
        for i, record in enumerate(nav_history):
            record["nav"] = 1.0 - i * 0.005  # Declining trend

        composite = CompositeStrategy(primary_strategy=mock_strategy, modifier=MAFilter())
        composite.generate_signals(nav_history)

        blocked = composite.get_blocked_signals()
        assert len(blocked) == 3
        # Each blocked record should have the required fields
        for record in blocked:
            assert "original" in record
            assert "modifier" in record
            assert "reason" in record
            assert record["original"].action == "BUY"


class TestCompositeStrategySignalContext:
    """Tests for SignalContext building in CompositeStrategy."""

    def test_build_context_ma_calculation(self):
        """CompositeStrategy should correctly calculate MA and trend_relation."""
        # Create nav history with known values
        nav_history = [
            {"date": date(2023, 1, i), "nav": 1.0 + i * 0.01}  # Rising
            for i in range(1, 31)
        ]

        # Use mock strategy to get the last signal
        signal = Signal(
            date=date(2023, 1, 30),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test"
        )
        mock_strategy = MockStrategy([signal])

        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=mock_strategy, modifier=ma_filter)

        signals = composite.generate_signals(nav_history)

        # Signal should pass (rising trend = above MA)
        assert len(signals) == 1

    def test_build_context_exact_window_records(self):
        """CompositeStrategy should work with exactly window records."""
        # Exactly 20 records
        nav_history = [
            {"date": date(2023, 1, i), "nav": 1.0 + i * 0.01}
            for i in range(1, 21)
        ]

        signal = Signal(
            date=date(2023, 1, 20),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test"
        )
        mock_strategy = MockStrategy([signal])

        ma_filter = MAFilter(window=20)
        composite = CompositeStrategy(primary_strategy=mock_strategy, modifier=ma_filter)

        signals = composite.generate_signals(nav_history)
        # Should be able to calculate MA with exactly 20 records
        assert len(signals) == 1  # Passes because rising trend
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/domain/backtest/strategies/test_composite.py::TestCompositeStrategy -v`
Expected: FAIL with "cannot import name 'CompositeStrategy'"

- [ ] **Step 3: Implement CompositeStrategy**

```python
# domain/backtest/strategies/composite.py
"""Composite strategy that combines a primary strategy with a signal modifier."""
from datetime import date
import dataclasses
from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.modifiers.base import SignalModifier


class CompositeStrategy(Strategy):
    """Strategy that wraps a primary strategy and applies a signal modifier.

    Phase 3A: Only supports SignalModifier. RebalancePolicy is explicitly blocked.
    """

    def __init__(
        self,
        primary_strategy: Strategy,
        modifier: SignalModifier | None = None
    ):
        self.primary_strategy = primary_strategy
        self.modifier = modifier
        self._blocked_signals: list[dict] = []

        # Phase 3A: 明确禁止 RebalancePolicy
        if modifier is not None:
            # 检查是否是 RebalancePolicy 的实例（通过模块名判断）
            modifier_module = type(modifier).__module__
            if "rebalance" in modifier_module:
                raise NotImplementedError(
                    "RebalancePolicy is not supported in Phase 3A. "
                    "Use SignalModifier (e.g., MAFilter) instead."
                )

    def name(self) -> str:
        """Return composite strategy name in format 'Primary+Modifier(params)'."""
        if self.modifier is None:
            return self.primary_strategy.name()
        return f"{self.primary_strategy.name()}+{self.modifier.name()}"

    def get_blocked_signals(self) -> list[dict]:
        """Return list of blocked signals from last generate_signals call."""
        return self._blocked_signals.copy()

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        """Generate signals from primary strategy and apply modifier filter."""
        # Clear blocked signals at start
        self._blocked_signals = []

        # Handle empty input
        if not nav_history:
            return []

        # Get signals from primary strategy
        primary_signals = self.primary_strategy.generate_signals(nav_history)

        # If no modifier, return signals unchanged
        if self.modifier is None:
            return primary_signals

        # Apply modifier to each signal
        filtered_signals = []
        for signal in primary_signals:
            # Build SignalContext for this signal
            context = self._build_context(signal, nav_history)

            # Apply modifier
            modified = self.modifier.modify(signal, context)

            if modified is None:
                # Signal blocked - record it
                self._blocked_signals.append({
                    "original": dataclasses.replace(signal),
                    "modifier": self.modifier.name(),
                    "reason": self.modifier.explain_block(signal, context)
                })
            else:
                filtered_signals.append(modified)

        return filtered_signals

    def _build_context(self, signal: Signal, nav_history: list[dict]) -> SignalContext:
        """Build SignalContext with precomputed indicators for MAFilter."""
        signal_date = signal.date
        current_nav = None

        # Find current NAV for signal date
        navs_up_to_signal = []
        for record in nav_history:
            if record["date"] <= signal_date:
                navs_up_to_signal.append(record["nav"])
            if record["date"] == signal_date:
                current_nav = record["nav"]

        # Fallback logic: 如果找不到同日 NAV，使用最近的可用 NAV
        if current_nav is None:
            if navs_up_to_signal:
                # 使用信号日期之前最近的 NAV
                current_nav = navs_up_to_signal[-1]
            else:
                # nav_history 中没有任何早于或等于信号日期的记录
                # 这是数据问题，抛出明确错误而不是返回 magic number
                raise ValueError(
                    f"No NAV data available for signal date {signal_date}. "
                    f"nav_history should contain records on or before this date."
                )

        # Calculate MA indicators (for MAFilter)
        window = getattr(self.modifier, 'window', 20) if self.modifier else 20

        if len(navs_up_to_signal) < window:
            # Insufficient data
            indicators = {
                "ma_window": window,
                "ma_value": None,
                "trend_relation": "unknown",
                "ma_available": False,
            }
        else:
            # Calculate MA
            ma_value = sum(navs_up_to_signal[-window:]) / window
            trend_relation = self._determine_trend(current_nav, ma_value)
            indicators = {
                "ma_window": window,
                "ma_value": ma_value,
                "trend_relation": trend_relation,
                "ma_available": True,
            }

        return SignalContext(
            date=signal_date,
            current_nav=current_nav,
            indicators=indicators
        )

    def _determine_trend(self, current_nav: float, ma_value: float) -> str:
        """Determine trend relation between current NAV and MA."""
        # Use small tolerance for "equal" comparison
        tolerance = 0.0001
        if abs(current_nav - ma_value) < tolerance:
            return "equal"
        elif current_nav > ma_value:
            return "above"
        else:
            return "below"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/domain/backtest/strategies/test_composite.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add domain/backtest/strategies/composite.py tests/domain/backtest/strategies/test_composite.py
git commit -m "feat(backtest): implement CompositeStrategy with MAFilter support"
```

---

## Task 6: Run Full Test Suite

- [ ] **Step 1: Run all backtest tests**

Run: `uv run pytest tests/domain/backtest/ -v`
Expected: All tests pass

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest`
Expected: All tests pass

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address test failures"
```

---

## Summary

| Task | Files Created | Files Modified | Tests Added |
|------|---------------|----------------|-------------|
| 1. SignalContext | - | models.py | 2 |
| 2. SignalModifier ABC | modifiers/__init__.py, base.py | - | 2 |
| 3. MAFilter | ma_filter.py | - | 14 |
| 4. RebalancePolicy stub | rebalance/__init__.py, policy.py, threshold.py | - | 0 |
| 5. CompositeStrategy | composite.py | - | 15+ |
| 6. Test suite | - | - | - |

**Total new files:** 7
**Total new tests:** ~33
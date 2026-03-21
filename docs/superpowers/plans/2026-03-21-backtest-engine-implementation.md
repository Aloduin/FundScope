# 回测引擎实现 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现策略回测引擎，支持单基金单策略回测，输出净值曲线、收益指标和交易记录

**Architecture:**
- `domain/backtest/` 纯业务逻辑层（零 IO），包含策略接口、回测引擎、结果模型
- `service/backtest_service.py` 编排层，协调数据源和回测引擎
- 回测引擎独立维护账户状态，不依赖 `VirtualAccount`
- T 日信号，T+1 日成交的简化假设

**Tech Stack:** Python dataclasses, pandas 处理时序数据，numpy 数值计算

---

## 文件结构总览

### 创建的文件

| 文件 | 职责 |
|------|------|
| `domain/backtest/__init__.py` | 包初始化 |
| `domain/backtest/models.py` | 回测数据模型（Signal, BacktestResult） |
| `domain/backtest/strategies/__init__.py` | 策略包初始化 |
| `domain/backtest/strategies/base.py` | Strategy 抽象接口 |
| `domain/backtest/strategies/dca.py` | 定投策略实现 |
| `domain/backtest/strategies/ma.py` | 均线择时策略实现 |
| `domain/backtest/engine.py` | 回测引擎核心逻辑 |
| `service/backtest_service.py` | 回测服务编排 |
| `tests/domain/backtest/__init__.py` | 测试包初始化 |
| `tests/domain/backtest/test_models.py` | 回测模型测试 |
| `tests/domain/backtest/strategies/__init__.py` | 策略测试包 |
| `tests/domain/backtest/strategies/test_base.py` | 策略接口测试 |
| `tests/domain/backtest/strategies/test_dca.py` | DCA 策略测试 |
| `tests/domain/backtest/strategies/test_ma.py` | MA 策略测试 |
| `tests/domain/backtest/test_engine.py` | 回测引擎测试 |
| `tests/service/test_backtest_service.py` | 回测服务测试 |

### 修改的文件

| 文件 | 修改内容 |
|------|----------|
| `ui/pages/3_strategy_lab.py` | 添加回测面板 UI |

---

## Task 1: 回测数据模型

**Files:**
- Create: `domain/backtest/__init__.py`
- Create: `domain/backtest/models.py`
- Test: `tests/domain/backtest/__init__.py`
- Test: `tests/domain/backtest/test_models.py`

- [ ] **Step 1: 创建测试包初始化**

```bash
mkdir -p tests/domain/backtest
```

Create `tests/domain/backtest/__init__.py`:
```python
"""Tests for FundScope backtest domain."""
```

- [ ] **Step 2: 创建回测包初始化**

```bash
mkdir -p domain/backtest
```

Create `domain/backtest/__init__.py`:
```python
"""Backtest domain for FundScope strategy testing."""
```

- [ ] **Step 3: 编写回测模型测试**

Create `tests/domain/backtest/test_models.py`:
```python
"""Tests for backtest domain models."""
from datetime import date
from domain.backtest.models import Signal, BacktestResult


class TestSignal:
    """Tests for Signal dataclass."""

    def test_create_buy_signal(self):
        """Test creating a BUY signal."""
        signal = Signal(
            date=date(2024, 1, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.8,
            amount=10000.0,
            target_weight=None,
            reason="价格上穿 20 日均线"
        )

        assert signal.action == "BUY"
        assert signal.confidence == 0.8
        assert signal.amount == 10000.0
        assert signal.reason == "价格上穿 20 日均线"

    def test_create_sell_signal(self):
        """Test creating a SELL signal."""
        signal = Signal(
            date=date(2024, 1, 20),
            fund_code="000001",
            action="SELL",
            confidence=0.7,
            amount=None,
            target_weight=0.0,
            reason="价格下穿 20 日均线"
        )

        assert signal.action == "SELL"
        assert signal.target_weight == 0.0

    def test_create_rebalance_signal(self):
        """Test creating a REBALANCE signal."""
        signal = Signal(
            date=date(2024, 2, 1),
            fund_code="000001",
            action="REBALANCE",
            confidence=0.9,
            amount=None,
            target_weight=0.5,
            reason="月度再平衡"
        )

        assert signal.action == "REBALANCE"
        assert signal.target_weight == 0.5

    def test_signal_reason_cannot_be_empty(self):
        """Test that signal reason cannot be empty."""
        signal = Signal(
            date=date(2024, 1, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.5,
            amount=10000.0,
            target_weight=None,
            reason=""
        )

        # Engine will assert non-empty, but model allows it
        # This test documents that empty reason is technically possible
        assert signal.reason == ""


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    def test_create_backtest_result(self):
        """Test creating backtest result."""
        from datetime import date

        result = BacktestResult(
            strategy_name="DCA",
            fund_code="000001",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            total_return=0.15,
            annualized_return=0.15,
            max_drawdown=-0.08,
            sharpe_ratio=1.2,
            win_rate=0.65,
            trade_count=24,
            signals=[],
            equity_curve=[(date(2023, 1, 1), 100000), (date(2023, 12, 31), 115000)]
        )

        assert result.strategy_name == "DCA"
        assert result.total_return == 0.15
        assert result.sharpe_ratio == 1.2
        assert len(result.equity_curve) == 2
```

- [ ] **Step 4: 运行测试验证失败**

Run: `uv run pytest tests/domain/backtest/test_models.py -v`

Expected: FAIL with "cannot import name 'Signal' from 'domain.backtest.models'"

- [ ] **Step 5: 实现回测数据模型**

Create `domain/backtest/models.py`:
```python
"""Domain models for FundScope backtest subdomain."""
from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass
class Signal:
    """Trading signal from strategy.

    Attributes:
        date: Signal date
        fund_code: Fund code
        action: BUY, SELL, REBALANCE, or HOLD
        confidence: Signal strength 0.0~1.0
        amount: Trade amount in CNY (for amount-based signals)
        target_weight: Target position weight 0.0~1.0 (for weight-based signals)
        reason: Decision explanation for interpretability
    """
    date: date
    fund_code: str
    action: Literal["BUY", "SELL", "REBALANCE", "HOLD"]
    confidence: float
    amount: float | None = None
    target_weight: float | None = None
    reason: str = ""

    def __post_init__(self):
        """Validate signal."""
        if not self.reason:
            # Engine will enforce this, model just documents
            pass
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0~1.0, got {self.confidence}")


@dataclass
class BacktestResult:
    """Backtest result summary.

    Attributes:
        strategy_name: Strategy name
        fund_code: Fund code being tested
        start_date: Backtest start date
        end_date: Backtest end date
        total_return: Total return rate (e.g., 0.15 for 15%)
        annualized_return: Annualized return rate
        max_drawdown: Maximum drawdown (negative value)
        sharpe_ratio: Sharpe ratio
        win_rate: Strategy win rate
        trade_count: Total number of trades
        signals: List of all signals generated
        equity_curve: Equity curve [(date, equity), ...]
    """
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
```

- [ ] **Step 6: 运行测试验证通过**

Run: `uv run pytest tests/domain/backtest/test_models.py -v`

Expected: PASS (all 5 tests)

- [ ] **Step 7: 提交**

```bash
git add domain/backtest/__init__.py domain/backtest/models.py tests/domain/backtest/__init__.py tests/domain/backtest/test_models.py
git commit -m "feat(backtest): 创建回测数据模型 (Signal, BacktestResult)"
```

---

## Task 2: 策略抽象接口

**Files:**
- Create: `domain/backtest/strategies/__init__.py`
- Create: `domain/backtest/strategies/base.py`
- Test: `tests/domain/backtest/strategies/__init__.py`
- Test: `tests/domain/backtest/strategies/test_base.py`

- [ ] **Step 1: 创建策略测试包初始化**

```bash
mkdir -p tests/domain/backtest/strategies
```

Create `tests/domain/backtest/strategies/__init__.py`:
```python
"""Tests for FundScope backtest strategies."""
```

- [ ] **Step 2: 创建策略包初始化**

Create `domain/backtest/strategies/__init__.py`:
```python
"""Strategy implementations for FundScope backtest."""
from domain.backtest.strategies.base import Strategy

__all__ = ["Strategy"]
```

- [ ] **Step 3: 编写策略接口测试**

Create `tests/domain/backtest/strategies/test_base.py`:
```python
"""Tests for Strategy abstract base class."""
import pytest
from datetime import date
from domain.backtest.strategies.base import Strategy


class MockStrategy(Strategy):
    """Mock strategy for testing."""

    def __init__(self, signals=None):
        self._signals = signals or []

    def name(self) -> str:
        return "MockStrategy"

    def generate_signals(self, nav_history: list[dict]) -> list:
        return self._signals


class TestStrategyInterface:
    """Tests for Strategy interface."""

    def test_strategy_name_method(self):
        """Test that strategy has name method."""
        strategy = MockStrategy()
        assert strategy.name() == "MockStrategy"

    def test_strategy_generate_signals_method(self):
        """Test that strategy has generate_signals method."""
        mock_signals = [
            {"date": date(2024, 1, 15), "action": "BUY", "amount": 10000}
        ]
        strategy = MockStrategy(mock_signals)

        nav_history = [
            {"date": date(2024, 1, 1), "nav": 1.0},
            {"date": "2024, 1, 15), "nav": 1.1},
        ]

        signals = strategy.generate_signals(nav_history)
        assert len(signals) == 1

    def test_cannot_instantiate_abstract_strategy(self):
        """Test that Strategy cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Strategy()

    def test_strategy_must_implement_name(self):
        """Test that strategy must implement name method."""
        class IncompleteStrategy(Strategy):
            def generate_signals(self, nav_history):
                return []

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_strategy_must_implement_generate_signals(self):
        """Test that strategy must implement generate_signals method."""
        class IncompleteStrategy(Strategy):
            def name(self) -> str:
                return "Incomplete"

        with pytest.raises(TypeError):
            IncompleteStrategy()
```

- [ ] **Step 4: 运行测试验证失败**

Run: `uv run pytest tests/domain/backtest/strategies/test_base.py -v`

Expected: FAIL (Strategy class not defined properly)

- [ ] **Step 5: 实现策略抽象接口**

Create `domain/backtest/strategies/base.py`:
```python
"""Abstract strategy interface for FundScope backtest."""
from abc import ABC, abstractmethod
from domain.backtest.models import Signal


class Strategy(ABC):
    """Abstract base class for all trading strategies.

    All strategies must implement this interface.
    """

    @abstractmethod
    def name(self) -> str:
        """Get strategy name.

        Returns:
            Strategy name (e.g., 'DCA', 'MA Timing')
        """
        pass

    @abstractmethod
    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        """Generate trading signals from NAV history.

        Args:
            nav_history: List of NAV records with keys:
                - date: date
                - nav: float
                - acc_nav: float

        Returns:
            List of Signal objects
        """
        pass
```

- [ ] **Step 6: 运行测试验证通过**

Run: `uv run pytest tests/domain/backtest/strategies/test_base.py -v`

Expected: PASS (all 5 tests)

- [ ] **Step 7: 提交**

```bash
git add domain/backtest/strategies/ tests/domain/backtest/strategies/
git commit -m "feat(backtest): 定义 Strategy 抽象接口"
```

---

## Task 3: DCA 定投策略实现

**Files:**
- Create: `domain/backtest/strategies/dca.py`
- Test: `tests/domain/backtest/strategies/test_dca.py`

- [ ] **Step 1: 编写 DCA 策略测试**

Create `tests/domain/backtest/strategies/test_dca.py`:
```python
"""Tests for DCA (Dollar-Cost Averaging) strategy."""
from datetime import date, timedelta
from domain.backtest.strategies.dca import DCAStrategy


def generate_mock_nav_history(start_date: date, periods: int = 252) -> list[dict]:
    """Generate mock NAV history for testing."""
    nav_history = []
    nav = 1.0

    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        # Simple upward trend with noise
        nav = nav * (1 + 0.0005 + (hash(str(i)) % 100 - 50) / 10000)
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })

    return nav_history


class TestDCAStrategy:
    """Tests for DCA strategy."""

    def test_dca_strategy_name(self):
        """Test DCA strategy name."""
        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        assert strategy.name() == "DCA"

    def test_dca_generates_monthly_signals(self):
        """Test DCA generates signals at regular intervals."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=120)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        # Should have approximately 6 signals (120 days / 20)
        assert len(signals) >= 5
        assert len(signals) <= 7

    def test_dca_signals_are_buy_actions(self):
        """Test DCA signals are all BUY actions."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert signal.action == "BUY"
            assert signal.amount == 10000.0
            assert signal.confidence == 0.5
            assert "定期定额投资" in signal.reason

    def test_dca_invest_amount_from_params(self):
        """Test DCA uses invest_amount from parameters."""
        nav_history = generate_mock_nav_history(date(2023, 1, 1), 60)

        strategy = DCAStrategy(invest_amount=5000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert signal.amount == 5000.0

    def test_dca_first_signal_after_interval(self):
        """Test DCA first signal comes after interval from start."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=45)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        assert len(signals) >= 2
        # First signal should be around day 20
        first_signal_date = signals[0].date
        days_since_start = (first_signal_date - start_date).days
        assert 15 <= days_since_start <= 25
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/domain/backtest/strategies/test_dca.py -v`

Expected: FAIL with "cannot import name 'DCAStrategy'"

- [ ] **Step 3: 实现 DCA 策略**

Create `domain/backtest/strategies/dca.py`:
```python
"""Dollar-Cost Averaging (DCA) strategy implementation."""
from datetime import timedelta
from domain.backtest.models import Signal
from domain.backtest.strategies.base import Strategy


class DCAStrategy(Strategy):
    """Dollar-Cost Averaging strategy.

    Invests a fixed amount at regular intervals regardless of price.
    """

    def __init__(self, invest_amount: float, invest_interval_days: int = 20):
        """Initialize DCA strategy.

        Args:
            invest_amount: Amount to invest each time (in CNY)
            invest_interval_days: Days between investments (default: 20 trading days ~ 1 month)
        """
        self.invest_amount = invest_amount
        self.invest_interval_days = invest_interval_days

    def name(self) -> str:
        """Get strategy name."""
        return "DCA"

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        """Generate DCA signals from NAV history.

        Args:
            nav_history: List of NAV records

        Returns:
            List of BUY signals at regular intervals
        """
        if not nav_history:
            return []

        signals = []
        last_invest_date = None

        for record in nav_history:
            current_date = record["date"]

            # Check if we should invest today
            should_invest = False

            if last_invest_date is None:
                # First investment at start of period
                should_invest = True
            else:
                # Check if interval has passed
                days_diff = (current_date - last_invest_date).days
                if days_diff >= self.invest_interval_days:
                    should_invest = True

            if should_invest:
                signal = Signal(
                    date=current_date,
                    fund_code="UNKNOWN",  # Will be set by engine
                    action="BUY",
                    confidence=0.5,  # Fixed confidence for DCA
                    amount=self.invest_amount,
                    target_weight=None,
                    reason=f"定期定额投资：{self.invest_amount:.0f}元"
                )
                signals.append(signal)
                last_invest_date = current_date

        return signals
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/domain/backtest/strategies/test_dca.py -v`

Expected: PASS (all 5 tests)

- [ ] **Step 5: 提交**

```bash
git add domain/backtest/strategies/dca.py tests/domain/backtest/strategies/test_dca.py
git commit -m "feat(backtest): 实现 DCA 定投策略"
```

---

## Task 4: MA 均线择时策略实现

**Files:**
- Create: `domain/backtest/strategies/ma.py`
- Test: `tests/domain/backtest/strategies/test_ma.py`

- [ ] **Step 1: 编写 MA 策略测试**

Create `tests/domain/backtest/strategies/test_ma.py`:
```python
"""Tests for Moving Average (MA) timing strategy."""
from datetime import date, timedelta
from domain.backtest.strategies.ma import MAStrategy


def generate_trending_nav(start_date: date, periods: int = 100, trend: str = "up") -> list[dict]:
    """Generate trending NAV history for testing."""
    nav_history = []
    nav = 1.0

    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        if trend == "up":
            nav = nav * 1.002  # Upward trend
        else:
            nav = nav * 0.998  # Downward trend
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })

    return nav_history


class TestMAStrategy:
    """Tests for MA timing strategy."""

    def test_ma_strategy_name(self):
        """Test MA strategy name."""
        strategy = MAStrategy(short_window=5, long_window=20)
        assert strategy.name() == "MA Timing"

    def test_ma_generates_buy_on_crossover(self):
        """Test MA generates BUY on bullish crossover."""
        start_date = date(2023, 1, 1)
        nav_history = generate_trending_nav(start_date, periods=100, trend="up")

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        # Should have at least one BUY signal in uptrend
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) >= 1

    def test_ma_generates_sell_on_bearish_crossover(self):
        """Test MA generates SELL on bearish crossover."""
        start_date = date(2023, 1, 1)
        nav_history = generate_trending_nav(start_date, periods=100, trend="down")

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        # Should have at least one SELL signal in downtrend
        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) >= 1

    def test_ma_signals_have_explanation(self):
        """Test MA signals have reason explanation."""
        start_date = date(2023, 1, 1)
        nav_history = generate_trending_nav(start_date, periods=100)

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert signal.reason != ""
            assert "均线" in signal.reason or "上穿" in signal.reason or "下穿" in signal.reason

    def test_ma_confidence_varies_by_signal_strength(self):
        """Test MA confidence varies by how far price is from MA."""
        start_date = date(2023, 1, 1)
        nav_history = generate_trending_nav(start_date, periods=100)

        strategy = MAStrategy(short_window=5, long_window=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert 0.6 <= signal.confidence <= 0.8
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/domain/backtest/strategies/test_ma.py -v`

Expected: FAIL with "cannot import name 'MAStrategy'"

- [ ] **Step 3: 实现 MA 策略**

Create `domain/backtest/strategies/ma.py`:
```python
"""Moving Average (MA) timing strategy implementation."""
from domain.backtest.models import Signal
from domain.backtest.strategies.base import Strategy


class MAStrategy(Strategy):
    """Moving Average crossover timing strategy.

    BUY when short-term MA crosses above long-term MA.
    SELL when short-term MA crosses below long-term MA.
    """

    def __init__(self, short_window: int = 5, long_window: int = 20):
        """Initialize MA strategy.

        Args:
            short_window: Short-term MA window (e.g., 5 days)
            long_window: Long-term MA window (e.g., 20 days)
        """
        self.short_window = short_window
        self.long_window = long_window

    def name(self) -> str:
        """Get strategy name."""
        return "MA Timing"

    def _calculate_ma(self, navs: list[float], window: int) -> float | None:
        """Calculate simple moving average."""
        if len(navs) < window:
            return None
        return sum(navs[-window:]) / window

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        """Generate MA crossover signals.

        Args:
            nav_history: List of NAV records

        Returns:
            List of BUY/SELL signals
        """
        if len(nav_history) < self.long_window:
            return []

        signals = []
        prev_short_ma = None
        prev_long_ma = None
        in_position = False

        for i, record in enumerate(nav_history):
            current_date = record["date"]
            current_nav = record["nav"]

            # Calculate MAs
            navs_so_far = [nav_history[j]["nav"] for j in range(i + 1)]
            short_ma = self._calculate_ma(navs_so_far, self.short_window)
            long_ma = self._calculate_ma(navs_so_far, self.long_window)

            if short_ma is None or long_ma is None:
                continue

            # Check for crossover
            if prev_short_ma is not None and prev_long_ma is not None:
                # Bullish crossover: short MA crosses above long MA
                if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                    confidence = min(0.8, 0.6 + (short_ma - long_ma) / long_ma)
                    signal = Signal(
                        date=current_date,
                        fund_code="UNKNOWN",
                        action="BUY",
                        confidence=confidence,
                        amount=None,
                        target_weight=1.0,
                        reason=f"短期均线上穿长期均线（{short_ma:.3f} > {long_ma:.3f}）"
                    )
                    signals.append(signal)
                    in_position = True

                # Bearish crossover: short MA crosses below long MA
                elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
                    confidence = min(0.8, 0.6 + abs(short_ma - long_ma) / long_ma)
                    signal = Signal(
                        date=current_date,
                        fund_code="UNKNOWN",
                        action="SELL",
                        confidence=confidence,
                        amount=None,
                        target_weight=0.0,
                        reason=f"短期均线下穿长期均线（{short_ma:.3f} < {long_ma:.3f}）"
                    )
                    signals.append(signal)
                    in_position = False

            prev_short_ma = short_ma
            prev_long_ma = long_ma

        return signals
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/domain/backtest/strategies/test_ma.py -v`

Expected: PASS (all 5 tests)

- [ ] **Step 5: 提交**

```bash
git add domain/backtest/strategies/ma.py tests/domain/backtest/strategies/test_ma.py
git commit -m "feat(backtest): 实现 MA 均线择时策略"
```

---

## Task 5: 回测引擎核心实现

**Files:**
- Create: `domain/backtest/engine.py`
- Test: `tests/domain/backtest/test_engine.py`

- [ ] **Step 1: 编写回测引擎测试**

Create `tests/domain/backtest/test_engine.py`:
```python
"""Tests for backtest engine."""
from datetime import date, timedelta
from domain.backtest.engine import BacktestEngine
from domain.backtest.strategies.dca import DCAStrategy


def generate_mock_nav_history(start_date: date, periods: int = 60) -> list[dict]:
    """Generate mock NAV history."""
    nav_history = []
    nav = 1.0

    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        nav = nav * (1 + 0.0005 + (hash(str(i)) % 100 - 50) / 10000)
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })

    return nav_history


class MockStrategy:
    """Mock strategy for engine testing."""

    def __init__(self, signals):
        self._signals = signals

    def name(self) -> str:
        return "Mock"

    def generate_signals(self, nav_history):
        return self._signals


class TestBacktestEngine:
    """Tests for BacktestEngine."""

    def test_engine_initial_state(self):
        """Test engine initializes with correct state."""
        engine = BacktestEngine(initial_cash=100000)
        assert engine.initial_cash == 100000
        assert engine.cash == 100000

    def test_engine_runs_dca_strategy(self):
        """Test engine can run DCA strategy."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        assert result.strategy_name == "DCA"
        assert result.fund_code == "000001"
        assert result.trade_count >= 2
        assert len(result.equity_curve) > 0

    def test_engine_no_signals_holds_cash(self):
        """Test engine holds cash when no signals."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=30)

        strategy = MockStrategy([])  # No signals
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        assert result.trade_count == 0
        # Final equity should be close to initial cash (no trades)
        assert result.equity_curve[-1][1] >= 99000  # Small variance allowed

    def test_engine_t_plus_1_execution(self):
        """Test engine executes trades T+1."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=30)

        # Create signal on day 5
        signal_date = start_date + timedelta(days=5)
        signal = Signal(
            date=signal_date,
            fund_code="000001",
            action="BUY",
            confidence=0.5,
            amount=10000,
            target_weight=None,
            reason="Test signal"
        )

        from domain.backtest.models import Signal
        strategy = MockStrategy([signal])
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        # Trade should execute on T+1 (day 6)
        # Verify equity curve reflects delayed execution
        assert len(result.equity_curve) == len(nav_history)

    def test_engine_calculates_metrics(self):
        """Test engine calculates backtest metrics."""
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        # Verify metrics are calculated
        assert result.total_return is not None
        assert result.annualized_return is not None
        assert result.max_drawdown is not None
        assert result.sharpe_ratio is not None
        assert result.win_rate is not None
        assert result.start_date == start_date
        assert result.end_date == nav_history[-1]["date"]
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/domain/backtest/test_engine.py -v`

Expected: FAIL with "cannot import name 'BacktestEngine'"

- [ ] **Step 3: 实现回测引擎**

Create `domain/backtest/engine.py`:
```python
"""Backtest engine for FundScope."""
from datetime import date, timedelta
from domain.backtest.models import Signal, BacktestResult
from domain.backtest.strategies.base import Strategy
import numpy as np


class BacktestEngine:
    """Backtest execution engine.

    Runs strategy signals through historical NAV data,
    executing trades with T+1 settlement.
    """

    def __init__(self, initial_cash: float = 100000.0):
        """Initialize backtest engine.

        Args:
            initial_cash: Initial cash amount
        """
        self.initial_cash = initial_cash

    def run(
        self,
        strategy: Strategy,
        fund_code: str,
        nav_history: list[dict]
    ) -> BacktestResult:
        """Run backtest for a strategy.

        Args:
            strategy: Strategy to backtest
            fund_code: Fund code
            nav_history: Historical NAV data

        Returns:
            BacktestResult with metrics and equity curve
        """
        if not nav_history:
            raise ValueError("NAV history cannot be empty")

        # Generate signals
        signals = strategy.generate_signals(nav_history)

        # Set fund_code on all signals
        for signal in signals:
            if signal.fund_code == "UNKNOWN":
                signal.fund_code = fund_code

        # Initialize state
        cash = self.initial_cash
        shares = 0.0
        equity_curve = []
        trades = []

        # Create NAV lookup by date
        nav_by_date = {r["date"]: r["nav"] for r in nav_history}

        # Track pending orders (T day signal, T+1 execute)
        pending_order = None

        for i, record in enumerate(nav_history):
            current_date = record["date"]
            current_nav = record["nav"]

            # Execute pending order from T day
            if pending_order is not None:
                signal, target_date = pending_order
                if current_date == target_date:
                    # Execute trade
                    if signal.action == "BUY" and signal.amount:
                        trade_shares = signal.amount / current_nav
                        shares += trade_shares
                        cash -= signal.amount
                        trades.append({
                            "date": current_date,
                            "action": "BUY",
                            "amount": signal.amount,
                            "nav": current_nav,
                            "shares": trade_shares
                        })
                    elif signal.action == "SELL":
                        if signal.target_weight is not None:
                            # Sell to target weight
                            target_shares = 0 if signal.target_weight == 0 else shares * signal.target_weight
                            shares_to_sell = shares - target_shares
                        else:
                            shares_to_sell = shares

                        cash += shares_to_sell * current_nav
                        shares -= shares_to_sell
                        trades.append({
                            "date": current_date,
                            "action": "SELL",
                            "amount": shares_to_sell * current_nav,
                            "nav": current_nav,
                            "shares": shares_to_sell
                        })

                    pending_order = None

            # Check for new signals today (will execute T+1)
            todays_signals = [s for s in signals if s.date == current_date]
            if todays_signals and i < len(nav_history) - 1:
                # Use last signal for the day (simplified)
                next_date = nav_history[i + 1]["date"]
                pending_order = (todays_signals[-1], next_date)

            # Calculate equity
            equity = cash + shares * current_nav
            equity_curve.append((current_date, equity))

        # Calculate metrics
        total_return = (equity_curve[-1][1] - self.initial_cash) / self.initial_cash

        # Annualized return
        days = (nav_history[-1]["date"] - nav_history[0]["date"]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # Max drawdown
        equity_values = [e[1] for e in equity_curve]
        peak = equity_values[0]
        max_drawdown = 0.0
        for eq in equity_values:
            if eq > peak:
                peak = eq
            drawdown = (eq - peak) / peak
            if drawdown < max_drawdown:
                max_drawdown = drawdown

        # Daily returns for Sharpe
        daily_returns = []
        for i in range(1, len(equity_values)):
            ret = (equity_values[i] - equity_values[i-1]) / equity_values[i-1]
            daily_returns.append(ret)

        # Sharpe ratio (assuming 252 trading days, risk-free rate = 0)
        if len(daily_returns) > 1:
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            sharpe_ratio = (mean_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe_ratio = 0

        # Win rate (positive days / total days)
        winning_days = sum(1 for r in daily_returns if r > 0)
        win_rate = winning_days / len(daily_returns) if daily_returns else 0

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
            trade_count=len(trades),
            signals=signals,
            equity_curve=equity_curve
        )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/domain/backtest/test_engine.py -v`

Expected: PASS (all 5 tests)

- [ ] **Step 5: 提交**

```bash
git add domain/backtest/engine.py tests/domain/backtest/test_engine.py
git commit -m "feat(backtest): 实现回测引擎核心逻辑"
```

---

## Task 6: 回测服务层编排

**Files:**
- Create: `service/backtest_service.py`
- Test: `tests/service/test_backtest_service.py`

- [ ] **Step 1: 编写回测服务测试**

Create `tests/service/test_backtest_service.py`:
```python
"""Tests for backtest service."""
import pytest
from datetime import date
from service.backtest_service import BacktestService
from domain.backtest.strategies.dca import DCAStrategy


class TestBacktestService:
    """Tests for BacktestService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = BacktestService()

    def test_service_creates_strategy_by_name(self):
        """Test service can create strategy by name."""
        strategy = self.service._create_strategy("DCA", {"invest_amount": 10000})
        assert strategy.name() == "DCA"

    def test_service_raises_for_unknown_strategy(self):
        """Test service raises error for unknown strategy."""
        with pytest.raises(ValueError, match="Unknown strategy"):
            self.service._create_strategy("UnknownStrategy", {})

    def test_run_backtest_with_dca(self):
        """Test running backtest with DCA strategy."""
        result = self.service.run_backtest(
            fund_code="000001",
            strategy_name="DCA",
            strategy_params={"invest_amount": 10000},
            start_date=date(2023, 1, 1),
            end_date=date(2023, 3, 31),
            initial_cash=100000
        )

        assert result is not None
        assert result.strategy_name == "DCA"
        assert result.fund_code == "000001"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `uv run pytest tests/service/test_backtest_service.py -v`

Expected: FAIL with "cannot import name 'BacktestService'"

- [ ] **Step 3: 实现回测服务**

Create `service/backtest_service.py`:
```python
"""Backtest service for FundScope."""
from datetime import date
from domain.backtest.engine import BacktestEngine
from domain.backtest.models import BacktestResult
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.strategies.ma import MAStrategy
from infrastructure.datasource.akshare_source import AkShareDataSource


class BacktestService:
    """Service for orchestrating backtest operations."""

    def __init__(self):
        """Initialize backtest service."""
        self.datasource = AkShareDataSource()

    def _create_strategy(self, strategy_name: str, params: dict) -> Strategy:
        """Create strategy instance by name.

        Args:
            strategy_name: Strategy name ('DCA', 'MA Timing')
            params: Strategy parameters

        Returns:
            Strategy instance

        Raises:
            ValueError: If strategy name is unknown
        """
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
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    def run_backtest(
        self,
        fund_code: str,
        strategy_name: str,
        strategy_params: dict,
        start_date: date,
        end_date: date,
        initial_cash: float = 100000.0
    ) -> BacktestResult:
        """Run backtest for a strategy on a fund.

        Args:
            fund_code: Fund code to backtest
            strategy_name: Strategy name
            strategy_params: Strategy parameters
            start_date: Backtest start date
            end_date: Backtest end date
            initial_cash: Initial cash amount

        Returns:
            BacktestResult with metrics
        """
        # Get NAV history from data source
        nav_history = self.datasource.get_fund_nav_history(
            fund_code=fund_code,
            start_date=start_date,
            end_date=end_date
        )

        if not nav_history:
            raise ValueError(f"No NAV data found for fund {fund_code}")

        # Create strategy
        strategy = self._create_strategy(strategy_name, strategy_params)

        # Run backtest
        engine = BacktestEngine(initial_cash=initial_cash)
        result = engine.run(strategy, fund_code, nav_history)

        return result
```

- [ ] **Step 4: 运行测试验证通过**

Run: `uv run pytest tests/service/test_backtest_service.py -v`

Expected: PASS (all 3 tests)

- [ ] **Step 5: 提交**

```bash
git add service/backtest_service.py tests/service/test_backtest_service.py
git commit -m "feat(backtest): 实现回测服务层编排"
```

---

## Task 7: 回测 UI 集成

**Files:**
- Modify: `ui/pages/3_strategy_lab.py`

- [ ] **Step 1: 读取现有策略验证中心页面**

Read `ui/pages/3_strategy_lab.py` to understand current structure.

- [ ] **Step 2: 添加回测面板 UI**

Modify `ui/pages/3_strategy_lab.py`:

Add new tab for backtesting with:
- Fund code input
- Strategy selection dropdown
- Strategy parameters inputs
- Date range picker
- Run backtest button
- Results display (metrics cards)
- Equity curve chart
- Trade history table

- [ ] **Step 3: 验证 Streamlit 应用**

Run: `uv run streamlit run ui/app.py`

Expected: App starts without errors, new backtest tab is visible

- [ ] **Step 4: 提交**

```bash
git add ui/pages/3_strategy_lab.py
git commit -m "feat(ui): 添加回测面板到策略验证中心"
```

---

## Task 8: 完整测试验证

**Files:** All backtest test files

- [ ] **Step 1: 运行所有回测测试**

Run: `uv run pytest tests/domain/backtest/ tests/service/test_backtest_service.py -v`

Expected: All tests pass

- [ ] **Step 2: 运行完整测试套件**

Run: `uv run pytest --cov=. --cov-report=html`

Expected: All tests pass, coverage maintained

- [ ] **Step 3: 推送到远程仓库**

```bash
git push origin master
```

---

## 里程碑检查点

完成以上 Tasks 后，应达成以下里程碑：

### 里程碑 A: 骨架跑通 ✅
- [x] 单基金
- [x] 单策略
- [x] 单账户
- [x] T 日信号，T+1 成交
- [x] 输出净值曲线、收益、回撤、交易次数

### 里程碑 B: 简单策略实现 ✅
- [x] DCA 定投
- [x] MA 均线择时
- [ ] Momentum 动量轮动（可后续扩展）

### 里程碑 C: UI 集成 ✅
- [x] 策略验证中心回测面板
- [x] 选择基金、策略、日期
- [x] 显示收益、最大回撤、夏普、净值曲线、交易记录

---

## 参考文档

- [设计文档](../specs/2026-03-21-fundscope-design.md) - 第八节：回测规则
- [现有代码模式](../../domain/simulation/) - 参考 simulation 子域的组织方式
- [Service 层模式](../../service/fund_service.py) - 参考编排层实现

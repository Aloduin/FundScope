"""Tests for backtest engine."""
from datetime import date, timedelta
from domain.backtest.engine import BacktestEngine
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.models import Signal


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

    def __init__(self, signals: list):
        self._signals = signals

    def name(self) -> str:
        return "Mock"

    def generate_signals(self, nav_history):
        return self._signals


class TestBacktestEngine:
    """Tests for BacktestEngine."""

    def test_engine_initial_state(self):
        engine = BacktestEngine(initial_cash=100000)
        assert engine.initial_cash == 100000

    def test_engine_runs_dca_strategy(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        assert result.strategy_name == "DCA"
        assert result.fund_code == "000001"
        assert result.trade_count >= 2
        assert len(result.equity_curve) > 0
        assert len(result.executed_trades) == result.trade_count

    def test_engine_no_signals_holds_cash(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=30)

        strategy = MockStrategy([])
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        assert result.trade_count == 0
        assert result.equity_curve[-1][1] >= 99000

    def test_engine_t_plus_1_execution(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=30)

        signal_date = start_date + timedelta(days=5)
        signal = Signal(
            date=signal_date,
            fund_code="000001",
            action="BUY",
            confidence=0.5,
            reason="Test signal",
            amount=10000,
            target_weight=None,
        )

        strategy = MockStrategy([signal])
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        assert len(result.equity_curve) == len(nav_history)
        assert result.trade_count == 1
        assert result.executed_trades[0].date == nav_history[6]["date"]

    def test_engine_calculates_metrics(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        engine = BacktestEngine(initial_cash=100000)

        result = engine.run(strategy, "000001", nav_history)

        assert result.total_return is not None
        assert result.annualized_return is not None
        assert result.max_drawdown is not None
        assert result.max_drawdown >= 0
        assert result.sharpe_ratio is not None
        assert result.win_rate is not None
        assert result.start_date == start_date
        assert result.end_date == nav_history[-1]["date"]

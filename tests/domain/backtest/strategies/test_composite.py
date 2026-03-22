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

        # First signal on day 0 passes (insufficient MA data), rest are blocked
        assert len(signals) == 1
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
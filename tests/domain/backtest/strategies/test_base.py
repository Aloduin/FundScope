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
        strategy = MockStrategy()
        assert strategy.name() == "MockStrategy"

    def test_strategy_generate_signals_method(self):
        mock_signals = [
            {"date": date(2024, 1, 15), "action": "BUY", "amount": 10000}
        ]
        strategy = MockStrategy(mock_signals)

        nav_history = [
            {"date": date(2024, 1, 1), "nav": 1.0},
            {"date": date(2024, 1, 15), "nav": 1.1},
        ]

        signals = strategy.generate_signals(nav_history)
        assert len(signals) == 1

    def test_cannot_instantiate_abstract_strategy(self):
        with pytest.raises(TypeError):
            Strategy()

    def test_strategy_must_implement_name(self):
        class IncompleteStrategy(Strategy):
            def generate_signals(self, nav_history):
                return []

        with pytest.raises(TypeError):
            IncompleteStrategy()

    def test_strategy_must_implement_generate_signals(self):
        class IncompleteStrategy(Strategy):
            def name(self) -> str:
                return "Incomplete"

        with pytest.raises(TypeError):
            IncompleteStrategy()

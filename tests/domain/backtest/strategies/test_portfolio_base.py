"""Tests for PortfolioStrategy abstract base class."""
from datetime import date
from domain.backtest.strategies.portfolio_base import PortfolioStrategy
from domain.backtest.models import PortfolioSignal
import pytest


class ConcretePortfolioStrategy(PortfolioStrategy):
    """Concrete implementation for testing."""

    def name(self) -> str:
        return "ConcretePortfolio"

    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date],
    ) -> list[PortfolioSignal]:
        return [
            PortfolioSignal(
                date=aligned_dates[0],
                action="REBALANCE",
                target_weights={"000001": 0.5, "CASH": 0.5},
                confidence=1.0,
                reason="Test signal",
            )
        ]


class TestPortfolioStrategy:
    """Tests for PortfolioStrategy base class."""

    def test_concrete_strategy_implements_interface(self):
        strategy = ConcretePortfolioStrategy()
        assert strategy.name() == "ConcretePortfolio"

    def test_generate_portfolio_signals_returns_list(self):
        strategy = ConcretePortfolioStrategy()
        nav_histories = {
            "000001": [{"date": date(2023, 1, 1), "nav": 1.0}]
        }
        aligned_dates = [date(2023, 1, 1)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        assert isinstance(signals, list)
        assert len(signals) == 1
        assert isinstance(signals[0], PortfolioSignal)

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            PortfolioStrategy()

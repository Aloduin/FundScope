"""Tests for revised RebalancePolicy interface."""
from datetime import date
from domain.backtest.strategies.rebalance.policy import RebalancePolicy
from domain.backtest.models import PortfolioSignal, SignalContext
import pytest


class ConcreteRebalancePolicy(RebalancePolicy):
    """Concrete implementation for testing."""

    def name(self) -> str:
        return "ConcretePolicy"

    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        # Pass through if CASH position > 0, otherwise block
        for pos in current_positions:
            if pos["fund_code"] == "CASH" and pos["weight"] > 0:
                return signal
        return None


class TestRebalancePolicyInterface:
    """Tests for revised RebalancePolicy interface."""

    def test_apply_returns_signal_when_passed(self):
        policy = ConcreteRebalancePolicy()
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000001": 0.5, "CASH": 0.5},
            confidence=1.0,
            reason="Test",
        )
        positions = [{"fund_code": "CASH", "weight": 0.3}]
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is signal

    def test_apply_returns_none_when_blocked(self):
        policy = ConcreteRebalancePolicy()
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000001": 0.5, "CASH": 0.5},
            confidence=1.0,
            reason="Test",
        )
        positions = [{"fund_code": "000001", "weight": 1.0}]  # No CASH
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is None

    def test_cannot_instantiate_abc_directly(self):
        with pytest.raises(TypeError):
            RebalancePolicy()

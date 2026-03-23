"""Tests for ThresholdRebalancePolicy."""
from datetime import date
from domain.backtest.strategies.rebalance.threshold import ThresholdRebalancePolicy
from domain.backtest.models import PortfolioSignal, SignalContext
import pytest


class TestThresholdRebalancePolicy:
    """Tests for ThresholdRebalancePolicy."""

    def test_policy_name(self):
        policy = ThresholdRebalancePolicy(threshold=0.05)
        assert "5%" in policy.name()

    def test_apply_passes_when_deviation_above_threshold(self):
        policy = ThresholdRebalancePolicy(threshold=0.05)
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000001": 0.5, "000002": 0.3, "CASH": 0.2},
            confidence=1.0,
            reason="Test",
        )
        # Current: 000001=0.3, CASH=0.7 - deviation is 0.2 for 000001
        positions = [
            {"fund_code": "000001", "weight": 0.3},
            {"fund_code": "CASH", "weight": 0.7},
        ]
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is signal

    def test_apply_blocks_when_deviation_below_threshold(self):
        policy = ThresholdRebalancePolicy(threshold=0.10)
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000001": 0.5, "CASH": 0.5},
            confidence=1.0,
            reason="Test",
        )
        # Current: 000001=0.48, CASH=0.52 - deviation is 0.02
        positions = [
            {"fund_code": "000001", "weight": 0.48},
            {"fund_code": "CASH", "weight": 0.52},
        ]
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is None

    def test_apply_includes_cash_in_deviation(self):
        policy = ThresholdRebalancePolicy(threshold=0.05)
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000001": 0.5, "CASH": 0.5},
            confidence=1.0,
            reason="Test",
        )
        # Current: 000001=0.5, CASH=0.5 - no deviation
        positions = [
            {"fund_code": "000001", "weight": 0.5},
            {"fund_code": "CASH", "weight": 0.5},
        ]
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is None  # Blocked because deviation is 0

    def test_apply_handles_missing_cash_in_current(self):
        policy = ThresholdRebalancePolicy(threshold=0.05)
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000001": 0.5, "CASH": 0.5},
            confidence=1.0,
            reason="Test",
        )
        # Current: 000001=1.0, no CASH entry - deviation for CASH is 0.5
        positions = [{"fund_code": "000001", "weight": 1.0}]
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is signal  # Passed because CASH deviation is 0.5 > 0.05

    def test_apply_handles_new_fund_not_in_current(self):
        policy = ThresholdRebalancePolicy(threshold=0.05)
        signal = PortfolioSignal(
            date=date(2023, 1, 15),
            action="REBALANCE",
            target_weights={"000002": 0.5, "CASH": 0.5},
            confidence=1.0,
            reason="Test",
        )
        # Current: only 000001, target has 000002 - deviation for 000002 is 0.5
        positions = [
            {"fund_code": "000001", "weight": 1.0},
        ]
        context = SignalContext(date=date(2023, 1, 15), current_nav=0.0, indicators={})

        result = policy.apply(signal, positions, context)

        assert result is signal  # Passed because new fund deviation is 0.5 > 0.05

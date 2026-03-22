# tests/domain/backtest/strategies/test_modifiers.py
"""Tests for signal modifiers."""
import pytest
from datetime import date

from domain.backtest.models import Signal, SignalContext


class TestSignalModifierABC:
    """Tests for SignalModifier abstract base class."""

    def test_signal_modifier_is_abstract(self):
        """SignalModifier cannot be instantiated directly."""
        from domain.backtest.strategies.modifiers.base import SignalModifier

        with pytest.raises(TypeError):
            SignalModifier()

    def test_signal_modifier_has_required_methods(self):
        """Concrete implementation must implement all abstract methods."""
        from domain.backtest.strategies.modifiers.base import SignalModifier

        class ConcreteModifier(SignalModifier):
            def name(self) -> str:
                return "TestModifier"

            def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
                return signal

            def explain_block(self, signal: Signal, context: SignalContext) -> str:
                return "test reason"

        modifier = ConcreteModifier()
        assert modifier.name() == "TestModifier"

    def test_signal_modifier_modify_can_return_none(self):
        """modify() can return None to block a signal."""
        from domain.backtest.strategies.modifiers.base import SignalModifier

        class BlockingModifier(SignalModifier):
            def name(self) -> str:
                return "Blocker"

            def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
                return None  # Block all signals

            def explain_block(self, signal: Signal, context: SignalContext) -> str:
                return "blocked for testing"

        modifier = BlockingModifier()
        signal = Signal(
            date=date(2026, 3, 22),
            fund_code="000001",
            action="BUY",
            confidence=0.8,
            reason="test signal",
        )
        context = SignalContext(
            date=date(2026, 3, 22),
            current_nav=1.5,
            indicators={},
        )

        result = modifier.modify(signal, context)
        assert result is None
        assert modifier.explain_block(signal, context) == "blocked for testing"

    def test_signal_modifier_modify_can_transform_signal(self):
        """modify() can transform a signal's properties."""
        from domain.backtest.strategies.modifiers.base import SignalModifier

        class ConfidenceAdjuster(SignalModifier):
            def name(self) -> str:
                return "ConfidenceAdjuster"

            def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
                # Reduce confidence by 10%
                new_confidence = max(0.0, signal.confidence - 0.1)
                return Signal(
                    date=signal.date,
                    fund_code=signal.fund_code,
                    action=signal.action,
                    confidence=new_confidence,
                    reason=f"{signal.reason} (adjusted by {self.name()})",
                    amount=signal.amount,
                    target_weight=signal.target_weight,
                )

            def explain_block(self, signal: Signal, context: SignalContext) -> str:
                return "should not be called for non-blocking modify"

        modifier = ConfidenceAdjuster()
        signal = Signal(
            date=date(2026, 3, 22),
            fund_code="000001",
            action="BUY",
            confidence=0.8,
            reason="test signal",
        )
        context = SignalContext(
            date=date(2026, 3, 22),
            current_nav=1.5,
            indicators={},
        )

        result = modifier.modify(signal, context)
        assert result is not None
        assert result.confidence == pytest.approx(0.7)
        assert "adjusted by ConfidenceAdjuster" in result.reason
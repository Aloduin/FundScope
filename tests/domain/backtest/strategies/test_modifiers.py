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
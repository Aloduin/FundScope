"""Tests for backtest domain models."""
import pytest
from datetime import date
from domain.backtest.models import Signal, ExecutedTrade, BacktestResult


class TestSignal:
    """Tests for Signal dataclass."""

    def test_create_buy_signal(self):
        """Test creating a BUY signal."""
        signal = Signal(
            date=date(2024, 1, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.8,
            reason="价格上穿 20 日均线",
            amount=10000.0,
            target_weight=None,
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
            reason="价格下穿 20 日均线",
            amount=None,
            target_weight=0.0,
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
            reason="月度再平衡",
            amount=None,
            target_weight=0.5,
        )

        assert signal.action == "REBALANCE"
        assert signal.target_weight == 0.5

    def test_signal_reason_required(self):
        """Test that signal reason is required and cannot be empty."""
        with pytest.raises(ValueError, match="reason cannot be empty"):
            Signal(
                date=date(2024, 1, 15),
                fund_code="000001",
                action="BUY",
                confidence=0.5,
                reason="",
                amount=10000.0,
                target_weight=None,
            )

    def test_signal_confidence_range(self):
        """Test confidence must be 0.0~1.0."""
        with pytest.raises(ValueError, match="confidence must be 0.0~1.0"):
            Signal(
                date=date(2024, 1, 15),
                fund_code="000001",
                action="BUY",
                confidence=1.5,
                reason="测试信号",
                amount=10000.0,
                target_weight=None,
            )


class TestExecutedTrade:
    """Tests for ExecutedTrade dataclass."""

    def test_create_executed_trade(self):
        trade = ExecutedTrade(
            date=date(2024, 1, 16),
            fund_code="000001",
            action="BUY",
            amount=10000.0,
            nav=1.25,
            shares=8000.0,
            reason="短期均线上穿长期均线"
        )

        assert trade.action == "BUY"
        assert trade.amount == 10000.0
        assert trade.nav == 1.25
        assert trade.shares == 8000.0


class TestSignalContext:
    """Tests for SignalContext dataclass."""

    def test_signal_context_creation(self):
        from datetime import date
        from domain.backtest.models import SignalContext

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
        from datetime import date
        from domain.backtest.models import SignalContext

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


class TestBacktestResult:
    """Tests for BacktestResult dataclass."""

    def test_create_backtest_result(self):
        """Test creating backtest result."""
        result = BacktestResult(
            strategy_name="DCA",
            fund_code="000001",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            total_return=0.15,
            annualized_return=0.15,
            max_drawdown=0.08,  # Positive value
            sharpe_ratio=1.2,
            win_rate=0.65,
            trade_count=24,
            signals=[],
            equity_curve=[(date(2023, 1, 1), 100000), (date(2023, 12, 31), 115000)],
            executed_trades=[]
        )

        assert result.strategy_name == "DCA"
        assert result.total_return == 0.15
        assert result.sharpe_ratio == 1.2
        assert result.max_drawdown == 0.08
        assert len(result.equity_curve) == 2


class TestBlockedSignalTrace:
    """Tests for BlockedSignalTrace dataclass."""

    def test_blocked_signal_trace_creation(self):
        from domain.backtest.models import Signal, BlockedSignalTrace

        signal = Signal(
            date=date(2023, 6, 15),
            fund_code="000001",
            action="BUY",
            confidence=0.7,
            reason="test buy"
        )
        trace = BlockedSignalTrace(
            original=signal,
            modifier="MAFilter(20, trend_confirm)",
            reason="买入信号被拦截：当前净值低于20日均线"
        )

        assert trace.original == signal
        assert trace.modifier == "MAFilter(20, trend_confirm)"
        assert "买入信号被拦截" in trace.reason

    def test_backtest_result_blocked_signals_default_empty(self):
        from domain.backtest.models import BacktestResult

        result = BacktestResult(
            strategy_name="DCA",
            fund_code="000001",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            total_return=0.10,
            annualized_return=0.10,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            win_rate=0.6,
            trade_count=5,
        )

        assert result.blocked_signals == []

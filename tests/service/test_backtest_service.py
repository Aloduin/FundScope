"""Tests for backtest service."""
import pytest
from datetime import date, timedelta
from unittest.mock import patch
from service.backtest_service import BacktestService


class TestBacktestService:
    """Tests for BacktestService."""

    def setup_method(self):
        self.service = BacktestService()

    def test_service_creates_strategy_by_name(self):
        strategy = self.service._create_strategy("DCA", {"invest_amount": 10000})
        assert strategy.name() == "DCA"

    def test_service_raises_for_unknown_strategy(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            self.service._create_strategy("UnknownStrategy", {})

    def test_run_backtest_with_dca(self):
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
        assert len(result.equity_curve) > 0

    def test_service_creates_composite_strategy(self):
        """Test that service creates DCA + MA Filter composite strategy."""
        service = BacktestService()

        strategy = service._create_strategy("DCA + MA Filter", {
            "invest_amount": 10000,
            "interval_days": 20,
            "ma_window": 20,
        })

        assert strategy.name() == "DCA+MAFilter(20, trend_confirm)"

    def test_run_backtest_returns_blocked_signals_in_result(self):
        """Test that run_backtest returns blocked_signals in result."""
        service = BacktestService()

        nav_history = []
        for i in range(60):
            d = date(2023, 1, 1) + timedelta(days=i)
            nav_history.append({"date": d, "nav": 1.0 - i * 0.01, "acc_nav": 1.0})

        with patch.object(service.datasource, "get_fund_nav_history", return_value=nav_history):
            result = service.run_backtest(
                fund_code="000001",
                strategy_name="DCA + MA Filter",
                strategy_params={
                    "invest_amount": 1000,
                    "interval_days": 20,
                    "ma_window": 20,
                },
                start_date=date(2023, 1, 1),
                end_date=date(2023, 3, 1),
                initial_cash=100000
            )

        assert len(result.blocked_signals) > 0
        assert result.blocked_signals[0].original.action == "BUY"

"""Tests for backtest service."""
import pytest
from datetime import date
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

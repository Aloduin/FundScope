"""Tests for PortfolioMomentumStrategy."""
from datetime import date, timedelta
from domain.backtest.strategies.portfolio_momentum import MomentumConfig, PortfolioMomentumStrategy
from domain.backtest.models import PortfolioSignal


def generate_multi_fund_nav_history(
    fund_codes: list[str],
    start_date: date,
    periods: int = 100,
) -> dict[str, list[dict]]:
    """Generate mock NAV history for multiple funds."""
    nav_histories = {}

    for fund_idx, fund_code in enumerate(fund_codes):
        nav_history = []
        nav = 1.0 + fund_idx * 0.1  # Different starting NAVs

        for i in range(periods):
            current_date = start_date + timedelta(days=i)
            # Fund 0 grows, Fund 1 declines, Fund 2 stable
            if fund_idx == 0:
                nav = nav * (1 + 0.001)
            elif fund_idx == 1:
                nav = nav * (1 - 0.0005)
            else:
                nav = nav * (1 + 0.0001 * ((-1) ** i))

            nav_history.append({
                "date": current_date,
                "nav": nav,
                "acc_nav": nav,
            })

        nav_histories[fund_code] = nav_history

    return nav_histories


class TestMomentumConfig:
    """Tests for MomentumConfig."""

    def test_default_config(self):
        config = MomentumConfig()
        assert config.lookback_periods == 60
        assert config.top_n == 2
        assert config.signal_interval_periods == 20

    def test_custom_config(self):
        config = MomentumConfig(lookback_periods=30, top_n=3, signal_interval_periods=15)
        assert config.lookback_periods == 30
        assert config.top_n == 3
        assert config.signal_interval_periods == 15


class TestPortfolioMomentumStrategy:
    """Tests for PortfolioMomentumStrategy."""

    def test_strategy_name(self):
        strategy = PortfolioMomentumStrategy()
        assert "PortfolioMomentum" in strategy.name()

    def test_no_signals_when_insufficient_data(self):
        strategy = PortfolioMomentumStrategy(config=MomentumConfig(lookback_periods=60))
        nav_histories = generate_multi_fund_nav_history(
            ["000001", "000002"], date(2023, 1, 1), periods=50
        )
        aligned_dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(50)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        assert signals == []

    def test_generates_signals_with_sufficient_data(self):
        strategy = PortfolioMomentumStrategy(config=MomentumConfig(lookback_periods=30, signal_interval_periods=20))
        nav_histories = generate_multi_fund_nav_history(
            ["000001", "000002", "000003"], date(2023, 1, 1), periods=100
        )
        aligned_dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        assert len(signals) > 0
        for sig in signals:
            assert isinstance(sig, PortfolioSignal)
            assert sig.action == "REBALANCE"
            assert sig.target_weights is not None
            assert "CASH" in sig.target_weights

    def test_top_funds_selected_by_momentum(self):
        strategy = PortfolioMomentumStrategy(
            config=MomentumConfig(lookback_periods=30, top_n=1, signal_interval_periods=20)
        )
        nav_histories = generate_multi_fund_nav_history(
            ["000001", "000002", "000003"], date(2023, 1, 1), periods=100
        )
        aligned_dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        # Fund 0 (000001) grows fastest — should be selected
        assert len(signals) > 0
        first_signal = signals[0]
        assert "000001" in first_signal.target_weights

    def test_signal_interval_respected(self):
        config = MomentumConfig(lookback_periods=30, top_n=2, signal_interval_periods=30)
        strategy = PortfolioMomentumStrategy(config=config)
        nav_histories = generate_multi_fund_nav_history(
            ["000001", "000002"], date(2023, 1, 1), periods=100
        )
        aligned_dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        # Signals should be at least 30 trading periods apart
        if len(signals) >= 2:
            dates = [sig.date for sig in signals]
            for i in range(1, len(dates)):
                gap = aligned_dates.index(dates[i]) - aligned_dates.index(dates[i - 1])
                assert gap >= 30

    def test_weights_sum_to_one(self):
        strategy = PortfolioMomentumStrategy(
            config=MomentumConfig(lookback_periods=30, top_n=2, signal_interval_periods=20)
        )
        nav_histories = generate_multi_fund_nav_history(
            ["000001", "000002", "000003"], date(2023, 1, 1), periods=100
        )
        aligned_dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        for sig in signals:
            total = sum(sig.target_weights.values())
            assert abs(total - 1.0) < 1e-9

    def test_no_duplicate_signal_dates(self):
        strategy = PortfolioMomentumStrategy(
            config=MomentumConfig(lookback_periods=30, top_n=2, signal_interval_periods=20)
        )
        nav_histories = generate_multi_fund_nav_history(
            ["000001", "000002"], date(2023, 1, 1), periods=100
        )
        aligned_dates = [date(2023, 1, 1) + timedelta(days=i) for i in range(100)]

        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        dates = [sig.date for sig in signals]
        assert len(dates) == len(set(dates))

"""Tests for DCA (Dollar-Cost Averaging) strategy."""
from datetime import date, timedelta
from domain.backtest.strategies.dca import DCAStrategy


def generate_mock_nav_history(start_date: date, periods: int = 252) -> list[dict]:
    """Generate mock NAV history for testing."""
    nav_history = []
    nav = 1.0

    for i in range(periods):
        current_date = start_date + timedelta(days=i)
        nav = nav * (1 + 0.0005 + (hash(str(i)) % 100 - 50) / 10000)
        nav_history.append({
            "date": current_date,
            "nav": nav,
            "acc_nav": nav
        })

    return nav_history


class TestDCAStrategy:
    """Tests for DCA strategy."""

    def test_dca_strategy_name(self):
        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        assert strategy.name() == "DCA"

    def test_dca_generates_monthly_signals(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=120)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        assert len(signals) >= 5
        assert len(signals) <= 7

    def test_dca_signals_are_buy_actions(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=60)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert signal.action == "BUY"
            assert signal.amount == 10000.0
            assert signal.confidence == 0.5
            assert "定期定额投资" in signal.reason

    def test_dca_invest_amount_from_params(self):
        nav_history = generate_mock_nav_history(date(2023, 1, 1), 60)

        strategy = DCAStrategy(invest_amount=5000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        for signal in signals:
            assert signal.amount == 5000.0

    def test_dca_first_signal_on_start_date(self):
        start_date = date(2023, 1, 1)
        nav_history = generate_mock_nav_history(start_date, periods=45)

        strategy = DCAStrategy(invest_amount=10000, invest_interval_days=20)
        signals = strategy.generate_signals(nav_history)

        assert len(signals) >= 2

        first_signal_date = signals[0].date
        days_since_start = (first_signal_date - start_date).days
        assert 0 <= days_since_start <= 5

        second_interval = (signals[1].date - signals[0].date).days
        assert 15 <= second_interval <= 25

"""Tests for fund metrics calculation."""
from datetime import date, timedelta
from domain.fund.metrics import calculate_metrics
from domain.fund.models import FundMetrics


class TestCalculateMetrics:
    """Tests for calculate_metrics function."""

    def test_empty_nav_history_returns_zero_completeness(self):
        """Test that empty NAV history returns 0 data completeness."""
        metrics = calculate_metrics([], "000001")

        assert metrics.fund_code == "000001"
        assert metrics.data_completeness == 0.0

    def test_insufficient_data_returns_low_completeness(self):
        """Test that insufficient data returns low completeness."""
        nav_history = [
            {"date": date(2024, 1, 1), "nav": 1.0, "acc_nav": 1.0},
        ]
        metrics = calculate_metrics(nav_history, "000001")

        assert metrics.data_completeness < 0.5

    def test_sufficient_data_calculates_all_metrics(self):
        """Test that sufficient data calculates all metrics."""
        # Generate 3 years of mock data
        nav_history = self._generate_mock_nav(years=3)
        metrics = calculate_metrics(nav_history, "000001")

        assert metrics.fund_code == "000001"
        assert metrics.return_1y is not None
        assert metrics.annualized_return is not None
        assert metrics.max_drawdown is not None
        assert metrics.volatility is not None
        assert metrics.sharpe_ratio is not None
        assert metrics.win_rate is not None
        assert metrics.data_completeness > 0.5

    def test_max_drawdown_is_negative(self):
        """Test that max drawdown is negative or zero."""
        nav_history = self._generate_mock_nav(years=2)
        metrics = calculate_metrics(nav_history, "000001")

        assert metrics.max_drawdown <= 0

    def test_volatility_is_positive(self):
        """Test that volatility is positive."""
        nav_history = self._generate_mock_nav(years=2)
        metrics = calculate_metrics(nav_history, "000001")

        assert metrics.volatility > 0

    def test_longer_history_higher_completeness(self):
        """Test that longer history gives higher completeness."""
        # 1 year of data
        nav_1y = self._generate_mock_nav(years=1)
        metrics_1y = calculate_metrics(nav_1y, "000001")

        # 5 years of data
        nav_5y = self._generate_mock_nav(years=5)
        metrics_5y = calculate_metrics(nav_5y, "000001")

        assert metrics_5y.data_completeness >= metrics_1y.data_completeness

    def _generate_mock_nav(self, years: int) -> list[dict]:
        """Generate mock NAV data for testing."""
        import numpy as np
        result = []
        base_nav = 1.0
        current = date.today() - timedelta(days=years * 365)

        while current <= date.today():
            if current.weekday() < 5:  # Weekdays only
                daily_return = np.random.normal(0.0005, 0.02)
                nav = round(base_nav * (1 + daily_return), 4)
                result.append({
                    "date": current,
                    "nav": nav,
                    "acc_nav": nav,
                })
                base_nav = nav
            current += timedelta(days=1)

        return result


class TestPeriodReturn:
    """Tests for period return calculations."""

    def test_positive_return(self):
        """Test positive return calculation with sufficient data."""
        # Need at least 252 trading days for 1-year return, generate 1.5 years to be safe
        nav_history = self._generate_mock_nav_with_return(years=1.5, target_return=0.15)
        metrics = calculate_metrics(nav_history, "000001")

        # With mock randomness, just verify return_1y is calculable
        assert metrics.return_1y is not None
        assert metrics.annualized_return is not None
        # Annualized return should be positive (target is 0.15, but randomness applies)
        assert metrics.annualized_return > 0

    def _generate_mock_nav_with_return(self, years: int, target_return: float) -> list[dict]:
        """Generate mock NAV data with approximately target return."""
        import numpy as np
        result = []
        base_nav = 1.0
        current = date.today() - timedelta(days=years * 365)

        # Calculate daily drift needed to achieve target return
        trading_days = years * 252
        daily_drift = (1 + target_return) ** (1 / trading_days) - 1

        while current <= date.today():
            if current.weekday() < 5:  # Weekdays only
                daily_return = np.random.normal(daily_drift, 0.02)
                nav = round(base_nav * (1 + daily_return), 4)
                result.append({
                    "date": current,
                    "nav": nav,
                    "acc_nav": nav,
                })
                base_nav = nav
            current += timedelta(days=1)

        return result

"""Tests for akshare data source with mock fallback."""
from datetime import date, timedelta
import pytest
from infrastructure.datasource.akshare_source import AkShareDataSource


class TestMockFundInfo:
    """Tests for mock fund basic info."""

    def setup_method(self):
        """Set up test fixtures."""
        self.datasource = AkShareDataSource(use_mock=True)

    def test_mock_fund_info_returns_dict(self):
        """Test mock fund info returns correct structure."""
        result = self.datasource.get_fund_basic_info("000001")

        assert isinstance(result, dict)
        assert result["fund_code"] == "000001"
        assert "fund_name" in result
        assert result["fund_type"] == "混合型"
        assert "manager_name" in result
        assert "manager_tenure" in result
        assert "fund_size" in result
        assert "management_fee" in result
        assert "custodian_fee" in result
        assert "subscription_fee" in result

    def test_mock_fund_info_different_codes(self):
        """Test mock fund info with different fund codes."""
        codes = ["000001", "110022", "005827"]

        for code in codes:
            result = self.datasource.get_fund_basic_info(code)
            assert result["fund_code"] == code
            assert code in result["fund_name"]


class TestMockNavHistory:
    """Tests for mock NAV history."""

    def setup_method(self):
        """Set up test fixtures."""
        self.datasource = AkShareDataSource(use_mock=True)

    def test_mock_nav_history_returns_list(self):
        """Test mock NAV history returns list of dicts."""
        result = self.datasource.get_fund_nav_history("000001")

        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure of first item
        first = result[0]
        assert "date" in first
        assert "nav" in first
        assert "acc_nav" in first
        assert isinstance(first["date"], date)
        assert isinstance(first["nav"], float)

    def test_mock_nav_history_with_date_range(self):
        """Test mock NAV history with custom date range."""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = self.datasource.get_fund_nav_history(
            "000001",
            start_date=start_date,
            end_date=end_date
        )

        assert isinstance(result, list)
        # Should have roughly 20-22 weekdays in 30 days
        assert len(result) >= 15
        assert len(result) <= 22

    def test_mock_nav_history_weekdays_only(self):
        """Test mock NAV history only returns weekdays."""
        result = self.datasource.get_fund_nav_history("000001")

        for item in result:
            # weekday() returns 0-4 for Monday-Friday, 5-6 for Saturday-Sunday
            assert item["date"].weekday() < 5

    def test_mock_nav_history_nav_positive(self):
        """Test mock NAV history has positive values."""
        result = self.datasource.get_fund_nav_history("000001")

        for item in result:
            assert item["nav"] > 0
            assert item["acc_nav"] > 0


class TestRealAkShareApi:
    """Tests for real akshare API integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.datasource = AkShareDataSource(use_mock=False)

    def test_real_fund_info_returns_dict(self):
        """Test real fund info returns correct structure."""
        result = self.datasource.get_fund_basic_info("000001")

        assert isinstance(result, dict)
        assert result["fund_code"] == "000001"
        assert "fund_name" in result
        assert result["fund_name"] != ""  # Should have real name
        assert "fund_type" in result
        assert "management_fee" in result

    def test_real_fund_info_cache(self):
        """Test that fund info is cached."""
        # First call (fetches from API)
        result1 = self.datasource.get_fund_basic_info("000001")
        assert isinstance(result1, dict)

        # Second call (should use cache)
        result2 = self.datasource.get_fund_basic_info("000001")
        assert result1 == result2

    def test_real_nav_history_returns_list(self):
        """Test real NAV history returns list of dicts."""
        result = self.datasource.get_fund_nav_history("000001")

        assert isinstance(result, list)
        assert len(result) > 0

        # Check structure of first item
        first = result[0]
        assert "date" in first
        assert "nav" in first
        assert "acc_nav" in first
        assert isinstance(first["date"], date)
        assert isinstance(first["nav"], float)

    def test_real_nav_history_with_date_range(self):
        """Test real NAV history with custom date range."""
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = self.datasource.get_fund_nav_history(
            "000001",
            start_date=start_date,
            end_date=end_date
        )

        assert isinstance(result, list)
        # Should have at least some data points
        assert len(result) > 0

        # Check all dates are within range
        for item in result:
            assert item["date"] >= start_date
            assert item["date"] <= end_date

    def test_real_nav_history_cache(self):
        """Test that NAV history is cached."""
        # First call (fetches from API)
        result1 = self.datasource.get_fund_nav_history("000001")
        assert isinstance(result1, list)

        # Second call (should use cache)
        result2 = self.datasource.get_fund_nav_history("000001")
        assert result1 == result2


class TestMockFallback:
    """Tests for mock fallback mechanism."""

    def test_use_mock_false_uses_real_api(self):
        """Test that use_mock=False now uses real API (not raises)."""
        datasource = AkShareDataSource(use_mock=False)

        # Real API is now implemented, should NOT raise
        result = datasource.get_fund_basic_info("000001")
        assert isinstance(result, dict)
        assert result["fund_code"] == "000001"

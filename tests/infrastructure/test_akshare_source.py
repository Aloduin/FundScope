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


class TestMockFallback:
    """Tests for mock fallback mechanism."""

    def test_use_mock_false_raises_not_implemented(self):
        """Test that use_mock=False raises NotImplementedError for real API."""
        datasource = AkShareDataSource(use_mock=False)

        # Real API not implemented yet in Task 2
        with pytest.raises(NotImplementedError):
            datasource.get_fund_basic_info("000001")

        with pytest.raises(NotImplementedError):
            datasource.get_fund_nav_history("000001")

"""Tests for datasource module."""
from datetime import date, timedelta
from infrastructure.datasource.abstract import AbstractDataSource
from infrastructure.datasource.akshare_source import AkShareDataSource


class TestAkShareDataSource:
    """Tests for AkShareDataSource mock implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.datasource = AkShareDataSource()

    def test_get_fund_basic_info_returns_dict(self):
        """Test get_fund_basic_info returns correct structure."""
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

    def test_get_fund_nav_history_returns_list(self):
        """Test get_fund_nav_history returns list of dicts."""
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

    def test_get_fund_nav_history_with_date_range(self):
        """Test get_fund_nav_history with custom date range."""
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

    def test_datasource_implements_abstract(self):
        """Test AkShareDataSource implements AbstractDataSource."""
        assert isinstance(self.datasource, AbstractDataSource)

"""Tests for fund service."""
from service.fund_service import FundService
from domain.fund.models import FundInfo, FundMetrics, FundScore


class TestFundService:
    """Tests for FundService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FundService()

    def test_analyze_fund_returns_dict(self):
        """Test analyze_fund returns correct structure."""
        result = self.service.analyze_fund("000001")

        assert isinstance(result, dict)
        assert "info" in result
        assert "metrics" in result
        assert "score" in result
        assert "primary_sector" in result
        assert "sectors" in result
        assert "sector_source" in result

    def test_analyze_fund_info_type(self):
        """Test analyze_fund returns FundInfo."""
        result = self.service.analyze_fund("000001")

        assert isinstance(result["info"], FundInfo)
        assert result["info"].fund_code == "000001"

    def test_analyze_fund_metrics_type(self):
        """Test analyze_fund returns FundMetrics."""
        result = self.service.analyze_fund("000001")

        assert isinstance(result["metrics"], FundMetrics)
        assert result["metrics"].fund_code == "000001"

    def test_analyze_fund_score_type(self):
        """Test analyze_fund returns FundScore."""
        result = self.service.analyze_fund("000001")

        assert isinstance(result["score"], FundScore)
        assert result["score"].fund_code == "000001"
        assert result["score"].total_score > 0

    def test_analyze_fund_data_completeness(self):
        """Test that analyze_fund has data_completeness > 0."""
        result = self.service.analyze_fund("000001")

        # MVP mock data should have some completeness
        assert result["metrics"].data_completeness > 0
        assert result["score"].data_completeness > 0

    def test_sector_classification(self):
        """Test sector classification is performed."""
        result = self.service.analyze_fund("000001")

        # sector_source should be one of the valid values
        assert result["sector_source"] in ["auto", "auto_ambiguous", "auto_unknown"]

    def test_get_fund_info_after_analyze(self):
        """Test get_fund_info returns data after analyze."""
        # First analyze
        self.service.analyze_fund("000002")

        # Then retrieve
        info = self.service.get_fund_info("000002")

        assert info is not None
        assert info.fund_code == "000002"

    def test_get_fund_info_nonexistent(self):
        """Test get_fund_info returns None for nonexistent fund."""
        info = self.service.get_fund_info("999999")

        assert info is None

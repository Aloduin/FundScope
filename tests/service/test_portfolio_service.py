"""Tests for portfolio service."""
from service.portfolio_service import PortfolioService
from domain.portfolio.models import Portfolio


class TestPortfolioService:
    """Tests for PortfolioService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = PortfolioService()

    def test_create_portfolio_returns_portfolio(self):
        """Test create_portfolio returns Portfolio object."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 10000.0},
            {"fund_code": "000002", "fund_name": "基金 2", "amount": 20000.0},
        ]

        portfolio = self.service.create_portfolio("test_001", holdings)

        assert isinstance(portfolio, Portfolio)
        assert portfolio.portfolio_id == "test_001"
        assert len(portfolio.positions) == 2
        assert portfolio.total_amount == 30000.0

    def test_create_portfolio_calculates_weights(self):
        """Test create_portfolio calculates weights correctly."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 10000.0},
            {"fund_code": "000002", "fund_name": "基金 2", "amount": 20000.0},
            {"fund_code": "000003", "fund_name": "基金 3", "amount": 30000.0},
        ]

        portfolio = self.service.create_portfolio("test_002", holdings)

        assert abs(portfolio.positions[0].weight - 1/6) < 0.01
        assert abs(portfolio.positions[1].weight - 1/3) < 0.01
        assert abs(portfolio.positions[2].weight - 0.5) < 0.01

    def test_create_portfolio_calculates_effective_n(self):
        """Test create_portfolio calculates effective_n."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 10000.0},
            {"fund_code": "000002", "fund_name": "基金 2", "amount": 10000.0},
            {"fund_code": "000003", "fund_name": "基金 3", "amount": 10000.0},
        ]

        portfolio = self.service.create_portfolio("test_003", holdings)

        assert abs(portfolio.effective_n - 3.0) < 0.1

    def test_analyze_returns_diagnosis(self):
        """Test analyze returns PortfolioDiagnosis."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 50000.0},
            {"fund_code": "000002", "fund_name": "基金 2", "amount": 50000.0},
        ]

        portfolio = self.service.create_portfolio("test_004", holdings)
        diagnosis = self.service.analyze(portfolio)

        assert diagnosis is not None
        assert hasattr(diagnosis, "concentration_risk")
        assert hasattr(diagnosis, "effective_n")
        assert hasattr(diagnosis, "sector_overlap")
        assert hasattr(diagnosis, "suggestions")

    def test_get_diagnosis_returns_dict(self):
        """Test get_diagnosis returns dict with expected keys."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 100000.0},
        ]

        result = self.service.get_diagnosis(holdings)

        assert isinstance(result, dict)
        assert "concentration_risk" in result
        assert "effective_n" in result
        assert "sector_overlap" in result
        assert "missing_defense" in result
        assert "suggestions" in result

    def test_get_diagnosis_single_position_concentrated(self):
        """Test get_diagnosis detects concentrated portfolio."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 100000.0},
        ]

        result = self.service.get_diagnosis(holdings)

        assert result["concentration_risk"] == 1.0  # Single position
        assert result["effective_n"] == 1.0

    def test_get_diagnosis_suggestions_generated(self):
        """Test get_diagnosis generates suggestions."""
        holdings = [
            {"fund_code": "000001", "fund_name": "基金 1", "amount": 100000.0},
        ]

        result = self.service.get_diagnosis(holdings)

        assert len(result["suggestions"]) > 0

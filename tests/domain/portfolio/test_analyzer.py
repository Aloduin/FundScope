"""Tests for portfolio analyzer."""
from domain.portfolio.models import Portfolio, Position
from domain.portfolio.analyzer import analyze_portfolio, _calculate_hhi


class TestAnalyzePortfolio:
    """Tests for analyze_portfolio function."""

    def test_analyze_concentrated_portfolio(self):
        """Test analysis of concentrated portfolio."""
        portfolio = Portfolio(portfolio_id="test_001")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=90000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=10000.0))

        position_sectors = {
            "000001": ["AI"],
            "000002": ["AI"],
        }

        diagnosis = analyze_portfolio(portfolio, position_sectors)

        assert diagnosis.concentration_risk > 0.5  # High HHI
        assert diagnosis.effective_n < 2.0
        assert "AI" in diagnosis.sector_overlap
        assert diagnosis.missing_defense is True
        assert len(diagnosis.suggestions) > 0

    def test_analyze_diversified_portfolio(self):
        """Test analysis of diversified portfolio."""
        portfolio = Portfolio(portfolio_id="test_002")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=25000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=25000.0))
        portfolio.add_position(Position(fund_code="000003", fund_name="基金 3", amount=25000.0))
        portfolio.add_position(Position(fund_code="000004", fund_name="基金 4", amount=25000.0))

        position_sectors = {
            "000001": ["AI"],
            "000002": ["医疗"],
            "000003": ["消费"],
            "000004": ["债券"],
        }

        diagnosis = analyze_portfolio(portfolio, position_sectors)

        assert diagnosis.concentration_risk < 0.3  # Low HHI
        assert abs(diagnosis.effective_n - 4.0) < 0.1
        assert diagnosis.sector_overlap == []
        assert diagnosis.missing_defense is False  # Has bond

    def test_empty_portfolio(self):
        """Test analysis of empty portfolio."""
        portfolio = Portfolio(portfolio_id="test_empty")

        diagnosis = analyze_portfolio(portfolio, {})

        assert diagnosis.concentration_risk == 0.0
        assert diagnosis.effective_n == 0.0
        assert diagnosis.sector_overlap == []
        assert diagnosis.missing_defense is True

    def test_sector_overlap_detection(self):
        """Test sector overlap detection."""
        portfolio = Portfolio(portfolio_id="test_overlap")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=50000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=50000.0))

        # Both in same sector
        position_sectors = {
            "000001": ["半导体", "AI"],
            "000002": ["半导体", "消费"],
        }

        diagnosis = analyze_portfolio(portfolio, position_sectors)

        assert "半导体" in diagnosis.sector_overlap

    def test_defensive_sector_detection(self):
        """Test defensive sector detection."""
        portfolio = Portfolio(portfolio_id="test_defense")
        portfolio.add_position(Position(fund_code="000001", fund_name="红利基金", amount=100000.0))

        position_sectors = {
            "000001": ["红利低波"],
        }

        diagnosis = analyze_portfolio(portfolio, position_sectors)

        assert diagnosis.missing_defense is False

    def test_suggestions_generated(self):
        """Test that suggestions are generated."""
        portfolio = Portfolio(portfolio_id="test_suggestions")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=100000.0))

        position_sectors = {
            "000001": ["AI"],
        }

        diagnosis = analyze_portfolio(portfolio, position_sectors)

        assert len(diagnosis.suggestions) > 0
        assert all(isinstance(s, str) for s in diagnosis.suggestions)


class TestCalculateHHI:
    """Tests for HHI calculation."""

    def test_hhi_single_position(self):
        """Test HHI with single position."""
        portfolio = Portfolio(portfolio_id="test")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=10000.0))

        hhi = _calculate_hhi(portfolio)

        assert abs(hhi - 1.0) < 0.001  # 100% concentration

    def test_hhi_equal_positions(self):
        """Test HHI with equal positions."""
        portfolio = Portfolio(portfolio_id="test")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=10000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=10000.0))

        hhi = _calculate_hhi(portfolio)

        assert abs(hhi - 0.5) < 0.001  # 0.5^2 + 0.5^2 = 0.5

    def test_hhi_unequal_positions(self):
        """Test HHI with unequal positions."""
        portfolio = Portfolio(portfolio_id="test")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=70000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=30000.0))

        hhi = _calculate_hhi(portfolio)

        # 0.7^2 + 0.3^2 = 0.49 + 0.09 = 0.58
        assert abs(hhi - 0.58) < 0.001

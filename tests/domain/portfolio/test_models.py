"""Tests for domain/portfolio models."""
from datetime import datetime
from domain.portfolio.models import Position, Portfolio, PortfolioDiagnosis


class TestPosition:
    """Tests for Position dataclass."""

    def test_create_position_with_defaults(self):
        """Test creating position with default values."""
        pos = Position(
            fund_code="000001",
            fund_name="测试基金",
            amount=10000.0,
        )

        assert pos.fund_code == "000001"
        assert pos.amount == 10000.0
        assert pos.weight == 0.0
        assert pos.shares is None
        assert pos.cost_nav is None

    def test_recalculate_weight(self):
        """Test weight recalculation."""
        pos = Position(fund_code="000001", fund_name="测试基金", amount=10000.0)

        pos.recalculate_weight(50000.0)

        assert abs(pos.weight - 0.2) < 0.001

    def test_recalculate_weight_zero_total(self):
        """Test weight recalculation with zero total."""
        pos = Position(fund_code="000001", fund_name="测试基金", amount=10000.0)

        pos.recalculate_weight(0)

        assert pos.weight == 0.0


class TestPortfolio:
    """Tests for Portfolio dataclass."""

    def test_create_portfolio_with_defaults(self):
        """Test creating portfolio with default values."""
        portfolio = Portfolio(portfolio_id="test_001")

        assert portfolio.portfolio_id == "test_001"
        assert portfolio.positions == []
        assert portfolio.total_amount == 0.0
        assert portfolio.effective_n == 0.0
        assert portfolio.created_at is not None
        assert portfolio.updated_at is not None

    def test_post_init_initializes_timestamps(self):
        """Test that __post_init__ initializes both timestamps."""
        portfolio = Portfolio(portfolio_id="test_001")

        assert portfolio.created_at is not None
        assert portfolio.updated_at is not None

    def test_add_single_position(self):
        """Test adding a single position."""
        portfolio = Portfolio(portfolio_id="test_001")
        pos = Position(fund_code="000001", fund_name="基金 1", amount=10000.0)

        portfolio.add_position(pos)

        assert len(portfolio.positions) == 1
        assert portfolio.total_amount == 10000.0
        assert portfolio.positions[0].weight == 1.0
        assert portfolio.effective_n == 1.0

    def test_add_multiple_positions(self):
        """Test adding multiple positions."""
        portfolio = Portfolio(portfolio_id="test_001")

        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=10000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=20000.0))
        portfolio.add_position(Position(fund_code="000003", fund_name="基金 3", amount=30000.0))

        assert portfolio.total_amount == 60000.0
        assert abs(portfolio.positions[0].weight - 1/6) < 0.01
        assert abs(portfolio.positions[1].weight - 1/3) < 0.01
        assert abs(portfolio.positions[2].weight - 0.5) < 0.01

    def test_effective_n_calculation(self):
        """Test effective_n calculation."""
        portfolio = Portfolio(portfolio_id="test_001")

        # Equal weights should give effective_n = number of positions
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=10000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=10000.0))
        portfolio.add_position(Position(fund_code="000003", fund_name="基金 3", amount=10000.0))

        assert portfolio.total_amount == 30000.0
        assert abs(portfolio.effective_n - 3.0) < 0.01

    def test_effective_n_concentrated(self):
        """Test effective_n with concentrated portfolio."""
        portfolio = Portfolio(portfolio_id="test_001")

        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=90000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=10000.0))

        # HHI = 0.9^2 + 0.1^2 = 0.82, effective_n = 1/0.82 ≈ 1.22
        assert portfolio.effective_n < 2.0

    def test_remove_position(self):
        """Test removing a position."""
        portfolio = Portfolio(portfolio_id="test_001")
        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=10000.0))
        portfolio.add_position(Position(fund_code="000002", fund_name="基金 2", amount=20000.0))

        portfolio.remove_position("000001")

        assert len(portfolio.positions) == 1
        assert portfolio.positions[0].fund_code == "000002"
        assert portfolio.total_amount == 20000.0

    def test_updated_at_changes_on_modification(self):
        """Test that updated_at changes when portfolio is modified."""
        portfolio = Portfolio(portfolio_id="test_001")
        old_updated = portfolio.updated_at

        portfolio.add_position(Position(fund_code="000001", fund_name="基金 1", amount=10000.0))

        assert portfolio.updated_at > old_updated


class TestPortfolioDiagnosis:
    """Tests for PortfolioDiagnosis dataclass."""

    def test_create_diagnosis(self):
        """Test creating diagnosis."""
        diagnosis = PortfolioDiagnosis(
            concentration_risk=0.5,
            effective_n=2.5,
            sector_overlap=["红利低波"],
            missing_defense=True,
            style_balance={"growth": 0.6, "value": 0.4},
            suggestions=["增加防守资产"],
        )

        assert diagnosis.concentration_risk == 0.5
        assert diagnosis.effective_n == 2.5
        assert "红利低波" in diagnosis.sector_overlap
        assert diagnosis.missing_defense is True

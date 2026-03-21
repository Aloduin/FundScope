"""Tests for domain/fund models."""
from datetime import date, datetime
from domain.fund.models import FundInfo, FundNav, FundMetrics, FundScore


class TestFundInfo:
    """Tests for FundInfo dataclass."""

    def test_create_fund_info_with_required_fields(self):
        """Test creating FundInfo with required fields."""
        fund = FundInfo(
            fund_code="000001",
            fund_name="测试基金 000001",
            fund_type="混合型",
            primary_sector="红利低波",
        )

        assert fund.fund_code == "000001"
        assert fund.fund_name == "测试基金 000001"
        assert fund.fund_type == "混合型"
        assert fund.primary_sector == "红利低波"
        assert fund.sectors == []  # Default empty list
        assert fund.sector_source == "auto"

    def test_create_fund_info_with_all_fields(self):
        """Test creating FundInfo with all fields."""
        fund = FundInfo(
            fund_code="000001",
            fund_name="测试基金 000001",
            fund_type="混合型",
            primary_sector="红利低波",
            sectors=["红利低波", "债券"],
            sector_source="auto_ambiguous",
            manager_name="张三",
            manager_tenure=5.0,
            fund_size=10.0,
            management_fee=0.015,
            custodian_fee=0.0025,
            subscription_fee=0.015,
            data_version="20240101_abc123",
        )

        assert fund.sectors == ["红利低波", "债券"]
        assert fund.manager_name == "张三"
        assert fund.manager_tenure == 5.0
        assert fund.fund_size == 10.0


class TestFundNav:
    """Tests for FundNav dataclass."""

    def test_create_fund_nav(self):
        """Test creating FundNav."""
        nav = FundNav(
            fund_code="000001",
            date=date(2024, 1, 1),
            nav=1.0,
            acc_nav=1.0,
            daily_return=0.0,
        )

        assert nav.fund_code == "000001"
        assert nav.nav == 1.0
        assert nav.daily_return == 0.0


class TestFundMetrics:
    """Tests for FundMetrics dataclass."""

    def test_create_fund_metrics_with_defaults(self):
        """Test creating FundMetrics with default values."""
        metrics = FundMetrics(fund_code="000001")

        assert metrics.fund_code == "000001"
        assert metrics.return_1y is None
        assert metrics.return_3y is None
        assert metrics.return_5y is None
        assert metrics.data_completeness == 0.0

    def test_create_fund_metrics_with_values(self):
        """Test creating FundMetrics with computed values."""
        metrics = FundMetrics(
            fund_code="000001",
            return_1y=0.15,
            return_3y=0.45,
            annualized_return=0.12,
            max_drawdown=-0.20,
            volatility=0.18,
            sharpe_ratio=1.2,
            win_rate=0.65,
            data_completeness=0.8,
        )

        assert metrics.return_1y == 0.15
        assert metrics.sharpe_ratio == 1.2
        assert metrics.data_completeness == 0.8


class TestFundScore:
    """Tests for FundScore dataclass."""

    def test_create_fund_score_with_defaults(self):
        """Test creating FundScore with default values."""
        score = FundScore(fund_code="000001")

        assert score.fund_code == "000001"
        assert score.total_score == 0.0
        assert score.return_score is None
        assert score.missing_dimensions == []

    def test_create_fund_score_with_dimensions(self):
        """Test creating FundScore with dimension scores."""
        score = FundScore(
            fund_code="000001",
            total_score=75.0,
            return_score=80.0,
            risk_score=70.0,
            stability_score=75.0,
            cost_score=60.0,
            size_score=50.0,
            manager_score=55.0,
            data_completeness=1.0,
            missing_dimensions=[],
        )

        assert score.total_score == 75.0
        assert len([s for s in [score.return_score, score.risk_score, score.stability_score,
                                score.cost_score, score.size_score, score.manager_score] if s is not None]) == 6

    def test_missing_dimensions_tracked(self):
        """Test that missing dimensions are tracked."""
        score = FundScore(
            fund_code="000001",
            total_score=60.0,
            return_score=70.0,
            risk_score=50.0,
            manager_score=None,
            size_score=None,
            missing_dimensions=["manager", "size"],
            data_completeness=0.67,
        )

        assert "manager" in score.missing_dimensions
        assert "size" in score.missing_dimensions
        assert score.manager_score is None

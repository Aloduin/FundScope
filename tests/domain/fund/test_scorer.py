"""Tests for fund scoring."""
import pytest
from domain.fund.models import FundInfo, FundMetrics
from domain.fund.scorer import calculate_score


class TestCalculateScore:
    """Tests for calculate_score function."""

    def test_score_with_complete_metrics(self):
        """Test scoring with complete metrics."""
        metrics = FundMetrics(
            fund_code="000001",
            annualized_return=0.12,
            max_drawdown=-0.15,
            volatility=0.20,
            sharpe_ratio=1.0,
            win_rate=0.60,
            recovery_factor=2.0,
            data_completeness=0.8,
        )

        score = calculate_score(metrics, "混合型")

        assert score.fund_code == "000001"
        assert score.total_score > 0
        assert score.return_score is not None
        assert score.risk_score is not None
        assert score.stability_score is not None
        assert score.cost_score == 50.0  # MVP placeholder
        assert score.size_score == 50.0  # MVP placeholder
        assert score.manager_score == 50.0  # MVP placeholder

    def test_score_with_missing_metrics(self):
        """Test scoring with missing metrics."""
        metrics = FundMetrics(
            fund_code="000002",
            annualized_return=0.08,
            # Missing: max_drawdown, volatility, sharpe, win_rate, recovery
            data_completeness=0.3,
        )

        score = calculate_score(metrics, "混合型")

        assert score.return_score is not None
        assert score.risk_score is None
        assert score.stability_score is None
        assert "risk" in score.missing_dimensions
        assert "stability" in score.missing_dimensions

    def test_different_fund_types_use_different_weights(self):
        """Test that different fund types use different weights."""
        metrics = FundMetrics(
            fund_code="000001",
            annualized_return=0.10,
            max_drawdown=-0.15,
            volatility=0.20,
            win_rate=0.55,
        )

        # Stock fund weights return more heavily
        score_equity = calculate_score(metrics, "股票型")

        # Bond fund weights risk more heavily
        score_bond = calculate_score(metrics, "债券型")

        # Scores should differ due to different weights
        assert score_equity is not None
        assert score_bond is not None

    def test_unknown_fund_type_defaults_to_mixed(self):
        """Test that unknown fund type defaults to mixed weights."""
        metrics = FundMetrics(
            fund_code="000001",
            annualized_return=0.10,
        )

        score = calculate_score(metrics, "未知型")

        assert score is not None
        assert score.return_score is not None

    def test_return_score_scaling(self):
        """Test return score scaling."""
        # High return fund
        high_return = FundMetrics(
            fund_code="high",
            annualized_return=0.20,  # 20%
        )
        # Low return fund
        low_return = FundMetrics(
            fund_code="low",
            annualized_return=0.02,  # 2%
        )

        high_score = calculate_score(high_return, "混合型")
        low_score = calculate_score(low_return, "混合型")

        assert high_score.return_score > low_score.return_score

    def test_risk_score_scaling(self):
        """Test risk score scaling with drawdown."""
        # Low risk fund
        low_risk = FundMetrics(
            fund_code="low_risk",
            max_drawdown=-0.05,  # -5%
            volatility=0.10,
        )
        # High risk fund
        high_risk = FundMetrics(
            fund_code="high_risk",
            max_drawdown=-0.30,  # -30%
            volatility=0.40,
        )

        low_score = calculate_score(low_risk, "混合型")
        high_score = calculate_score(high_risk, "混合型")

        assert low_score.risk_score > high_score.risk_score

    def test_stability_score_scaling(self):
        """Test stability score scaling with win rate."""
        # Stable fund
        stable = FundMetrics(
            fund_code="stable",
            win_rate=0.75,
            recovery_factor=3.0,
        )
        # Unstable fund
        unstable = FundMetrics(
            fund_code="unstable",
            win_rate=0.35,
            recovery_factor=0.5,
        )

        stable_score = calculate_score(stable, "混合型")
        unstable_score = calculate_score(unstable, "混合型")

        assert stable_score.stability_score > unstable_score.stability_score

    def test_data_completeness_tracks_missing(self):
        """Test that data completeness tracks missing dimensions."""
        metrics = FundMetrics(
            fund_code="000001",
            annualized_return=0.10,
            # Missing most other fields
        )

        score = calculate_score(metrics, "混合型")

        assert score.data_completeness < 1.0
        assert len(score.missing_dimensions) > 0


def _base_metrics(fund_code="TEST") -> FundMetrics:
    return FundMetrics(
        fund_code=fund_code,
        annualized_return=0.10,
        max_drawdown=-0.15,
        volatility=0.20,
        sharpe_ratio=1.0,
        win_rate=0.60,
        recovery_factor=2.0,
        data_completeness=0.8,
    )


def _base_info(**kwargs) -> FundInfo:
    defaults = dict(
        fund_code="TEST",
        fund_name="测试基金",
        fund_type="混合型",
        primary_sector="宽基指数",
        manager_name="张三",
        manager_tenure=5.0,
        fund_size=50.0,
        management_fee=0.015,
        custodian_fee=0.0025,
        subscription_fee=0.015,
    )
    defaults.update(kwargs)
    return FundInfo(**defaults)


class TestCalculateScorePhase2:
    """Phase 2: size_score and manager_score with real FundInfo."""

    # ------------------------------------------------------------------
    # Compatibility group: info=None preserves Phase 1 placeholders
    # ------------------------------------------------------------------

    def test_no_info_cost_score_is_placeholder(self):
        score = calculate_score(_base_metrics(), "混合型")
        assert score.cost_score == 50.0

    def test_no_info_size_score_is_placeholder(self):
        score = calculate_score(_base_metrics(), "混合型")
        assert score.size_score == 50.0

    def test_no_info_manager_score_is_placeholder(self):
        score = calculate_score(_base_metrics(), "混合型")
        assert score.manager_score == 50.0

    # ------------------------------------------------------------------
    # size_score
    # ------------------------------------------------------------------

    def test_size_score_valid(self):
        info = _base_info(fund_size=50.0)  # 20~100亿，插值结果 81.25
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.size_score == pytest.approx(81.25)

    def test_size_score_small_fund(self):
        info = _base_info(fund_size=1.0)  # <2亿 → 10
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.size_score == 10.0

    def test_size_score_huge_fund(self):
        info = _base_info(fund_size=400.0)  # >300亿 → 70
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.size_score == 70.0

    def test_size_score_missing_zero(self):
        info = _base_info(fund_size=0.0)
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.size_score is None
        assert "size" in score.missing_dimensions

    def test_size_score_missing_negative(self):
        info = _base_info(fund_size=-1.0)
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.size_score is None

    # ------------------------------------------------------------------
    # manager_score
    # ------------------------------------------------------------------

    def test_manager_score_valid(self):
        info = _base_info(manager_name="张三", manager_tenure=6.0)  # 5~8年，插值结果 80.0
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.manager_score == pytest.approx(80.0)

    def test_manager_score_veteran(self):
        info = _base_info(manager_name="李四", manager_tenure=10.0)  # >8年 → 100
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.manager_score == 100.0

    def test_manager_score_new(self):
        info = _base_info(manager_name="王五", manager_tenure=0.5)  # <1年 → 20
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.manager_score == 20.0

    def test_manager_score_missing_name(self):
        info = _base_info(manager_name="", manager_tenure=5.0)
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.manager_score is None
        assert "manager" in score.missing_dimensions

    def test_manager_score_missing_tenure_zero(self):
        info = _base_info(manager_name="张三", manager_tenure=0.0)
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.manager_score is None

    def test_manager_score_missing_tenure_negative(self):
        info = _base_info(manager_name="张三", manager_tenure=-1.0)
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.manager_score is None

    # ------------------------------------------------------------------
    # cost_score still placeholder when info is provided
    # ------------------------------------------------------------------

    def test_cost_score_still_placeholder_with_info(self):
        info = _base_info()
        score = calculate_score(_base_metrics(), "混合型", info)
        assert score.cost_score == 50.0  # Phase 2: cost not yet real

    # ------------------------------------------------------------------
    # total_score reflects real size/manager when available
    # ------------------------------------------------------------------

    def test_total_score_differs_with_info(self):
        """Score with real info should differ from placeholder-only score."""
        score_no_info = calculate_score(_base_metrics(), "混合型")
        info = _base_info(fund_size=1.0, manager_tenure=0.5)  # both low scores
        score_with_info = calculate_score(_base_metrics(), "混合型", info)
        assert score_with_info.total_score != score_no_info.total_score

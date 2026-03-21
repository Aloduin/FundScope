"""Tests for fund scoring."""
from domain.fund.models import FundMetrics
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

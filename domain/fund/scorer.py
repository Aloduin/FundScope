"""Fund multi-dimensional scoring.

MVP Phase 1: Uses calculate_score(metrics, fund_type) with placeholder scores
for cost/size/manager dimensions.
Phase 2: Upgrade to calculate_score(info, metrics) for full integration.
"""
from shared.config import SCORE_WEIGHTS_BY_TYPE, DEFAULT_FUND_TYPE
from shared.logger import get_logger
from domain.fund.models import FundMetrics, FundScore

logger = get_logger(__name__)

# Minimum data completeness threshold for scoring
MIN_DATA_COMPLETENESS = 0.5


def calculate_score(metrics: FundMetrics, fund_type: str) -> FundScore:
    """Calculate fund comprehensive score.

    MVP Phase 1: Simple scoring using metrics only.
    - Return, risk, stability dimensions use computed metrics
    - Cost, size, manager dimensions use placeholder scores (50/100)

    Phase 2: Upgrade to use FundInfo for cost/size/manager dimensions.

    Args:
        metrics: Fund performance metrics
        fund_type: Fund type (股票型/混合型/债券型/指数型)

    Returns:
        FundScore with dimension scores and total score
    """
    # Map fund type to weight key
    type_mapping = {"股票型": "equity", "债券型": "bond", "指数型": "index"}
    weight_key = type_mapping.get(fund_type, DEFAULT_FUND_TYPE)
    weights = SCORE_WEIGHTS_BY_TYPE.get(weight_key, SCORE_WEIGHTS_BY_TYPE[DEFAULT_FUND_TYPE])

    # Calculate dimension scores (0-100 scale)
    return_score = _calculate_return_score(metrics)
    risk_score = _calculate_risk_score(metrics)
    stability_score = _calculate_stability_score(metrics)

    # MVP Phase 1 placeholders - Phase 2 will use FundInfo data
    cost_score = 50.0  # Placeholder: use actual fee data in Phase 2
    size_score = 50.0  # Placeholder: use actual fund size in Phase 2
    manager_score = 50.0  # Placeholder: use manager tenure in Phase 2

    # Track missing dimensions
    missing_dimensions = []
    if return_score is None:
        missing_dimensions.append("return")
    if risk_score is None:
        missing_dimensions.append("risk")
    if stability_score is None:
        missing_dimensions.append("stability")

    # Normalize scores to 0-100
    scores = {
        "return": return_score,
        "risk": risk_score,
        "stability": stability_score,
        "cost": cost_score,
        "size": size_score,
        "manager": manager_score,
    }

    # Calculate weighted total with re-normalization for missing dimensions
    total_score = 0.0
    total_weight = 0.0

    for dim, score in scores.items():
        weight = weights.get(dim, 0)
        if score is not None:
            total_score += score * weight
            total_weight += weight
        else:
            missing_dimensions.append(dim)

    # Re-normalize weights if some dimensions are missing
    if total_weight > 0 and total_weight < 1.0:
        total_score = total_score / total_weight

    # Data completeness based on non-missing dimensions
    data_completeness = 1.0 - (len(missing_dimensions) / 6)

    return FundScore(
        fund_code=metrics.fund_code,
        total_score=round(total_score, 2),
        return_score=round(return_score, 2) if return_score else None,
        risk_score=round(risk_score, 2) if risk_score else None,
        stability_score=round(stability_score, 2) if stability_score else None,
        cost_score=round(cost_score, 2),
        size_score=round(size_score, 2),
        manager_score=round(manager_score, 2),
        data_completeness=round(data_completeness, 2),
        missing_dimensions=missing_dimensions,
    )


def _calculate_return_score(metrics: FundMetrics) -> float | None:
    """Calculate return dimension score (0-100).

    Scoring:
    - 80-100: Excellent (>15% annualized)
    - 60-79: Good (10-15%)
    - 40-59: Average (5-10%)
    - 20-39: Poor (0-5%)
    - 0-19: Very poor (negative)
    """
    if metrics.annualized_return is None:
        return None

    annualized = metrics.annualized_return * 100  # Convert to percentage

    if annualized > 15:
        return min(100, 80 + (annualized - 15) * 2)
    elif annualized > 10:
        return 60 + (annualized - 10) * 4
    elif annualized > 5:
        return 40 + (annualized - 5) * 4
    elif annualized > 0:
        return 20 + annualized * 4
    else:
        return max(0, 20 + annualized * 4)


def _calculate_risk_score(metrics: FundMetrics) -> float | None:
    """Calculate risk dimension score (0-100).

    Scoring based on max drawdown and volatility:
    - Lower drawdown = higher score
    - Lower volatility = higher score
    """
    if metrics.max_drawdown is None or metrics.volatility is None:
        return None

    # Drawdown score (0-50)
    dd = abs(metrics.max_drawdown) * 100  # Convert to percentage
    if dd < 10:
        dd_score = 50
    elif dd < 20:
        dd_score = 40 - (dd - 10)
    elif dd < 30:
        dd_score = 30 - (dd - 20) * 1.5
    else:
        dd_score = max(0, 15 - (dd - 30) * 0.5)

    # Volatility score (0-50)
    vol = metrics.volatility * 100  # Convert to percentage
    if vol < 15:
        vol_score = 50
    elif vol < 25:
        vol_score = 40 - (vol - 15)
    elif vol < 35:
        vol_score = 30 - (vol - 25) * 1.5
    else:
        vol_score = max(0, 15 - (vol - 35) * 0.5)

    return dd_score + vol_score


def _calculate_stability_score(metrics: FundMetrics) -> float | None:
    """Calculate stability dimension score (0-100).

    Scoring based on win rate and recovery factor:
    - Higher win rate = more stable
    - Higher recovery factor = better recovery ability
    """
    if metrics.win_rate is None:
        return None

    # Win rate score (0-70)
    win_rate = metrics.win_rate * 100  # Convert to percentage
    if win_rate > 70:
        wr_score = 70
    elif win_rate > 50:
        wr_score = 50 + (win_rate - 50)
    else:
        wr_score = win_rate

    # Recovery factor bonus (0-30)
    recovery = metrics.recovery_factor
    if recovery is None:
        recovery_score = 0
    elif recovery > 3:
        recovery_score = 30
    elif recovery > 2:
        recovery_score = 20 + (recovery - 2) * 10
    elif recovery > 1:
        recovery_score = 10 + (recovery - 1) * 10
    else:
        recovery_score = max(0, recovery * 10)

    return wr_score + recovery_score

"""Fund multi-dimensional scoring.

MVP Phase 1: Uses calculate_score(metrics, fund_type) with placeholder scores
for cost/size/manager dimensions.
Phase 2: Upgrade to calculate_score(info, metrics) for full integration.
"""
from shared.config import SCORE_WEIGHTS_BY_TYPE, DEFAULT_FUND_TYPE
from shared.logger import get_logger
from domain.fund.models import FundInfo, FundMetrics, FundScore

logger = get_logger(__name__)

# Minimum data completeness threshold for scoring
MIN_DATA_COMPLETENESS = 0.5


def calculate_score(
    metrics: FundMetrics,
    fund_type: str,
    info: FundInfo | None = None,  # Phase 2: pass FundInfo for real size/manager scores
) -> FundScore:
    """Calculate fund comprehensive score.

    Phase 2 behaviour:
    - info=None: all info-dependent dimensions (cost/size/manager) use 50.0 placeholder
      (backwards-compatible with Phase 1 callers and existing tests)
    - info provided, field available: real score computed
    - info provided, field missing (<=0 / empty): None returned → triggers downweight

    TODO(Phase 3): remove info=None path; require info everywhere.

    Args:
        metrics: Fund performance metrics
        fund_type: Fund type (股票型/混合型/债券型/指数型)
        info: Optional FundInfo for cost/size/manager scoring

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

    # cost_score: fee data not yet reliably parsed from akshare → keep placeholder
    cost_score = 50.0

    # size_score and manager_score: use real data when info is available
    if info is None:
        # Backwards-compatible path: preserve Phase 1 placeholder behaviour
        size_score: float | None = 50.0
        manager_score: float | None = 50.0
    else:
        size_score = (
            _score_size(info.fund_size) if info.fund_size > 0 else None
        )
        manager_score = (
            _score_manager(info.manager_tenure)
            if info.manager_name and info.manager_tenure > 0
            else None
        )

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
        size_score=round(size_score, 2) if size_score is not None else None,
        manager_score=round(manager_score, 2) if manager_score is not None else None,
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


def _score_size(fund_size: float) -> float:
    """Score fund size (亿元) on 0-100 scale.

    Optimal range is 20-100 亿; very small or very large funds are penalised.
    Breakpoints: <2→10, 2-5→40, 5-20→70, 20-100→100, 100-300→85, >300→70.
    Values between breakpoints are linearly interpolated.
    """
    breakpoints = [
        (0, 10),
        (2, 10),
        (5, 40),
        (20, 70),
        (100, 100),
        (300, 85),
    ]
    if fund_size > 300:
        return 70.0
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if fund_size <= x1:
            if x1 == x0:
                return float(y1)
            t = (fund_size - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 70.0


def _score_manager(tenure_years: float) -> float:
    """Score manager tenure (years) on 0-100 scale.

    Breakpoints: <1→20, 1-3→50, 3-5→75, 5-8→90, >8→100.
    Values between breakpoints are linearly interpolated.
    """
    breakpoints = [
        (0, 20),
        (1, 20),
        (3, 50),
        (5, 75),
        (8, 90),
    ]
    if tenure_years > 8:
        return 100.0
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if tenure_years <= x1:
            if x1 == x0:
                return float(y1)
            t = (tenure_years - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)
    return 100.0


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

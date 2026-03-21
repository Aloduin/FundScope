"""Portfolio analysis and diagnosis.

Pure calculation logic - no IO.
"""
from typing import Literal
from shared.logger import get_logger
from domain.portfolio.models import Portfolio, Position, PortfolioDiagnosis

logger = get_logger(__name__)

# Defensive sectors
DEFENSIVE_SECTORS = {"债券", "红利低波", "宽基指数"}


def analyze_portfolio(portfolio: Portfolio, position_sectors: dict[str, list[str]]) -> PortfolioDiagnosis:
    """Analyze portfolio and generate diagnosis.

    Args:
        portfolio: Portfolio with positions
        position_sectors: Dict mapping fund_code to list of sectors

    Returns:
        PortfolioDiagnosis with analysis results
    """
    # 1. Concentration risk (HHI index)
    hhi = _calculate_hhi(portfolio)

    # 2. Effective n (already calculated in portfolio)
    effective_n = portfolio.effective_n

    # 3. Sector overlap
    sector_overlap = _find_sector_overlap(portfolio, position_sectors)

    # 4. Missing defense check
    missing_defense = _check_missing_defense(portfolio, position_sectors)

    # 5. Style balance (simplified)
    style_balance = _calculate_style_balance(portfolio, position_sectors)

    # 6. Generate suggestions
    suggestions = _generate_suggestions(
        hhi=hhi,
        effective_n=effective_n,
        sector_overlap=sector_overlap,
        missing_defense=missing_defense,
        style_balance=style_balance,
    )

    return PortfolioDiagnosis(
        concentration_risk=hhi,
        effective_n=effective_n,
        sector_overlap=sector_overlap,
        missing_defense=missing_defense,
        style_balance=style_balance,
        suggestions=suggestions,
    )


def _calculate_hhi(portfolio: Portfolio) -> float:
    """Calculate Herfindahl-Hirschman Index (HHI).

    HHI = sum(weight^2) for all positions
    Range: 0 to 1 (higher = more concentrated)
    """
    if not portfolio.positions:
        return 0.0

    return sum(p.weight ** 2 for p in portfolio.positions if p.weight > 0)


def _find_sector_overlap(portfolio: Portfolio, position_sectors: dict[str, list[str]]) -> list[str]:
    """Find overlapping sectors across positions.

    Returns list of sectors that appear in multiple positions.
    """
    sector_count: dict[str, int] = {}

    for position in portfolio.positions:
        sectors = position_sectors.get(position.fund_code, [])
        for sector in sectors:
            sector_count[sector] = sector_count.get(sector, 0) + 1

    # Return sectors that appear in 2+ positions
    return [sector for sector, count in sector_count.items() if count >= 2]


def _check_missing_defense(portfolio: Portfolio, position_sectors: dict[str, list[str]]) -> bool:
    """Check if portfolio lacks defensive assets.

    Returns True if no defensive sector exposure.
    """
    for position in portfolio.positions:
        sectors = position_sectors.get(position.fund_code, [])
        for sector in sectors:
            if sector in DEFENSIVE_SECTORS:
                return False

    return True


def _calculate_style_balance(portfolio: Portfolio, position_sectors: dict[str, list[str]]) -> dict[str, float]:
    """Calculate style balance across sectors.

    Returns dict of sector -> weight.
    """
    sector_weights: dict[str, float] = {}

    for position in portfolio.positions:
        sectors = position_sectors.get(position.fund_code, [])
        weight_per_sector = position.weight / len(sectors) if sectors else 0

        for sector in sectors:
            sector_weights[sector] = sector_weights.get(sector, 0) + weight_per_sector

    return sector_weights


def _generate_suggestions(
    hhi: float,
    effective_n: float,
    sector_overlap: list[str],
    missing_defense: bool,
    style_balance: dict[str, float],
) -> list[str]:
    """Generate optimization suggestions based on analysis."""
    suggestions = []

    # Concentration suggestion
    if hhi > 0.5:
        suggestions.append("持仓集中度过高，建议分散投资")
    elif hhi > 0.3:
        suggestions.append("持仓集中度中等，可考虑适度分散")

    # Effective n suggestion
    if effective_n < 2:
        suggestions.append(f"有效持仓数仅 {effective_n:.1f}，建议增加持仓数量或均衡配置")
    elif effective_n < 4:
        suggestions.append(f"有效持仓数 {effective_n:.1f}，可继续优化分散度")

    # Sector overlap suggestion
    if sector_overlap:
        suggestions.append(f"赛道重叠：{', '.join(sector_overlap)}，建议减少重复赛道配置")

    # Defense suggestion
    if missing_defense:
        suggestions.append("缺乏防守资产，建议配置债券或红利低波类基金")

    # Style balance suggestion
    if style_balance:
        max_sector = max(style_balance.items(), key=lambda x: x[1])
        if max_sector[1] > 0.6:
            suggestions.append(f"{max_sector[0]}赛道占比过高 ({max_sector[1]:.0%})，建议适度降低")

    if not suggestions:
        suggestions.append("持仓结构良好，继续保持")

    return suggestions

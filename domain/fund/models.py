"""Domain models for FundScope fund subdomain."""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


@dataclass
class FundInfo:
    """Fund basic information.

    Attributes:
        fund_code: Fund code (e.g., '000001')
        fund_name: Fund name
        fund_type: Fund type (股票型/混合型/债券型/指数型)
        primary_sector: Primary sector classification
        sectors: All sector labels (multi-label support)
        sector_source: Classification source ('auto' | 'auto_ambiguous' | 'auto_unknown' | 'manual')
        manager_name: Fund manager name
        manager_tenure: Manager tenure in years
        fund_size: Fund size in 亿元
        management_fee: Management fee rate
        custodian_fee: Custodian fee rate
        subscription_fee: Subscription fee rate
        data_version: Data version string (YYYYMMDD_<hash>)
    """
    fund_code: str
    fund_name: str
    fund_type: str
    primary_sector: str
    sectors: list[str] = field(default_factory=list)
    sector_source: str = "auto"
    manager_name: str = ""
    manager_tenure: float = 0.0
    fund_size: float = 0.0
    management_fee: float = 0.0
    custodian_fee: float = 0.0
    subscription_fee: float = 0.0
    data_version: str = ""


@dataclass
class FundNav:
    """Fund NAV (Net Asset Value) record.

    Attributes:
        fund_code: Fund code
        date: NAV date
        nav: Unit net value (单位净值)
        acc_nav: Accumulated net value (累计净值)
        daily_return: Daily return rate
    """
    fund_code: str
    date: date
    nav: float
    acc_nav: float
    daily_return: float = 0.0


@dataclass
class FundMetrics:
    """Fund performance metrics.

    Attributes:
        fund_code: Fund code
        return_1y: 1-year return (or None if not enough data)
        return_3y: 3-year return (or None if not enough data)
        return_5y: 5-year return (or None if not enough data)
        annualized_return: Annualized return
        max_drawdown: Maximum drawdown (negative value)
        volatility: Annualized volatility
        sharpe_ratio: Sharpe ratio
        win_rate: Monthly win rate
        recovery_factor: Drawdown recovery ability
        data_completeness: Data completeness (0.0~1.0), computed as computable_metrics/total_metrics
    """
    fund_code: str
    return_1y: float | None = None
    return_3y: float | None = None
    return_5y: float | None = None
    annualized_return: float | None = None
    max_drawdown: float | None = None
    volatility: float | None = None
    sharpe_ratio: float | None = None
    win_rate: float | None = None
    recovery_factor: float | None = None
    data_completeness: float = 0.0


@dataclass
class FundScore:
    """Fund comprehensive score.

    Attributes:
        fund_code: Fund code
        total_score: Total weighted score
        return_score: Return dimension score (or None)
        risk_score: Risk dimension score (or None)
        stability_score: Stability dimension score (or None)
        cost_score: Cost dimension score (or None)
        size_score: Size dimension score (or None)
        manager_score: Manager dimension score (or None)
        data_completeness: Score credibility (0.0~1.0)
        missing_dimensions: List of missing dimension names
    """
    fund_code: str
    total_score: float = 0.0
    return_score: float | None = None
    risk_score: float | None = None
    stability_score: float | None = None
    cost_score: float | None = None
    size_score: float | None = None
    manager_score: float | None = None
    data_completeness: float = 0.0
    missing_dimensions: list[str] = field(default_factory=list)

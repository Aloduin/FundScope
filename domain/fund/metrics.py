"""Fund performance metrics calculation.

All calculations are pure functions - no IO.
"""
import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import Literal
from shared.logger import get_logger
from domain.fund.models import FundMetrics

logger = get_logger(__name__)

# Risk-free rate for Sharpe ratio (annualized)
RISK_FREE_RATE = 0.03


def calculate_metrics(nav_history: list[dict], fund_code: str) -> FundMetrics:
    """Calculate fund performance metrics from NAV history.

    Args:
        nav_history: List of dicts with keys [date, nav, acc_nav]
        fund_code: Fund code

    Returns:
        FundMetrics with computed values

    Metrics calculated:
    - return_1y, return_3y, return_5y (or None if not enough data)
    - annualized_return
    - max_drawdown
    - volatility
    - sharpe_ratio
    - win_rate (monthly)
    - recovery_factor
    - data_completeness (computable_metrics / total_metrics)
    """
    if not nav_history or len(nav_history) < 2:
        logger.warning(f"Not enough NAV data for {fund_code}")
        return FundMetrics(fund_code=fund_code, data_completeness=0.0)

    # Convert to DataFrame for easier calculation
    df = pd.DataFrame(nav_history)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)

    # Calculate daily returns if not provided
    if 'daily_return' not in df.columns:
        df['daily_return'] = df['nav'].pct_change()

    # Calculate metrics
    metrics = {}

    # 1. Period returns
    metrics['return_1y'] = _calculate_period_return(df, years=1)
    metrics['return_3y'] = _calculate_period_return(df, years=3)
    metrics['return_5y'] = _calculate_period_return(df, years=5)

    # 2. Annualized return
    metrics['annualized_return'] = _calculate_annualized_return(df)

    # 3. Maximum drawdown
    metrics['max_drawdown'] = _calculate_max_drawdown(df)

    # 4. Volatility (annualized)
    metrics['volatility'] = _calculate_volatility(df)

    # 5. Sharpe ratio
    metrics['sharpe_ratio'] = _calculate_sharpe_ratio(df)

    # 6. Win rate (monthly)
    metrics['win_rate'] = _calculate_win_rate(df)

    # 7. Recovery factor
    metrics['recovery_factor'] = _calculate_recovery_factor(df)

    # Calculate data completeness
    total_metrics = 8  # return_1y/3y/5y, annualized, dd, vol, sharpe, win_rate, recovery
    computable_metrics = sum(1 for v in metrics.values() if v is not None)
    metrics['data_completeness'] = computable_metrics / total_metrics

    return FundMetrics(fund_code=fund_code, **metrics)


def _calculate_period_return(df: pd.DataFrame, years: int) -> float | None:
    """Calculate return over specified period."""
    if len(df) < years * 252:  # Approximate trading days
        return None

    start_idx = 0
    end_idx = len(df) - 1

    # Find start point (approximately 'years' ago)
    trading_days_per_year = 252
    start_date = df.iloc[end_idx]['date'] - pd.Timedelta(days=years * 365)
    start_points = df[df['date'] <= start_date]

    if len(start_points) == 0:
        return None

    start_idx = start_points.index[-1]
    start_nav = df.loc[start_idx, 'nav']
    end_nav = df.iloc[end_idx]['nav']

    return (end_nav / start_nav) - 1


def _calculate_annualized_return(df: pd.DataFrame) -> float | None:
    """Calculate annualized return."""
    if len(df) < 2:
        return None

    start_nav = df.iloc[0]['nav']
    end_nav = df.iloc[-1]['nav']
    days = (df.iloc[-1]['date'] - df.iloc[0]['date']).days

    if days <= 0:
        return None

    years = days / 365.0
    if years <= 0:
        return None

    total_return = (end_nav / start_nav) - 1
    return (1 + total_return) ** (1 / years) - 1


def _calculate_max_drawdown(df: pd.DataFrame) -> float | None:
    """Calculate maximum drawdown (as negative value)."""
    if len(df) < 2:
        return None

    nav = df['nav'].values
    peak = nav[0]
    max_dd = 0.0

    for nav_value in nav:
        if nav_value > peak:
            peak = nav_value
        drawdown = (nav_value - peak) / peak
        if drawdown < max_dd:
            max_dd = drawdown

    return max_dd


def _calculate_volatility(df: pd.DataFrame) -> float | None:
    """Calculate annualized volatility."""
    if 'daily_return' not in df.columns or len(df) < 2:
        return None

    daily_returns = df['daily_return'].dropna()
    if len(daily_returns) < 2:
        return None

    daily_vol = daily_returns.std()
    return daily_vol * np.sqrt(252)  # Annualized


def _calculate_sharpe_ratio(df: pd.DataFrame) -> float | None:
    """Calculate Sharpe ratio."""
    annualized_return = _calculate_annualized_return(df)
    volatility = _calculate_volatility(df)

    if annualized_return is None or volatility is None or volatility == 0:
        return None

    return (annualized_return - RISK_FREE_RATE) / volatility


def _calculate_win_rate(df: pd.DataFrame) -> float | None:
    """Calculate monthly win rate."""
    if len(df) < 2:
        return None

    # Resample to monthly
    df_monthly = df.copy()
    df_monthly.set_index('date', inplace=True)
    monthly_nav = df_monthly['nav'].resample('ME').last()

    if len(monthly_nav) < 2:
        return None

    monthly_returns = monthly_nav.pct_change().dropna()
    winning_months = (monthly_returns > 0).sum()
    total_months = len(monthly_returns)

    return winning_months / total_months if total_months > 0 else None


def _calculate_recovery_factor(df: pd.DataFrame) -> float | None:
    """Calculate recovery factor (annualized return / max drawdown)."""
    annualized_return = _calculate_annualized_return(df)
    max_drawdown = _calculate_max_drawdown(df)

    if annualized_return is None or max_drawdown is None or max_drawdown == 0:
        return None

    return annualized_return / abs(max_drawdown)

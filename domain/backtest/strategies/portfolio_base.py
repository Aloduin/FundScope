"""Abstract portfolio strategy interface for FundScope backtest."""
from abc import ABC, abstractmethod
from datetime import date
from domain.backtest.models import PortfolioSignal


class PortfolioStrategy(ABC):
    """Abstract base class for portfolio-level trading strategies.

    Unlike Strategy (single-fund), PortfolioStrategy operates across
    multiple funds simultaneously and generates portfolio-level signals.
    """

    @abstractmethod
    def name(self) -> str:
        """Get strategy name."""
        raise NotImplementedError

    @abstractmethod
    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date],
    ) -> list[PortfolioSignal]:
        """Generate portfolio-level signals from multi-fund NAV histories.

        Args:
            nav_histories: Mapping of fund_code -> list of NAV records,
                           each record has at least 'date' and 'nav' keys.
            aligned_dates: Sorted list of dates present across all funds.

        Returns:
            List of PortfolioSignal ordered by date.
        """
        raise NotImplementedError

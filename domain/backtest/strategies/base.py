"""Abstract strategy interface for FundScope backtest."""
from abc import ABC, abstractmethod
from domain.backtest.models import Signal


class Strategy(ABC):
    """Abstract base class for all trading strategies."""

    @abstractmethod
    def name(self) -> str:
        """Get strategy name."""
        raise NotImplementedError

    @abstractmethod
    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        """Generate trading signals from NAV history."""
        raise NotImplementedError

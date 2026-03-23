"""Abstract base class for rebalance policies."""
from abc import ABC, abstractmethod
from domain.backtest.models import PortfolioSignal, SignalContext


class RebalancePolicy(ABC):
    """Signal filter for portfolio-level rebalance signals.

    Determines whether a PortfolioSignal should be executed given
    current positions and market context.
    """

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        """决定是否执行组合级再平衡信号。

        Returns:
            PortfolioSignal if signal should be executed,
            None if signal should be blocked.
        """
        raise NotImplementedError

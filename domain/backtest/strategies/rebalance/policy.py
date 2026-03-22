"""Abstract base class for rebalance policies."""
from abc import ABC, abstractmethod
from domain.backtest.models import Signal, SignalContext


class RebalancePolicy(ABC):
    """Phase 3A: interface only, not integrated into main backtest flow."""

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def rebalance(
        self,
        current_positions: list[dict],
        target_weights: dict[str, float],
        context: SignalContext
    ) -> list[Signal]:
        raise NotImplementedError
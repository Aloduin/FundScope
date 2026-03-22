"""Threshold-based rebalance policy."""
from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.rebalance.policy import RebalancePolicy


class ThresholdRebalancePolicy(RebalancePolicy):
    """Stub only for Phase 3A."""

    def __init__(self, threshold: float = 0.05, mode: str = "threshold"):
        self.threshold = threshold
        self.mode = mode
        if mode != "threshold":
            raise NotImplementedError(f"mode={mode} not supported in Phase 3A")

    def name(self) -> str:
        return f"ThresholdRebalance({self.threshold:.0%})"

    def rebalance(
        self,
        current_positions: list[dict],
        target_weights: dict[str, float],
        context: SignalContext
    ) -> list[Signal]:
        return []
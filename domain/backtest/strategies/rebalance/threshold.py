"""Threshold-based rebalance policy."""
from domain.backtest.models import PortfolioSignal, SignalContext
from domain.backtest.strategies.rebalance.policy import RebalancePolicy


class ThresholdRebalancePolicy(RebalancePolicy):
    """Passes a rebalance signal only when any weight deviates >= threshold."""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold

    def name(self) -> str:
        return f"ThresholdRebalance({self.threshold:.0%})"

    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        current = {p["fund_code"]: p["weight"] for p in current_positions}
        all_codes = set(signal.target_weights) | set(current)
        max_deviation = max(
            abs(signal.target_weights.get(code, 0.0) - current.get(code, 0.0))
            for code in all_codes
        )
        return signal if max_deviation >= self.threshold else None

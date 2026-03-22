"""Composite strategy that combines a primary strategy with a signal modifier."""
import dataclasses

from domain.backtest.models import Signal, SignalContext, BlockedSignalTrace
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.modifiers.base import SignalModifier
from domain.backtest.strategies.modifiers.ma_filter import MAFilter
from domain.backtest.strategies.rebalance.policy import RebalancePolicy


class CompositeStrategy(Strategy):
    """Phase 3A: only supports primary strategy + SignalModifier."""

    def __init__(
        self,
        primary_strategy: Strategy,
        modifier: SignalModifier | None = None
    ):
        self.primary_strategy = primary_strategy
        self.modifier = modifier
        self._blocked_signals: list[BlockedSignalTrace] = []

        if isinstance(modifier, RebalancePolicy):
            raise NotImplementedError(
                "RebalancePolicy is not supported in Phase 3A. "
                "Use SignalModifier (e.g., MAFilter) instead."
            )

    def name(self) -> str:
        if self.modifier is None:
            return self.primary_strategy.name()
        return f"{self.primary_strategy.name()}+{self.modifier.name()}"

    def get_blocked_signals(self) -> list[BlockedSignalTrace]:
        return self._blocked_signals.copy()

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        self._blocked_signals = []

        if not nav_history:
            return []

        base_signals = self.primary_strategy.generate_signals(nav_history)

        if self.modifier is None:
            return base_signals

        final_signals = []
        for signal in base_signals:
            context = self._build_context(signal.date, nav_history)
            result = self.modifier.modify(signal, context)
            if result is None:
                self._blocked_signals.append(
                BlockedSignalTrace(
                    original=dataclasses.replace(signal),
                    modifier=self.modifier.name(),
                    reason=self.modifier.explain_block(signal, context),
                )
            )
            else:
                final_signals.append(result)

        return final_signals

    def _build_context(self, as_of_date, nav_history: list[dict]) -> SignalContext:
        records_before = [r for r in nav_history if r["date"] <= as_of_date]
        if not records_before:
            raise ValueError(f"No NAV data found on or before signal date {as_of_date}")

        record = records_before[-1]
        indicators: dict[str, float | str | bool | None] = {}

        if isinstance(self.modifier, MAFilter):
            window = self.modifier.window

            if len(records_before) < window:
                indicators = {
                    "ma_window": window,
                    "ma_value": None,
                    "trend_relation": "unknown",
                    "ma_available": False,
                }
            else:
                window_records = records_before[-window:]
                ma_value = sum(r["nav"] for r in window_records) / window
                current_nav = record["nav"]

                if abs(current_nav - ma_value) < 1e-9:
                    trend_relation = "equal"
                elif current_nav > ma_value:
                    trend_relation = "above"
                else:
                    trend_relation = "below"

                indicators = {
                    "ma_window": window,
                    "ma_value": ma_value,
                    "trend_relation": trend_relation,
                    "ma_available": True,
                }

        return SignalContext(
            date=as_of_date,
            current_nav=record["nav"],
            indicators=indicators
        )
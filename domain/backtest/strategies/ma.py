"""Moving Average (MA) timing strategy implementation."""
from domain.backtest.models import Signal
from domain.backtest.strategies.base import Strategy


class MAStrategy(Strategy):
    """Moving Average crossover timing strategy."""

    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def name(self) -> str:
        return "MA Timing"

    def _calculate_ma(self, navs: list[float], window: int) -> float | None:
        if len(navs) < window:
            return None
        return sum(navs[-window:]) / window

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        if len(nav_history) < self.long_window:
            return []

        signals = []
        prev_short_ma = None
        prev_long_ma = None

        for i, record in enumerate(nav_history):
            current_date = record["date"]

            navs_so_far = [nav_history[j]["nav"] for j in range(i + 1)]
            short_ma = self._calculate_ma(navs_so_far, self.short_window)
            long_ma = self._calculate_ma(navs_so_far, self.long_window)

            if short_ma is None or long_ma is None:
                continue

            if prev_short_ma is not None and prev_long_ma is not None:
                if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                    confidence = min(0.8, 0.6 + (short_ma - long_ma) / long_ma)
                    signals.append(
                        Signal(
                            date=current_date,
                            fund_code="UNKNOWN",
                            action="BUY",
                            confidence=confidence,
                            reason=f"短期均线上穿长期均线（{short_ma:.3f} > {long_ma:.3f}）",
                            amount=None,
                            target_weight=1.0,
                        )
                    )
                elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
                    confidence = min(0.8, 0.6 + abs(short_ma - long_ma) / long_ma)
                    signals.append(
                        Signal(
                            date=current_date,
                            fund_code="UNKNOWN",
                            action="SELL",
                            confidence=confidence,
                            reason=f"短期均线下穿长期均线（{short_ma:.3f} < {long_ma:.3f}）",
                            amount=None,
                            target_weight=0.0,
                        )
                    )

            prev_short_ma = short_ma
            prev_long_ma = long_ma

        return signals

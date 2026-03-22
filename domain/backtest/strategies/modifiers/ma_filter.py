# domain/backtest/strategies/modifiers/ma_filter.py
"""Moving Average filter for signal modification."""
import dataclasses
from domain.backtest.models import Signal, SignalContext
from domain.backtest.strategies.modifiers.base import SignalModifier


class MAFilter(SignalModifier):
    """Moving Average filter that blocks signals against the trend."""

    def __init__(self, window: int = 20, filter_mode: str = "trend_confirm"):
        self.window = window
        self.filter_mode = filter_mode
        if filter_mode != "trend_confirm":
            raise NotImplementedError(f"filter_mode={filter_mode} not supported in Phase 3A")

    def name(self) -> str:
        return f"MAFilter({self.window}, {self.filter_mode})"

    def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
        trend = context.indicators.get("trend_relation", "unknown")
        ma_value = context.indicators.get("ma_value")
        window = context.indicators.get("ma_window", self.window)

        if signal.action in ("HOLD", "REBALANCE"):
            return signal

        if trend == "unknown":
            return signal

        if signal.action == "BUY":
            if trend == "above":
                return dataclasses.replace(
                    signal,
                    reason=f"{signal.reason}（上涨趋势确认，MA{window}={ma_value:.4f}）"
                )
            return None

        if signal.action == "SELL":
            if trend == "below":
                return dataclasses.replace(
                    signal,
                    reason=f"{signal.reason}（下跌趋势确认，MA{window}={ma_value:.4f}）"
                )
            return None

        return signal

    def explain_block(self, signal: Signal, context: SignalContext) -> str:
        trend = context.indicators.get("trend_relation", "unknown")
        window = context.indicators.get("ma_window", self.window)

        if signal.action == "BUY":
            if trend == "below":
                return f"买入信号被拦截：当前净值低于{window}日均线"
            if trend == "equal":
                return "信号被拦截：当前净值等于均线，趋势不明确"

        if signal.action == "SELL":
            if trend == "above":
                return f"卖出信号被拦截：当前净值高于{window}日均线"
            if trend == "equal":
                return "信号被拦截：当前净值等于均线，趋势不明确"

        return "信号被拦截：未知原因"
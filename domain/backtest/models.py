"""Domain models for FundScope backtest subdomain."""
from dataclasses import dataclass, field
from datetime import date
from typing import Literal


@dataclass
class ExecutedTrade:
    """Executed trade record."""
    date: date
    fund_code: str
    action: Literal["BUY", "SELL"]
    amount: float
    nav: float
    shares: float
    reason: str


@dataclass
class Signal:
    """Trading signal from strategy."""
    date: date
    fund_code: str
    action: Literal["BUY", "SELL", "REBALANCE", "HOLD"]
    confidence: float
    reason: str
    amount: float | None = None
    target_weight: float | None = None

    def __post_init__(self):
        if not self.reason:
            raise ValueError("reason cannot be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0~1.0, got {self.confidence}")


@dataclass
class SignalContext:
    """Context information for signal modification."""
    date: date
    current_nav: float
    indicators: dict[str, float | str | bool | None]


@dataclass
class BacktestResult:
    """Backtest result summary."""
    strategy_name: str
    fund_code: str
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float  # Positive value, e.g. 0.08 for 8%
    sharpe_ratio: float
    win_rate: float
    trade_count: int
    signals: list[Signal] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    executed_trades: list[ExecutedTrade] = field(default_factory=list)

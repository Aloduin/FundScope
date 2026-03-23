"""Domain models for FundScope backtest subdomain."""
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, TYPE_CHECKING


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
    rebalance_id: str | None = None


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
class BlockedSignalTrace:
    """Trace record for a blocked signal."""
    original: Signal
    modifier: str
    reason: str


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
    blocked_signals: list[BlockedSignalTrace] = field(default_factory=list)


@dataclass
class PortfolioSignal:
    """组合级再平衡信号。"""
    date: date
    action: Literal["REBALANCE", "HOLD"]
    confidence: float = 1.0
    reason: str = ""
    target_weights: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.action == "REBALANCE":
            if self.target_weights is None:
                raise ValueError("target_weights is required for REBALANCE action")

            if "CASH" not in self.target_weights:
                raise ValueError("target_weights must include 'CASH'")

            total = sum(self.target_weights.values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"target_weights must sum to 1.0, got {total:.6f}")

            for fund_code, weight in self.target_weights.items():
                if not 0.0 <= weight <= 1.0:
                    raise ValueError(f"invalid weight for {fund_code}: {weight}")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0~1.0, got {self.confidence}")

        if not self.reason:
            raise ValueError("reason cannot be empty")


@dataclass
class PortfolioBacktestResult:
    """组合回测结果。"""
    strategy_name: str
    fund_codes: list[str]
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    rebalance_signals: list["PortfolioSignal"] = field(default_factory=list)
    executed_trades: list[ExecutedTrade] = field(default_factory=list)
    portfolio_weights_history: list[tuple[date, dict[str, float]]] = field(default_factory=list)

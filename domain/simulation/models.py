"""Domain models for FundScope simulation subdomain."""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Literal


@dataclass
class Trade:
    """Trade record.

    Attributes:
        trade_id: Trade identifier
        account_id: Account identifier (required)
        fund_code: Fund code
        action: BUY or SELL
        amount: Trade amount in CNY
        nav: Net value at execution
        shares: Trade shares
        trade_date: Trade date
        reason: Trade reason
    """
    trade_id: str
    account_id: str
    fund_code: str
    action: Literal["BUY", "SELL"]
    amount: float
    nav: float
    shares: float
    trade_date: date
    reason: str


@dataclass
class VirtualAccount:
    """Virtual trading account.

    Attributes:
        account_id: Account identifier
        initial_cash: Initial cash amount
        cash: Current cash balance
        positions: List of positions
        trades: List of trade records
        equity_curve: Cached equity curve [(date, equity), ...]
        created_at: Creation timestamp
    """
    account_id: str
    initial_cash: float
    cash: float
    positions: list = field(default_factory=list)
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize equity curve with initial state."""
        if self.equity_curve is None:
            self.equity_curve = []
        if not self.equity_curve:
            self.equity_curve = [(date.today(), self.initial_cash)]

    def get_position(self, fund_code: str) -> dict | None:
        """Get position by fund code."""
        for pos in self.positions:
            if pos["fund_code"] == fund_code:
                return pos
        return None

    def add_position(self, fund_code: str, fund_name: str, amount: float, nav: float, shares: float) -> None:
        """Add or update a position."""
        existing = self.get_position(fund_code)
        if existing:
            existing["amount"] += amount
            existing["shares"] += shares
            # Update cost_nav on buy (simplified: use latest nav)
            if nav:
                existing["cost_nav"] = nav
        else:
            self.positions.append({
                "fund_code": fund_code,
                "fund_name": fund_name,
                "amount": amount,
                "shares": shares,
                "cost_nav": nav,
            })

    def remove_position(self, fund_code: str) -> dict | None:
        """Remove a position."""
        for i, pos in enumerate(self.positions):
            if pos["fund_code"] == fund_code:
                return self.positions.pop(i)
        return None

    def update_cash(self, amount: float) -> None:
        """Update cash balance."""
        self.cash += amount

    def get_total_equity(self, nav_map: dict[str, float]) -> float:
        """Calculate total equity using given NAV map.

        Args:
            nav_map: Dict mapping fund_code to current nav

        Returns:
            Total equity (cash + position values)
        """
        position_value = 0.0
        for pos in self.positions:
            nav = nav_map.get(pos["fund_code"], pos.get("cost_nav") or 1.0)
            position_value += pos["shares"] * nav

        return self.cash + position_value

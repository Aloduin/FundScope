"""Domain models for FundScope portfolio subdomain."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class Position:
    """Portfolio position.

    Attributes:
        fund_code: Fund code
        fund_name: Fund name
        amount: Position amount in CNY (fact field)
        weight: Position weight (derived field = amount / total_amount)
        shares: Position shares (optional)
        cost_nav: Cost net value (optional)
    """
    fund_code: str
    fund_name: str
    amount: float
    weight: float = 0.0
    shares: float | None = None
    cost_nav: float | None = None

    def recalculate_weight(self, total_amount: float) -> None:
        """Recalculate weight based on total portfolio amount."""
        if total_amount > 0:
            self.weight = self.amount / total_amount
        else:
            self.weight = 0.0


@dataclass
class Portfolio:
    """Investment portfolio.

    Attributes:
        portfolio_id: Portfolio identifier
        positions: List of positions
        total_amount: Total portfolio value
        effective_n: Effective number of holdings (1 / sum(weight^2))
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    portfolio_id: str
    positions: list[Position] = field(default_factory=list)
    total_amount: float = 0.0
    effective_n: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize timestamps and calculate derived fields."""
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = self.created_at
        self._recalculate()

    def _recalculate(self) -> None:
        """Recalculate total amount, weights, and effective_n."""
        self.total_amount = sum(p.amount for p in self.positions)

        for position in self.positions:
            position.recalculate_weight(self.total_amount)

        # effective_n = 1 / sum(weight^2)
        sum_weight_squared = sum(p.weight ** 2 for p in self.positions if p.weight > 0)
        self.effective_n = 1.0 / sum_weight_squared if sum_weight_squared > 0 else 0.0

    def add_position(self, position: Position) -> None:
        """Add or update a position."""
        existing = next((p for p in self.positions if p.fund_code == position.fund_code), None)
        if existing:
            existing.amount += position.amount
            existing.shares = (existing.shares or 0) + (position.shares or 0)
        else:
            self.positions.append(position)
        self._recalculate()
        self.updated_at = datetime.now()

    def remove_position(self, fund_code: str) -> None:
        """Remove a position."""
        self.positions = [p for p in self.positions if p.fund_code != fund_code]
        self._recalculate()
        self.updated_at = datetime.now()


@dataclass
class PortfolioDiagnosis:
    """Portfolio diagnosis result.

    Attributes:
        concentration_risk: Concentration risk (HHI index)
        effective_n: Effective number of holdings
        sector_overlap: List of overlapping sectors
        missing_defense: Whether lacking defensive assets
        style_balance: Style distribution
        suggestions: List of optimization suggestions
    """
    concentration_risk: float
    effective_n: float
    sector_overlap: list[str]
    missing_defense: bool
    style_balance: dict[str, float]
    suggestions: list[str]

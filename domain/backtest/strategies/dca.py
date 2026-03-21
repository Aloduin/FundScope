"""Dollar-Cost Averaging (DCA) strategy implementation."""
from domain.backtest.models import Signal
from domain.backtest.strategies.base import Strategy


class DCAStrategy(Strategy):
    """Dollar-Cost Averaging strategy."""

    def __init__(self, invest_amount: float, invest_interval_days: int = 20):
        self.invest_amount = invest_amount
        self.invest_interval_days = invest_interval_days

    def name(self) -> str:
        return "DCA"

    def generate_signals(self, nav_history: list[dict]) -> list[Signal]:
        if not nav_history:
            return []

        signals = []
        last_invest_date = None

        for record in nav_history:
            current_date = record["date"]
            should_invest = False

            if last_invest_date is None:
                should_invest = True
            else:
                days_diff = (current_date - last_invest_date).days
                if days_diff >= self.invest_interval_days:
                    should_invest = True

            if should_invest:
                signals.append(
                    Signal(
                        date=current_date,
                        fund_code="UNKNOWN",
                        action="BUY",
                        confidence=0.5,
                        reason=f"定期定额投资：{self.invest_amount:.0f}元",
                        amount=self.invest_amount,
                        target_weight=None,
                    )
                )
                last_invest_date = current_date

        return signals

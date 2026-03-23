"""Portfolio momentum strategy for multi-fund rotation."""
from dataclasses import dataclass
from datetime import date
from domain.backtest.models import PortfolioSignal
from domain.backtest.strategies.portfolio_base import PortfolioStrategy


@dataclass
class MomentumConfig:
    """Configuration for PortfolioMomentumStrategy."""
    lookback_periods: int = 60
    top_n: int = 2
    signal_interval_periods: int = 20


class PortfolioMomentumStrategy(PortfolioStrategy):
    """Multi-fund momentum rotation strategy.

    Ranks funds by trailing return over lookback_periods trading periods,
    allocates equally to the top_n funds, emits a REBALANCE signal when
    the ranking changes (subject to signal_interval_periods cooldown).
    """

    def __init__(self, config: MomentumConfig | None = None):
        self.config = config or MomentumConfig()

    def name(self) -> str:
        return (
            f"PortfolioMomentum("
            f"lookback={self.config.lookback_periods}, "
            f"top_n={self.config.top_n}, "
            f"interval={self.config.signal_interval_periods})"
        )

    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date],
    ) -> list[PortfolioSignal]:
        if len(aligned_dates) <= self.config.lookback_periods:
            return []

        nav_by_date = self._index_nav_by_date(nav_histories)
        signals: list[PortfolioSignal] = []
        last_signal_index: int | None = None

        for i in range(self.config.lookback_periods, len(aligned_dates)):
            if (
                last_signal_index is not None
                and i - last_signal_index < self.config.signal_interval_periods
            ):
                continue

            end_date = aligned_dates[i]
            start_date = aligned_dates[i - self.config.lookback_periods]

            returns = self._calculate_returns_by_dates(
                nav_by_date=nav_by_date,
                start_date=start_date,
                end_date=end_date,
            )

            if not returns:
                continue

            sorted_funds = sorted(returns.items(), key=lambda x: x[1], reverse=True)
            top_funds = [fund_code for fund_code, _ in sorted_funds[: self.config.top_n]]

            target_weights = self._build_target_weights(top_funds)

            signals.append(
                PortfolioSignal(
                    date=end_date,
                    action="REBALANCE",
                    target_weights=target_weights,
                    confidence=1.0,
                    reason=(
                        f"Momentum top-{self.config.top_n}: "
                        + ", ".join(top_funds)
                    ),
                )
            )
            last_signal_index = i

        return signals

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _index_nav_by_date(
        self, nav_histories: dict[str, list[dict]]
    ) -> dict[date, dict[str, float]]:
        """Build {date: {fund_code: nav}} lookup."""
        nav_by_date: dict[date, dict[str, float]] = {}
        for fund_code, records in nav_histories.items():
            for record in records:
                d = record["date"]
                if d not in nav_by_date:
                    nav_by_date[d] = {}
                nav_by_date[d][fund_code] = record["nav"]
        return nav_by_date

    def _calculate_returns_by_dates(
        self,
        nav_by_date: dict[date, dict[str, float]],
        start_date: date,
        end_date: date,
    ) -> dict[str, float]:
        """Calculate return for each fund between start_date and end_date."""
        start_navs = nav_by_date.get(start_date, {})
        end_navs = nav_by_date.get(end_date, {})

        returns: dict[str, float] = {}
        for fund_code in start_navs:
            if fund_code in end_navs and start_navs[fund_code] > 0:
                returns[fund_code] = (
                    end_navs[fund_code] / start_navs[fund_code] - 1.0
                )
        return returns

    def _build_target_weights(self, top_funds: list[str]) -> dict[str, float]:
        """Equal-weight top funds, remainder in CASH."""
        n = len(top_funds)
        if n == 0:
            return {"CASH": 1.0}
        per_fund = round(1.0 / n, 10)
        weights: dict[str, float] = {fund: per_fund for fund in top_funds}
        weights["CASH"] = round(1.0 - per_fund * n, 10)
        return weights

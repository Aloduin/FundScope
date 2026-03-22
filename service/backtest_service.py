"""Backtest service for FundScope."""
from datetime import date
from domain.backtest.engine import BacktestEngine
from domain.backtest.models import BacktestResult
from domain.backtest.strategies.base import Strategy
from domain.backtest.strategies.composite import CompositeStrategy
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.strategies.ma import MAStrategy
from domain.backtest.strategies.modifiers.ma_filter import MAFilter
from infrastructure.datasource.akshare_source import AkShareDataSource
from infrastructure.datasource.abstract import AbstractDataSource


class BacktestService:
    """Service for orchestrating backtest operations.

    Note (Phase 2): Currently uses datasource directly for NAV data.
    Future: Integrate with Parquet / unified cache layer.
    """

    def __init__(self, datasource: AbstractDataSource | None = None):
        self.datasource = datasource or AkShareDataSource()

    def _create_strategy(self, strategy_name: str, params: dict) -> Strategy:
        if strategy_name == "DCA":
            return DCAStrategy(
                invest_amount=params.get("invest_amount", 10000),
                invest_interval_days=params.get("interval_days", 20)
            )
        elif strategy_name == "MA Timing":
            return MAStrategy(
                short_window=params.get("short_window", 5),
                long_window=params.get("long_window", 20)
            )
        elif strategy_name == "DCA + MA Filter":
            dca = DCAStrategy(
                invest_amount=params.get("invest_amount", 10000),
                invest_interval_days=params.get("interval_days", 20),
            )
            ma_filter = MAFilter(
                window=params.get("ma_window", 20)
            )
            return CompositeStrategy(
                primary_strategy=dca,
                modifier=ma_filter,
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")

    def run_backtest(
        self,
        fund_code: str,
        strategy_name: str,
        strategy_params: dict,
        start_date: date,
        end_date: date,
        initial_cash: float = 100000.0
    ) -> BacktestResult:
        nav_history = self.datasource.get_fund_nav_history(
            fund_code=fund_code,
            start_date=start_date,
            end_date=end_date
        )

        if not nav_history:
            raise ValueError(f"No NAV data found for fund {fund_code}")

        strategy = self._create_strategy(strategy_name, strategy_params)

        engine = BacktestEngine(initial_cash=initial_cash)
        return engine.run(strategy, fund_code, nav_history)

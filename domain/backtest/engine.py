"""Backtest engine for FundScope."""
import numpy as np
from domain.backtest.models import ExecutedTrade, BacktestResult
from domain.backtest.strategies.base import Strategy


class BacktestEngine:
    """Backtest execution engine."""

    def __init__(self, initial_cash: float = 100000.0):
        self.initial_cash = initial_cash

    def run(
        self,
        strategy: Strategy,
        fund_code: str,
        nav_history: list[dict]
    ) -> BacktestResult:
        if not nav_history:
            raise ValueError("NAV history cannot be empty")

        signals = strategy.generate_signals(nav_history)
        blocked_signals = strategy.get_blocked_signals()

        for signal in signals:
            if signal.fund_code == "UNKNOWN":
                signal.fund_code = fund_code

        cash = self.initial_cash
        shares = 0.0
        equity_curve = []
        executed_trades: list[ExecutedTrade] = []
        pending_order = None

        for i, record in enumerate(nav_history):
            current_date = record["date"]
            current_nav = record["nav"]

            if pending_order is not None:
                signal, target_date = pending_order
                if current_date == target_date:
                    if signal.action == "BUY" and signal.amount:
                        buy_amount = min(signal.amount, cash)
                        if buy_amount > 0:
                            trade_shares = buy_amount / current_nav
                            shares += trade_shares
                            cash -= buy_amount
                            executed_trades.append(
                                ExecutedTrade(
                                    date=current_date,
                                    fund_code=fund_code,
                                    action="BUY",
                                    amount=buy_amount,
                                    nav=current_nav,
                                    shares=trade_shares,
                                    reason=signal.reason
                                )
                            )

                    elif signal.action == "SELL":
                        if signal.target_weight is not None:
                            target_shares = 0.0 if signal.target_weight == 0 else shares * signal.target_weight
                            shares_to_sell = shares - target_shares
                        else:
                            shares_to_sell = shares

                        shares_to_sell = max(0.0, min(shares_to_sell, shares))
                        if shares_to_sell > 0:
                            sell_amount = shares_to_sell * current_nav
                            cash += sell_amount
                            shares -= shares_to_sell
                            executed_trades.append(
                                ExecutedTrade(
                                    date=current_date,
                                    fund_code=fund_code,
                                    action="SELL",
                                    amount=sell_amount,
                                    nav=current_nav,
                                    shares=shares_to_sell,
                                    reason=signal.reason
                                )
                            )

                    pending_order = None

            todays_signals = [s for s in signals if s.date == current_date]
            if todays_signals and i < len(nav_history) - 1:
                next_date = nav_history[i + 1]["date"]
                pending_order = (todays_signals[-1], next_date)

            equity = cash + shares * current_nav
            equity_curve.append((current_date, equity))

        total_return = (equity_curve[-1][1] - self.initial_cash) / self.initial_cash

        days = (nav_history[-1]["date"] - nav_history[0]["date"]).days
        years = days / 365.25
        annualized_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        equity_values = [e[1] for e in equity_curve]
        peak = equity_values[0]
        max_drawdown = 0.0
        for eq in equity_values:
            if eq > peak:
                peak = eq
            drawdown = (peak - eq) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        daily_returns = []
        for i in range(1, len(equity_values)):
            ret = (equity_values[i] - equity_values[i - 1]) / equity_values[i - 1]
            daily_returns.append(ret)

        if len(daily_returns) > 1:
            mean_return = np.mean(daily_returns)
            std_return = np.std(daily_returns)
            sharpe_ratio = (mean_return * 252) / (std_return * np.sqrt(252)) if std_return > 0 else 0.0
        else:
            sharpe_ratio = 0.0

        winning_days = sum(1 for r in daily_returns if r > 0)
        win_rate = winning_days / len(daily_returns) if daily_returns else 0.0

        return BacktestResult(
            strategy_name=strategy.name(),
            fund_code=fund_code,
            start_date=nav_history[0]["date"],
            end_date=nav_history[-1]["date"],
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate,
            trade_count=len(executed_trades),
            signals=signals,
            equity_curve=equity_curve,
            executed_trades=executed_trades,
            blocked_signals=blocked_signals,
        )

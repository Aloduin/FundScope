"""Virtual account trading logic.

Pure calculation logic - no IO.
"""
from datetime import date, datetime
from typing import Literal
from shared.logger import get_logger
from domain.simulation.models import VirtualAccount, Trade

logger = get_logger(__name__)


def buy(
    account: VirtualAccount,
    fund_code: str,
    fund_name: str,
    amount: float,
    nav: float,
    trade_date: date | None = None,
    reason: str = ""
) -> Trade:
    """Execute a buy order.

    Args:
        account: Virtual account
        fund_code: Fund code to buy
        fund_name: Fund name
        amount: Amount to invest (CNY)
        nav: Execution net value
        trade_date: Trade date (default: today)
        reason: Trade reason

    Returns:
        Trade record

    Raises:
        ValueError: If insufficient cash
    """
    if trade_date is None:
        trade_date = date.today()

    if not reason:
        reason = f"买入 {fund_name}"

    # Calculate shares
    shares = amount / nav if nav > 0 else 0

    # Check cash
    if amount > account.cash:
        raise ValueError(f"Insufficient cash: {account.cash} < {amount}")

    # Update cash
    account.update_cash(-amount)

    # Update position
    account.add_position(fund_code, fund_name, amount, nav, shares)

    # Create trade record (must include account_id)
    trade = Trade(
        trade_id=_generate_trade_id(account.account_id, fund_code, trade_date, "BUY"),
        account_id=account.account_id,
        fund_code=fund_code,
        action="BUY",
        amount=amount,
        nav=nav,
        shares=shares,
        trade_date=trade_date,
        reason=reason,
    )
    account.trades.append(trade)

    logger.info(f"BUY: {account.account_id} bought {shares:.2f} shares of {fund_code} @ {nav:.4f}")

    return trade


def sell(
    account: VirtualAccount,
    fund_code: str,
    fund_name: str,
    amount: float,
    nav: float,
    trade_date: date | None = None,
    reason: str = ""
) -> Trade:
    """Execute a sell order.

    Args:
        account: Virtual account
        fund_code: Fund code to sell
        fund_name: Fund name
        amount: Amount to sell (CNY)
        nav: Execution net value
        trade_date: Trade date (default: today)
        reason: Trade reason

    Returns:
        Trade record

    Raises:
        ValueError: If insufficient position
    """
    if trade_date is None:
        trade_date = date.today()

    if not reason:
        reason = f"卖出 {fund_name}"

    # Calculate shares to sell
    shares_to_sell = amount / nav if nav > 0 else 0

    # Check position
    position = account.get_position(fund_code)
    if position is None:
        raise ValueError(f"No position for {fund_code}")

    if shares_to_sell > position["shares"]:
        raise ValueError(f"Insufficient shares: {position['shares']} < {shares_to_sell}")

    # Update position
    position["shares"] -= shares_to_sell
    position["amount"] -= amount

    # Remove position if zero
    if position["shares"] <= 0:
        account.remove_position(fund_code)

    # Update cash
    account.update_cash(amount)

    # Create trade record (must include account_id)
    trade = Trade(
        trade_id=_generate_trade_id(account.account_id, fund_code, trade_date, "SELL"),
        account_id=account.account_id,
        fund_code=fund_code,
        action="SELL",
        amount=amount,
        nav=nav,
        shares=shares_to_sell,
        trade_date=trade_date,
        reason=reason,
    )
    account.trades.append(trade)

    logger.info(f"SELL: {account.account_id} sold {shares_to_sell:.2f} shares of {fund_code} @ {nav:.4f}")

    return trade


def _generate_trade_id(
    account_id: str,
    fund_code: str,
    trade_date: date,
    action: str
) -> str:
    """Generate unique trade ID."""
    return f"{account_id}_{fund_code}_{trade_date.strftime('%Y%m%d')}_{action}"

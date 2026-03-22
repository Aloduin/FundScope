"""Simulation service orchestration.

Orchestrates virtual account operations.
"""
import json
from datetime import date
from infrastructure.storage.sqlite_store import init_db, get_connection
from domain.simulation.models import VirtualAccount, Trade
from domain.simulation.account import buy, sell
from shared.logger import get_logger

logger = get_logger(__name__)


class SimulationService:
    """Simulation service for virtual account operations.

    Orchestrates:
    1. Account creation
    2. Buy/sell operations
    3. Position and trade persistence
    """

    def __init__(self):
        """Initialize simulation service."""
        init_db()  # Ensure database is initialized
        logger.info("SimulationService initialized")

    def create_account(self, account_id: str, initial_cash: float) -> VirtualAccount:
        """Create a new virtual account.

        Args:
            account_id: Account identifier
            initial_cash: Initial cash amount

        Returns:
            VirtualAccount
        """
        logger.info(f"Creating account: {account_id} with {initial_cash}")

        account = VirtualAccount(
            account_id=account_id,
            initial_cash=initial_cash,
            cash=initial_cash,
        )

        # Persist to database
        self._persist_account(account)

        return account

    def get_account(self, account_id: str) -> VirtualAccount | None:
        """Get account from database.

        Args:
            account_id: Account identifier

        Returns:
            VirtualAccount or None if not found
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Get account header
        cursor.execute("SELECT * FROM virtual_account WHERE account_id = ?", (account_id,))
        row = cursor.fetchone()

        if row is None:
            conn.close()
            return None

        # Get positions
        cursor.execute("SELECT * FROM virtual_account_position WHERE account_id = ?", (account_id,))
        positions = [dict(row) for row in cursor.fetchall()]

        # Get trades
        cursor.execute("SELECT * FROM trade_record WHERE account_id = ? ORDER BY trade_date", (account_id,))
        trades = [dict(row) for row in cursor.fetchall()]

        conn.close()

        # Reconstruct account
        account = VirtualAccount(
            account_id=row["account_id"],
            initial_cash=row["initial_cash"],
            cash=row["cash"],
            positions=positions,
            trades=[],  # Will reconstruct from trade records
        )

        # Reconstruct trades
        for t in trades:
            account.trades.append(Trade(
                trade_id=t["trade_id"],
                account_id=t["account_id"],
                fund_code=t["fund_code"],
                action=t["action"],
                amount=t["amount"],
                nav=t["nav"],
                shares=t["shares"],
                trade_date=date.fromisoformat(t["trade_date"]) if isinstance(t["trade_date"], str) else t["trade_date"],
                reason=t.get("reason", ""),
            ))

        return account

    def execute_buy(
        self,
        account_id: str,
        fund_code: str,
        fund_name: str,
        amount: float,
        nav: float,
        trade_date: date | None = None,
        reason: str = ""
    ) -> Trade:
        """Execute a buy order.

        Args:
            account_id: Account identifier
            fund_code: Fund code to buy
            fund_name: Fund name
            amount: Amount to invest
            nav: Execution net value
            trade_date: Trade date (default: today)
            reason: Trade reason

        Returns:
            Trade record

        Raises:
            ValueError: If account not found or insufficient cash
        """
        logger.info(f"Executing BUY: {account_id} buying {fund_code}")

        # Get account
        account = self.get_account(account_id)
        if account is None:
            raise ValueError(f"Account not found: {account_id}")

        # Execute buy
        trade = buy(account, fund_code, fund_name, amount, nav, trade_date, reason)

        # Persist updates
        self._update_account(account, trade)

        return trade

    def execute_sell(
        self,
        account_id: str,
        fund_code: str,
        fund_name: str,
        amount: float,
        nav: float,
        trade_date: date | None = None,
        reason: str = ""
    ) -> Trade:
        """Execute a sell order.

        Args:
            account_id: Account identifier
            fund_code: Fund code to sell
            fund_name: Fund name
            amount: Amount to sell
            nav: Execution net value
            trade_date: Trade date (default: today)
            reason: Trade reason

        Returns:
            Trade record

        Raises:
            ValueError: If account not found or insufficient position
        """
        logger.info(f"Executing SELL: {account_id} selling {fund_code}")

        # Get account
        account = self.get_account(account_id)
        if account is None:
            raise ValueError(f"Account not found: {account_id}")

        # Execute sell
        trade = sell(account, fund_code, fund_name, amount, nav, trade_date, reason)

        # Persist updates
        self._update_account(account, trade)

        return trade

    def import_holdings(
        self,
        holdings: list[dict],
        account_id: str,
        mode: str = "append",
        initial_cash: float = 0.0,
        nav: float = 1.0,
    ) -> dict:
        """Import holdings to virtual account.

        Args:
            holdings: List of holdings with fund_code, fund_name, amount
            account_id: Account identifier (required)
            mode: "append" or "replace"
            initial_cash: Initial cash for new accounts
            nav: Net value for trades (default 1.0)

        Returns:
            Dict with account, created_new_account, imported_count, etc.

        Raises:
            ValueError: If mode invalid, account not found, or insufficient cash
        """
        # Validate mode
        if mode not in ("append", "replace"):
            raise ValueError(f"Invalid mode: {mode}. Must be 'append' or 'replace'.")

        # Calculate total amount
        total_amount = sum(h.get("amount", 0) for h in holdings)

        # Check if account exists
        account = self.get_account(account_id)
        created_new_account = account is None

        if mode == "append":
            return self._import_append(account_id, holdings, nav, total_amount)
        else:
            # replace mode - will implement in next task
            return self._import_replace(account_id, holdings, nav, total_amount, initial_cash, created_new_account)

    def _import_append(
        self,
        account_id: str,
        holdings: list[dict],
        nav: float,
        total_amount: float,
    ) -> dict:
        """Append holdings to existing account."""
        account = self.get_account(account_id)
        if account is None:
            raise ValueError(f"Account not found: {account_id}")

        if account.cash < total_amount:
            raise ValueError(
                f"Insufficient cash: {account.cash:.2f} < {total_amount:.2f}"
            )

        reason = "从持仓诊断页导入，按 NAV=1.0 初始化模拟持仓"
        imported_count = 0

        for h in holdings:
            self.execute_buy(
                account_id=account_id,
                fund_code=h["fund_code"],
                fund_name=h["fund_name"],
                amount=h["amount"],
                nav=nav,
                reason=reason,
            )
            imported_count += 1

        account = self.get_account(account_id)
        return {
            "account": account,
            "created_new_account": False,
            "imported_count": imported_count,
            "skipped_count": 0,
            "mode": "append",
            "nav_used": nav,
            "message": f"已将 {imported_count} 条持仓追加到账户 {account_id}",
        }

    def _import_replace(
        self,
        account_id: str,
        holdings: list[dict],
        nav: float,
        total_amount: float,
        initial_cash: float,
        created_new_account: bool,
    ) -> dict:
        """Replace account holdings with imported holdings."""
        # Placeholder - will implement in next task
        return {
            "account": None,
            "created_new_account": created_new_account,
            "imported_count": 0,
            "skipped_count": 0,
            "mode": "replace",
            "nav_used": nav,
            "message": "Not implemented",
        }

    def _persist_account(self, account: VirtualAccount) -> None:
        """Persist new account to SQLite."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO virtual_account (account_id, initial_cash, cash, created_at)
            VALUES (?, ?, ?, ?)
        """, (account.account_id, account.initial_cash, account.cash, account.created_at.isoformat()))

        conn.commit()
        conn.close()
        logger.debug(f"Persisted account {account.account_id}")

    def _update_account(self, account: VirtualAccount, trade: Trade) -> None:
        """Update account in SQLite after trade.

        Updates:
        - Account cash
        - Positions (full rewrite)
        - Trades (append only)
        """
        conn = get_connection()
        cursor = conn.cursor()

        # Update account cash
        cursor.execute("""
            UPDATE virtual_account SET cash = ? WHERE account_id = ?
        """, (account.cash, account.account_id))

        # Delete and rewrite positions
        cursor.execute("DELETE FROM virtual_account_position WHERE account_id = ?", (account.account_id,))

        for pos in account.positions:
            if isinstance(pos, dict):
                cursor.execute("""
                    INSERT INTO virtual_account_position (
                        account_id, fund_code, fund_name, amount, weight, shares, cost_nav
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    account.account_id,
                    pos["fund_code"],
                    pos.get("fund_name", ""),
                    pos["amount"],
                    pos.get("weight", 0.0),
                    pos.get("shares"),
                    pos.get("cost_nav"),
                ))

        # Append trade (only the new one)
        cursor.execute("""
            INSERT INTO trade_record (
                trade_id, account_id, fund_code, action, amount, nav, shares, trade_date, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.trade_id,
            trade.account_id,
            trade.fund_code,
            trade.action,
            trade.amount,
            trade.nav,
            trade.shares,
            trade.trade_date.isoformat() if trade.trade_date else date.today().isoformat(),
            trade.reason,
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Updated account {account.account_id} with trade {trade.trade_id}")

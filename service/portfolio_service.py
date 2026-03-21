"""Portfolio service orchestration.

Orchestrates portfolio analysis and diagnosis.
"""
import json
from datetime import date
from infrastructure.storage.sqlite_store import init_db, get_connection
from domain.portfolio.models import Portfolio, Position, PortfolioDiagnosis
from domain.portfolio.analyzer import analyze_portfolio
from shared.logger import get_logger

logger = get_logger(__name__)


class PortfolioService:
    """Portfolio service for end-to-end portfolio analysis.

    Orchestrates:
    1. Portfolio creation from holdings
    2. Sector lookup for each position
    3. Portfolio diagnosis
    4. Persistence to SQLite
    """

    def __init__(self):
        """Initialize portfolio service."""
        init_db()  # Ensure database is initialized
        logger.info("PortfolioService initialized")

    def create_portfolio(self, portfolio_id: str, holdings: list[dict]) -> Portfolio:
        """Create portfolio from holdings.

        Args:
            portfolio_id: Portfolio identifier
            holdings: List of dicts with keys [fund_code, fund_name, amount]

        Returns:
            Portfolio with positions
        """
        logger.info(f"Creating portfolio: {portfolio_id} with {len(holdings)} positions")

        positions = []
        for h in holdings:
            positions.append(Position(
                fund_code=h["fund_code"],
                fund_name=h.get("fund_name", ""),
                amount=h.get("amount", 0.0),
                shares=h.get("shares"),
                cost_nav=h.get("cost_nav"),
            ))

        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            positions=positions,
        )

        # Persist to database
        self._persist_portfolio(portfolio)

        return portfolio

    def analyze(self, portfolio: Portfolio) -> PortfolioDiagnosis:
        """Analyze portfolio and generate diagnosis.

        Args:
            portfolio: Portfolio to analyze

        Returns:
            PortfolioDiagnosis with analysis results
        """
        logger.info(f"Analyzing portfolio: {portfolio.portfolio_id}")

        # Get sector for each position
        position_sectors = {}
        for pos in portfolio.positions:
            sectors = self._get_fund_sectors(pos.fund_code)
            position_sectors[pos.fund_code] = sectors

        # Analyze
        diagnosis = analyze_portfolio(portfolio, position_sectors)

        return diagnosis

    def _get_fund_sectors(self, fund_code: str) -> list[str]:
        """Get sectors for a fund from database."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT sectors FROM fund_info WHERE fund_code = ?", (fund_code,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            # If fund not in database, use classifier
            cursor2 = conn.cursor()
            cursor2.execute("SELECT fund_name FROM fund_info WHERE fund_code = ?", (fund_code,))
            return []

        return json.loads(row["sectors"]) if row["sectors"] else []

    def _persist_portfolio(self, portfolio: Portfolio) -> None:
        """Persist Portfolio to SQLite."""
        conn = get_connection()
        cursor = conn.cursor()

        # Insert portfolio header
        cursor.execute("""
            INSERT OR REPLACE INTO portfolio (
                portfolio_id, total_amount, effective_n, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            portfolio.portfolio_id,
            portfolio.total_amount,
            portfolio.effective_n,
            portfolio.created_at.isoformat(),
            portfolio.updated_at.isoformat(),
        ))

        # Get portfolio_id (for insert, use lastrowid or existing)
        # Delete existing positions first
        cursor.execute("DELETE FROM portfolio_position WHERE portfolio_id = ?", (portfolio.portfolio_id,))

        # Insert positions
        for pos in portfolio.positions:
            cursor.execute("""
                INSERT INTO portfolio_position (
                    portfolio_id, fund_code, fund_name, amount, weight, shares, cost_nav
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                portfolio.portfolio_id,
                pos.fund_code,
                pos.fund_name,
                pos.amount,
                pos.weight,
                pos.shares,
                pos.cost_nav,
            ))

        conn.commit()
        conn.close()
        logger.debug(f"Persisted portfolio {portfolio.portfolio_id}")

    def get_diagnosis(self, holdings: list[dict]) -> dict:
        """Get portfolio diagnosis from holdings.

        Args:
            holdings: List of dicts with keys [fund_code, fund_name, amount]

        Returns:
            Dict containing diagnosis results
        """
        # Create temporary portfolio for analysis
        portfolio = self.create_portfolio("temp_analysis", holdings)
        diagnosis = self.analyze(portfolio)

        return {
            "concentration_risk": diagnosis.concentration_risk,
            "effective_n": diagnosis.effective_n,
            "sector_overlap": diagnosis.sector_overlap,
            "missing_defense": diagnosis.missing_defense,
            "style_balance": diagnosis.style_balance,
            "suggestions": diagnosis.suggestions,
        }

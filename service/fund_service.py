"""Fund service orchestration.

Orchestrates data retrieval, metrics calculation, scoring, and classification.
"""
import json
from datetime import date
from infrastructure.datasource.akshare_source import AkShareDataSource
from infrastructure.storage.sqlite_store import init_db, get_connection
from infrastructure.storage.parquet_store import ParquetStore
from domain.fund.models import FundInfo, FundMetrics, FundScore
from domain.fund.metrics import calculate_metrics
from domain.fund.scorer import calculate_score
from domain.fund.classifier import classify_sector
from shared.logger import get_logger
from shared.config import DATA_VERSION, USE_REAL_DATA

logger = get_logger(__name__)


class FundService:
    """Fund service for end-to-end fund analysis.

    Orchestrates:
    1. Data retrieval from datasource
    2. Metrics calculation
    3. Score calculation
    4. Sector classification
    5. Persistence to SQLite
    """

    def __init__(self):
        """Initialize fund service."""
        init_db()  # Ensure database is initialized
        self.datasource = AkShareDataSource(use_mock=not USE_REAL_DATA)
        logger.info(f"FundService initialized with USE_REAL_DATA={USE_REAL_DATA}")

    def analyze_fund(self, fund_code: str, use_mock: bool = None) -> dict:
        """Analyze a fund end-to-end.

        Args:
            fund_code: Fund code (e.g., '000001')
            use_mock: If True, use mock data. If False, use real akshare API.
                      If None, uses USE_REAL_DATA config setting.

        Returns:
            Dict containing:
            - info: FundInfo
            - metrics: FundMetrics
            - score: FundScore
            - primary_sector: str
            - sectors: list[str]
            - sector_source: str
        """
        logger.info(f"Analyzing fund: {fund_code}")

        # Use provided use_mock or fall back to config
        if use_mock is not None:
            # Temporarily override datasource for this call
            datasource = AkShareDataSource(use_mock=use_mock)
        else:
            datasource = self.datasource

        # 1. Get basic info
        basic_info = datasource.get_fund_basic_info(fund_code)

        # 2. Get NAV history
        nav_history = datasource.get_fund_nav_history(fund_code)

        # 3. Classify sector
        primary_sector, sectors, sector_source = classify_sector(
            basic_info.get("fund_name", ""),
            fund_code
        )

        # 4. Create FundInfo
        info = FundInfo(
            fund_code=fund_code,
            fund_name=basic_info.get("fund_name", ""),
            fund_type=basic_info.get("fund_type", "混合型"),
            primary_sector=primary_sector,
            sectors=sectors,
            sector_source=sector_source,
            manager_name=basic_info.get("manager_name", ""),
            manager_tenure=basic_info.get("manager_tenure", 0.0),
            fund_size=basic_info.get("fund_size", 0.0),
            management_fee=basic_info.get("management_fee", 0.0),
            custodian_fee=basic_info.get("custodian_fee", 0.0),
            subscription_fee=basic_info.get("subscription_fee", 0.0),
            data_version=DATA_VERSION,
        )

        # 5. Calculate metrics
        metrics = calculate_metrics(nav_history, fund_code)

        # 6. Calculate score
        score = calculate_score(metrics, info.fund_type, info)

        # 7. Save NAV history to Parquet
        self._save_nav_to_parquet(nav_history, fund_code)

        # 8. Persist to database
        self._persist_fund_info(info)
        self._persist_fund_score(score)

        return {
            "info": info,
            "metrics": metrics,
            "score": score,
            "primary_sector": primary_sector,
            "sectors": sectors,
            "sector_source": sector_source,
        }

    def _save_nav_to_parquet(
        self,
        nav_history: list[dict],
        fund_code: str
    ) -> None:
        """Save NAV history to Parquet file.

        Args:
            nav_history: List of dicts with keys [date, nav, acc_nav]
            fund_code: Fund code
        """
        if not nav_history:
            logger.warning(f"No NAV data to save for {fund_code}")
            return

        parquet_store = ParquetStore(fund_code)
        parquet_store.write_nav_data(nav_history, DATA_VERSION)
        logger.info(f"Saved NAV history to Parquet for {fund_code}")

    def _persist_fund_info(self, info: FundInfo) -> None:
        """Persist FundInfo to SQLite."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO fund_info (
                fund_code, fund_name, fund_type, primary_sector, sectors,
                sector_source, manager_name, manager_tenure, fund_size,
                management_fee, custodian_fee, subscription_fee,
                data_version, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            info.fund_code,
            info.fund_name,
            info.fund_type,
            info.primary_sector,
            json.dumps(info.sectors),
            info.sector_source,
            info.manager_name,
            info.manager_tenure,
            info.fund_size,
            info.management_fee,
            info.custodian_fee,
            info.subscription_fee,
            info.data_version,
            date.today().isoformat(),
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Persisted FundInfo for {info.fund_code}")

    def _persist_fund_score(self, score: FundScore) -> None:
        """Persist FundScore to SQLite."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO fund_score (
                fund_code, total_score, return_score, risk_score,
                stability_score, cost_score, size_score, manager_score,
                data_completeness, data_version, missing_dimensions, scored_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            score.fund_code,
            score.total_score,
            score.return_score,
            score.risk_score,
            score.stability_score,
            score.cost_score,
            score.size_score,
            score.manager_score,
            score.data_completeness,
            date.today().strftime("%Y%m%d"),
            json.dumps(score.missing_dimensions),
            date.today().isoformat(),
        ))

        conn.commit()
        conn.close()
        logger.debug(f"Persisted FundScore for {score.fund_code}")

    def get_fund_info(self, fund_code: str) -> FundInfo | None:
        """Get FundInfo from database."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM fund_info WHERE fund_code = ?", (fund_code,))
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        return FundInfo(
            fund_code=row["fund_code"],
            fund_name=row["fund_name"],
            fund_type=row["fund_type"],
            primary_sector=row["primary_sector"],
            sectors=json.loads(row["sectors"]),
            sector_source=row["sector_source"],
            manager_name=row["manager_name"],
            manager_tenure=row["manager_tenure"],
            fund_size=row["fund_size"],
            management_fee=row["management_fee"],
            custodian_fee=row["custodian_fee"],
            subscription_fee=row["subscription_fee"],
            data_version=row["data_version"],
        )

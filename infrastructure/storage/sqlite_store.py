"""SQLite storage for FundScope business data.

Provides init_db() for idempotent database initialization
and get_connection() for database access.
"""
import sqlite3
from pathlib import Path
from shared.logger import get_logger
from shared.config import SQLITE_DB_PATH

logger = get_logger(__name__)


def get_connection() -> sqlite3.Connection:
    """Get a database connection.

    Returns:
        sqlite3.Connection with row_factory set to sqlite3.Row
    """
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database with all required tables.

    This function is idempotent - safe to call multiple times.
    Creates tables if they don't exist and adds indexes.
    """
    logger.info(f"Initializing database: {SQLITE_DB_PATH}")

    conn = get_connection()
    cursor = conn.cursor()

    # Fund info table (with auto-classification results)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_info (
            fund_code        TEXT PRIMARY KEY,
            fund_name        TEXT NOT NULL,
            fund_type        TEXT,
            primary_sector   TEXT,
            sectors          TEXT,
            sector_source    TEXT,
            manager_name     TEXT,
            manager_tenure   REAL,
            fund_size        REAL,
            management_fee   REAL,
            custodian_fee    REAL,
            subscription_fee REAL,
            data_version     TEXT,
            updated_at       DATETIME NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_info_sector ON fund_info(primary_sector)")

    # Fund score cache
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_score (
            fund_code            TEXT PRIMARY KEY,
            total_score          REAL,
            return_score         REAL,
            risk_score           REAL,
            stability_score      REAL,
            cost_score           REAL,
            size_score           REAL,
            manager_score        REAL,
            data_completeness    REAL,
            data_version         TEXT,
            missing_dimensions   TEXT,
            scored_at            DATETIME NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fund_score_version ON fund_score(data_version)")

    # Fund sector override (manual corrections)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fund_sector_override (
            fund_code       TEXT PRIMARY KEY,
            primary_sector  TEXT NOT NULL,
            sectors         TEXT NOT NULL,
            updated_at      DATETIME NOT NULL
        )
    """)

    # Portfolio header
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            portfolio_id TEXT PRIMARY KEY,
            total_amount REAL,
            effective_n  REAL,
            created_at   DATETIME NOT NULL,
            updated_at   DATETIME NOT NULL
        )
    """)

    # Portfolio positions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_position (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_id TEXT NOT NULL,
            fund_code    TEXT NOT NULL,
            fund_name    TEXT,
            amount       REAL NOT NULL,
            weight       REAL NOT NULL,
            shares       REAL,
            cost_nav     REAL,
            FOREIGN KEY (portfolio_id) REFERENCES portfolio(portfolio_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_position_pid ON portfolio_position(portfolio_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolio_position_code ON portfolio_position(fund_code)")

    # Virtual account header
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_account (
            account_id   TEXT PRIMARY KEY,
            initial_cash REAL NOT NULL,
            cash         REAL NOT NULL,
            created_at   DATETIME NOT NULL
        )
    """)

    # Virtual account positions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_account_position (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id  TEXT NOT NULL,
            fund_code   TEXT NOT NULL,
            fund_name   TEXT,
            amount      REAL NOT NULL,
            weight      REAL NOT NULL,
            shares      REAL,
            cost_nav    REAL,
            FOREIGN KEY (account_id) REFERENCES virtual_account(account_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vap_account ON virtual_account_position(account_id)")

    # Trade records
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_record (
            trade_id    TEXT PRIMARY KEY,
            account_id  TEXT NOT NULL,
            fund_code   TEXT NOT NULL,
            action      TEXT NOT NULL,
            amount      REAL NOT NULL,
            nav         REAL NOT NULL,
            shares      REAL NOT NULL,
            trade_date  DATE NOT NULL,
            reason      TEXT,
            FOREIGN KEY (account_id) REFERENCES virtual_account(account_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_account ON trade_record(account_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trade_date ON trade_record(trade_date)")

    # Virtual account equity curve
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS virtual_account_equity_curve (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id TEXT NOT NULL,
            date       DATE NOT NULL,
            equity     REAL NOT NULL,
            FOREIGN KEY (account_id) REFERENCES virtual_account(account_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vaec_account_date ON virtual_account_equity_curve(account_id, date)")

    conn.commit()
    conn.close()
    logger.info("Database initialization complete")

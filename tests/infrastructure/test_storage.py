"""Tests for storage module."""
import os
import pandas as pd
from datetime import date, timedelta
from pathlib import Path
from infrastructure.storage.parquet_store import ParquetStore
from infrastructure.storage.sqlite_store import init_db, get_connection
from shared.config import PARQUET_DIR, SQLITE_DB_PATH


class TestParquetStore:
    """Tests for ParquetStore."""

    def setup_method(self):
        """Set up test fixtures."""
        self.test_fund_code = "000001"
        self.store = ParquetStore(self.test_fund_code)
        # Clean up any existing test file
        if self.store.file_path.exists():
            self.store.file_path.unlink()

    def teardown_method(self):
        """Clean up after tests."""
        if self.store.file_path.exists():
            self.store.file_path.unlink()

    def test_write_and_read_nav_data(self):
        """Test writing and reading NAV data."""
        nav_data = [
            {"date": date(2024, 1, 1), "nav": 1.0, "acc_nav": 1.0},
            {"date": date(2024, 1, 2), "nav": 1.02, "acc_nav": 1.02},
            {"date": date(2024, 1, 3), "nav": 1.01, "acc_nav": 1.01},
        ]

        self.store.write_nav_data(nav_data, "20240101_test")

        assert self.store.exists()

        df = self.store.read_nav_data()
        assert len(df) == 3
        assert "nav" in df.columns
        assert "acc_nav" in df.columns
        assert "data_version" in df.columns

    def test_read_nonexistent_file(self):
        """Test reading from nonexistent file returns empty DataFrame."""
        store = ParquetStore("999999")
        df = store.read_nav_data()
        assert df.empty

    def test_delete(self):
        """Test deleting parquet file."""
        nav_data = [{"date": date(2024, 1, 1), "nav": 1.0, "acc_nav": 1.0}]
        self.store.write_nav_data(nav_data, "20240101_test")
        assert self.store.exists()

        self.store.delete()
        assert not self.store.exists()


class TestSqliteStore:
    """Tests for SQLite storage."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use a test database file
        os.environ["SQLITE_DB_PATH"] = str(Path(__file__).parent.parent.parent / "data" / "sqlite" / "test_fundscope.db")

    def teardown_method(self):
        """Clean up after tests."""
        if SQLITE_DB_PATH.exists():
            SQLITE_DB_PATH.unlink()

    def test_init_db_is_idempotent(self):
        """Test init_db can be called multiple times."""
        init_db()
        init_db()  # Should not raise

        conn = get_connection()
        cursor = conn.cursor()

        # Check all tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {
            "fund_info",
            "fund_score",
            "fund_sector_override",
            "portfolio",
            "portfolio_position",
            "virtual_account",
            "virtual_account_position",
            "trade_record",
            "virtual_account_equity_curve",
        }

        assert expected_tables.issubset(tables)
        conn.close()

    def test_get_connection_returns_valid_connection(self):
        """Test get_connection returns usable connection."""
        init_db()
        conn = get_connection()

        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        conn.close()

    def test_indexes_are_created(self):
        """Test that indexes are created."""
        init_db()
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_fund_info_sector" in indexes
        assert "idx_fund_score_version" in indexes
        assert "idx_portfolio_position_pid" in indexes
        assert "idx_trade_account" in indexes

        conn.close()

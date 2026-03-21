"""Tests for fund service Parquet persistence."""
import pytest
from pathlib import Path
from service.fund_service import FundService
from infrastructure.storage.parquet_store import ParquetStore
from shared.config import PARQUET_DIR


class TestFundServiceParquetPersistence:
    """Tests for Parquet data persistence in FundService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = FundService()

    def teardown_method(self):
        """Clean up test files."""
        # Clean up test parquet files
        for fund_code in ["000001", "000002"]:
            parquet_file = PARQUET_DIR / f"{fund_code}.parquet"
            if parquet_file.exists():
                parquet_file.unlink()

    def test_analyze_fund_saves_parquet(self):
        """Test that analyze_fund saves NAV data to Parquet."""
        fund_code = "000001"
        parquet_file = PARQUET_DIR / f"{fund_code}.parquet"

        # Ensure file doesn't exist before test
        if parquet_file.exists():
            parquet_file.unlink()

        # Analyze fund
        result = self.service.analyze_fund(fund_code)

        # Check Parquet file was created
        assert parquet_file.exists(), f"Parquet file should be created for {fund_code}"

    def test_parquet_contains_nav_data(self):
        """Test that saved Parquet contains correct NAV data."""
        fund_code = "000001"

        # Analyze fund
        result = self.service.analyze_fund(fund_code)

        # Read back from Parquet
        store = ParquetStore(fund_code)
        df = store.read_nav_data()

        # Check DataFrame is not empty
        assert not df.empty, "Parquet should contain NAV data"

        # Check required columns
        assert "nav" in df.columns, "Parquet should have 'nav' column"
        assert "acc_nav" in df.columns, "Parquet should have 'acc_nav' column"
        assert "data_version" in df.columns, "Parquet should have 'data_version' column"

    def test_parquet_data_version(self):
        """Test that data_version is correctly saved."""
        fund_code = "000001"

        # Analyze fund
        result = self.service.analyze_fund(fund_code)

        # Read back from Parquet
        store = ParquetStore(fund_code)
        df = store.read_nav_data()

        # Check data_version is consistent
        data_versions = df["data_version"].unique()
        assert len(data_versions) == 1, "Should have single data version"

    def test_get_fund_score_after_analyze(self):
        """Test get_fund_score returns data after analyze."""
        # First analyze
        self.service.analyze_fund("000002")

        # Then retrieve from SQLite
        info = self.service.get_fund_info("000002")

        assert info is not None
        assert info.fund_code == "000002"
        assert info.data_version is not None

"""Parquet storage for fund NAV time-series data."""
import pandas as pd
from pathlib import Path
from shared.logger import get_logger
from shared.config import PARQUET_DIR

logger = get_logger(__name__)


class ParquetStore:
    """Parquet storage for fund NAV time-series data.

    Each fund's NAV history is stored in a separate parquet file:
    {fund_code}.parquet

    Columns:
    - date: date index
    - nav: float (单位净值)
    - acc_nav: float (累计净值)
    - data_version: str (YYYYMMDD_<hash>)
    """

    def __init__(self, fund_code: str):
        """Initialize parquet store for a specific fund.

        Args:
            fund_code: Fund code (e.g., '000001')
        """
        self.fund_code = fund_code
        self.file_path = PARQUET_DIR / f"{fund_code}.parquet"

    def write_nav_data(
        self,
        nav_data: list[dict],
        data_version: str
    ) -> None:
        """Write NAV data to parquet file.

        Args:
            nav_data: List of dicts with keys [date, nav, acc_nav]
            data_version: Data version string (YYYYMMDD_<hash>)
        """
        if not nav_data:
            logger.warning(f"No NAV data to write for {self.fund_code}")
            return

        df = pd.DataFrame(nav_data)
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df['data_version'] = data_version

        df.to_parquet(self.file_path, engine='pyarrow', index=True)
        logger.info(f"Wrote {len(nav_data)} NAV records to {self.file_path}")

    def read_nav_data(
        self,
        start_date: pd.Timestamp | None = None,
        end_date: pd.Timestamp | None = None
    ) -> pd.DataFrame:
        """Read NAV data from parquet file.

        Args:
            start_date: Start date (default: earliest available)
            end_date: End date (default: latest available)

        Returns:
            DataFrame with columns [nav, acc_nav, data_version]
        """
        if not self.file_path.exists():
            logger.warning(f"Parquet file not found: {self.file_path}")
            return pd.DataFrame()

        df = pd.read_parquet(self.file_path, engine='pyarrow')

        if start_date is not None:
            df = df[df.index >= start_date]
        if end_date is not None:
            df = df[df.index <= end_date]

        return df

    def exists(self) -> bool:
        """Check if parquet file exists."""
        return self.file_path.exists()

    def delete(self) -> None:
        """Delete parquet file."""
        if self.file_path.exists():
            self.file_path.unlink()
            logger.info(f"Deleted parquet file: {self.file_path}")

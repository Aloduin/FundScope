"""Abstract data source interface for FundScope."""
from abc import ABC, abstractmethod
from datetime import date


class AbstractDataSource(ABC):
    """Abstract data source interface.

    All data sources must implement this interface to ensure pluggability.
    """

    @abstractmethod
    def get_fund_basic_info(self, fund_code: str) -> dict:
        """Get basic fund information.

        Args:
            fund_code: Fund code (e.g., '000001')

        Returns:
            Dictionary containing fund basic info:
            - fund_code: str
            - fund_name: str
            - fund_type: str (股票型/混合型/债券型/指数型)
            - manager_name: str
            - manager_tenure: float (years)
            - fund_size: float (亿元)
            - management_fee: float
            - custodian_fee: float
            - subscription_fee: float
        """
        pass

    @abstractmethod
    def get_fund_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        """Get fund NAV (Net Asset Value) history.

        Args:
            fund_code: Fund code (e.g., '000001')
            start_date: Start date (default: 3 years ago)
            end_date: End date (default: today)

        Returns:
            List of dictionaries containing:
            - date: date
            - nav: float (单位净值)
            - acc_nav: float (累计净值)
        """
        pass

"""akshare data source implementation.

MVP Phase 1: Mock data for interface testing.
Phase 2: Replace with real akshare API calls.
"""
from datetime import date, timedelta
import numpy as np
from shared.logger import get_logger
from .abstract import AbstractDataSource

logger = get_logger(__name__)


class AkShareDataSource(AbstractDataSource):
    """akshare data source implementation.

    MVP Phase 1: Returns mock data to打通 interfaces.
    Phase 2: Replace mock methods with real akshare API calls.

    Args:
        use_mock: If True, use mock data. If False, use real akshare API.
                  Defaults to True for backward compatibility.
    """

    def __init__(self, use_mock: bool = True):
        """Initialize AkShareDataSource.

        Args:
            use_mock: If True, use mock data as fallback.
                      If False, use real akshare API (not implemented in Task 2).
        """
        self.use_mock = use_mock
        if not use_mock:
            logger.info("使用真实 akshare API（暂未实现，将抛出 NotImplementedError）")
        else:
            logger.info("使用 Mock 数据模式")

    def get_fund_basic_info(self, fund_code: str) -> dict:
        """Get basic fund information.

        Phase 2: Replace with akshare.fund_open_fund_info_em() calls.

        Args:
            fund_code: Fund code (e.g., '000001')

        Returns:
            Dictionary containing fund basic info.

        Raises:
            NotImplementedError: If use_mock is False (real API not implemented).
        """
        if not self.use_mock:
            # Task 6: Implement real akshare API call
            raise NotImplementedError(
                "Real akshare API for get_fund_basic_info not implemented yet. "
                "Set use_mock=True to use mock data."
            )

        logger.info(f"获取基金基本信息：{fund_code}")
        return {
            "fund_code": fund_code,
            "fund_name": f"测试基金{fund_code}",
            "fund_type": "混合型",
            "manager_name": "张三",
            "manager_tenure": 5.0,
            "fund_size": 10.0,
            "management_fee": 0.015,
            "custodian_fee": 0.0025,
            "subscription_fee": 0.015,
        }

    def get_fund_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        """Get fund NAV history.

        Phase 2: Replace with akshare.fund_open_fund_daily_em() calls.

        Args:
            fund_code: Fund code (e.g., '000001')
            start_date: Start date (default: 3 years ago)
            end_date: End date (default: today)

        Returns:
            List of dictionaries containing NAV history.

        Raises:
            NotImplementedError: If use_mock is False (real API not implemented).
        """
        if not self.use_mock:
            # Task 6: Implement real akshare API call
            raise NotImplementedError(
                "Real akshare API for get_fund_nav_history not implemented yet. "
                "Set use_mock=True to use mock data."
            )

        logger.info(f"获取基金净值历史：{fund_code}")

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365 * 3)

        result = []
        current = start_date
        base_nav = 1.0

        while current <= end_date:
            if current.weekday() < 5:  # Weekdays only
                daily_return = np.random.normal(0.0005, 0.02)
                nav = round(base_nav * (1 + daily_return), 4)
                result.append({
                    "date": current,
                    "nav": nav,
                    "acc_nav": nav,
                })
                base_nav = nav
            current += timedelta(days=1)

        return result

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
    """

    def get_fund_basic_info(self, fund_code: str) -> dict:
        """Get basic fund information (MVP mock).

        Phase 2: Replace with akshare.fund_open_fund_info_em() calls.
        """
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
        """Get fund NAV history (MVP mock).

        Phase 2: Replace with akshare.fund_open_fund_daily_em() calls.
        """
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

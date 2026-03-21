"""akshare data source implementation.

MVP Phase 1: Mock data for interface testing.
Phase 2: Replace with real akshare API calls.
"""
from datetime import date, timedelta
from typing import Any
import numpy as np
import pandas as pd
import akshare as ak
from shared.logger import get_logger
from .abstract import AbstractDataSource
from .cache import cached
from .raw_cache import load_cached_response, save_cached_response

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
                      If False, use real akshare API.
        """
        self.use_mock = use_mock
        if not use_mock:
            logger.info("使用真实 akshare API")
        else:
            logger.info("使用 Mock 数据模式")

    @cached(key_prefix="fund_info")
    def get_fund_basic_info(self, fund_code: str) -> dict:
        """Get basic fund information.

        Phase 2: Uses akshare API for real data.

        Args:
            fund_code: Fund code (e.g., '000001')

        Returns:
            Dictionary containing fund basic info.

        Raises:
            NotImplementedError: If use_mock is False and real API fails.
        """
        if not self.use_mock:
            # Check L2 cache first
            cached_data = load_cached_response(fund_code, "fund_info")
            if cached_data is not None:
                return cached_data

            # Call real akshare API with fallback to mock
            try:
                result = self._get_real_fund_info(fund_code)
                if self._validate_fund_info(result):
                    save_cached_response(fund_code, "fund_info", result)
                    return result
            except Exception as e:
                logger.error(f"真实 API 获取基金信息失败 {fund_code}：{e}")
                raise

        logger.info(f"获取基金基本信息：{fund_code} (Mock)")
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

    def _get_real_fund_info(self, fund_code: str) -> dict:
        """Get real fund info from akshare API.

        Args:
            fund_code: Fund code (e.g., '000001', '510300')

        Returns:
            Dictionary containing standardized fund info.
        """
        logger.info(f"获取真实基金信息：{fund_code}")

        # Detect fund type by code prefix
        # 51xxxx, 15xxxx, 16xxxx are typically ETF/LOF
        is_etf = fund_code.startswith(('51', '15', '16'))

        if is_etf:
            return self._get_etf_fund_info(fund_code)
        else:
            return self._get_open_fund_info(fund_code)

    def _get_etf_fund_info(self, fund_code: str) -> dict:
        """Get ETF fund info from akshare API (东方财富数据源)."""
        logger.info(f"获取 ETF 基金信息：{fund_code}")

        # Try to get basic info from fund_name_em
        fund_name = ""
        fund_type = "指数型"  # Default for ETF
        try:
            name_df = ak.fund_name_em()
            matching = name_df[name_df['基金代码'] == fund_code]
            if not matching.empty:
                fund_name = matching.iloc[0]['基金简称']
                fund_type_raw = matching.iloc[0].get('基金类型', '')
                fund_type = self._map_fund_type(fund_type_raw)
        except Exception as e:
            logger.warning(f"Failed to get ETF name for {fund_code}: {e}")

        return {
            "fund_code": fund_code,
            "fund_name": fund_name if fund_name else f"ETF{fund_code}",
            "fund_full_name": fund_name if fund_name else f"ETF{fund_code}",
            "fund_type": fund_type,
            "manager_name": "",  # ETF manager info not available from this API
            "manager_tenure": 0.0,
            "fund_size": 0.0,  # Need separate API call for size
            "establishment_date": None,
            "fund_company": "",
            "custodian": "",
            "investment_objective": "",
            "investment_strategy": "",
            "benchmark": "",
            "management_fee": 0.005,  # ETF typically has lower fees
            "custodian_fee": 0.001,
            "subscription_fee": 0.001,
        }

    def _get_open_fund_info(self, fund_code: str) -> dict:
        """Get open-ended fund info from akshare API (雪球数据源)."""
        logger.info(f"获取开放式基金信息：{fund_code}")

        df = ak.fund_individual_basic_info_xq(symbol=fund_code)

        # Convert DataFrame (item/value pairs) to dict
        info_dict = {}
        for _, row in df.iterrows():
            item = row['item']
            value = row['value']
            info_dict[item] = value

        # Map to standardized field names
        result = {
            "fund_code": fund_code,
            "fund_name": info_dict.get("基金名称", ""),
            "fund_full_name": info_dict.get("基金全称", ""),
            "fund_type": self._map_fund_type(info_dict.get("投资类型", "")),
            "manager_name": info_dict.get("基金经理", ""),
            "manager_tenure": self._parse_manager_tenure(info_dict.get("基金经理", info_dict.get("任职时间", ""))),
            "fund_size": self._parse_fund_size(info_dict.get("最新规模", "")),
            "establishment_date": self._parse_date(info_dict.get("成立时间", "")),
            "fund_company": info_dict.get("基金公司", ""),
            "custodian": info_dict.get("托管银行", ""),
            "investment_objective": info_dict.get("投资目标", ""),
            "investment_strategy": info_dict.get("投资策略", ""),
            "benchmark": info_dict.get("业绩比较基准", ""),
            # Default fee values (akshare doesn't always provide fee info)
            "management_fee": 0.015,
            "custodian_fee": 0.0025,
            "subscription_fee": 0.015,
        }

        return result

    def _validate_fund_info(self, info: dict) -> bool:
        """Validate fund info data quality.

        Args:
            info: Fund info dictionary

        Returns:
            True if valid, False otherwise
        """
        if not info:
            return False

        # Required fields
        required = ["fund_code", "fund_name"]
        for field in required:
            if not info.get(field):
                logger.warning(f"Missing required field: {field}")
                return False

        logger.info(f"基金信息验证通过：{info['fund_code']}")
        return True

    def _map_fund_type(self, raw_type: str) -> str:
        """Map raw fund type to standardized type.

        Args:
            raw_type: Raw type string from akshare

        Returns:
            Standardized type (股票型/混合型/债券型/指数型/货币型/QDII)
        """
        if not raw_type:
            return "混合型"

        type_mapping = {
            "股票": "股票型",
            "股票型": "股票型",
            "混合": "混合型",
            "混合型": "混合型",
            "债券": "债券型",
            "债券型": "债券型",
            "指数": "指数型",
            "指数型": "指数型",
            "货币": "货币型",
            "货币型": "货币型",
            "QDII": "QDII",
            "qdii": "QDII",
        }

        for key, value in type_mapping.items():
            if key in raw_type:
                return value

        return "混合型"  # Default

    def _parse_fund_size(self, raw_size: str) -> float:
        """Parse fund size string to float (in 亿元).

        Args:
            raw_size: Raw size string (e.g., "29.37 亿", "1000 万")

        Returns:
            Fund size in 亿元
        """
        if not raw_size or pd.isna(raw_size):
            return 0.0

        try:
            raw_size = str(raw_size)
            if "亿" in raw_size:
                return float(raw_size.replace("亿", "").replace("元", "").strip())
            elif "万" in raw_size:
                return float(raw_size.replace("万", "").replace("元", "").strip()) / 10000
            else:
                return float(raw_size.replace("元", "").strip())
        except (ValueError, AttributeError):
            return 0.0

    def _parse_manager_tenure(self, raw_tenure: str) -> float:
        """Parse manager tenure string to float (in years).

        Args:
            raw_tenure: Raw tenure string

        Returns:
            Manager tenure in years
        """
        if not raw_tenure or pd.isna(raw_tenure):
            return 0.0

        try:
            raw_tenure = str(raw_tenure)
            if "年" in raw_tenure:
                return float(raw_tenure.replace("年", "").strip())
            else:
                return 0.0
        except (ValueError, AttributeError):
            return 0.0

    def _parse_date(self, raw_date: str) -> date | None:
        """Parse date string to date object.

        Args:
            raw_date: Raw date string (e.g., "2001-12-18")

        Returns:
            date object or None
        """
        if not raw_date or pd.isna(raw_date):
            return None

        try:
            return date.fromisoformat(str(raw_date))
        except ValueError:
            return None

    @cached(key_prefix="nav_history")
    def get_fund_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        """Get fund NAV history.

        Phase 2: Uses akshare API for real data.

        Args:
            fund_code: Fund code (e.g., '000001')
            start_date: Start date (default: 3 years ago)
            end_date: End date (default: today)

        Returns:
            List of dictionaries containing NAV history.

        Raises:
            NotImplementedError: If use_mock is False and real API fails.
        """
        if not self.use_mock:
            # Check L2 cache first
            cached_data = load_cached_response(fund_code, "nav_history")
            if cached_data is not None:
                return cached_data

            # Call real akshare API with fallback to mock
            try:
                result = self._get_real_nav_history(fund_code, start_date, end_date)
                if self._validate_nav_history(result):
                    save_cached_response(fund_code, "nav_history", result)
                    return result
            except Exception as e:
                logger.error(f"真实 API 获取净值历史失败 {fund_code}：{e}")
                raise

        logger.info(f"获取基金净值历史：{fund_code} (Mock)")

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

    def _get_real_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        """Get real NAV history from akshare API.

        Args:
            fund_code: Fund code (e.g., '000001')
            start_date: Start date (default: 3 years ago)
            end_date: End date (default: today)

        Returns:
            List of dictionaries containing standardized NAV history.
        """
        logger.info(f"获取真实基金净值历史：{fund_code}")

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365 * 3)

        # Detect fund type and use appropriate API
        is_etf = fund_code.startswith(('51', '15', '16'))

        if is_etf:
            # Use ETF API
            df = self._fetch_etf_nav(fund_code, start_date, end_date)
            # If ETF API fails, try open-ended fund API as fallback
            if df.empty:
                logger.info(f"ETF API failed, trying open-ended fund API for {fund_code}")
                df = self._fetch_open_fund_nav(fund_code, start_date, end_date)
        else:
            # Use open-ended fund API
            df = self._fetch_open_fund_nav(fund_code, start_date, end_date)

        # Handle empty DataFrame
        if df.empty:
            logger.warning(f"No NAV data found for {fund_code}")
            return []

        # Sort by date (ascending)
        df.sort_values('date', inplace=True)

        # Convert to list of dicts
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": row["date"],
                "nav": row["nav"],
                "acc_nav": row.get("acc_nav", row["nav"]),
            })

        logger.info(f"获取净值历史完成：{fund_code}, {len(result)} 条记录")
        return result

    def _fetch_open_fund_nav(
        self,
        fund_code: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Fetch NAV history for open-ended funds (东方财富数据源)."""
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")

        # Check if DataFrame is empty
        if df.empty:
            logger.warning(f"fund_open_fund_info_em returned empty data for {fund_code}")
            return pd.DataFrame()

        # Standardize column names
        column_mapping = {
            "净值日期": "date",
            "单位净值": "nav",
            "累计净值": "acc_nav",
            "日增长率": "daily_growth",
        }

        # Rename columns if they exist
        available_cols = {col: column_mapping.get(col, col) for col in df.columns}
        df = df.rename(columns=available_cols)

        # Parse date
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date

        # Filter by date range
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

        # Parse NAV values
        df['nav'] = df['nav'].apply(lambda x: float(x) if pd.notna(x) and x > 0 else 0.0)
        if 'acc_nav' not in df.columns:
            df['acc_nav'] = df['nav']
        else:
            df['acc_nav'] = df['acc_nav'].apply(lambda x: float(x) if pd.notna(x) and x > 0 else df['nav'])

        return df[['date', 'nav', 'acc_nav']]

    def _fetch_etf_nav(
        self,
        fund_code: str,
        start_date: date,
        end_date: date
    ) -> pd.DataFrame:
        """Fetch NAV history for ETF funds (东方财富数据源)."""
        try:
            df = ak.fund_etf_fund_info_em(
                fund=fund_code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d")
            )
        except Exception as e:
            logger.warning(f"ETF API failed for {fund_code}: {e}")
            return pd.DataFrame()

        # Check if DataFrame is empty
        if df.empty:
            logger.warning(f"fund_etf_fund_info_em returned empty data for {fund_code}")
            return pd.DataFrame()

        # Standardize column names
        column_mapping = {
            "净值日期": "date",
            "单位净值": "nav",
            "累计净值": "acc_nav",
            "涨跌幅": "daily_growth",
        }

        # Rename columns if they exist
        available_cols = {col: column_mapping.get(col, col) for col in df.columns}
        df = df.rename(columns=available_cols)

        # Parse date
        df['date'] = pd.to_datetime(df['date'], errors='coerce').dt.date

        # Filter by date range (already filtered by API, but double-check)
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]

        # Parse NAV values
        df['nav'] = df['nav'].apply(lambda x: float(x) if pd.notna(x) and x > 0 else 0.0)
        if 'acc_nav' not in df.columns:
            df['acc_nav'] = df['nav']
        else:
            df['acc_nav'] = df['acc_nav'].apply(lambda x: float(x) if pd.notna(x) and x > 0 else df['nav'])

        return df[['date', 'nav', 'acc_nav']]

    def _validate_nav_history(self, history: list[dict]) -> bool:
        """Validate NAV history data quality.

        Args:
            history: List of NAV records

        Returns:
            True if valid, False otherwise
        """
        if not history:
            return False

        if len(history) < 10:  # Minimum data points
            logger.warning(f"NAV history too short: {len(history)} records")
            return False

        # Check required fields and positive values
        for record in history:
            if "date" not in record or "nav" not in record:
                logger.warning("Missing required field in NAV record")
                return False
            if record["nav"] <= 0:
                logger.warning("Invalid NAV value <= 0")
                return False

        logger.info(f"NAV 历史验证通过：{len(history)} 条记录")
        return True

    def _parse_nav_value(self, value: Any) -> float:
        """Parse NAV value string to float.

        Args:
            value: Raw value (string or numeric)

        Returns:
            Parsed float value, or 0.0 if invalid
        """
        if value is None or pd.isna(value):
            return 0.0

        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

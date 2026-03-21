"""数据质量校验与缺失容错模块."""
import logging
from typing import Any

from shared.logger import get_logger

logger = get_logger(__name__)


class DataValidationError(Exception):
    """数据校验异常."""

    def __init__(self, message: str, field: str | None = None):
        self.message = message
        self.field = field
        super().__init__(self.message)


# 基金类型白名单
FUND_TYPE_WHITELIST = {
    "股票型",
    "混合型",
    "债券型",
    "指数型",
    "QDII",
    "FOF",
    "货币型",
}

# 必填字段定义
FUND_INFO_REQUIRED_FIELDS = {"fund_code", "fund_name"}
NAV_HISTORY_REQUIRED_FIELDS = {"date", "nav"}


def validate_fund_info(data: dict[str, Any]) -> dict[str, Any]:
    """验证基金基本信息。

    Args:
        data: 基金信息字典

    Returns:
        验证通过的数据字典

    Raises:
        DataValidationError: 校验失败时抛出异常
    """
    if not isinstance(data, dict):
        raise DataValidationError(
            f"基金信息必须为字典类型，当前类型：{type(data).__name__}",
            field="data"
        )

    # 检查必填字段
    missing_fields = FUND_INFO_REQUIRED_FIELDS - set(data.keys())
    if missing_fields:
        raise DataValidationError(
            f"基金信息缺失必填字段：{missing_fields}",
            field=str(missing_fields)
        )

    # 验证 fund_code 非空
    if not data.get("fund_code"):
        raise DataValidationError(
            "fund_code 不能为空",
            field="fund_code"
        )

    # 验证 fund_name 非空
    if not data.get("fund_name"):
        raise DataValidationError(
            "fund_name 不能为空",
            field="fund_name"
        )

    # 验证 fund_type 白名单
    fund_type = data.get("fund_type")
    if fund_type and fund_type not in FUND_TYPE_WHITELIST:
        logger.warning(
            f"基金类型 '{fund_type}' 不在白名单中，允许通过。白名单：{FUND_TYPE_WHITELIST}"
        )

    # 验证数字字段非负
    numeric_fields = ["fund_size", "management_fee", "custodian_fee", "subscription_fee", "manager_tenure"]
    for field in numeric_fields:
        value = data.get(field)
        if value is not None:
            try:
                num_value = float(value)
                if num_value < 0:
                    logger.warning(
                        f"基金 {data.get('fund_code')} 的 {field}={value} 为负值，允许通过"
                    )
            except (TypeError, ValueError):
                logger.warning(
                    f"基金 {data.get('fund_code')} 的 {field}={value} 无法转换为数字，允许通过"
                )

    return data


def validate_nav_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """验证净值历史记录。

    采用容错策略：跳过无效记录而非抛出异常。

    Args:
        history: 净值历史列表

    Returns:
        验证通过的有效记录列表

    Raises:
        DataValidationError: 当输入为空列表时抛出异常
    """
    if not isinstance(history, list):
        raise DataValidationError(
            f"净值历史必须为列表类型，当前类型：{type(history).__name__}",
            field="history"
        )

    if len(history) == 0:
        raise DataValidationError(
            "净值历史不能为空",
            field="history"
        )

    valid_records = []
    skipped_count = 0

    for idx, record in enumerate(history):
        # 检查记录是否为字典
        if not isinstance(record, dict):
            logger.warning(f"净值历史第 {idx} 条记录非字典类型，跳过：{type(record).__name__}")
            skipped_count += 1
            continue

        # 检查必填字段
        missing_fields = NAV_HISTORY_REQUIRED_FIELDS - set(record.keys())
        if missing_fields:
            logger.warning(
                f"净值历史第 {idx} 条记录缺失必填字段 {missing_fields}，跳过"
            )
            skipped_count += 1
            continue

        # 验证 nav 为正值
        nav = record.get("nav")
        if nav is not None:
            try:
                nav_value = float(nav)
                if nav_value <= 0:
                    logger.warning(
                        f"净值历史第 {idx} 条记录 nav={nav} 非正值，跳过"
                    )
                    skipped_count += 1
                    continue
            except (TypeError, ValueError):
                logger.warning(
                    f"净值历史第 {idx} 条记录 nav={nav} 无法转换为数字，跳过"
                )
                skipped_count += 1
                continue

        # 验证 acc_nav (如果存在) 为正值
        acc_nav = record.get("acc_nav")
        if acc_nav is not None:
            try:
                acc_nav_value = float(acc_nav)
                if acc_nav_value <= 0:
                    logger.warning(
                        f"净值历史第 {idx} 条记录 acc_nav={acc_nav} 非正值，跳过"
                    )
                    skipped_count += 1
                    continue
            except (TypeError, ValueError):
                logger.warning(
                    f"净值历史第 {idx} 条记录 acc_nav={acc_nav} 无法转换为数字，跳过"
                )
                skipped_count += 1
                continue

        valid_records.append(record)

    if skipped_count > 0:
        logger.info(
            f"净值历史校验完成：原始 {len(history)} 条，有效 {len(valid_records)} 条，跳过 {skipped_count} 条"
        )

    return valid_records

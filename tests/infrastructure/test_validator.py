"""数据质量校验器测试."""
from datetime import date, timedelta

import pytest

from infrastructure.datasource.validator import (
    DataValidationError,
    validate_fund_info,
    validate_nav_history,
)


class TestValidateFundInfo:
    """测试 validate_fund_info 函数."""

    def test_validate_fund_info_success(self):
        """测试验证成功场景."""
        data = {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "fund_type": "混合型",
            "manager_name": "张三",
            "manager_tenure": 5.5,
            "fund_size": 100.5,
            "management_fee": 0.015,
            "custodian_fee": 0.0025,
            "subscription_fee": 0.001,
        }

        result = validate_fund_info(data)

        assert result == data
        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "华夏成长混合"

    def test_validate_fund_info_minimal_success(self):
        """测试仅含必填字段的成功场景."""
        data = {
            "fund_code": "000001",
            "fund_name": "测试基金",
        }

        result = validate_fund_info(data)

        assert result["fund_code"] == "000001"
        assert result["fund_name"] == "测试基金"

    def test_validate_fund_info_missing_required(self):
        """测试缺失必填字段抛出异常."""
        # 缺失 fund_name
        data_missing_name = {"fund_code": "000001"}

        with pytest.raises(DataValidationError) as exc_info:
            validate_fund_info(data_missing_name)

        assert "缺失必填字段" in str(exc_info.value.message)
        assert "fund_name" in str(exc_info.value.message)

        # 缺失 fund_code
        data_missing_code = {"fund_name": "测试基金"}

        with pytest.raises(DataValidationError) as exc_info:
            validate_fund_info(data_missing_code)

        assert "缺失必填字段" in str(exc_info.value.message)
        assert "fund_code" in str(exc_info.value.message)

    def test_validate_fund_info_empty_code(self):
        """测试 fund_code 为空抛出异常."""
        data = {"fund_code": "", "fund_name": "测试基金"}

        with pytest.raises(DataValidationError) as exc_info:
            validate_fund_info(data)

        assert "fund_code 不能为空" in str(exc_info.value.message)

    def test_validate_fund_info_empty_name(self):
        """测试 fund_name 为空抛出异常."""
        data = {"fund_code": "000001", "fund_name": ""}

        with pytest.raises(DataValidationError) as exc_info:
            validate_fund_info(data)

        assert "fund_name 不能为空" in str(exc_info.value.message)

    def test_validate_fund_info_invalid_type(self):
        """测试输入非字典类型抛出异常."""
        with pytest.raises(DataValidationError) as exc_info:
            validate_fund_info("not a dict")  # type: ignore

        assert "必须为字典类型" in str(exc_info.value.message)

    def test_validate_fund_info_unknown_fund_type_warning(self):
        """测试未知基金类型记录警告但允许通过."""
        data = {
            "fund_code": "000001",
            "fund_name": "测试基金",
            "fund_type": "未知类型",
        }

        # 不应抛出异常
        result = validate_fund_info(data)
        assert result["fund_type"] == "未知类型"

    def test_validate_fund_info_negative_numeric_warning(self):
        """测试负值数字字段记录警告但允许通过."""
        data = {
            "fund_code": "000001",
            "fund_name": "测试基金",
            "fund_size": -100.5,
        }

        # 不应抛出异常
        result = validate_fund_info(data)
        assert result["fund_size"] == -100.5


class TestValidateNavHistory:
    """测试 validate_nav_history 函数."""

    def test_validate_nav_history_success(self):
        """测试净值验证成功场景."""
        history = [
            {"date": date.today() - timedelta(days=2), "nav": 1.5, "acc_nav": 2.0},
            {"date": date.today() - timedelta(days=1), "nav": 1.52, "acc_nav": 2.05},
            {"date": date.today(), "nav": 1.55, "acc_nav": 2.1},
        ]

        result = validate_nav_history(history)

        assert len(result) == 3
        assert result[0]["nav"] == 1.5
        assert result[2]["nav"] == 1.55

    def test_validate_nav_history_minimal_success(self):
        """测试仅含必填字段的成功场景."""
        history = [
            {"date": date.today(), "nav": 1.5},
        ]

        result = validate_nav_history(history)

        assert len(result) == 1
        assert result[0]["nav"] == 1.5

    def test_validate_nav_history_empty(self):
        """测试空数据抛出异常."""
        with pytest.raises(DataValidationError) as exc_info:
            validate_nav_history([])

        assert "净值历史不能为空" in str(exc_info.value.message)

    def test_validate_nav_history_not_list(self):
        """测试输入非列表类型抛出异常."""
        with pytest.raises(DataValidationError) as exc_info:
            validate_nav_history("not a list")  # type: ignore

        assert "必须为列表类型" in str(exc_info.value.message)

    def test_validate_nav_history_skip_invalid_record(self):
        """测试跳过无效记录（容错）."""
        history = [
            {"date": date.today() - timedelta(days=2), "nav": 1.5},
            {"date": date.today() - timedelta(days=1)},  # 缺失 nav
            {"date": date.today(), "nav": 1.55},
        ]

        result = validate_nav_history(history)

        assert len(result) == 2
        assert result[0]["nav"] == 1.5
        assert result[1]["nav"] == 1.55

    def test_validate_nav_history_skip_non_dict_record(self):
        """测试跳过非字典记录."""
        history = [
            {"date": date.today() - timedelta(days=1), "nav": 1.5},
            "invalid string",  # type: ignore
            {"date": date.today(), "nav": 1.55},
        ]

        result = validate_nav_history(history)

        assert len(result) == 2

    def test_validate_nav_history_skip_negative_nav(self):
        """测试跳过负值净值记录."""
        history = [
            {"date": date.today() - timedelta(days=2), "nav": 1.5},
            {"date": date.today() - timedelta(days=1), "nav": -1.0},
            {"date": date.today(), "nav": 1.55},
        ]

        result = validate_nav_history(history)

        assert len(result) == 2
        assert all(r["nav"] > 0 for r in result)

    def test_validate_nav_history_skip_zero_nav(self):
        """测试跳过零值净值记录."""
        history = [
            {"date": date.today() - timedelta(days=2), "nav": 1.5},
            {"date": date.today() - timedelta(days=1), "nav": 0},
            {"date": date.today(), "nav": 1.55},
        ]

        result = validate_nav_history(history)

        assert len(result) == 2

    def test_validate_nav_history_skip_invalid_acc_nav(self):
        """测试跳过 acc_nav 无效的记录."""
        history = [
            {"date": date.today() - timedelta(days=2), "nav": 1.5, "acc_nav": 2.0},
            {"date": date.today() - timedelta(days=1), "nav": 1.52, "acc_nav": -1.0},
            {"date": date.today(), "nav": 1.55, "acc_nav": 2.1},
        ]

        result = validate_nav_history(history)

        # 第二条记录 acc_nav 为负，应被跳过
        assert len(result) == 2

    def test_validate_nav_history_all_invalid_returns_empty(self):
        """测试所有记录均无效时返回空列表."""
        history = [
            {"date": date.today() - timedelta(days=2), "nav": -1.0},
            {"date": date.today() - timedelta(days=1), "nav": 0},
            {"nav": 1.5},  # 缺失 date
        ]

        result = validate_nav_history(history)

        assert len(result) == 0

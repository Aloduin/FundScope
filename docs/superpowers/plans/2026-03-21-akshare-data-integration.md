# AkShare 真实数据接入实施计划（最终修正版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Mock 数据源替换为真实 akshare API 调用，同时实现缓存层、数据质量校验和缺失容错机制。

**Architecture:**

* 保留 `AbstractDataSource` 接口不变，确保可插拔性
* `AkShareDataSource` 实现真实 API 调用 + 三层缓存（L1 内存 → L2 原始响应文件 → L3 Parquet/SQLite）
* 新增数据校验层，处理 API 异常、数据缺失、格式校验
* Service 层只通过配置切换真实 / mock 数据源，不改调用方式
* 真实 API 调用失败时，允许自动降级到 mock 数据，保证系统可运行

**Tech Stack:**

* `akshare`（基金数据源 API）
* `pandas` / `pyarrow`（数据处理）
* `cachetools.TTLCache`（L1 内存缓存）
* 文件系统 JSON（L2 原始响应缓存）
* Parquet / SQLite（L3 持久化存储）

---

## 一、实施原则

* 默认单元测试不依赖外网，不依赖 akshare 实时返回
* 真实 API 测试单独标记为 integration / online
* 数据源层必须遵循：

  1. 先查 L1
  2. 再查 L2
  3. 再查 L3
  4. 最后请求真实 API
* 真实 API 失败时：

  * 若存在缓存，则优先返回缓存
  * 若无缓存，则回退到 mock
* 所有真实数据在进入 domain/service 前必须经过校验
* 不允许 Service 层自己处理 akshare 细节，所有外部 API 适配都放在 datasource 层

---

## 二、文件结构总览

### 新增文件

| 文件                                                   | 职责                    |
| ---------------------------------------------------- | --------------------- |
| `docs/superpowers/research/akshare-api-reference.md` | akshare API 探测记录与最终参考 |
| `infrastructure/datasource/cache.py`                 | L1 内存缓存工具             |
| `infrastructure/datasource/raw_cache.py`             | L2 原始响应文件缓存           |
| `infrastructure/datasource/validator.py`             | 数据校验与清洗               |
| `tests/infrastructure/test_akshare_source.py`        | 数据源测试                 |
| `tests/infrastructure/test_cache.py`                 | 缓存测试                  |
| `tests/infrastructure/test_validator.py`             | 校验器测试                 |

### 修改文件

| 文件                                            | 修改内容                      |
| --------------------------------------------- | ------------------------- |
| `infrastructure/datasource/akshare_source.py` | 实现真实 API + Mock 回退 + 缓存整合 |
| `service/fund_service.py`                     | 支持配置切换真实 / mock 数据源       |
| `shared/config.py`                            | 增加数据源与缓存配置                |
| `README.md`                                   | 增加真实数据开关说明                |
| `docs/guides/quickstart.md`                   | 增加数据源使用说明                 |

---

# Task 1: 研究并探测 akshare API

**Files:**

* Research: akshare runtime exploration

* Output: `docs/superpowers/research/akshare-api-reference.md`

* [ ] **Step 1: 本地探测 akshare 基金相关 API**

目标：确认以下能力的真实可用调用方式，而不是仅凭记忆写文档：

1. 获取基金基本信息
2. 获取基金历史净值
3. 获取基金列表
4. 判断开放式基金 / ETF / LOF 的接口差异
5. 确认返回字段名、字段类型、异常行为

建议本地探测脚本：

```python
import akshare as ak

# 候选接口示例，逐个验证可用性与字段
# 这里只做探测，不直接固化到生产代码
```

* [ ] **Step 2: 编写 API 参考文档**

Create `docs/superpowers/research/akshare-api-reference.md`

建议文档结构：

```markdown
# AkShare API Reference for FundScope

## 目标
记录 FundScope 当前版本实际验证可用的 akshare 基金接口，而非理论接口。

## 已验证接口

### 1. 基金列表接口
- 接口名：
- 用途：
- 返回字段：
- 示例代码：
- 注意事项：

### 2. 基金净值历史接口
- 接口名：
- 适用基金类型：
- 返回字段：
- 示例代码：
- 注意事项：

### 3. 基金基本信息获取策略
- 直接接口是否存在：
- 若不存在，如何从基金列表/其他接口拼装：
- 默认值策略：

## 错误处理观察
- 网络异常
- 空 DataFrame
- 字段缺失
- 频率限制
```

* [ ] **Step 3: 提交**

```bash
git add docs/superpowers/research/akshare-api-reference.md
git commit -m "docs: 添加 akshare API 探测参考文档"
```

---

# Task 2: 实现真实 API 调用层（保留 Mock 回退）

**Files:**

* Modify: `infrastructure/datasource/akshare_source.py`
* Test: `tests/infrastructure/test_akshare_source.py`

## 关键修正规范

* 不把未验证的 akshare 接口名直接写死成“唯一方案”

* 真实 API 调用封装为内部私有方法

* `use_mock=False` 不等于“绝不回退”，真实失败时仍允许自动降级

* 测试分为：

  * 离线单元测试
  * 在线真实 API 测试（可选）

* [ ] **Step 1: 编写离线测试**

Create `tests/infrastructure/test_akshare_source.py`:

```python
"""Tests for AkShareDataSource."""
from infrastructure.datasource.akshare_source import AkShareDataSource


class TestAkShareDataSource:
    def test_mock_fund_info(self):
        datasource = AkShareDataSource(use_mock=True)
        info = datasource.get_fund_basic_info("000001")

        assert info["fund_code"] == "000001"
        assert "fund_name" in info
        assert "fund_type" in info

    def test_mock_nav_history(self):
        datasource = AkShareDataSource(use_mock=True)
        history = datasource.get_fund_nav_history("000001")

        assert len(history) > 0
        assert "date" in history[0]
        assert "nav" in history[0]
        assert isinstance(history[0]["nav"], float)
```

* [ ] **Step 2: 编写在线测试（可选）**

如果项目里使用 pytest marker，建议单独标记：

```python
import pytest
from infrastructure.datasource.akshare_source import AkShareDataSource


@pytest.mark.online
def test_real_api_fund_info():
    datasource = AkShareDataSource(use_mock=False)
    info = datasource.get_fund_basic_info("000001")
    assert info["fund_code"] == "000001"
    assert "fund_name" in info


@pytest.mark.online
def test_real_api_nav_history():
    datasource = AkShareDataSource(use_mock=False)
    history = datasource.get_fund_nav_history("000001")
    assert len(history) > 0
    assert "date" in history[0]
    assert "nav" in history[0]
```

* [ ] **Step 3: 实现数据源骨架**

Modify `infrastructure/datasource/akshare_source.py`:

```python
"""akshare data source implementation."""
from datetime import date, timedelta
import numpy as np
from shared.logger import get_logger
from .abstract import AbstractDataSource

logger = get_logger(__name__)


class AkShareDataSource(AbstractDataSource):
    """akshare data source with real API + mock fallback."""

    def __init__(self, use_mock: bool = False):
        self.use_mock = use_mock
        logger.info(f"AkShareDataSource initialized (mock={use_mock})")

    def get_fund_basic_info(self, fund_code: str) -> dict:
        if self.use_mock:
            return self._get_mock_fund_info(fund_code)

        try:
            return self._get_real_fund_info(fund_code)
        except Exception as e:
            logger.warning(f"Real API failed for {fund_code}: {e}, fallback to mock")
            return self._get_mock_fund_info(fund_code)

    def get_fund_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        if self.use_mock:
            return self._get_mock_nav_history(fund_code, start_date, end_date)

        try:
            return self._get_real_nav_history(fund_code, start_date, end_date)
        except Exception as e:
            logger.warning(f"Real API failed for {fund_code}: {e}, fallback to mock")
            return self._get_mock_nav_history(fund_code, start_date, end_date)

    def _get_real_fund_info(self, fund_code: str) -> dict:
        raise NotImplementedError

    def _get_real_nav_history(
        self,
        fund_code: str,
        start_date: date | None,
        end_date: date | None
    ) -> list[dict]:
        raise NotImplementedError

    def _get_mock_fund_info(self, fund_code: str) -> dict:
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

    def _get_mock_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=365 * 3)

        result = []
        current = start_date
        base_nav = 1.0

        while current <= end_date:
            if current.weekday() < 5:
                daily_return = np.random.normal(0.0005, 0.02)
                nav = round(base_nav * (1 + daily_return), 4)
                result.append({
                    "date": current,
                    "nav": float(nav),
                    "acc_nav": float(nav),
                })
                base_nav = nav
            current += timedelta(days=1)

        return result
```

* [ ] **Step 4: 运行离线测试**

```bash
uv run pytest tests/infrastructure/test_akshare_source.py -v
```

* [ ] **Step 5: 提交**

```bash
git add infrastructure/datasource/akshare_source.py tests/infrastructure/test_akshare_source.py
git commit -m "feat(datasource): 搭建真实 API 调用层骨架（带 Mock 回退）"
```

---

# Task 3: 实现 L1 内存缓存（TTL）

**Files:**

* Create: `infrastructure/datasource/cache.py`
* Modify: `infrastructure/datasource/akshare_source.py`
* Test: `tests/infrastructure/test_cache.py`

## 关键修正规范

* `cache.py` 必须有自己的 logger

* 缓存 key 必须包含方法名 + 关键参数

* L1 只缓存“已处理后的 Python 对象”，不直接缓存 DataFrame 原对象

* [ ] **Step 1: 创建缓存工具**

Create `infrastructure/datasource/cache.py`:

```python
"""Caching utilities for datasource layer."""
from functools import wraps
from typing import Any, Callable
from cachetools import TTLCache
from shared.logger import get_logger

logger = get_logger(__name__)

_L1_CACHE = TTLCache(maxsize=1000, ttl=1800)  # 30 minutes


def cached(key_prefix: str = ""):
    """Cache decorator with TTL."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(a) for a in args[1:])  # skip self
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            if cache_key in _L1_CACHE:
                logger.debug(f"L1 cache hit: {cache_key}")
                return _L1_CACHE[cache_key]

            result = func(*args, **kwargs)
            _L1_CACHE[cache_key] = result
            logger.debug(f"L1 cache miss: {cache_key}")
            return result

        return wrapper
    return decorator


def clear_l1_cache() -> None:
    """Clear L1 cache."""
    _L1_CACHE.clear()
```

* [ ] **Step 2: 应用到数据源**
  在 `akshare_source.py` 中对公开读取方法应用装饰器：

```python
from .cache import cached

class AkShareDataSource(AbstractDataSource):

    @cached(key_prefix="fund_info")
    def get_fund_basic_info(self, fund_code: str) -> dict:
        ...

    @cached(key_prefix="nav_history")
    def get_fund_nav_history(self, fund_code: str, start_date=None, end_date=None) -> list[dict]:
        ...
```

* [ ] **Step 3: 编写缓存测试**

Create `tests/infrastructure/test_cache.py`:

```python
"""Tests for datasource cache."""
from infrastructure.datasource.akshare_source import AkShareDataSource


def test_l1_cache_hits():
    datasource = AkShareDataSource(use_mock=True)

    info1 = datasource.get_fund_basic_info("000001")
    info2 = datasource.get_fund_basic_info("000001")

    assert info1 == info2
```

* [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/infrastructure/test_cache.py -v
```

* [ ] **Step 5: 提交**

```bash
git add infrastructure/datasource/cache.py infrastructure/datasource/akshare_source.py tests/infrastructure/test_cache.py
git commit -m "feat(datasource): 实现 L1 内存缓存（TTL 30 分钟）"
```

---

# Task 4: 实现 L2 原始响应缓存（文件系统）

**Files:**

* Create: `infrastructure/datasource/raw_cache.py`
* Modify: `infrastructure/datasource/akshare_source.py`

## 关键修正规范

* L2 缓存的是“原始响应或标准化后的轻量字典/列表”

* 必须处理 `date` / `datetime` 等 JSON 序列化问题

* 文件命名使用 `fund_code + data_type + date_suffix`

* 超期缓存允许读取失败后静默忽略

* [ ] **Step 1: 实现原始缓存**

Create `infrastructure/datasource/raw_cache.py`:

```python
"""Raw response cache for datasource."""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from shared.logger import get_logger
from shared.config import CACHE_DIR, L2A_CACHE_TTL_DAYS

logger = get_logger(__name__)


def _json_default(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Path):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def get_cache_path(fund_code: str, data_type: str, date_suffix: str) -> Path:
    return CACHE_DIR / f"{fund_code}_{data_type}_{date_suffix}.json"


def load_cached_response(fund_code: str, data_type: str):
    today = datetime.now().strftime("%Y%m%d")
    cache_path = get_cache_path(fund_code, data_type, today)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        cached_at = datetime.fromisoformat(payload["_cached_at"])
        if datetime.now() - cached_at > timedelta(days=L2A_CACHE_TTL_DAYS):
            return None

        logger.debug(f"L2 cache hit: {cache_path}")
        return payload["_data"]
    except Exception as e:
        logger.warning(f"L2 cache read failed: {e}")
        return None


def save_cached_response(fund_code: str, data_type: str, data) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    cache_path = get_cache_path(fund_code, data_type, today)

    payload = {
        "_cached_at": datetime.now().isoformat(),
        "_data": data,
    }

    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=_json_default)
        logger.debug(f"L2 cache saved: {cache_path}")
    except Exception as e:
        logger.warning(f"L2 cache write failed: {e}")
```

* [ ] **Step 2: 集成到数据源**
  原则：

* 公开方法先经过 L1

* 内部真实请求前先查 L2

* L2 命中则直接返回

* L2 未命中才真实拉取

* [ ] **Step 3: 提交**

```bash
git add infrastructure/datasource/raw_cache.py infrastructure/datasource/akshare_source.py
git commit -m "feat(datasource): 实现 L2 原始响应缓存（文件系统）"
```

---

# Task 5: 数据质量校验与缺失容错

**Files:**

* Create: `infrastructure/datasource/validator.py`

* Modify: `infrastructure/datasource/akshare_source.py`

* Test: `tests/infrastructure/test_validator.py`

* [ ] **Step 1: 实现校验器**

Create `infrastructure/datasource/validator.py`:

```python
"""Data quality validation for datasource responses."""
from shared.logger import get_logger

logger = get_logger(__name__)


class DataValidationError(Exception):
    """Raised when datasource validation fails."""


def validate_fund_info(data: dict) -> dict:
    required_fields = ["fund_code", "fund_name"]
    for field in required_fields:
        if field not in data:
            raise DataValidationError(f"Missing required field: {field}")
        if not data[field]:
            raise DataValidationError(f"Empty required field: {field}")

    valid_types = ["股票型", "混合型", "债券型", "指数型", "FOF", "QDII"]
    if data.get("fund_type") not in valid_types:
        logger.warning(f"Unknown fund_type: {data.get('fund_type')}, defaulting to 混合型")
        data["fund_type"] = "混合型"

    numeric_fields = ["fund_size", "management_fee", "custodian_fee", "subscription_fee", "manager_tenure"]
    for field in numeric_fields:
        try:
            value = float(data.get(field, 0) or 0)
            if value < 0:
                value = 0.0
            data[field] = value
        except (TypeError, ValueError):
            data[field] = 0.0

    data.setdefault("manager_name", "")
    return data


def validate_nav_history(history: list[dict]) -> list[dict]:
    if not history:
        raise DataValidationError("NAV history is empty")

    validated = []
    for record in history:
        if "date" not in record or "nav" not in record:
            continue
        try:
            nav = float(record["nav"])
            if nav <= 0:
                continue
            acc_nav = float(record.get("acc_nav", nav) or nav)
            validated.append({
                "date": record["date"],
                "nav": nav,
                "acc_nav": acc_nav,
            })
        except (TypeError, ValueError):
            continue

    if not validated:
        raise DataValidationError("No valid NAV records after validation")

    return validated
```

* [ ] **Step 2: 编写校验测试**

Create `tests/infrastructure/test_validator.py`:

```python
"""Tests for datasource validator."""
import pytest
from infrastructure.datasource.validator import (
    validate_fund_info,
    validate_nav_history,
    DataValidationError,
)


def test_validate_fund_info_success():
    data = {
        "fund_code": "000001",
        "fund_name": "测试基金",
        "fund_type": "混合型",
        "fund_size": 10,
    }
    result = validate_fund_info(data)
    assert result["fund_code"] == "000001"


def test_validate_fund_info_missing_required():
    with pytest.raises(DataValidationError):
        validate_fund_info({"fund_name": "测试基金"})


def test_validate_nav_history_success():
    result = validate_nav_history([
        {"date": "2024-01-01", "nav": 1.01, "acc_nav": 1.01},
        {"date": "2024-01-02", "nav": 1.02, "acc_nav": 1.02},
    ])
    assert len(result) == 2


def test_validate_nav_history_empty():
    with pytest.raises(DataValidationError):
        validate_nav_history([])
```

* [ ] **Step 3: 集成到数据源**
  真实 API 拉取后统一进入：
* `validate_fund_info`
* `validate_nav_history`

校验失败触发：

* 优先回退缓存

* 再回退 mock

* [ ] **Step 4: 提交**

```bash
git add infrastructure/datasource/validator.py tests/infrastructure/test_validator.py infrastructure/datasource/akshare_source.py
git commit -m "feat(datasource): 实现数据质量校验与缺失容错"
```

---

# Task 6: 整合真实 akshare API（核心实现）

**Files:**

* Modify: `infrastructure/datasource/akshare_source.py`

## 关键修正规范

* 不直接假设某个接口适配所有基金类型

* 先以“已探测确认可用”的接口为主

* 若单接口不覆盖所有场景，则做：

  * 基金列表接口获取基本信息
  * 净值接口获取历史净值
  * 统一标准化输出

* [ ] **Step 1: 实现真实基金信息获取**

建议结构：

```python
import akshare as ak
import pandas as pd
from .validator import validate_fund_info, validate_nav_history, DataValidationError
from .raw_cache import load_cached_response, save_cached_response

class AkShareDataSource(AbstractDataSource):

    def _get_real_fund_info(self, fund_code: str) -> dict:
        cached = load_cached_response(fund_code, "fund_info")
        if cached:
            return validate_fund_info(cached)

        try:
            df = ak.fund_open_fund_daily_em()  # 以实际探测结果为准
            row_df = df[df["基金代码"] == fund_code]
            if row_df.empty:
                raise DataValidationError(f"Fund {fund_code} not found")

            row = row_df.iloc[0]
            result = {
                "fund_code": fund_code,
                "fund_name": row.get("基金名称", ""),
                "fund_type": row.get("基金类型", "混合型"),
                "manager_name": "",
                "manager_tenure": 0.0,
                "fund_size": float(row.get("最新规模/亿", 0) or 0),
                "management_fee": 0.015,
                "custodian_fee": 0.0025,
                "subscription_fee": 0.015,
            }
            result = validate_fund_info(result)
            save_cached_response(fund_code, "fund_info", result)
            return result
        except Exception as e:
            raise DataValidationError(str(e))
```

* [ ] **Step 2: 实现真实净值历史获取**

这里不要把某个接口名写死成唯一真理，建议实现成“适配层”：

```python
def _fetch_nav_df_from_akshare(self, fund_code: str, start_date: date, end_date: date):
    """Return raw NAV dataframe from a verified akshare API.
    Actual API should be chosen based on Task 1 research results.
    """
    raise NotImplementedError
```

然后：

```python
def _get_real_nav_history(self, fund_code: str, start_date: date | None, end_date: date | None) -> list[dict]:
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365 * 3)

    cached = load_cached_response(fund_code, "nav_history")
    if cached:
        return validate_nav_history(cached)

    try:
        df = self._fetch_nav_df_from_akshare(fund_code, start_date, end_date)

        result = []
        for _, row in df.iterrows():
            result.append({
                "date": pd.to_datetime(row["日期"]).date(),
                "nav": float(row["单位净值"]),
                "acc_nav": float(row.get("累计净值", row["单位净值"])),
            })

        result = validate_nav_history(result)
        save_cached_response(fund_code, "nav_history", result)
        return result
    except Exception as e:
        raise DataValidationError(str(e))
```

* [ ] **Step 3: 按探测结果补齐 `_fetch_nav_df_from_akshare()`**
  以 Task 1 的真实验证结果为准。

* [ ] **Step 4: 运行在线测试（可选）**

```bash
uv run pytest tests/infrastructure/test_akshare_source.py -m online -v
```

* [ ] **Step 5: 提交**

```bash
git add infrastructure/datasource/akshare_source.py
git commit -m "feat(datasource): 整合 akshare 真实 API 调用"
```

---

# Task 7: 与 L3 Parquet / SQLite 持久化整合

**Files:**

* Modify: `service/fund_service.py`
* Verify: existing `ParquetStore` / `sqlite_store.py`

## 关键修正规范

* datasource 负责 L1/L2 与真实 API

* service 继续负责：

  * 保存 Parquet
  * 保存 SQLite

* 不把 L3 持久化逻辑塞回 datasource

* [ ] **Step 1: 确认 `FundService` 仍走现有链路**
  即：

1. datasource 获取真实数据
2. service 计算指标 / 评分
3. 保存到 Parquet / SQLite

* [ ] **Step 2: 确认真实数据下 `ParquetStore.save_nav_history()` 可正常工作**

* `date`

* `nav`

* `acc_nav`

* `daily_return`

* `data_version`

* [ ] **Step 3: 确认真实数据下 SQLite 落库正常**
  至少验证：

* `fund_info`

* `fund_score`

* [ ] **Step 4: 提交（如有代码改动）**

```bash
git add service/fund_service.py
git commit -m "feat(service): 打通真实数据与 L3 持久化链路"
```

---

# Task 8: 配置切换与服务层接入

**Files:**

* Modify: `shared/config.py`

* Modify: `service/fund_service.py`

* [ ] **Step 1: 添加配置项**

Modify `shared/config.py`:

```python
# Data source configuration
USE_REAL_DATA = False
```

* [ ] **Step 2: Service 使用配置**

Modify `service/fund_service.py`:

```python
from shared.config import USE_REAL_DATA

class FundService:
    def __init__(self):
        init_db()
        self.datasource = AkShareDataSource(use_mock=not USE_REAL_DATA)
        logger.info(f"FundService initialized (real_data={USE_REAL_DATA})")
```

* [ ] **Step 3: 视情况同步到其他 Service**
  如果页面 / service 里还有直接构造 `AkShareDataSource()` 的地方，一并统一。

* [ ] **Step 4: 提交**

```bash
git add shared/config.py service/fund_service.py
git commit -m "feat(service): 支持配置切换真实/模拟数据源"
```

---

# Task 9: 最终测试与文档

**Files:**

* Modify: `README.md`

* Modify: `docs/guides/quickstart.md`

* [ ] **Step 1: 运行离线完整测试**

```bash
uv run pytest
```

Expected: 全部通过。

* [ ] **Step 2: 运行在线测试（可选）**

```bash
uv run pytest -m online -v
```

* [ ] **Step 3: 更新 README**

新增内容示例：

```markdown
### 数据源配置

默认使用 mock 数据。

切换到真实 akshare 数据：

1. 编辑 `shared/config.py`
2. 设置 `USE_REAL_DATA = True`
3. 重启应用

注意：
- 若真实 API 调用失败，系统会自动回退到 mock 数据
- 建议首次启用时先测试单只基金（如 000001）
```

* [ ] **Step 4: 更新 quickstart**
  补充：

* 是否需要联网

* 首次真实数据拉取可能较慢

* 缓存目录位置

* 如何清理缓存

* [ ] **Step 5: 提交**

```bash
git add README.md docs/guides/quickstart.md
git commit -m "docs: 更新真实数据接入与配置说明"
```

---

## 验证清单

* [ ] 真实 API 调用正常（至少 000001 等测试基金）
* [ ] L1 缓存命中（重复查询加速）
* [ ] L2 缓存生效（重启后仍可复用）
* [ ] L3 Parquet / SQLite 正常落库
* [ ] 数据校验通过（异常数据可处理）
* [ ] Mock 回退生效（API 失败时自动降级）
* [ ] 所有离线测试通过
* [ ] 在线测试可选通过
* [ ] 文档更新完成

---

## 建议执行顺序

```text
Task 1 研究与探测 API
    ↓
Task 2 搭建真实 API 骨架 + Mock 回退
    ↓
Task 3 L1 内存缓存
    ↓
Task 4 L2 原始响应缓存
    ↓
Task 5 数据校验与缺失容错
    ↓
Task 6 整合真实 akshare API
    ↓
Task 7 打通 L3 持久化
    ↓
Task 8 配置切换
    ↓
Task 9 完整测试与文档
```

---

## 里程碑

### 里程碑 A：真实 API 骨架跑通

* [x] 可切换真实 / mock 数据源
* [x] 真实失败自动回退
* [x] 单元测试不依赖外网

### 里程碑 B：缓存与校验完善

* [x] L1 / L2 缓存接入
* [x] 数据校验与缺失容错
* [x] 重启后仍可复用缓存

### 里程碑 C：真实数据全链路打通

* [x] Service 层无需大改
* [x] Parquet / SQLite 正常落库
* [x] UI 自动获得真实数据能力



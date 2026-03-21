# AkShare 真实数据接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Mock 数据源替换为真实 akshare API 调用，同时实现缓存层、数据质量校验和缺失容错机制

**Architecture:**
- 保留 AbstractDataSource 接口不变，确保可插拔性
- AkShareDataSource 实现真实 API 调用 + 三层缓存（内存→原始响应→Parquet/SQLite）
- 新增数据校验层，处理 API 异常、数据缺失、格式校验
- Service 层无需修改，依赖注入自动获得真实数据

**Tech Stack:**
- akshare (基金数据源 API)
- pandas/pyarrow (数据处理)
- functools.lru_cache (L1 内存缓存)
- 文件系统 (L2 原始响应缓存)
- Parquet/SQLite (L3 持久化存储)

---

## Task 1: 研究 akshare API 并确定调用方式

**Files:**
- Research: akshare documentation
- Output: `docs/superpowers/research/akshare-api-reference.md`

- [ ] **Step 1: 研究 akshare 基金数据 API**

查阅 akshare 文档，确定以下 API 调用方式：
1. 获取基金基本信息（基金名称、类型、经理、规模、费率）
2. 获取基金历史净值（单位净值、累计净值）
3. 获取基金持仓数据（可选，第二阶段）
4. 错误处理和限流机制

- [ ] **Step 2: 编写 akshare API 参考文档**

```markdown
# akshare API Reference

## 基金基本信息

```python
import akshare as ak

# 获取开放式基金基本信息
ak.fund_open_fund_info_em(fund="基金代码", indicator="单位净值走势")
# 返回：DataFrame[日期，单位净值，累计净值，日增长，日增长率]

# 获取所有基金列表
ak.fund_open_fund_daily_em()
# 返回：DataFrame[基金代码，基金名称，基金类型，单位净值，累计净值，...]
```

## 基金历史净值

```python
# 获取单只基金历史净值
ak.fund_etf_fund_info_em(fund="000001", start_date="20230101", end_date="20231231")
```

## 错误处理

- API 限流：每 N 秒请求一次
- 数据缺失：返回空 DataFrame
- 网络异常：抛出 HTTPError
```

- [ ] **Step 3: 提交**

```bash
git add docs/superpowers/research/akshare-api-reference.md
git commit -m "docs: 添加 akshare API 参考文档"
```

---

## Task 2: 实现真实 API 调用层（保留 Mock 回退）

**Files:**
- Modify: `infrastructure/datasource/akshare_source.py`
- Test: `tests/infrastructure/test_akshare_source.py`

- [ ] **Step 1: 编写测试（真实 API 调用验证）**

```python
# tests/infrastructure/test_akshare_source.py
def test_real_api_fund_info():
    """Test real API returns valid fund info."""
    datasource = AkShareDataSource(use_mock=False)
    info = datasource.get_fund_basic_info("000001")

    assert info["fund_code"] == "000001"
    assert "fund_name" in info
    assert info["fund_type"] in ["股票型", "混合型", "债券型", "指数型"]

def test_real_api_nav_history():
    """Test real API returns NAV history."""
    datasource = AkShareDataSource(use_mock=False)
    history = datasource.get_fund_nav_history("000001")

    assert len(history) > 0
    assert "date" in history[0]
    assert "nav" in history[0]
    assert all(isinstance(r["nav"], float) for r in history)
```

- [ ] **Step 2: 实现真实 API 调用（带 Mock 回退）**

```python
# infrastructure/datasource/akshare_source.py
"""akshare data source implementation."""
from datetime import date, timedelta
import akshare as ak
import pandas as pd
from shared.logger import get_logger
from .abstract import AbstractDataSource

logger = get_logger(__name__)


class AkShareDataSource(AbstractDataSource):
    """akshare data source with real API + mock fallback."""

    def __init__(self, use_mock: bool = False):
        """Initialize data source.

        Args:
            use_mock: If True, use mock data. If False, use real akshare API.
        """
        self.use_mock = use_mock
        logger.info(f"AkShareDataSource initialized (mock={use_mock})")

    def get_fund_basic_info(self, fund_code: str) -> dict:
        """Get basic fund information.

        Phase 2: Real akshare API with mock fallback.
        """
        if self.use_mock:
            return self._get_mock_fund_info(fund_code)

        try:
            return self._get_real_fund_info(fund_code)
        except Exception as e:
            logger.warning(f"Real API failed for {fund_code}: {e}, falling back to mock")
            return self._get_mock_fund_info(fund_code)

    def _get_real_fund_info(self, fund_code: str) -> dict:
        """Fetch real fund info from akshare."""
        # TODO: Implement akshare API calls
        pass

    def _get_mock_fund_info(self, fund_code: str) -> dict:
        """Mock data fallback."""
        # Existing mock implementation
        pass
```

- [ ] **Step 3: 运行测试验证**

```bash
uv run pytest tests/infrastructure/test_akshare_source.py -v
```

Expected: 2 tests pass (may skip if akshare not installed)

- [ ] **Step 4: 提交**

```bash
git add infrastructure/datasource/akshare_source.py tests/infrastructure/test_akshare_source.py
git commit -m "feat(datasource): 实现真实 API 调用层（带 Mock 回退）"
```

---

## Task 3: 实现 L1 内存缓存（TTL 缓存）

**Files:**
- Modify: `infrastructure/datasource/akshare_source.py`
- Create: `infrastructure/datasource/cache.py`

- [ ] **Step 1: 创建缓存装饰器**

```python
# infrastructure/datasource/cache.py
"""Caching utilities for data source."""
from functools import wraps
from datetime import datetime, timedelta
from typing import Any, Callable
from cachetools import TTLCache

# L1 cache: 30 minutes TTL
_L1_CACHE = TTLCache(maxsize=1000, ttl=1800)  # 30 minutes = 1800 seconds


def cached(key_prefix: str = ""):
    """Cache decorator with TTL.

    Args:
        key_prefix: Prefix for cache key

    Usage:
        @cached(key_prefix="fund_info")
        def get_fund_info(self, fund_code: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Build cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(a) for a in args[1:])  # Skip self
            key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
            cache_key = ":".join(key_parts)

            # Check cache
            if cache_key in _L1_CACHE:
                cached_at, value = _L1_CACHE[cache_key]
                logger.debug(f"Cache hit: {cache_key}")
                return value

            # Cache miss - call function
            result = func(*args, **kwargs)
            _L1_CACHE[cache_key] = (datetime.now(), result)
            logger.debug(f"Cache miss: {cache_key}")
            return result

        return wrapper
    return decorator
```

- [ ] **Step 2: 应用缓存到数据源**

```python
# infrastructure/datasource/akshare_source.py
from .cache import cached

class AkShareDataSource(AbstractDataSource):

    @cached(key_prefix="fund_info")
    def get_fund_basic_info(self, fund_code: str) -> dict:
        ...

    @cached(key_prefix="nav_history")
    def get_fund_nav_history(
        self,
        fund_code: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> list[dict]:
        ...
```

- [ ] **Step 3: 编写缓存测试**

```python
# tests/infrastructure/test_cache.py
def test_l1_cache_hits():
    """Test that L1 cache returns cached values."""
    datasource = AkShareDataSource(use_mock=True)

    # First call (cache miss)
    info1 = datasource.get_fund_basic_info("000001")

    # Second call (cache hit)
    info2 = datasource.get_fund_basic_info("000001")

    assert info1 == info2  # Same result
    # Should be faster due to cache
```

- [ ] **Step 4: 提交**

```bash
git add infrastructure/datasource/cache.py infrastructure/datasource/akshare_source.py tests/infrastructure/test_cache.py
git commit -m "feat(datasource): 实现 L1 内存缓存（TTL 30 分钟）"
```

---

## Task 4: 实现 L2 原始响应缓存（文件系统）

**Files:**
- Create: `infrastructure/datasource/raw_cache.py`
- Modify: `infrastructure/datasource/akshare_source.py`

- [ ] **Step 1: 实现原始响应缓存**

```python
# infrastructure/datasource/raw_cache.py
"""Raw response cache for akshare API responses."""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from shared.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path("data/cache")
CACHE_TTL_DAYS = 7


def get_cache_path(fund_code: str, data_type: str, date_suffix: str) -> Path:
    """Get cache file path."""
    return CACHE_DIR / f"{fund_code}_{data_type}_{date_suffix}.json"


def load_cached_response(fund_code: str, data_type: str) -> dict | None:
    """Load cached response if not expired."""
    today = datetime.now().strftime("%Y%m%d")
    cache_path = get_cache_path(fund_code, data_type, today)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r") as f:
            data = json.load(f)

        # Check expiration
        cached_at = datetime.fromisoformat(data["_cached_at"])
        if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
            logger.debug(f"Cache expired: {cache_path}")
            return None

        logger.debug(f"Cache hit: {cache_path}")
        return data["_data"]
    except Exception as e:
        logger.warning(f"Cache read failed: {e}")
        return None


def save_cached_response(fund_code: str, data_type: str, data: dict) -> None:
    """Save response to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y%m%d")
    cache_path = get_cache_path(fund_code, data_type, today)

    cache_data = {
        "_cached_at": datetime.now().isoformat(),
        "_data": data
    }

    try:
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)
        logger.debug(f"Cache saved: {cache_path}")
    except Exception as e:
        logger.warning(f"Cache write failed: {e}")
```

- [ ] **Step 2: 集成到数据源**

```python
# infrastructure/datasource/akshare_source.py
from .raw_cache import load_cached_response, save_cached_response

class AkShareDataSource(AbstractDataSource):

    def get_fund_basic_info(self, fund_code: str) -> dict:
        # Check L1 cache first (via decorator)
        # Check L2 cache
        cached = load_cached_response(fund_code, "fund_info")
        if cached:
            return cached

        # Fetch from API
        result = self._fetch_fund_info(fund_code)

        # Save to L2 cache
        save_cached_response(fund_code, "fund_info", result)
        return result
```

- [ ] **Step 3: 提交**

```bash
git add infrastructure/datasource/raw_cache.py infrastructure/datasource/akshare_source.py
git commit -m "feat(datasource): 实现 L2 原始响应缓存（7 天 TTL）"
```

---

## Task 5: 数据质量校验与缺失容错

**Files:**
- Create: `infrastructure/datasource/validator.py`
- Modify: `infrastructure/datasource/akshare_source.py`

- [ ] **Step 1: 实现数据校验器**

```python
# infrastructure/datasource/validator.py
"""Data quality validation for akshare responses."""
from typing import Any
from shared.logger import get_logger

logger = get_logger(__name__)


class DataValidationError(Exception):
    """Data validation failed."""
    pass


def validate_fund_info(data: dict) -> dict:
    """Validate fund basic info.

    Raises:
        DataValidationError: If validation fails
    """
    required_fields = ["fund_code", "fund_name"]

    for field in required_fields:
        if field not in data:
            raise DataValidationError(f"Missing required field: {field}")
        if not data[field]:
            raise DataValidationError(f"Empty required field: {field}")

    # Validate fund_type
    valid_types = ["股票型", "混合型", "债券型", "指数型", "FOF", "QDII"]
    if "fund_type" in data and data["fund_type"] not in valid_types:
        logger.warning(f"Unknown fund_type: {data['fund_type']}, defaulting to '混合型'")
        data["fund_type"] = "混合型"

    # Validate numeric fields
    numeric_fields = ["fund_size", "management_fee", "custodian_fee", "subscription_fee"]
    for field in numeric_fields:
        if field in data:
            try:
                value = float(data[field])
                if value < 0:
                    logger.warning(f"Negative {field}: {value}, setting to 0")
                    data[field] = 0.0
            except (TypeError, ValueError):
                logger.warning(f"Invalid {field}: {data[field]}, setting to 0")
                data[field] = 0.0

    return data


def validate_nav_history(history: list[dict]) -> list[dict]:
    """Validate NAV history.

    Raises:
        DataValidationError: If validation fails
    """
    if not history:
        raise DataValidationError("NAV history is empty")

    validated = []
    for record in history:
        if "date" not in record or "nav" not in record:
            continue  # Skip invalid records

        try:
            nav = float(record["nav"])
            if nav <= 0:
                continue  # Skip invalid NAV

            validated.append({
                "date": record["date"],
                "nav": nav,
                "acc_nav": float(record.get("acc_nav", nav))
            })
        except (TypeError, ValueError):
            continue

    if not validated:
        raise DataValidationError("No valid NAV records after validation")

    return validated
```

- [ ] **Step 2: 集成校验到数据源**

```python
# infrastructure/datasource/akshare_source.py
from .validator import validate_fund_info, validate_nav_history, DataValidationError

class AkShareDataSource(AbstractDataSource):

    def _get_real_fund_info(self, fund_code: str) -> dict:
        try:
            raw_data = ...  # akshare API call
            return validate_fund_info(raw_data)
        except DataValidationError as e:
            logger.error(f"Validation failed for {fund_code}: {e}")
            raise  # Re-raise to trigger mock fallback
```

- [ ] **Step 3: 提交**

```bash
git add infrastructure/datasource/validator.py infrastructure/datasource/akshare_source.py
git commit -m "feat(datasource): 实现数据质量校验与缺失容错"
```

---

## Task 6: 整合 akshare API 实现（核心调用）

**Files:**
- Modify: `infrastructure/datasource/akshare_source.py`

- [ ] **Step 1: 实现真实基金信息获取**

```python
# infrastructure/datasource/akshare_source.py
import akshare as ak
import pandas as pd

class AkShareDataSource(AbstractDataSource):

    def _get_real_fund_info(self, fund_code: str) -> dict:
        """Fetch real fund info from akshare."""
        try:
            # Get all funds daily data
            df = ak.fund_open_fund_daily_em()

            # Filter by fund code
            fund_row = df[df["基金代码"] == fund_code]

            if fund_row.empty:
                raise DataValidationError(f"Fund {fund_code} not found")

            row = fund_row.iloc[0]

            return {
                "fund_code": fund_code,
                "fund_name": row["基金名称"],
                "fund_type": self._map_fund_type(row["基金类型"]),
                "manager_name": "",  # akshare doesn't provide manager info in daily
                "manager_tenure": 0.0,
                "fund_size": float(row.get("最新规模/亿", 0) or 0),
                "management_fee": 0.015,  # Default values
                "custodian_fee": 0.0025,
                "subscription_fee": 0.015,
            }
        except Exception as e:
            logger.error(f"Failed to fetch fund info for {fund_code}: {e}")
            raise DataValidationError(str(e))

    def _map_fund_type(self, fund_type_str: str) -> str:
        """Map akshare fund type to our types."""
        type_mapping = {
            "股票型": "股票型",
            "混合型": "混合型",
            "债券型": "债券型",
            "指数型": "指数型",
            "QDII": "QDII",
            "FOF": "FOF",
        }
        return type_mapping.get(fund_type_str, "混合型")
```

- [ ] **Step 2: 实现真实净值历史获取**

```python
    def _get_real_nav_history(self, fund_code: str, start_date: date, end_date: date) -> list[dict]:
        """Fetch real NAV history from akshare."""
        try:
            df = ak.fund_etf_fund_info_em(
                fund=fund_code,
                start_date=start_date.strftime("%Y%m%d"),
                end_date=end_date.strftime("%Y%m%d")
            )

            result = []
            for _, row in df.iterrows():
                result.append({
                    "date": pd.to_datetime(row["日期"]).date(),
                    "nav": float(row["单位净值"]),
                    "acc_nav": float(row.get("累计净值", row["单位净值"]))
                })

            return validate_nav_history(result)
        except Exception as e:
            logger.error(f"Failed to fetch NAV history for {fund_code}: {e}")
            raise DataValidationError(str(e))
```

- [ ] **Step 3: 运行端到端测试**

```bash
uv run pytest tests/infrastructure/test_akshare_source.py::test_real_api_fund_info -v
uv run pytest tests/infrastructure/test_akshare_source.py::test_real_api_nav_history -v
```

- [ ] **Step 4: 提交**

```bash
git add infrastructure/datasource/akshare_source.py
git commit -m "feat(datasource): 整合 akshare API 真实调用"
```

---

## Task 7: Service 层配置切换

**Files:**
- Modify: `service/fund_service.py`
- Modify: `shared/config.py`

- [ ] **Step 1: 添加配置项**

```python
# shared/config.py
# Data source configuration
USE_REAL_DATA = False  # Set to True to use real akshare API
```

- [ ] **Step 2: 更新 Service 使用配置**

```python
# service/fund_service.py
from shared.config import USE_REAL_DATA

class FundService:
    def __init__(self):
        init_db()
        self.datasource = AkShareDataSource(use_mock=not USE_REAL_DATA)
        logger.info(f"FundService initialized (real_data={USE_REAL_DATA})")
```

- [ ] **Step 3: 提交**

```bash
git add shared/config.py service/fund_service.py
git commit -m "feat(service): 支持配置切换真实/模拟数据源"
```

---

## Task 8: 最终测试与文档

**Files:**
- Modify: `README.md`
- Modify: `docs/guides/quickstart.md`

- [ ] **Step 1: 运行完整测试套件**

```bash
uv run pytest
```

Expected: 134+ tests pass

- [ ] **Step 2: 更新 README**

Add section about real data support:

```markdown
### 数据源配置

MVP 阶段默认使用 mock 数据。切换到真实 akshare 数据：

1. 编辑 `shared/config.py`
2. 设置 `USE_REAL_DATA = True`
3. 重启应用
```

- [ ] **Step 3: 提交**

```bash
git add README.md docs/guides/quickstart.md shared/config.py service/fund_service.py
git commit -m "docs: 更新数据源配置说明"
```

---

## 验证清单

- [ ] 真实 API 调用正常（000001 等测试基金）
- [ ] L1 缓存命中（重复查询加速）
- [ ] L2 缓存回退（重启后仍有效）
- [ ] 数据校验通过（异常数据处理）
- [ ] Mock 回退生效（API 失败时自动降级）
- [ ] 所有测试通过（134+ 测试）
- [ ] 文档更新完成

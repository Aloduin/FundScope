# FundScope MVP 实施计划（最终冻结版）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 FundScope MVP 主链路：数据获取 → 指标计算 → 基金评分 → 赛道分类 → 持仓分析 → 虚拟账户 → Streamlit 三页面

**Architecture:** 四层架构（ui → service → domain → infrastructure），domain 层零 IO，基础设施层封装 akshare 和存储

**Tech Stack:** Python 3.13, akshare, pandas, numpy, pyarrow, streamlit, plotly, cachetools, pytest

---

## 一、执行原则

* 每个 Task 完成后，必须先跑对应测试，再提交 commit
* 不允许跨 Task 累积未修复失败测试
* 每个 Task 完成后保持主分支可运行
* MVP 第一阶段优先保证三条主链路打通：

  1. 输入基金代码 → 拉数据 → 算指标 → 出评分
  2. 手动录入持仓 → 算 effective_n → 出诊断建议
  3. 创建虚拟账户 → 买入基金 → 更新持仓与账户汇总
* UI 第一阶段只追求“能用”，不追求美化和复杂组件抽象
* 数据源第一阶段允许使用 mock，第二阶段替换为真实 akshare 调用

---

## 二、文件结构总览

### 基础设施层（infrastructure）

| 文件                                            | 职责                      |
| --------------------------------------------- | ----------------------- |
| `infrastructure/datasource/abstract.py`       | AbstractDataSource 接口定义 |
| `infrastructure/datasource/akshare_source.py` | akshare 数据源实现           |
| `infrastructure/storage/parquet_store.py`     | Parquet 时序数据读写          |
| `infrastructure/storage/sqlite_store.py`      | SQLite 业务数据读写           |

### 领域层（domain）

| 文件                                   | 职责                                                  |
| ------------------------------------ | --------------------------------------------------- |
| `domain/fund/models.py`              | FundInfo, FundNav, FundMetrics, FundScore dataclass |
| `domain/fund/metrics.py`             | 指标计算（夏普、回撤、波动率等）                                    |
| `domain/fund/scorer.py`              | 多维度加权评分（支持动态权重）                                     |
| `domain/fund/classifier.py`          | 赛道分类（关键词 + 手动覆盖）                                    |
| `domain/portfolio/models.py`         | Position, Portfolio, PortfolioDiagnosis             |
| `domain/portfolio/analyzer.py`       | 组合诊断（集中度、赛道重叠、有效持仓数）                                |
| `domain/backtest/models.py`          | Signal, BacktestResult                              |
| `domain/backtest/engine.py`          | 回测引擎（含独立账户状态）                                       |
| `domain/backtest/strategies/base.py` | Strategy 接口 + CompositeStrategy 骨架                  |
| `domain/simulation/models.py`        | VirtualAccount, Trade                               |
| `domain/simulation/account.py`       | 虚拟账户操作逻辑                                            |

### 服务层（service）

| 文件                              | 职责               |
| ------------------------------- | ---------------- |
| `service/fund_service.py`       | 数据获取 + 评分 + 分类编排 |
| `service/portfolio_service.py`  | 持仓分析编排           |
| `service/simulation_service.py` | 模拟账户编排           |
| `service/backtest_service.py`   | 回测编排骨架           |

### 用户界面层（ui）

| 文件                            | 职责           |
| ----------------------------- | ------------ |
| `ui/app.py`                   | Streamlit 入口 |
| `ui/pages/1_fund_research.py` | 基金研究页        |
| `ui/pages/2_portfolio.py`     | 持仓诊断页        |
| `ui/pages/3_strategy_lab.py`  | 策略验证中心       |

### 共享模块（shared）

| 文件                 | 职责                  |
| ------------------ | ------------------- |
| `shared/config.py` | 所有可调参数（权重、阈值、路径、映射） |
| `shared/logger.py` | 统一日志                |

### 测试目录

| 目录                         | 职责                     |
| -------------------------- | ---------------------- |
| `tests/domain/fund/`       | domain/fund 子域测试       |
| `tests/domain/portfolio/`  | domain/portfolio 子域测试  |
| `tests/domain/simulation/` | domain/simulation 子域测试 |
| `tests/service/`           | service 层测试            |
| `tests/infrastructure/`    | 基础设施层测试                |

---

## 三、Task 1：项目骨架与共享模块

**Files:**

* Create: `shared/config.py`

* Create: `shared/logger.py`

* Create: `tests/__init__.py`

* Modify: `pyproject.toml`

* [ ] **Step 1: 添加项目依赖**

编辑 `pyproject.toml`：

```toml
[project]
name = "fundscope"
version = "0.1.0"
description = "数据驱动 + 策略可验证 + 决策可解释 的基金投资系统"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "akshare>=1.0.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pyarrow>=14.0.0",
    "streamlit>=1.30.0",
    "plotly>=5.18.0",
    "cachetools>=5.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.21.0",
]
```

* [ ] **Step 2: 同步依赖**

```bash
uv sync
```

* [ ] **Step 3: 创建 `shared/config.py`**

```python
"""FundScope 统一配置模块"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PARQUET_DIR = DATA_DIR / "parquet"
SQLITE_DB_PATH = DATA_DIR / "sqlite" / "fundscope.db"
CACHE_DIR = DATA_DIR / "cache"

PARQUET_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

FUND_TYPE_MAPPING = {
    "股票型": "equity",
    "混合型": "mixed",
    "债券型": "bond",
    "指数型": "index",
}
DEFAULT_FUND_TYPE = "mixed"

SCORE_WEIGHTS_BY_TYPE: dict[str, dict[str, float]] = {
    "equity": {
        "return": 0.35,
        "risk": 0.25,
        "stability": 0.20,
        "cost": 0.10,
        "size": 0.05,
        "manager": 0.05,
    },
    "bond": {
        "return": 0.20,
        "risk": 0.35,
        "stability": 0.25,
        "cost": 0.10,
        "size": 0.05,
        "manager": 0.05,
    },
    "index": {
        "return": 0.35,
        "risk": 0.25,
        "stability": 0.15,
        "cost": 0.15,
        "size": 0.05,
        "manager": 0.05,
    },
    "mixed": {
        "return": 0.30,
        "risk": 0.25,
        "stability": 0.20,
        "cost": 0.10,
        "size": 0.08,
        "manager": 0.07,
    },
}

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "红利低波": ["红利", "低波", "高股息", "dividend"],
    "半导体": ["半导体", "芯片", "集成电路", "科创芯片"],
    "医疗": ["医疗", "医药", "生物", "健康", "医健"],
    "AI": ["人工智能", "AI", "数字经济", "科技创新"],
    "消费": ["消费", "白酒", "食品", "零售"],
    "新能源": ["新能源", "光伏", "储能", "电池", "碳中和"],
    "债券": ["债券", "纯债", "信用债", "利率债"],
    "宽基指数": ["沪深 300", "中证 500", "中证 1000", "全 A"],
}

L1_CACHE_TTL_SECONDS = 30 * 60
L2A_CACHE_TTL_DAYS = 7

BACKTEST_DEFAULT_INITIAL_CASH = 100000.0
```

* [ ] **Step 4: 创建 `shared/logger.py`**

```python
"""FundScope 统一日志模块"""
import logging
import sys
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    log_dir = Path(__file__).parent.parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handler = logging.FileHandler(log_dir / f"{name}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [%(filename)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger
```

* [ ] **Step 5: 创建测试目录结构**

```bash
mkdir -p tests/domain/fund tests/domain/portfolio tests/domain/simulation tests/service tests/infrastructure
touch tests/__init__.py tests/domain/__init__.py tests/domain/fund/__init__.py tests/domain/portfolio/__init__.py tests/domain/simulation/__init__.py tests/service/__init__.py tests/infrastructure/__init__.py
```

* [ ] **Step 6: 创建 `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -v --tb=short
```

* [ ] **Step 7: 提交**

```bash
git add pyproject.toml shared/ pytest.ini tests/
git commit -m "feat: 项目骨架与共享模块（config, logger, pytest 配置）"
```

---

## 四、Task 2：基础设施层（数据源 + 存储）

**Files:**

* Create: `infrastructure/datasource/abstract.py`

* Create: `infrastructure/datasource/akshare_source.py`

* Create: `infrastructure/storage/parquet_store.py`

* Create: `infrastructure/storage/sqlite_store.py`

* [ ] **Step 1: 创建抽象数据源接口**

创建 `infrastructure/datasource/abstract.py`

* [ ] **Step 2: 实现 `akshare_source.py`（第一阶段 mock，可运行）**

```python
"""akshare 数据源实现"""
from datetime import date, timedelta
import numpy as np
from shared.logger import get_logger
from .abstract import AbstractDataSource

logger = get_logger(__name__)

class AkShareDataSource(AbstractDataSource):
    """MVP 第一阶段：mock 数据打通接口；第二阶段替换为真实 akshare 调用"""

    def get_fund_basic_info(self, fund_code: str) -> dict:
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

    def get_fund_nav_history(self, fund_code: str, start_date: date | None = None, end_date: date | None = None) -> list[dict]:
        logger.info(f"获取基金净值历史：{fund_code}")

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
                    "nav": nav,
                    "acc_nav": nav,
                })
                base_nav = nav
            current += timedelta(days=1)

        return result
```

* [ ] **Step 3: 创建 `parquet_store.py`**
* [ ] **Step 4: 创建 `sqlite_store.py`**

**硬性要求：**

* `sqlite_store.py` 必须提供 `init_db()`、`get_connection()`

* `init_db()` 必须可重复执行且幂等

* [ ] **Step 5: 编写基础设施测试**

* [ ] **Step 6: 运行**

```bash
pytest tests/infrastructure/ -v
```

* [ ] **Step 7: 提交**

```bash
git add infrastructure/ tests/infrastructure/
git commit -m "feat: 基础设施层（datasource, parquet, sqlite）"
```

---

## 五、Task 3：Domain 层 - 基金子域

### 关键修正规范

* `data_completeness` 使用“可算指标数 / 总指标数”口径

* `scorer.py` 第一阶段维持 `calculate_score(metrics, fund_type)` 签名

* 成本 / 规模 / 经理维度第一阶段使用占位分，第二阶段升级为 `calculate_score(info, metrics)`

* [ ] **Step 1: 创建 `domain/fund/models.py`**

* [ ] **Step 2: 编写 `test_models.py` 并通过**

* [ ] **Step 3: 创建 `metrics.py`**

* [ ] **Step 4: 编写 `test_metrics.py` 并通过**

* [ ] **Step 5: 创建 `scorer.py`**

* [ ] **Step 6: 编写 `test_scorer.py` 并通过**

* [ ] **Step 7: 创建 `classifier.py`**

* [ ] **Step 8: 编写 `test_classifier.py` 并通过**

* [ ] **Step 9: 运行**

```bash
pytest tests/domain/fund/ -v
```

* [ ] **Step 10: 提交**

```bash
git add domain/fund/ tests/domain/fund/
git commit -m "feat(domain/fund): 实现基金子域（models, metrics, scorer, classifier）"
```

---

## 六、Task 4：Domain 层 - 组合子域 + 模拟账户

### 关键修正规范

* `Portfolio.__post_init__()` 必须同时初始化 `created_at` 和 `updated_at`

* `VirtualAccount.positions` 使用明确类型 `list[Position]`

* `Trade` 必须包含 `account_id`

* `domain/simulation/account.py` 必须导入 `date`

* [ ] **Step 1: 创建 `domain/portfolio/models.py`**

* [ ] **Step 2: 编写 `test_models.py` 并通过**

* [ ] **Step 3: 创建 `domain/portfolio/analyzer.py`**

* [ ] **Step 4: 编写 `test_analyzer.py` 并通过**

* [ ] **Step 5: 创建 `domain/simulation/models.py`**

`Trade` 模型必须是：

```python
@dataclass
class Trade:
    trade_id: str
    account_id: str
    fund_code: str
    action: Literal["BUY", "SELL"]
    amount: float
    nav: float
    shares: float
    trade_date: date
    reason: str
```

* [ ] **Step 6: 创建 `domain/simulation/account.py`**

**硬性要求：**

* `buy()` / `sell()` 创建 `Trade` 时必须写入 `account_id`

* 买入后若 `Position.cost_nav` 为空，设置为成交净值

* 再次买入同一基金时，允许先维持简单逻辑：`cost_nav` 不做复杂加权平均

* 后续可升级，但 MVP 保持可运行

* [ ] **Step 7: 编写 `test_account.py` 并通过**

* [ ] **Step 8: 运行**

```bash
pytest tests/domain/portfolio/ tests/domain/simulation/ -v
```

* [ ] **Step 9: 提交**

```bash
git add domain/portfolio/ domain/simulation/ tests/domain/portfolio/ tests/domain/simulation/
git commit -m "feat(domain): 实现组合分析与虚拟账户子域"
```

---

## 七、Task 5：Service 层编排

### 关键修正规范

* `FundService`、`PortfolioService`、`SimulationService` 的构造函数里都先调用 `init_db()`

* `simulation_service.py` 不允许全量重复插入历史交易

* 账户更新逻辑拆成：

  * 更新账户 cash
  * 全量重写持仓
  * 仅追加最新交易

* `fund_service.py` 保存 `sectors` 和 `missing_dimensions` 时，建议使用 JSON 序列化而不是 `str()`

* [ ] **Step 1: 创建 `service/fund_service.py`**

* [ ] **Step 2: 编写 `test_fund_service.py` 并通过**

* [ ] **Step 3: 创建 `service/portfolio_service.py`**

* [ ] **Step 4: 编写 `test_portfolio_service.py` 并通过**

* [ ] **Step 5: 创建 `service/simulation_service.py`**

* [ ] **Step 6: 编写 `test_simulation_service.py` 并通过**

* [ ] **Step 7: 运行**

```bash
pytest tests/service/ -v
```

* [ ] **Step 8: 提交**

```bash
git add service/ tests/service/
git commit -m "feat(service): 实现服务层编排"
```

---

## 八、Task 6：Streamlit UI 三页面

### 关键修正规范

* UI 第一阶段只追求可用，不做复杂组件抽象
* 页面 3 的持仓估值不能统一写死为 `1.0`
* 默认估值优先使用 `Position.cost_nav`，若为空再退回 `1.0`

示例：

```python
nav_map = {p.fund_code: (p.cost_nav or 1.0) for p in account.positions}
```

* [ ] **Step 1: 创建 `ui/app.py`**
* [ ] **Step 2: 创建 `ui/pages/1_fund_research.py`**
* [ ] **Step 3: 创建 `ui/pages/2_portfolio.py`**
* [ ] **Step 4: 创建 `ui/pages/3_strategy_lab.py`**
* [ ] **Step 5: 运行**

```bash
streamlit run ui/app.py
```

* [ ] **Step 6: 页面验收**

  * 页面 1：输入 `000001`，显示基金信息、评分、指标
  * 页面 2：录入 2 只基金，显示 `effective_n` 和建议
  * 页面 3：创建账户 10 万，买入 5 万，显示正确现金和持仓

* [ ] **Step 7: 提交**

```bash
git add ui/
git commit -m "feat(ui): 实现 Streamlit 三页面"
```

---

## 九、执行顺序与依赖

```text
Task 1 (项目骨架)
    ↓
Task 2 (基础设施：数据源 + 存储)
    ↓
Task 3 (基金子域：models + metrics + scorer + classifier)
    ↓
Task 4 (组合子域 + 模拟账户)
    ↓
Task 5 (Service 层编排)
    ↓
Task 6 (Streamlit UI)
```

**关键里程碑：**

1. Task 1 完成后 → 可运行 `pytest`
2. Task 2 完成后 → 接口层可返回 mock 数据
3. Task 3 完成后 → 可计算基金评分
4. Task 4 完成后 → 可跑虚拟账户基础买卖
5. Task 5 完成后 → 三条主链路可端到端调用
6. Task 6 完成后 → Streamlit 三页面可访问

---

## 十、验收标准

### 基础设施验收

* [ ] `pytest tests/infrastructure/ -v` 全部通过
* [ ] `AkShareDataSource` 接口可调用，返回数据结构正确（MVP 第一阶段允许 mock）
* [ ] Parquet 文件正确生成到 `data/parquet/<fund_code>.parquet`
* [ ] SQLite 数据库正确初始化，包含所有表结构

### Domain 层验收

* [ ] `pytest tests/domain/ -v` 全部通过
* [ ] `FundMetrics` 正确计算年化收益、最大回撤、波动率、夏普
* [ ] `FundScore` 支持缺失维度降权
* [ ] `classifier` 正确识别多标签赛道
* [ ] `Portfolio` 正确计算 `effective_n`
* [ ] `VirtualAccount` 支持买卖与权益计算

### Service 层验收

* [ ] `pytest tests/service/ -v` 全部通过
* [ ] `fund_service` 端到端返回 `FundScore` 对象，`data_completeness > 0`
* [ ] `portfolio_service` 正确计算 `effective_n`
* [ ] `simulation_service` 买卖后余额和持仓正确，且无重复交易写入问题

### UI 验收

* [ ] `streamlit run ui/app.py` 无报错启动
* [ ] 页面 1 可搜索基金并显示评分
* [ ] 页面 2 可录入持仓并显示诊断建议
* [ ] 页面 3 可创建虚拟账户并执行买卖

### 端到端验收

* [ ] 输入基金代码 `000001`，系统可获取数据、计算评分、显示结果
* [ ] 录入 3 只基金持仓，系统输出有效持仓数和重复赛道提示
* [ ] 创建虚拟账户（10 万），买入 5 万基金，账户显示正确持仓和收益

---

## 十一、第二阶段预留（不在本次 MVP 内）

* 真实 akshare 数据接入
* scorer 升级为 `calculate_score(info, metrics)`
* CSV 导入持仓
* 导入真实持仓到虚拟账户
* 回测引擎与三种策略填充
* CompositeStrategy 实现
* 更完整的净值曲线重建逻辑
* 更真实的持仓成本均价逻辑

---
# FundScope

**数据驱动 + 策略可验证 + 决策可解释**的基金投资辅助系统

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🎯 项目目标

FundScope 旨在帮助个人投资者从经验驱动转向数据与策略驱动的投资决策。系统提供：

- **基金分析** - 多维度评分体系，动态权重适配不同基金类型
- **持仓诊断** - 集中度分析、赛道重叠检测、优化建议生成
- **策略验证** - 虚拟账户模拟交易，策略回测框架

**系统不做**：替代用户决策、实盘交易对接、自动下单

---

## 🚀 快速开始

### 环境要求

- Python 3.13+
- uv（推荐）或 pip

### 安装

```bash
# 克隆仓库
git clone https://github.com/Aloduin/FundScope.git
cd FundScope

# 使用 uv 安装依赖（推荐）
uv sync

# 或使用 pip
pip install -e ".[dev]"
```

### 启动应用

```bash
# 启动 Streamlit 应用
uv run streamlit run ui/app.py
```

访问 `http://localhost:8501` 使用应用。

---

## 📊 功能特性

### 1. 基金研究

- **基金搜索** - 输入基金代码快速获取信息
- **多维度评分** - 收益、风险、稳定性、成本、规模、经理六维度
- **动态权重** - 股票型/债券型/指数型/混合型使用不同评分权重
- **赛道分类** - 关键词自动匹配 + 多标签支持
- **绩效指标** - 年化收益、最大回撤、波动率、夏普比率、胜率

### 2. 持仓诊断

- **持仓录入** - 手动输入基金代码和持仓金额
- **集中度分析** - HHI 指数、有效持仓数（effective_n）
- **赛道重叠** - 检测重复赛道配置
- **防守资产检测** - 提示是否缺乏防守型资产
- **优化建议** - 自动生成文字建议

### 3. 策略验证中心

- **虚拟账户** - 创建账户并设置初始资金
- **模拟交易** - 买入/卖出操作，实时跟踪持仓
- **交易记录** - 完整交易历史
- **持仓跟踪** - 成本净值、份额、市值

---

## 🏗️ 系统架构

### 四层架构（严格单向依赖）

```
ui (Streamlit)
    ↓
service（编排层）
    ↓
domain（纯计算层，零 IO）
    ↓
infrastructure（数据源 + 存储）
```

### 目录结构

```
fundscope/
├── infrastructure/
│   ├── datasource/
│   │   ├── abstract.py              # AbstractDataSource 接口
│   │   └── akshare_source.py        # akshare 实现（MVP mock）
│   └── storage/
│       ├── parquet_store.py         # 时序净值读写
│       └── sqlite_store.py          # 业务数据读写
│
├── domain/
│   ├── fund/
│   │   ├── models.py                # FundInfo, FundMetrics, FundScore
│   │   ├── metrics.py               # 指标计算
│   │   ├── scorer.py                # 多维度评分
│   │   └── classifier.py            # 赛道分类
│   ├── portfolio/
│   │   ├── models.py                # Position, Portfolio
│   │   └── analyzer.py              # 组合诊断
│   └── simulation/
│       ├── models.py                # VirtualAccount, Trade
│       └── account.py               # 虚拟账户操作
│
├── service/
│   ├── fund_service.py              # 基金分析编排
│   ├── portfolio_service.py         # 持仓分析编排
│   └── simulation_service.py        # 模拟账户编排
│
├── ui/
│   ├── app.py                       # Streamlit 入口
│   └── pages/
│       ├── 1_fund_research.py       # 基金研究页
│       ├── 2_portfolio.py           # 持仓诊断页
│       └── 3_strategy_lab.py        # 策略验证中心
│
├── shared/
│   ├── config.py                    # 统一配置
│   └── logger.py                    # 统一日志
│
├── tests/
│   ├── infrastructure/
│   ├── domain/
│   │   ├── fund/
│   │   ├── portfolio/
│   │   └── simulation/
│   └── service/
│
└── data/
    ├── parquet/                     # 基金净值时序数据
    ├── sqlite/                      # 业务数据库
    └── cache/                       # 原始响应缓存
```

---

## 📐 设计原则

### 1. 领域层零 IO

- `domain/` 层不调用 akshare
- 不读写文件/数据库
- 仅处理 dataclass / DataFrame

### 2. 数据源可插拔

所有数据获取通过 `AbstractDataSource` 接口：

```python
from infrastructure.datasource.abstract import AbstractDataSource

class AkShareDataSource(AbstractDataSource):
    def get_fund_basic_info(self, fund_code: str) -> dict:
        ...
    def get_fund_nav_history(self, fund_code: str) -> list[dict]:
        ...
```

### 3. 配置与逻辑分离

所有可调参数在 `shared/config.py`：

```python
SCORE_WEIGHTS_BY_TYPE: dict[str, dict[str, float]] = {
    "equity": {"return": 0.35, "risk": 0.25, ...},
    "bond": {"return": 0.20, "risk": 0.35, ...},
    ...
}
```

### 4. 数据结构优先

优先使用 dataclass 而非 dict：

```python
@dataclass
class FundInfo:
    fund_code: str
    fund_name: str
    fund_type: str
    primary_sector: str
    sectors: list[str]
    ...
```

---

## 🧪 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定模块测试
uv run pytest tests/domain/fund/ -v
uv run pytest tests/service/ -v

# 覆盖率报告
uv run pytest --cov=. --cov-report=html
```

### 测试覆盖

| 模块 | 测试数 | 状态 |
|------|--------|------|
| 基础设施 | 10 | ✅ |
| 基金子域 | 30 | ✅ |
| 组合子域 | 21 | ✅ |
| 模拟子域 | 18 | ✅ |
| 服务层 | 25 | ✅ |
| **总计** | **94** | **✅** |

---

## 📋 评分体系

### 动态权重（按基金类型）

| 维度 | 股票型 | 债券型 | 指数型 | 混合型 |
|------|--------|--------|--------|--------|
| 收益 | 35% | 20% | 35% | 30% |
| 风险 | 25% | 35% | 25% | 25% |
| 稳定性 | 20% | 25% | 15% | 20% |
| 成本 | 10% | 10% | 15% | 10% |
| 规模 | 5% | 5% | 5% | 8% |
| 经理 | 5% | 5% | 5% | 7% |

### 各维度计算规则

| 维度 | 指标 | 说明 |
|------|------|------|
| 收益 | 近 1/3/5 年收益、年化收益 | 多周期加权 |
| 风险 | 最大回撤、波动率、夏普比率 | 越低越好（回撤/波动） |
| 稳定性 | 月度胜率、回撤修复能力 | 衡量收益一致性 |
| 成本 | 管理费 + 托管费 + 申购费 | 总费率越低越好 |
| 规模 | 基金规模（亿元） | 过小（<2 亿）有清盘风险 |
| 经理 | 任职年限、历史稳定性 | 数据缺失时降权 |

---

## 🗂️ 数据规范

### Parquet（时序数据）

- 路径：`data/parquet/<fund_code>.parquet`
- 字段：`date, nav, acc_nav, daily_return, data_version`
- 按基金代码分文件，date 为索引

### SQLite（业务数据）

- 路径：`data/sqlite/fundscope.db`
- 表：`fund_info, fund_score, portfolio, trade_record, virtual_account` 等
- 所有表有主键和索引

---

## 🔧 开发指南

### 添加新数据源

1. 继承 `AbstractDataSource`
2. 实现 `get_fund_basic_info()` 和 `get_fund_nav_history()`
3. 在 service 层切换数据源

```python
from infrastructure.datasource.abstract import AbstractDataSource

class MyDataSource(AbstractDataSource):
    def get_fund_basic_info(self, fund_code: str) -> dict:
        # 你的实现
        pass

    def get_fund_nav_history(self, fund_code: str) -> list[dict]:
        # 你的实现
        pass
```

### 添加新指标

1. 在 `domain/fund/models.py` 添加 `FundMetrics` 字段
2. 在 `domain/fund/metrics.py` 实现计算逻辑
3. 在 `domain/fund/scorer.py` 集成到评分

### 添加新页面

1. 在 `ui/pages/` 创建 `<N>_<name>.py`
2. Streamlit 自动识别并添加到侧边栏

---

## 📝 提交规范

```bash
# 格式
<type>: <subject>

# type 说明
feat:     新功能
fix:      修复 bug
refactor: 重构
docs:     文档
test:     测试
chore:    其他
```

---

## 🚧 MVP 状态

### 已完成

- [x] 基金数据获取（mock）
- [x] 指标计算 + 基金评分
- [x] 赛道分类（关键词 + 多标签）
- [x] 持仓分析与组合诊断
- [x] 虚拟账户基础买卖
- [x] Streamlit 三页面

### 第二阶段（计划中）

- [ ] 真实 akshare 数据接入
- [ ] scorer 升级为 `calculate_score(info, metrics)`
- [ ] CSV 导入持仓
- [ ] 导入真实持仓到虚拟账户
- [ ] 回测引擎与策略填充
- [ ] CompositeStrategy 实现

---

## 📄 许可证

MIT License

---

## 🙏 致谢

- [akshare](https://github.com/akfamily/akshare) - 基金数据源
- [streamlit](https://streamlit.io/) - UI 框架

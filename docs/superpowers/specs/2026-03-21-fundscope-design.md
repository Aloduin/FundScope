# FundScope 系统设计文档

**日期：** 2026-03-21
**版本：** v1.1
**目标：** 数据驱动 + 策略可验证 + 决策可解释 的基金投资辅助系统

---

## 一、项目背景与目标

### 核心问题
个人投资者在支付宝等平台进行基金投资时，普遍面临以下问题：
- 持仓分散、赛道重复，缺乏结构化视角
- 选基依赖主观判断，缺乏量化评分依据
- 缺少明确的调仓与择时策略
- 无法在真实投资前验证策略有效性

### 设计目标
构建一个集「数据分析、选基对比、组合优化、策略辅助与模拟验证」于一体的工具平台，帮助用户从经验驱动转向数据与策略驱动。

**系统不做：** 替代用户决策、实盘交易对接、自动下单。

---

## 二、系统架构

### 分层架构（严格单向依赖）

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
│   │   └── akshare_source.py        # akshare 实现
│   └── storage/
│       ├── parquet_store.py         # 时序净值读写
│       └── sqlite_store.py          # 业务数据读写
│
├── domain/
│   ├── fund/
│   │   ├── models.py                # FundInfo, FundNav, FundMetrics, FundScore
│   │   ├── metrics.py               # 指标计算（夏普、回撤、波动率等）
│   │   ├── scorer.py                # 多维度加权评分
│   │   └── classifier.py            # 赛道分类逻辑
│   ├── portfolio/
│   │   ├── models.py                # Position, Portfolio, PortfolioDiagnosis
│   │   ├── analyzer.py              # 组合诊断
│   │   └── optimizer.py             # 优化建议生成
│   ├── backtest/
│   │   ├── models.py                # Signal, BacktestResult
│   │   ├── engine.py                # 回测引擎
│   │   └── strategies/
│   │       ├── base.py              # Strategy 抽象接口 + CompositeStrategy 骨架
│   │       ├── dca.py               # 定投策略
│   │       ├── ma_timing.py         # 均线择时
│   │       └── momentum.py          # 动量轮动
│   └── simulation/
│       ├── models.py                # VirtualAccount, Trade
│       └── account.py               # 虚拟账户操作逻辑
│
├── service/
│   ├── fund_service.py              # 数据获取 + 评分 + 分类编排
│   ├── portfolio_service.py         # 持仓分析编排
│   ├── backtest_service.py          # 回测编排
│   └── simulation_service.py        # 模拟账户编排
│
├── ui/
│   ├── app.py                       # Streamlit 入口
│   ├── pages/
│   │   ├── 1_fund_research.py       # 基金研究页
│   │   ├── 2_portfolio.py           # 持仓诊断页
│   │   └── 3_strategy_lab.py        # 策略验证中心
│   └── components/                  # 可复用 UI 组件
│
├── shared/
│   ├── config.py                    # 所有可调参数（权重、阈值、路径）
│   └── logger.py                    # 统一日志
│
└── data/
    ├── parquet/                     # 基金净值时序数据（按基金代码分文件）
    ├── sqlite/                      # 业务数据库
    └── cache/                       # akshare 原始响应缓存
```

---

## 三、核心数据模型

### 基金层

```python
@dataclass
class FundInfo:
    fund_code: str
    fund_name: str
    fund_type: str                # 股票型 / 混合型 / 债券型 / 指数型
    primary_sector: str           # 主赛道（用于组合诊断、横向对比）
    sectors: list[str]            # 全部赛道标签（支持多标签，如 ["AI", "半导体"]）
    sector_source: str            # "auto" | "auto_ambiguous" | "auto_unknown" | "manual"
    manager_name: str
    manager_tenure: float         # 年
    fund_size: float              # 亿元
    management_fee: float         # 管理费率
    custodian_fee: float          # 托管费率
    subscription_fee: float       # 申购费率
    data_version: str             # 数据版本号，格式 YYYYMMDD_<hash>

# 基金类型与动态权重的映射规则（shared/config.py）
FUND_TYPE_MAPPING = {
    "股票型": "equity",
    "混合型": "mixed",
    "债券型": "bond",
    "指数型": "index",
}
# 未匹配到的类型回退到 "mixed"

@dataclass
class FundNav:
    fund_code: str
    date: date
    nav: float               # 单位净值
    acc_nav: float           # 累计净值
    daily_return: float      # 日收益率

@dataclass
class FundMetrics:
    fund_code: str
    return_1y: float | None
    return_3y: float | None
    return_5y: float | None
    annualized_return: float | None
    max_drawdown: float | None
    volatility: float | None
    sharpe_ratio: float | None
    win_rate: float | None           # 月度胜率
    recovery_factor: float | None    # 回撤修复能力
    data_completeness: float         # 0.0~1.0，数据完整度

@dataclass
class FundScore:
    fund_code: str
    total_score: float
    return_score: float | None
    risk_score: float | None
    stability_score: float | None
    cost_score: float | None
    size_score: float | None
    manager_score: float | None
    data_completeness: float         # 评分可信度提示
    missing_dimensions: list[str]    # 缺失维度列表（存储时序列化为 JSON 字符串）
```

### 组合层

```python
@dataclass
class Position:
    fund_code: str
    fund_name: str
    amount: float            # 持仓金额（元）— 事实字段
    weight: float            # 持仓权重 = amount / portfolio.total_amount — 派生字段，每次组合变动后统一重算并落库
    shares: float | None     # 持仓份额（可选）
    cost_nav: float | None   # 成本净值（可选）

# weight 一致性原则：
# - amount 是事实字段，weight 是派生字段
# - 每次组合变动（买入/卖出/调仓）后，必须重新计算所有 position.weight 并落库
# - 禁止单独修改 weight 而不更新 amount

@dataclass
class Portfolio:
    portfolio_id: str
    positions: list[Position]
    total_amount: float
    effective_n: float       # 有效持仓数 = 1 / sum(weight^2)，衡量真实分散度
    created_at: datetime
    updated_at: datetime

@dataclass
class PortfolioDiagnosis:
    concentration_risk: float        # 集中度风险（HHI 指数）
    effective_n: float               # 有效持仓数
    sector_overlap: list[str]        # 重复赛道列表
    missing_defense: bool            # 是否缺乏防守资产
    style_balance: dict[str, float]  # 风格分布
    suggestions: list[str]           # 优化建议文字
```

### 策略与回测层

```python
@dataclass
class Signal:
    date: date
    fund_code: str
    action: Literal["BUY", "SELL", "REBALANCE", "HOLD"]
    confidence: float        # 信号强度 0.0~1.0（定投默认 0.5，深度低估可达 0.9）
    amount: float | None
    target_weight: float | None
    reason: str              # 决策可解释性，必填，不允许空字符串（engine 层断言非空）

@dataclass
class BacktestResult:
    strategy_name: str
    fund_code: str
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float                         # 策略胜率
    trade_count: int                        # 总交易次数
    signals: list[Signal]
    equity_curve: list[tuple[date, float]]  # 净值曲线
```

### 模拟账户层

```python
@dataclass
class Trade:
    trade_id: str
    fund_code: str
    action: Literal["BUY", "SELL"]
    amount: float
    nav: float               # 成交净值
    shares: float
    trade_date: date
    reason: str

@dataclass
class VirtualAccount:
    account_id: str
    initial_cash: float
    cash: float
    positions: list[Position]
    trades: list[Trade]
    equity_curve: list[tuple[date, float]]  # 净值曲线缓存；持久化到 virtual_account_equity_curve 表
    created_at: datetime

# equity_curve 维护规则：
# - 每次交易完成后，更新当日及之后所有日期的 equity 值
# - 每日首次访问账户时，若当日无曲线记录，则重建完整曲线并落库
```

---

## 四、评分体系设计

### 按基金类型的动态权重（shared/config.py）

不同基金类型使用不同权重，避免用同一套标准误判债券基金或红利基金。

```python
SCORE_WEIGHTS_BY_TYPE: dict[str, dict[str, float]] = {
    "equity": {       # 股票型
        "return":    0.35,
        "risk":      0.25,
        "stability": 0.20,
        "cost":      0.10,
        "size":      0.05,
        "manager":   0.05,
    },
    "bond": {         # 债券型
        "return":    0.20,
        "risk":      0.35,
        "stability": 0.25,
        "cost":      0.10,
        "size":      0.05,
        "manager":   0.05,
    },
    "index": {        # 指数型
        "return":    0.35,
        "risk":      0.25,
        "stability": 0.15,
        "cost":      0.15,  # 费率对指数基金更重要
        "size":      0.05,
        "manager":   0.05,
    },
    "mixed": {        # 混合型（默认兜底）
        "return":    0.30,
        "risk":      0.25,
        "stability": 0.20,
        "cost":      0.10,
        "size":      0.08,
        "manager":   0.07,
    },
}
```

`scorer.py` 根据 `FundInfo.fund_type` 选取对应权重，未匹配类型回退到 `mixed`。

### 各维度计算规则

| 维度 | 指标 | 说明 |
|------|------|------|
| 收益 | 近 1/3/5 年收益、年化收益 | 多周期加权平均 |
| 风险 | 最大回撤、波动率、夏普比率 | 越低越好（回撤/波动），越高越好（夏普） |
| 稳定性 | 月度胜率、回撤修复能力 | 衡量收益一致性 |
| 成本 | 管理费 + 托管费 + 申购费 | 总费率越低越好 |
| 规模 | 基金规模（亿元） | 过小（<2 亿）有清盘风险 |
| 基金经理 | 任职年限、历史稳定性 | 数据缺失时降权跳过 |

### 数据缺失处理
- 某维度数据缺失时，该维度权重重新分配给其他有数据的维度
- `FundScore.data_completeness` 记录实际参与评分的维度比例
- `FundScore.missing_dimensions` 列出缺失维度，UI 层展示提示

---

## 五、赛道分类设计

### 两层分类机制

**第一层：关键词自动匹配**

```python
# shared/config.py
SECTOR_KEYWORDS: dict[str, list[str]] = {
    "红利低波": ["红利", "低波", "高股息", "dividend"],
    "半导体":   ["半导体", "芯片", "集成电路", "科创芯片"],
    "医疗":     ["医疗", "医药", "生物", "健康", "医健"],
    "AI":       ["人工智能", "AI", "数字经济", "科技创新"],
    "消费":     ["消费", "白酒", "食品", "零售"],
    "新能源":   ["新能源", "光伏", "储能", "电池", "碳中和"],
    "债券":     ["债券", "纯债", "信用债", "利率债"],
    "宽基指数": ["沪深 300", "中证 500", "中证 1000", "全 A"],
}
```

多赛道命中规则：
- 按 `SECTOR_KEYWORDS` 字典顺序取第一个命中的赛道作为 `primary_sector`
- 所有命中的赛道加入 `sectors` 列表（支持多标签）
- 多命中时 `sector_source` 标记为 `"auto_ambiguous"`，UI 提示用户人工确认
- 无命中时 `primary_sector` 设为 `"未分类"`，`sectors` 为空列表，`sector_source` 为 `"auto_unknown"`

自动分类结果直接写入 `FundInfo.primary_sector`、`FundInfo.sectors` 和 `FundInfo.sector_source`，不额外入库。

**第二层：手动覆盖表（SQLite）**

```sql
CREATE TABLE fund_sector_override (
    fund_code   TEXT PRIMARY KEY,
    primary_sector  TEXT NOT NULL,
    sectors         TEXT NOT NULL,  -- JSON 字符串，如 '["AI", "半导体"]'
    updated_at  DATETIME NOT NULL
);
```

- 仅存储人工确认/修正的赛道映射
- 查询时优先使用此表，无记录则回退到 `FundInfo` 的自动分类结果
- UI 展示时：有覆盖记录标注 `manual`，否则标注 `auto` / `auto_ambiguous` / `auto_unknown`

---

## 六、缓存策略

三层存储，读取优先级从高到低：

```
L1：内存缓存（functools.lru_cache / TTLCache）
    - 同一会话内重复查询同一基金数据
    - TTL：30 分钟

L2a：原始响应缓存（data/cache/）
    - 存储 akshare 原始 JSON 响应
    - 文件命名：<fund_code>_<data_type>_<YYYYMMDD>.json
    - 超过 7 天自动清理
    - 目的：减少对 akshare 的重复网络请求

L2b：处理后持久化存储
    - 时序净值：data/parquet/<fund_code>.parquet（含 data_version 字段，格式 YYYYMMDD_<hash>）
    - 业务数据：data/sqlite/fundscope.db（评分、持仓、账户等）
    - 跨天持久化，长期保留
```

读取路径：L1 命中 → 返回；L2a 命中且未过期 → 解析后返回并写 L1；L2b 命中 → 返回并写 L1；全部未命中 → 请求 akshare → 写 L2a → 解析处理 → 写 L2b → 写 L1。

缓存刷新策略：
- 每日首次请求时检查数据是否为当天最新
- 非交易日不强制刷新
- 用户可手动触发强制刷新（清除 L1 + L2a，保留 L2b）

---

## 七、UI 页面设计

### 页面 1：基金研究

功能：
- 搜索基金（按代码或名称）
- 查看基金详情（指标、评分、数据完整度）
- 赛道分类展示（标注 auto/manual，多标签显示）
- 同赛道基金横向对比（评分排名、指标对比表）
- 手动修正赛道分类

### 页面 2：持仓诊断

功能：
- 手动录入持仓（基金代码 + 持仓金额）
- 持仓结构可视化（赛道分布饼图、集中度）
- 组合诊断报告：
  - 有效持仓数（effective_n）— 判断「看似很多，其实高度集中」
  - 重复赛道检测（基于多标签）
  - 缺乏防守资产提示
  - 风格失衡分析
- 优化建议（文字说明 + 调整方向）
- 预留 CSV 导入入口（第二阶段实现）

### 页面 3：策略验证中心

功能（第一阶段）：
- 虚拟账户创建（设置初始资金）
- 手动模拟买入 / 卖出 / 定投
- 持仓与收益统计（总收益、持仓市值、现金余额）
- 交易记录查看
- 净值曲线可视化（基于 `equity_curve` 缓存）

功能（第二阶段扩展）：
- 策略回测（DCA / 均线择时 / 动量轮动）
- 回测结果可视化（净值曲线、最大回撤、夏普比率、胜率）
- 导入真实持仓作为虚拟账户初始状态
- 组合策略（CompositeStrategy）— 均线 + 定投、动量 + 再平衡
- **策略解释面板** — 显示当前信号、reason、指标依据

---

## 八、回测规则

- T 日产生信号，T+1 净值成交  `# 简化回测假设`
- 禁止未来函数（仅使用当前及历史数据）
- 所有策略必须通过 `Strategy` 抽象接口实现
- 每个 Signal 必须包含 `reason` 字段（决策可解释性），engine 层断言非空
- 回测引擎（`backtest/engine.py`）内部维护独立的账户状态，**不依赖 `VirtualAccount`**；两者逻辑独立，互不复用
- 支持 `CompositeStrategy` 骨架（第二阶段实现）

### MVP 策略

| 策略 | 信号逻辑 |
|------|---------|
| 定投（DCA） | 固定周期固定金额买入，confidence=0.5 |
| 均线择时 | 价格上穿均线 BUY，下穿 SELL，confidence=0.6~0.8 |
| 动量轮动 | 定期选取近期收益最高的 N 只基金 REBALANCE，confidence=0.7 |

---

## 九、数据规范

### Parquet（时序数据）
- 路径：`data/parquet/<fund_code>.parquet`
- 字段：`date, nav, acc_nav, daily_return, data_version`
- 按基金代码分文件，date 为索引

### SQLite（业务数据）
- 路径：`data/sqlite/fundscope.db`
- 所有表必须有主键
- 必须建立索引（fund_code / date）

#### 表结构说明

```sql
-- 基金基本信息（含自动分类结果）
CREATE TABLE fund_info (
    fund_code        TEXT PRIMARY KEY,
    fund_name        TEXT NOT NULL,
    fund_type        TEXT,
    primary_sector   TEXT,
    sectors          TEXT,      -- JSON 字符串
    sector_source    TEXT,      -- 'auto' | 'auto_ambiguous' | 'auto_unknown' | 'manual'
    manager_name     TEXT,
    manager_tenure   REAL,
    fund_size        REAL,
    management_fee   REAL,
    custodian_fee    REAL,
    subscription_fee REAL,
    data_version     TEXT,
    updated_at       DATETIME NOT NULL
);
CREATE INDEX idx_fund_info_sector ON fund_info(primary_sector);

-- 评分结果缓存（missing_dimensions 序列化为 JSON 字符串）
CREATE TABLE fund_score (
    fund_code            TEXT PRIMARY KEY,
    total_score          REAL,
    return_score         REAL,
    risk_score           REAL,
    stability_score      REAL,
    cost_score           REAL,
    size_score           REAL,
    manager_score        REAL,
    data_completeness    REAL,
    data_version         TEXT,   -- 评分基于的数据版本，格式 YYYYMMDD_<hash>
    missing_dimensions   TEXT,   -- JSON 字符串，如 '["manager", "return_5y"]'
    scored_at            DATETIME NOT NULL
);
CREATE INDEX idx_fund_score_version ON fund_score(data_version);

-- 赛道手动覆盖（仅存人工确认结果）
CREATE TABLE fund_sector_override (
    fund_code       TEXT PRIMARY KEY,
    primary_sector  TEXT NOT NULL,
    sectors         TEXT NOT NULL,  -- JSON 字符串
    updated_at      DATETIME NOT NULL
);

-- 持仓组合头信息
CREATE TABLE portfolio (
    portfolio_id TEXT PRIMARY KEY,
    total_amount REAL,
    effective_n  REAL,
    created_at   DATETIME NOT NULL,
    updated_at   DATETIME NOT NULL
);

-- 持仓明细（Portfolio.positions 拆分存储）
CREATE TABLE portfolio_position (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    portfolio_id TEXT NOT NULL,
    fund_code    TEXT NOT NULL,
    fund_name    TEXT,
    amount       REAL NOT NULL,
    weight       REAL NOT NULL,
    shares       REAL,
    cost_nav     REAL,
    FOREIGN KEY (portfolio_id) REFERENCES portfolio(portfolio_id)
);
CREATE INDEX idx_portfolio_position_pid ON portfolio_position(portfolio_id);
CREATE INDEX idx_portfolio_position_code ON portfolio_position(fund_code);

-- 虚拟账户头信息
CREATE TABLE virtual_account (
    account_id   TEXT PRIMARY KEY,
    initial_cash REAL NOT NULL,
    cash         REAL NOT NULL,
    created_at   DATETIME NOT NULL
);

-- 虚拟账户持仓（VirtualAccount.positions 拆分存储）
CREATE TABLE virtual_account_position (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id  TEXT NOT NULL,
    fund_code   TEXT NOT NULL,
    fund_name   TEXT,
    amount      REAL NOT NULL,
    weight      REAL NOT NULL,
    shares      REAL,
    cost_nav    REAL,
    FOREIGN KEY (account_id) REFERENCES virtual_account(account_id)
);
CREATE INDEX idx_vap_account ON virtual_account_position(account_id);

-- 交易记录
CREATE TABLE trade_record (
    trade_id    TEXT PRIMARY KEY,
    account_id  TEXT NOT NULL,
    fund_code   TEXT NOT NULL,
    action      TEXT NOT NULL,   -- 'BUY' | 'SELL'
    amount      REAL NOT NULL,
    nav         REAL NOT NULL,
    shares      REAL NOT NULL,
    trade_date  DATE NOT NULL,
    reason      TEXT,
    FOREIGN KEY (account_id) REFERENCES virtual_account(account_id)
);
CREATE INDEX idx_trade_account ON trade_record(account_id);
CREATE INDEX idx_trade_date ON trade_record(trade_date);

-- 虚拟账户净值曲线（方案 B：持久化存储，提升页面 3 加载性能）
CREATE TABLE virtual_account_equity_curve (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL,
    date       DATE NOT NULL,
    equity     REAL NOT NULL,
    FOREIGN KEY (account_id) REFERENCES virtual_account(account_id)
);
CREATE INDEX idx_vaec_account_date ON virtual_account_equity_curve(account_id, date);

-- equity_curve 维护规则：
-- - 每次交易完成后，更新当日及之后所有日期的 equity 值
-- - 每日首次访问账户时，若当日无曲线记录，则重建完整曲线并落库
```

---

## 十、第一阶段实施优先级

按主链路顺序（标注实现深度）：

1. **基础设施** — AbstractDataSource + akshare 实现 + Parquet/SQLite 存储 ✦ 完整实现
2. **基金数据获取** — 净值、基本信息、费率 ✦ 完整实现
3. **指标计算** — metrics.py（夏普、回撤、波动率等）✦ 完整实现
4. **基金评分** — scorer.py（多维度加权 + 动态权重，支持缺失降权）✦ 完整实现
5. **赛道分类** — classifier.py（关键词自动 + 手动覆盖 + 多标签）✦ 完整实现
6. **持仓录入与分析** — 手动录入 + 组合诊断（含 effective_n）✦ 完整实现
7. **虚拟账户基础** — 创建账户、买卖、收益统计、净值曲线缓存 ✦ 完整实现
8. **Streamlit 三页面框架** — 基础可用 ✦ 完整实现
9. **回测模块骨架** — `domain/backtest/` 目录结构 + Strategy 接口 + CompositeStrategy 骨架 + 三个策略文件 ✦ 仅建骨架，逻辑留空，第二阶段填充

---

## 十一、依赖库（预期）

| 库 | 用途 |
|----|------|
| akshare | 基金数据源 |
| pandas | 数据处理 |
| numpy | 数值计算 |
| pyarrow | Parquet 读写 |
| streamlit | UI 框架 |
| plotly | 图表可视化 |
| cachetools | L1 内存缓存 |

---

## 十二、非目标（Out of Scope）

MVP 阶段不包含：
- 实盘交易对接
- 自动下单
- 多用户系统
- 云端部署
- 高频交易策略
- CSV 导入（第二阶段）
- 导入真实持仓到虚拟账户（第二阶段）
- CompositeStrategy 完整实现（第二阶段）

# Phase 3A: CompositeStrategy 组合策略 — 设计文档

**日期：** 2026-03-22
**版本：** v1.0
**目标：** 实现过滤型组合策略框架，支持 DCA + MA Filter 等策略组合，为策略解释面板打基础。

---

## 一、背景与目标

### 1.1 当前状态
- 已有 3 个单策略：DCA、MA、Momentum
- `BacktestEngine` 只能运行单个策略
- 无组合策略能力

### 1.2 目标
- 实现过滤型组合策略框架
- 支持 DCA + MA Filter 组合
- 为后续 Phase 3B（解释面板）预留 trace 数据

### 1.3 不做的事
- 通用任意组合器
- 再平衡型组合（Momentum + Rebalance）— 留待后续
- 多层嵌套组合
- UI 层改动（Phase 3B）

---

## 二、整体架构

```
domain/backtest/strategies/
├── base.py              # Strategy 基类（已有）
├── dca.py               # DCA 策略（已有）
├── ma.py                # MA 策略（已有）
├── momentum.py          # Momentum 策略（已有）
├── composite.py         # CompositeStrategy（新增）
├── modifiers/
│   ├── __init__.py
│   ├── base.py          # SignalModifier 抽象基类（新增）
│   └── ma_filter.py     # MA Filter 具体实现（新增）
└── rebalance/
    ├── __init__.py
    ├── policy.py        # RebalancePolicy 抽象基类（新增，不接入主流程）
    └── threshold.py     # ThresholdRebalancePolicy（新增，不接入主流程）
```

**类关系：**
```
Strategy (abstract)
├── DCAStrategy
├── MAStrategy
├── MomentumStrategy
└── CompositeStrategy
    ├── primary_strategy: Strategy
    └── modifier: SignalModifier
```

---

## 三、核心接口定义

### 3.1 SignalContext（信号上下文）

```python
@dataclass
class SignalContext:
    date: date
    current_nav: float
    indicators: dict[str, float | str | bool]
```

**职责：** 为 SignalModifier 提供预计算的上下文信息。

**indicators 约定（MA Filter）：**
| 键 | 类型 | 说明 |
|---|---|---|
| `ma_window` | int | 均线窗口 |
| `ma_value` | float \| None | 均线值（数据不足时为 None） |
| `trend_relation` | str | "above" \| "below" \| "equal" \| "unknown" |
| `ma_available` | bool | 是否有足够数据计算均线 |

### 3.2 SignalModifier（信号修改器基类）

```python
class SignalModifier(ABC):
    @abstractmethod
    def name(self) -> str:
        """Get modifier name for display."""
        raise NotImplementedError

    @abstractmethod
    def modify(self, signal: Signal, context: SignalContext) -> Signal | None:
        """Return modified signal, or None to block."""
        raise NotImplementedError

    @abstractmethod
    def explain_block(self, signal: Signal, context: SignalContext) -> str:
        """Explain why signal was blocked."""
        raise NotImplementedError
```

**返回值语义：**
- `Signal` → 放行（可修改 reason 字段）
- `None` → 拦截

### 3.3 RebalancePolicy（再平衡策略基类）

```python
class RebalancePolicy(ABC):
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def rebalance(
        self,
        current_positions: list[dict],  # [{fund_code, weight}, ...]
        target_weights: dict[str, float],  # {fund_code: target_weight}
        context: SignalContext
    ) -> list[Signal]:
        raise NotImplementedError
```

**Phase 3A 状态：** 接口保留，不接入主流程。

---

## 四、MAFilter 实现

### 4.1 类定义

```python
class MAFilter(SignalModifier):
    def __init__(self, window: int = 20, filter_mode: str = "trend_confirm"):
        self.window = window
        self.filter_mode = filter_mode
        if filter_mode != "trend_confirm":
            raise NotImplementedError(f"filter_mode={filter_mode} not supported in Phase 3A")
```

### 4.2 过滤规则（trend_confirm）

| 信号类型 | 趋势关系 | 结果 |
|---|---|---|
| BUY | above | ALLOW |
| BUY | below | BLOCK |
| BUY | equal | BLOCK |
| SELL | above | BLOCK |
| SELL | below | ALLOW |
| SELL | equal | BLOCK |
| HOLD | * | ALLOW |
| REBALANCE | * | ALLOW |
| * | unknown | ALLOW（数据不足时默认放行）|

**一句话规则：** 上涨趋势只允许买入，下跌趋势只允许卖出。

### 4.3 数据不足处理

当 NAV 历史记录不足 `window` 条时：
- `ma_available = False`
- `trend_relation = "unknown"`
- 默认 **放行**（避免误伤）

---

## 五、CompositeStrategy 实现

### 5.1 类定义

```python
class CompositeStrategy(Strategy):
    def __init__(
        self,
        primary_strategy: Strategy,
        modifier: SignalModifier | None = None
    ):
        self.primary_strategy = primary_strategy
        self.modifier = modifier
        self._blocked_signals: list[dict] = []
```

### 5.2 generate_signals 流程

```
1. 清空 _blocked_signals
2. 调用 primary_strategy.generate_signals(nav_history)
3. 对每个 signal:
   a. 构建 SignalContext（预计算指标）
   b. 调用 modifier.modify(signal, context)
   c. 若返回 None，记录到 _blocked_signals
   d. 若返回 Signal，加入最终结果
4. 返回过滤后的信号列表
```

### 5.3 SignalContext 构建

对于 MAFilter：
1. 获取 `as_of_date` 及之前的 NAV 记录
2. 若记录数 < window，标记 `ma_available=False`
3. 否则计算均线值，判断 `trend_relation`

### 5.4 Blocked Signals 记录

```python
{
    "original": Signal,      # 原始信号
    "modifier": str,         # 修改器名称
    "reason": str            # 拦截原因
}
```

**用途：** 供 Phase 3B 解释面板展示被拦截的信号。

---

## 六、ThresholdRebalancePolicy 实现（预留）

### 6.1 类定义

```python
class ThresholdRebalancePolicy(RebalancePolicy):
    def __init__(self, threshold: float = 0.05, mode: str = "threshold"):
        self.threshold = threshold
        self.mode = mode
        if mode != "threshold":
            raise NotImplementedError(f"mode={mode} not supported in Phase 3A")
```

### 6.2 调仓规则

- 遍历当前持仓与目标权重的基金代码并集
- 目标缺失视为 `target_weight = 0.0`
- 仅当偏差 **大于** 阈值时触发调仓
- `target_weights` 必须由上游归一化（sum ≈ 1.0）

**Phase 3A 状态：** 实现但不接入主流程，等待 engine 层提供组合状态支持。

---

## 七、使用示例

### 7.1 DCA + MA Filter

```python
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.strategies.modifiers.ma_filter import MAFilter
from domain.backtest.strategies.composite import CompositeStrategy

# 创建组合策略
dca = DCAStrategy(invest_amount=1000, invest_interval_days=20)
ma_filter = MAFilter(window=20, filter_mode="trend_confirm")
composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

# 运行回测
engine = BacktestEngine(initial_cash=100000)
result = engine.run(composite, fund_code="000001", nav_history=nav_data)

# 查看被拦截的信号
blocked = composite.get_blocked_signals()
```

### 7.2 仅主策略（无 modifier）

```python
composite = CompositeStrategy(primary_strategy=dca, modifier=None)
# 等同于直接使用 dca
```

---

## 八、测试覆盖

| 测试用例 | 验证点 |
|---|---|
| CompositeStrategy + 无 modifier | 等同于原策略输出 |
| DCA + MAFilter（上涨趋势 BUY） | 信号通过 |
| DCA + MAFilter（下跌趋势 BUY） | 信号被拦截 |
| DCA + MAFilter（上涨趋势 SELL） | 信号被拦截 |
| DCA + MAFilter（下跌趋势 SELL） | 信号通过 |
| MAFilter 数据不足 | 默认放行 |
| MAFilter filter_mode 无效 | NotImplementedError |
| get_blocked_signals() | 返回被拦截的信号记录 |
| CompositeStrategy.name() | 返回 "DCA+MAFilter(20, trend_confirm)" |

---

## 九、文件变更清单

| 文件 | 动作 |
|---|---|
| `domain/backtest/models.py` | 新增 `SignalContext` dataclass |
| `domain/backtest/strategies/composite.py` | 新增 `CompositeStrategy` 类 |
| `domain/backtest/strategies/modifiers/__init__.py` | 新建目录和模块 |
| `domain/backtest/strategies/modifiers/base.py` | 新增 `SignalModifier` 抽象基类 |
| `domain/backtest/strategies/modifiers/ma_filter.py` | 新增 `MAFilter` 实现 |
| `domain/backtest/strategies/rebalance/__init__.py` | 新建目录和模块 |
| `domain/backtest/strategies/rebalance/policy.py` | 新增 `RebalancePolicy` 抽象基类 |
| `domain/backtest/strategies/rebalance/threshold.py` | 新增 `ThresholdRebalancePolicy` 实现 |
| `tests/domain/backtest/strategies/test_composite.py` | 新增测试文件 |

---

## 十、后续扩展

| Phase | 内容 |
|---|---|
| Phase 3A | 过滤型组合（本设计） |
| Phase 3B | 策略解释面板 |
| Phase 3C | 再平衡型组合（需 engine 层支持） |
| 未来 | 其他 SignalModifier（波动率过滤、回撤过滤等） |

---

## 十一、实现注意事项

1. `composite.py` 会直接引用 `MAFilter`，注意显式导入，避免循环导入
2. `MAFilter.modify()` 使用 `dataclasses.replace()`，需显式 `import dataclasses`
3. `RebalancePolicy` 接口保留但不在 Phase 3A 接入主流程
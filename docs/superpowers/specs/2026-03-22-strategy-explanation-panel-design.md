# Phase 3B: 策略解释面板 — 设计文档（修正版）

**日期：** 2026-03-22
**版本：** v1.1
**目标：** 在回测结果中展示组合策略拦截的信号及原因，让用户理解过滤逻辑，并为后续更完整的解释体系打基础。

---

## 一、背景与目标

### 1.1 当前状态

**已有数据流：**

```text
UI (策略选择) → BacktestService → BacktestEngine → Strategy → BacktestResult → UI (展示结果)
```

**CompositeStrategy 已实现：**

* `get_blocked_signals()` 返回被拦截信号列表
* 每条记录包含：

  * 原始信号
  * modifier 名称
  * 拦截原因

**当前缺失：**

1. `BacktestResult` 无 `blocked_signals` 字段
2. `Strategy` 基类未统一暴露 blocked trace 能力
3. `BacktestService` 不支持创建 `"DCA + MA Filter"` 组合策略
4. `3_strategy_lab.py` 无组合策略选项与解释面板展示

---

### 1.2 本阶段目标

* 扩展回测结果模型，正式携带 blocked signal trace
* 让 engine 以**统一接口**获取解释数据，而不是依赖具体策略类
* 在回测 UI 中增加 `"DCA + MA Filter"` 选项
* 在结果页展示**被拦截信号**及原因

---

### 1.3 本阶段不做

* 通用任意策略组合器 UI
* RebalancePolicy 接入主流程（留给 Phase 3C）
* 全量信号修改链路可视化
* 所有单策略的解释系统统一化
* “通过信号”的深度 trace 展示

---

## 二、设计原则

### 2.1 解耦原则

`BacktestEngine` 只关心“策略是否能提供 blocked signal trace”，不关心它是不是 `CompositeStrategy`。

### 2.2 结果优先原则

解释数据应跟随 `BacktestResult` 一起返回，UI 只负责展示，不自行推断。

### 2.3 最小实现原则

Phase 3B 只消费 Phase 3A 已具备的 `_blocked_signals` 数据，不额外扩展过多解释框架。

---

## 三、架构变更

### 3.1 数据模型变更

**文件：** `domain/backtest/models.py`

新增一个轻量 dataclass：

```python
from dataclasses import dataclass, field
from datetime import date

@dataclass
class BlockedSignalTrace:
    """Trace record for a blocked signal."""
    original: Signal
    modifier: str
    reason: str
```

然后扩展 `BacktestResult`：

```python
@dataclass
class BacktestResult:
    """Backtest result summary."""
    strategy_name: str
    fund_code: str
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    trade_count: int
    signals: list[Signal] = field(default_factory=list)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    executed_trades: list[ExecutedTrade] = field(default_factory=list)
    blocked_signals: list[BlockedSignalTrace] = field(default_factory=list)
```

---

### 3.2 Strategy 基类变更

**文件：** `domain/backtest/strategies/base.py`

为避免 engine 直接依赖 `CompositeStrategy`，在基类中增加一个默认方法：

```python
class Strategy(ABC):
    ...

    def get_blocked_signals(self) -> list[BlockedSignalTrace]:
        """Return blocked signal traces for explanation panel.

        Default: no blocked signals.
        """
        return []
```

这样：

* 普通策略：默认返回 `[]`
* `CompositeStrategy`：override 返回真实 blocked trace

---

### 3.3 CompositeStrategy 变更

**文件：** `domain/backtest/strategies/composite.py`

将现有 `get_blocked_signals()` 的返回类型由 `list[dict]` 改为 `list[BlockedSignalTrace]`。

原先类似：

```python
self._blocked_signals.append({
    "original": dataclasses.replace(signal),
    "modifier": self.modifier.name(),
    "reason": self.modifier.explain_block(signal, context)
})
```

改为：

```python
self._blocked_signals.append(
    BlockedSignalTrace(
        original=dataclasses.replace(signal),
        modifier=self.modifier.name(),
        reason=self.modifier.explain_block(signal, context)
    )
)
```

并保持：

```python
def get_blocked_signals(self) -> list[BlockedSignalTrace]:
    return self._blocked_signals.copy()
```

---

### 3.4 Engine 变更

**文件：** `domain/backtest/engine.py`

不要使用：

```python
if isinstance(strategy, CompositeStrategy):
    result.blocked_signals = strategy.get_blocked_signals()
```

改为统一接口调用：

```python
blocked_signals = strategy.get_blocked_signals()
```

并在构造 `BacktestResult` 时写入：

```python
return BacktestResult(
    strategy_name=strategy.name(),
    fund_code=fund_code,
    start_date=nav_history[0]["date"],
    end_date=nav_history[-1]["date"],
    total_return=total_return,
    annualized_return=annualized_return,
    max_drawdown=max_drawdown,
    sharpe_ratio=sharpe_ratio,
    win_rate=win_rate,
    trade_count=len(trades),
    signals=signals,
    equity_curve=equity_curve,
    executed_trades=executed_trades,
    blocked_signals=blocked_signals,
)
```

**好处：**

* engine 不再 import `CompositeStrategy`
* 后续其他策略也可暴露 blocked trace，而无需改 engine

---

### 3.5 Service 变更

**文件：** `service/backtest_service.py`

在 `_create_strategy()` 中新增：

```python
elif strategy_name == "DCA + MA Filter":
    dca = DCAStrategy(
        invest_amount=params.get("invest_amount", 10000),
        invest_interval_days=params.get("interval_days", 20),
    )
    ma_filter = MAFilter(
        window=params.get("ma_window", 20)
    )
    return CompositeStrategy(
        primary_strategy=dca,
        modifier=ma_filter,
    )
```

本阶段仅支持这一种组合策略入口，不开放通用组合 UI。

---

## 四、UI 设计

**文件：** `ui/pages/3_strategy_lab.py`

---

### 4.1 策略选择

```python
strategy_name = st.selectbox(
    "策略选择",
    options=["DCA", "MA Timing", "Momentum", "DCA + MA Filter"],
    key="bt_strategy"
)
```

若当前 UI 尚未暴露 Momentum，也可临时先保留：

```python
options=["DCA", "MA Timing", "DCA + MA Filter"]
```

---

### 4.2 参数区

当选择 `"DCA + MA Filter"` 时展示：

```python
if strategy_name == "DCA + MA Filter":
    col1, col2, col3 = st.columns(3)
    with col1:
        dca_invest_amount = st.number_input("每次投资金额 (元)", min_value=100.0, value=10000.0, step=100.0)
    with col2:
        dca_interval = st.number_input("投资间隔 (天)", min_value=1, value=20, step=1)
    with col3:
        ma_window = st.number_input("MA 窗口 (天)", min_value=5, value=20, step=1)
```

提交给 service 的参数：

```python
strategy_params = {
    "invest_amount": dca_invest_amount,
    "interval_days": dca_interval,
    "ma_window": ma_window,
}
```

---

### 4.3 解释面板展示逻辑

建议规则：

* 若策略名不是组合策略，解释面板不显示
* 若策略名是组合策略，则显示解释面板

  * 有拦截 → 展示拦截详情
  * 无拦截 → 展示“本次无信号被拦截”

---

### 4.4 解释面板 UI

不要用：

```python
passed_count = len(result.executed_trades)
```

因为“成交记录数”不等于“通过信号数”。

建议改成：

* `final_signal_count = len(result.signals)`
* `blocked_count = len(result.blocked_signals)`

实现如下：

```python
if strategy_name == "DCA + MA Filter":
    with st.expander("📋 信号解释", expanded=False):
        final_signal_count = len(result.signals)
        blocked_count = len(result.blocked_signals)

        col1, col2 = st.columns(2)
        with col1:
            st.metric("最终信号", final_signal_count)
        with col2:
            st.metric("被拦截信号", blocked_count)

        if blocked_count == 0:
            st.success("本次组合策略运行中没有信号被拦截。")
        else:
            st.markdown("**拦截详情：**")
            for item in result.blocked_signals:
                signal = item.original
                st.write(
                    f"- {signal.date} **{signal.action}** "
                    f"({item.modifier}) → {item.reason}"
                )
```

---

### 4.5 展示效果示意

```text
回测结果
├── 总收益、年化收益、最大回撤、夏普比率、胜率
├── 净值曲线图
├── 交易记录表
└── 📋 信号解释
    ├── 最终信号：3
    ├── 被拦截信号：2
    └── 拦截详情
        - 2023-02-15 BUY (MAFilter(20, trend_confirm)) → 买入信号被拦截：当前净值低于20日均线
        - 2023-03-15 BUY (MAFilter(20, trend_confirm)) → 买入信号被拦截：当前净值低于20日均线
```

---

## 五、文件变更清单

| 文件                                        | 动作                                                                    |
| ----------------------------------------- | --------------------------------------------------------------------- |
| `domain/backtest/models.py`               | 新增 `BlockedSignalTrace` dataclass；扩展 `BacktestResult.blocked_signals` |
| `domain/backtest/strategies/base.py`      | 新增 `get_blocked_signals()` 默认实现                                       |
| `domain/backtest/strategies/composite.py` | `get_blocked_signals()` 返回 `list[BlockedSignalTrace]`                 |
| `domain/backtest/engine.py`               | 统一通过 `strategy.get_blocked_signals()` 收集解释数据                          |
| `service/backtest_service.py`             | 新增 `"DCA + MA Filter"` 策略创建                                           |
| `ui/pages/3_strategy_lab.py`              | 增加组合策略选项、参数配置、解释面板                                                    |

---

## 六、测试覆盖

### 6.1 模型测试

| 测试用例                                   | 验证点          |
| -------------------------------------- | ------------ |
| `BlockedSignalTrace` 可正常构造             | dataclass 正常 |
| `BacktestResult.blocked_signals` 默认空列表 | 新字段默认值       |

### 6.2 Strategy/Engine 集成测试

| 测试用例                                             | 验证点                            |
| ------------------------------------------------ | ------------------------------ |
| 普通策略 `get_blocked_signals()` 返回空列表               | 基类默认行为                         |
| `CompositeStrategy.get_blocked_signals()` 返回拦截记录 | override 生效                    |
| Engine + 普通策略                                    | `result.blocked_signals == []` |
| Engine + CompositeStrategy（有拦截）                  | `result.blocked_signals` 正确写入  |
| Engine + CompositeStrategy（无拦截）                  | `result.blocked_signals == []` |

### 6.3 Service 测试

| 测试用例                                   | 验证点       |
| -------------------------------------- | --------- |
| BacktestService 创建 `"DCA + MA Filter"` | 组合策略实例化正确 |
| 回测结果中包含 `blocked_signals`              | 端到端链路正确   |

### 6.4 UI 测试

| 测试用例                             | 验证点    |
| -------------------------------- | ------ |
| 选择 `"DCA + MA Filter"` 时显示 MA 参数 | 条件渲染正确 |
| 组合策略有拦截时显示拦截详情                   | 展示正确   |
| 组合策略无拦截时显示“无拦截”提示                | 用户感知正确 |
| 非组合策略不显示解释面板                     | UI 不混乱 |

---

## 七、实现步骤建议

### Step 1

扩展 `models.py`

* 新增 `BlockedSignalTrace`
* 扩展 `BacktestResult`

### Step 2

扩展 `Strategy` 基类

* 新增 `get_blocked_signals()` 默认方法

### Step 3

修改 `CompositeStrategy`

* 返回 `BlockedSignalTrace` 对象列表

### Step 4

修改 `BacktestEngine`

* 统一读取 `strategy.get_blocked_signals()`

### Step 5

修改 `BacktestService`

* 支持 `"DCA + MA Filter"`

### Step 6

修改 `3_strategy_lab.py`

* 增加组合策略选项
* 增加参数输入
* 增加解释面板

### Step 7

补充测试并跑全量回归

---

## 八、使用示例

```python
from domain.backtest.strategies.dca import DCAStrategy
from domain.backtest.strategies.modifiers.ma_filter import MAFilter
from domain.backtest.strategies.composite import CompositeStrategy

dca = DCAStrategy(invest_amount=10000, invest_interval_days=20)
ma_filter = MAFilter(window=20, filter_mode="trend_confirm")
composite = CompositeStrategy(primary_strategy=dca, modifier=ma_filter)

result = engine.run(composite, fund_code="000001", nav_history=nav_data)

# 解释数据
blocked = result.blocked_signals
```

---

## 九、后续扩展

| Phase    | 内容                                   |
| -------- | ------------------------------------ |
| Phase 3B | 被拦截信号解释面板（本设计）                       |
| Phase 3C | RebalancePolicy 接入主流程                |
| 后续       | 通过信号解释、信号修改链路 trace、更多 modifier 解释体系 |

---

## 十、实现注意事项

1. `engine.py` 不要 import `CompositeStrategy` 做类型判断。
2. `blocked_signals` 使用 dataclass，不使用裸 `dict`。
3. UI 里“最终信号数”与“交易记录数”要区分。
4. 组合策略即使本次无拦截，也建议展示“无拦截信号”，避免用户误判。
5. 本阶段只支持 `"DCA + MA Filter"` 这一种组合策略入口，避免 UI 过度泛化。


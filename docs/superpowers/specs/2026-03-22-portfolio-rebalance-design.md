# Phase 3C: 多基金轮动与再平衡 — 设计文档

**日期：** 2026-03-22
**版本：** v1.1
**目标：** 实现固定基金池的多基金轮动回测能力，形成 `PortfolioMomentum + ThresholdRebalance` 的完整组合策略闭环。

---

## 一、背景与目标

### 1.1 当前状态

**Phase 3 已完成：**

* 3A：`CompositeStrategy + SignalModifier + MAFilter`（过滤型组合）
* 3B：策略解释面板（`BlockedSignalTrace`）

**现有基础设施：**

* `Strategy` 基类：单基金策略接口
* `BacktestEngine`：单基金回测引擎
* `RebalancePolicy` 接口：当前为 Phase 3A 预留存根，未接入主流程
* `ThresholdRebalancePolicy`：当前为存根实现

**当前缺失：**

1. 多基金组合回测能力
2. `PortfolioStrategy` 组合策略接口
3. 组合级信号模型
4. 再平衡策略真实实现
5. 多基金时间轴对齐与调仓执行能力

---

### 1.2 本阶段目标

* 实现固定基金池的多基金轮动回测
* 支持组合策略输出目标权重
* 支持阈值型再平衡（Threshold Rebalance）
* 支持 `T 日生成信号，T+1 日执行调仓`
* 形成组合策略的最小可用闭环

---

### 1.3 本阶段不做

* 与虚拟账户打通
* 税费 / 滑点 / 最小交易单位
* 动态基金池
* 任意嵌套组合策略树
* 跨资产类别特殊处理（货币基金、QDII 时差、ETF 场内成交规则差异）
* 修改现有单基金 `MomentumStrategy`

---

## 二、核心硬规则

### 2.1 信号生成方式

`generate_portfolio_signals()` 采用**一次性批量生成**：

* 策略一次性生成整段回测期间的所有组合信号
* Engine 不循环调用策略，只调用一次
* **每个交易日最多一条 `PortfolioSignal`**
* 若策略输出同日多条信号，直接报错

---

### 2.2 权重归一化约束

`target_weights` 必须满足：

* key 可包含基金代码和 `"CASH"`
* 所有权重满足 `0 <= w <= 1`
* 总和满足 `abs(sum(weights.values()) - 1.0) < 1e-6`
* 若策略输出不满足约束，视为无效信号并报错
* **必须在模型层 `__post_init__` 中校验**

---

### 2.3 动量策略默认配仓规则

* 回看过去 `lookback_periods` 个**有效交易点**
* 基于区间收益率排序
* 选前 `top_n` 只基金
* 入选基金**等权分配**
* 未入选部分全部给 `CASH`
* 若有效基金不足 `top_n`，剩余权重分配给 `CASH`

示例（`top_n=2`，基金池 3 只）：

```python
{
    "fund_a": 0.5,
    "fund_b": 0.5,
    "CASH": 0.0,
}
```

---

### 2.4 执行顺序规则

1. `T` 日生成组合信号
2. `T+1` 日执行调仓
3. `T+1` 当日**先卖出，再买入**
4. 卖出和买入都按 `T+1` 同一日 NAV 成交
5. 最后一个有效交易日产生的信号，如无 `T+1` 数据，则丢弃不执行
6. 执行后**不强制重置 cash**，现金仅由真实买卖结果自然更新

---

### 2.5 时间轴职责划分

* **Engine 负责**：

  * 所有基金净值日期的交集对齐
  * lookback 可用性裁剪
  * 有效交易时间轴生成
* **Strategy 负责**：

  * 在 Engine 提供的 `aligned_dates` 上生成组合信号
* `aligned_dates` 是唯一权威的组合时间轴
* 传给 Strategy 的 `nav_histories` 可以包含更长历史数据，但**只能在 `aligned_dates` 上生成信号**

---

### 2.6 策略隔离原则

* 新建 `PortfolioMomentumStrategy`，实现 `PortfolioStrategy`
* 不修改现有单基金 `MomentumStrategy`
* 保持 Phase 1 / 2 / 3A / 3B 已有功能和测试不变

---

## 三、数据模型

### 3.1 PortfolioSignal

**文件：** `domain/backtest/models.py`

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass
class PortfolioSignal:
    """组合级再平衡信号。"""
    date: date
    action: Literal["REBALANCE"]
    target_weights: dict[str, float]  # includes "CASH"
    confidence: float
    reason: str

    def __post_init__(self) -> None:
        if self.action != "REBALANCE":
            raise ValueError(
                f"PortfolioSignal.action must be 'REBALANCE', got {self.action}"
            )

        if "CASH" not in self.target_weights:
            raise ValueError("target_weights must include 'CASH'")

        total = sum(self.target_weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"target_weights must sum to 1.0, got {total:.6f}")

        for fund_code, weight in self.target_weights.items():
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"invalid weight for {fund_code}: {weight}")

        if not self.reason:
            raise ValueError("reason cannot be empty")
```

**说明：**

* `target_weights` 是**目标组合状态**
* Engine 负责根据当前持仓和目标权重拆分出实际买卖

---

### 3.2 PortfolioBacktestResult

**文件：** `domain/backtest/models.py`

```python
from dataclasses import dataclass, field
from datetime import date

@dataclass
class PortfolioBacktestResult:
    """组合回测结果。"""
    strategy_name: str
    fund_codes: list[str]
    start_date: date
    end_date: date
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    rebalance_signals: list[PortfolioSignal] = field(default_factory=list)
    executed_trades: list[ExecutedTrade] = field(default_factory=list)
    portfolio_weights_history: list[tuple[date, dict[str, float]]] = field(default_factory=list)
```

**字段说明：**

* `equity_curve`：组合净值曲线
* `rebalance_signals`：组合级信号
* `executed_trades`：拆单后的实际交易
* `portfolio_weights_history`：每个有效交易日的组合权重快照，包含 `"CASH"`

---

### 3.3 ExecutedTrade 扩展

**文件：** `domain/backtest/models.py`

```python
@dataclass
class ExecutedTrade:
    date: date
    fund_code: str
    action: Literal["BUY", "SELL"]
    amount: float
    nav: float
    shares: float
    reason: str
    rebalance_id: str | None = None
```

**用途：**

* 将单次组合调仓拆分为多笔基金交易时，保留 `rebalance_id`
* 便于后续解释面板追踪“某次调仓对应哪些买卖”

---

## 四、策略层设计

### 4.1 PortfolioStrategy 基类

**文件：** `domain/backtest/strategies/portfolio_base.py`

```python
from abc import ABC, abstractmethod
from datetime import date
from domain.backtest.models import PortfolioSignal

class PortfolioStrategy(ABC):
    """组合策略基类。"""

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date],
    ) -> list[PortfolioSignal]:
        """一次性生成整段期间的所有组合信号。

        Args:
            nav_histories: fund_code -> nav history
                可包含额外 warmup 数据
            aligned_dates: Engine 提供的有效交易时间轴

        Returns:
            按时间排序的 PortfolioSignal 列表
        """
        raise NotImplementedError
```

---

### 4.2 MomentumConfig

**文件：** `domain/backtest/strategies/portfolio_momentum.py`

```python
from dataclasses import dataclass

@dataclass
class MomentumConfig:
    """组合动量策略配置。"""
    lookback_periods: int = 60
    top_n: int = 2
    signal_interval_periods: int = 20
```

**说明：**

* `lookback_periods`：回看多少个**有效交易点**
* `signal_interval_periods`：每隔多少个**有效交易点**生成一次信号
* 全部使用“有效交易点”而不是“自然日”，避免节假日造成节奏漂移

---

### 4.3 PortfolioMomentumStrategy

**文件：** `domain/backtest/strategies/portfolio_momentum.py`

```python
from datetime import date
from domain.backtest.models import PortfolioSignal
from domain.backtest.strategies.portfolio_base import PortfolioStrategy

class PortfolioMomentumStrategy(PortfolioStrategy):
    """多基金动量轮动策略。"""

    def __init__(self, config: MomentumConfig | None = None):
        self.config = config or MomentumConfig()

    def name(self) -> str:
        return (
            f"PortfolioMomentum("
            f"{self.config.lookback_periods}, top{self.config.top_n}, "
            f"interval={self.config.signal_interval_periods})"
        )

    def generate_portfolio_signals(
        self,
        nav_histories: dict[str, list[dict]],
        aligned_dates: list[date],
    ) -> list[PortfolioSignal]:
        signals: list[PortfolioSignal] = []
        nav_by_date = self._index_nav_by_date(nav_histories)

        if len(aligned_dates) <= self.config.lookback_periods:
            return []

        last_signal_index: int | None = None

        for i in range(self.config.lookback_periods, len(aligned_dates)):
            if (
                last_signal_index is not None
                and i - last_signal_index < self.config.signal_interval_periods
            ):
                continue

            end_date = aligned_dates[i]
            start_date = aligned_dates[i - self.config.lookback_periods]

            returns = self._calculate_returns_by_dates(
                nav_by_date=nav_by_date,
                start_date=start_date,
                end_date=end_date,
            )

            if not returns:
                continue

            sorted_funds = sorted(returns.items(), key=lambda x: x[1], reverse=True)
            top_funds = [fund_code for fund_code, _ in sorted_funds[: self.config.top_n]]

            target_weights = self._build_target_weights(top_funds)

            signal = PortfolioSignal(
                date=end_date,
                action="REBALANCE",
                target_weights=target_weights,
                confidence=1.0,
                reason=f"动量轮动：{', '.join(top_funds)}" if top_funds else "动量轮动：全部转入现金",
            )
            signals.append(signal)
            last_signal_index = i

        return signals

    def _index_nav_by_date(
        self,
        nav_histories: dict[str, list[dict]],
    ) -> dict[date, dict[str, float]]:
        index: dict[date, dict[str, float]] = {}
        for fund_code, nav_list in nav_histories.items():
            for item in nav_list:
                d = item["date"]
                if d not in index:
                    index[d] = {}
                index[d][fund_code] = item["nav"]
        return index

    def _calculate_returns_by_dates(
        self,
        nav_by_date: dict[date, dict[str, float]],
        start_date: date,
        end_date: date,
    ) -> dict[str, float]:
        returns: dict[str, float] = {}

        start_navs = nav_by_date.get(start_date, {})
        end_navs = nav_by_date.get(end_date, {})

        for fund_code, end_nav in end_navs.items():
            start_nav = start_navs.get(fund_code)
            if start_nav is None or start_nav <= 0:
                continue
            returns[fund_code] = (end_nav - start_nav) / start_nav

        return returns

    def _build_target_weights(self, top_funds: list[str]) -> dict[str, float]:
        weights: dict[str, float] = {}

        if top_funds:
            per_fund = 1.0 / len(top_funds)
            for fund_code in top_funds:
                weights[fund_code] = per_fund

        weights["CASH"] = 1.0 - sum(weights.values())
        return weights
```

---

## 五、再平衡层设计

### 5.1 RebalancePolicy 接口

**文件：** `domain/backtest/strategies/rebalance/policy.py`

```python
from abc import ABC, abstractmethod
from domain.backtest.models import PortfolioSignal, SignalContext

class RebalancePolicy(ABC):
    """组合级再平衡策略接口。"""

    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        """决定是否执行组合级再平衡信号。"""
        raise NotImplementedError
```

---

### 5.2 ThresholdRebalancePolicy

**文件：** `domain/backtest/strategies/rebalance/threshold.py`

```python
from domain.backtest.models import PortfolioSignal, SignalContext
from domain.backtest.strategies.rebalance.policy import RebalancePolicy

class ThresholdRebalancePolicy(RebalancePolicy):
    """阈值触发型再平衡策略。"""

    def __init__(self, threshold: float = 0.05):
        self.threshold = threshold

    def name(self) -> str:
        return f"ThresholdRebalance({self.threshold:.0%})"

    def apply(
        self,
        signal: PortfolioSignal,
        current_positions: list[dict],
        context: SignalContext,
    ) -> PortfolioSignal | None:
        current_weights: dict[str, float] = {
            pos["fund_code"]: pos["weight"] for pos in current_positions
        }

        if "CASH" not in current_weights:
            current_weights["CASH"] = 0.0

        target_weights = signal.target_weights
        all_keys = set(current_weights.keys()) | set(target_weights.keys())

        max_deviation = 0.0
        for key in all_keys:
            current_w = current_weights.get(key, 0.0)
            target_w = target_weights.get(key, 0.0)
            max_deviation = max(max_deviation, abs(current_w - target_w))

        if max_deviation >= self.threshold:
            return signal
        return None
```

**语义：**

* `RebalancePolicy` 是**组合级信号过滤器**
* 它不负责重新生成目标权重，只负责决定当前信号是否值得执行

---

## 六、引擎层设计

### 6.1 PortfolioState

**文件：** `domain/backtest/engine.py`

```python
from dataclasses import dataclass, field

@dataclass
class PortfolioState:
    cash: float
    holdings: dict[str, float] = field(default_factory=dict)  # fund_code -> shares
    weights: dict[str, float] = field(default_factory=lambda: {"CASH": 1.0})
```

---

### 6.2 PortfolioBacktestEngine

**文件：** `domain/backtest/engine.py`

```python
from datetime import date
from domain.backtest.models import (
    PortfolioSignal,
    PortfolioBacktestResult,
    ExecutedTrade,
    SignalContext,
)
from domain.backtest.strategies.portfolio_base import PortfolioStrategy
from domain.backtest.strategies.rebalance.policy import RebalancePolicy

class PortfolioBacktestEngine:
    """组合回测引擎。"""

    def __init__(self, initial_cash: float = 100000.0):
        self.initial_cash = initial_cash

    def run(
        self,
        strategy: PortfolioStrategy,
        fund_codes: list[str],
        nav_histories: dict[str, list[dict]],
        rebalance_policy: RebalancePolicy | None = None,
        lookback_periods: int = 60,
    ) -> PortfolioBacktestResult:
        aligned_dates = self._prepare_aligned_dates(
            nav_histories=nav_histories,
            lookback_periods=lookback_periods,
        )
        if not aligned_dates:
            raise ValueError("No valid aligned dates after lookback filtering")

        state = PortfolioState(
            cash=self.initial_cash,
            holdings={},
            weights={"CASH": 1.0},
        )

        nav_by_date = self._index_nav_by_date(nav_histories)
        signals = strategy.generate_portfolio_signals(nav_histories, aligned_dates)

        self._validate_unique_signal_dates(signals)

        equity_curve: list[tuple[date, float]] = []
        executed_trades: list[ExecutedTrade] = []
        weights_history: list[tuple[date, dict[str, float]]] = []

        signal_map = {signal.date: signal for signal in signals}

        for i, current_date in enumerate(aligned_dates):
            current_navs = nav_by_date[current_date]

            portfolio_value = self._calculate_portfolio_value(state, current_navs)
            state.weights = self._calculate_weights(state, current_navs)
            equity_curve.append((current_date, portfolio_value))
            weights_history.append((current_date, state.weights.copy()))

            signal = signal_map.get(current_date)
            if signal is None:
                continue

            if i + 1 >= len(aligned_dates):
                continue  # 最后一个有效交易日信号无 T+1，丢弃

            next_date = aligned_dates[i + 1]
            next_navs = nav_by_date[next_date]

            filtered_signal = signal
            if rebalance_policy is not None:
                context = self._build_context(current_date, current_navs)
                current_positions = self._get_current_positions(state, current_navs)
                filtered_signal = rebalance_policy.apply(
                    signal=signal,
                    current_positions=current_positions,
                    context=context,
                )

            if filtered_signal is not None:
                trades = self._execute_rebalance(
                    signal=filtered_signal,
                    state=state,
                    execution_navs=next_navs,
                    execution_date=next_date,
                )
                executed_trades.extend(trades)

        metrics = self._calculate_metrics(equity_curve)

        return PortfolioBacktestResult(
            strategy_name=strategy.name(),
            fund_codes=fund_codes,
            start_date=aligned_dates[0],
            end_date=aligned_dates[-1],
            total_return=metrics["total_return"],
            annualized_return=metrics["annualized_return"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            equity_curve=equity_curve,
            rebalance_signals=signals,
            executed_trades=executed_trades,
            portfolio_weights_history=weights_history,
        )
```

---

### 6.3 时间轴准备

```python
    def _prepare_aligned_dates(
        self,
        nav_histories: dict[str, list[dict]],
        lookback_periods: int,
    ) -> list[date]:
        common_dates = self._align_dates(nav_histories)
        if len(common_dates) <= lookback_periods:
            return []
        return common_dates[lookback_periods:]
```

```python
    def _align_dates(
        self,
        nav_histories: dict[str, list[dict]],
    ) -> list[date]:
        date_sets = []
        for nav_list in nav_histories.values():
            dates = {item["date"] for item in nav_list}
            date_sets.append(dates)

        if not date_sets:
            return []

        return sorted(set.intersection(*date_sets))
```

**说明：**

* 统一以“交集日期 + lookback_periods”构造有效时间轴
* 不再混用自然日 `timedelta(days=...)`
* Strategy 的 `lookback_periods` 和 Engine 的裁剪逻辑完全一致

---

### 6.4 索引与持仓快照

```python
    def _index_nav_by_date(
        self,
        nav_histories: dict[str, list[dict]],
    ) -> dict[date, dict[str, float]]:
        index: dict[date, dict[str, float]] = {}
        for fund_code, nav_list in nav_histories.items():
            for item in nav_list:
                d = item["date"]
                if d not in index:
                    index[d] = {}
                index[d][fund_code] = item["nav"]
        return index
```

```python
    def _calculate_portfolio_value(
        self,
        state: PortfolioState,
        current_navs: dict[str, float],
    ) -> float:
        value = state.cash
        for fund_code, shares in state.holdings.items():
            nav = current_navs.get(fund_code, 0.0)
            value += shares * nav
        return value
```

```python
    def _calculate_weights(
        self,
        state: PortfolioState,
        current_navs: dict[str, float],
    ) -> dict[str, float]:
        total_value = self._calculate_portfolio_value(state, current_navs)
        if total_value <= 0:
            return {"CASH": 1.0}

        weights: dict[str, float] = {}
        for fund_code, shares in state.holdings.items():
            nav = current_navs.get(fund_code, 0.0)
            value = shares * nav
            if value > 0:
                weights[fund_code] = value / total_value

        weights["CASH"] = state.cash / total_value
        return weights
```

```python
    def _get_current_positions(
        self,
        state: PortfolioState,
        current_navs: dict[str, float],
    ) -> list[dict]:
        total_value = self._calculate_portfolio_value(state, current_navs)
        if total_value <= 0:
            return [{"fund_code": "CASH", "weight": 1.0, "value": state.cash, "shares": state.cash}]

        positions = []
        for fund_code, shares in state.holdings.items():
            nav = current_navs.get(fund_code, 0.0)
            value = shares * nav
            positions.append(
                {
                    "fund_code": fund_code,
                    "shares": shares,
                    "value": value,
                    "weight": value / total_value,
                }
            )

        positions.append(
            {
                "fund_code": "CASH",
                "shares": state.cash,
                "value": state.cash,
                "weight": state.cash / total_value,
            }
        )
        return positions
```

---

### 6.5 Signal 校验与上下文

```python
    def _validate_unique_signal_dates(
        self,
        signals: list[PortfolioSignal],
    ) -> None:
        dates = [signal.date for signal in signals]
        if len(dates) != len(set(dates)):
            duplicates = sorted({d for d in dates if dates.count(d) > 1})
            raise ValueError(f"Multiple PortfolioSignal on same date: {duplicates}")
```

```python
    def _build_context(
        self,
        current_date: date,
        current_navs: dict[str, float],
    ) -> SignalContext:
        return SignalContext(
            date=current_date,
            current_nav=0.0,  # 组合场景占位
            indicators=current_navs,
        )
```

---

### 6.6 再平衡执行逻辑

```python
    def _execute_rebalance(
        self,
        signal: PortfolioSignal,
        state: PortfolioState,
        execution_navs: dict[str, float],
        execution_date: date,
    ) -> list[ExecutedTrade]:
        trades: list[ExecutedTrade] = []
        rebalance_id = f"rebalance_{execution_date.isoformat()}"
        tolerance = 1e-8

        total_value = self._calculate_portfolio_value(state, execution_navs)

        target_amounts: dict[str, float] = {
            fund_code: total_value * weight
            for fund_code, weight in signal.target_weights.items()
        }

        current_amounts: dict[str, float] = {}
        all_funds = set(state.holdings.keys()) | {
            fund_code for fund_code in target_amounts.keys() if fund_code != "CASH"
        }

        for fund_code in all_funds:
            nav = execution_navs.get(fund_code, 0.0)
            shares = state.holdings.get(fund_code, 0.0)
            current_amounts[fund_code] = shares * nav

        sell_orders = []
        buy_orders = []

        for fund_code in all_funds:
            nav = execution_navs.get(fund_code, 0.0)
            if nav <= 0:
                continue

            current_amount = current_amounts.get(fund_code, 0.0)
            target_amount = target_amounts.get(fund_code, 0.0)
            delta = target_amount - current_amount

            if delta < -tolerance:
                sell_orders.append((fund_code, -delta, nav))
            elif delta > tolerance:
                buy_orders.append((fund_code, delta, nav))

        # 1. 先执行所有卖出
        for fund_code, amount_to_sell, nav in sell_orders:
            shares_to_sell = amount_to_sell / nav
            current_shares = state.holdings.get(fund_code, 0.0)
            shares_to_sell = min(shares_to_sell, current_shares)

            if shares_to_sell <= tolerance:
                continue

            actual_amount = shares_to_sell * nav
            state.cash += actual_amount
            remaining_shares = current_shares - shares_to_sell

            if remaining_shares <= tolerance:
                state.holdings.pop(fund_code, None)
            else:
                state.holdings[fund_code] = remaining_shares

            trades.append(
                ExecutedTrade(
                    date=execution_date,
                    fund_code=fund_code,
                    action="SELL",
                    amount=actual_amount,
                    nav=nav,
                    shares=shares_to_sell,
                    reason=f"再平衡卖出: {rebalance_id}",
                    rebalance_id=rebalance_id,
                )
            )

        # 2. 再执行所有买入
        for fund_code, amount_to_buy, nav in buy_orders:
            if amount_to_buy <= tolerance:
                continue

            actual_amount = min(amount_to_buy, state.cash)
            if actual_amount <= tolerance:
                continue

            shares_to_buy = actual_amount / nav
            state.cash -= actual_amount
            state.holdings[fund_code] = state.holdings.get(fund_code, 0.0) + shares_to_buy

            trades.append(
                ExecutedTrade(
                    date=execution_date,
                    fund_code=fund_code,
                    action="BUY",
                    amount=actual_amount,
                    nav=nav,
                    shares=shares_to_buy,
                    reason=f"再平衡买入: {rebalance_id}",
                    rebalance_id=rebalance_id,
                )
            )

        state.weights = self._calculate_weights(state, execution_navs)
        return trades
```

**关键修正：**

* 真正做到**全量先卖后买**
* 不再混合部分卖出与买入顺序
* 不再强制回写 `state.cash = target_amounts["CASH"]`
* 现金完全由卖出回流和买入扣减自然形成

---

### 6.7 绩效指标

```python
    def _calculate_metrics(
        self,
        equity_curve: list[tuple[date, float]],
    ) -> dict[str, float]:
        if len(equity_curve) < 2:
            return {
                "total_return": 0.0,
                "annualized_return": 0.0,
                "max_drawdown": 0.0,
                "sharpe_ratio": 0.0,
            }

        values = [value for _, value in equity_curve]
        total_return = (values[-1] - values[0]) / values[0]

        days = max((equity_curve[-1][0] - equity_curve[0][0]).days, 1)
        annualized_return = (1 + total_return) ** (365 / days) - 1

        peak = values[0]
        max_drawdown = 0.0
        for value in values:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            max_drawdown = max(max_drawdown, drawdown)

        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve, annualized_return)

        return {
            "total_return": total_return,
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
        }
```

```python
    def _calculate_sharpe_ratio(
        self,
        equity_curve: list[tuple[date, float]],
        annualized_return: float,
    ) -> float:
        if len(equity_curve) < 2:
            return 0.0

        import statistics

        values = [value for _, value in equity_curve]
        daily_returns = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            curr = values[i]
            if prev <= 0:
                continue
            daily_returns.append((curr - prev) / prev)

        if len(daily_returns) < 2:
            return 0.0

        std_dev = statistics.stdev(daily_returns)
        if std_dev == 0:
            return 0.0

        annualized_std = std_dev * (252 ** 0.5)
        return annualized_return / annualized_std
```

---

## 七、多基金时间轴规则

### 7.1 核心规则

1. 组合时间轴取**所有基金净值日期的交集**
2. Engine 再剔除最前面的 `lookback_periods` 个点，形成有效交易时间轴
3. 只有在 `aligned_dates` 上才允许生成信号与执行调仓
4. 若最后一个有效日期无 `T+1`，则该日信号丢弃

---

### 7.2 Warmup 数据规则

为了让策略在用户指定回测起点处拥有足够历史窗口：

* Service 层抓数时必须额外拉取 **warmup 历史数据**
* warmup 仅用于策略计算，不直接作为结果展示区间
* 最终结果仍以用户指定的 `start_date ~ end_date` 为主展示区间

---

## 八、Service 层设计

### 8.1 PortfolioBacktestService

**文件：** `service/portfolio_backtest_service.py`

```python
from datetime import date, timedelta
from domain.backtest.engine import PortfolioBacktestEngine
from domain.backtest.models import PortfolioBacktestResult
from domain.backtest.strategies.portfolio_base import PortfolioStrategy
from domain.backtest.strategies.portfolio_momentum import (
    PortfolioMomentumStrategy,
    MomentumConfig,
)
from domain.backtest.strategies.rebalance.policy import RebalancePolicy
from domain.backtest.strategies.rebalance.threshold import ThresholdRebalancePolicy
from infrastructure.datasource.akshare_source import AkShareDataSource

class PortfolioBacktestService:
    """组合回测服务。"""

    def __init__(self, datasource: AkShareDataSource | None = None):
        self.datasource = datasource or AkShareDataSource()
        self.engine = PortfolioBacktestEngine()

    def run_portfolio_backtest(
        self,
        fund_codes: list[str],
        strategy_name: str,
        strategy_params: dict,
        start_date: date,
        end_date: date,
        initial_cash: float = 100000.0,
        rebalance_policy_name: str | None = None,
        rebalance_params: dict | None = None,
    ) -> PortfolioBacktestResult:
        strategy = self._create_strategy(strategy_name, strategy_params)
        lookback_periods = strategy_params.get("lookback_periods", 60)

        # warmup 数据：为动量窗口预留更早历史
        fetch_start_date = start_date - timedelta(days=lookback_periods * 2)

        nav_histories: dict[str, list[dict]] = {}
        for fund_code in fund_codes:
            history = self.datasource.get_fund_nav_history(
                fund_code=fund_code,
                start_date=fetch_start_date,
                end_date=end_date,
            )
            nav_histories[fund_code] = history

        rebalance_policy = None
        if rebalance_policy_name and rebalance_policy_name != "无":
            rebalance_policy = self._create_rebalance_policy(
                rebalance_policy_name,
                rebalance_params or {},
            )

        result = self.engine.run(
            strategy=strategy,
            fund_codes=fund_codes,
            nav_histories=nav_histories,
            rebalance_policy=rebalance_policy,
            lookback_periods=lookback_periods,
        )

        return result

    def _create_strategy(
        self,
        name: str,
        params: dict,
    ) -> PortfolioStrategy:
        if name == "PortfolioMomentum":
            config = MomentumConfig(
                lookback_periods=params.get("lookback_periods", 60),
                top_n=params.get("top_n", 2),
                signal_interval_periods=params.get("signal_interval_periods", 20),
            )
            return PortfolioMomentumStrategy(config)
        raise ValueError(f"Unknown portfolio strategy: {name}")

    def _create_rebalance_policy(
        self,
        name: str,
        params: dict,
    ) -> RebalancePolicy:
        if name == "Threshold":
            return ThresholdRebalancePolicy(
                threshold=params.get("threshold", 0.05)
            )
        raise ValueError(f"Unknown rebalance policy: {name}")
```

**说明：**

* 返回类型应为 `PortfolioBacktestResult`，不是 `dict`
* Service 层负责 warmup 抓数
* Engine 负责最终有效时间轴裁剪

---

## 九、UI 变更

### 9.1 新增组合回测区块

**文件：** `ui/pages/3_strategy_lab.py`

在现有单基金回测区块后新增：

```python
st.divider()
st.subheader("组合策略回测")

fund_codes_input = st.text_input(
    "基金池（逗号分隔）",
    placeholder="000001,000002,000003",
    key="portfolio_fund_codes",
)

if fund_codes_input:
    fund_codes = [code.strip() for code in fund_codes_input.split(",") if code.strip()]

    col1, col2 = st.columns(2)
    with col1:
        portfolio_strategy = st.selectbox(
            "组合策略",
            options=["PortfolioMomentum"],
            key="portfolio_strategy",
        )
    with col2:
        rebalance_policy = st.selectbox(
            "再平衡策略",
            options=["无", "Threshold"],
            key="portfolio_rebalance_policy",
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        lookback_periods = st.number_input(
            "动量窗口（交易点）",
            min_value=10,
            value=60,
            key="portfolio_lookback_periods",
        )
    with col2:
        top_n = st.number_input(
            "持仓数量",
            min_value=1,
            max_value=10,
            value=2,
            key="portfolio_top_n",
        )
    with col3:
        signal_interval_periods = st.number_input(
            "调仓间隔（交易点）",
            min_value=5,
            value=20,
            key="portfolio_signal_interval_periods",
        )

    threshold = None
    if rebalance_policy == "Threshold":
        threshold = st.number_input(
            "调仓阈值",
            min_value=0.01,
            max_value=0.20,
            value=0.05,
            step=0.01,
            key="portfolio_threshold",
        )

    if st.button("运行组合回测", type="primary", key="run_portfolio_backtest"):
        # 调用 PortfolioBacktestService
        pass
```

---

### 9.2 结果展示建议

建议至少展示：

* 总收益
* 年化收益
* 最大回撤
* 夏普比率
* 组合净值曲线
* 调仓记录表
* 组合权重历史表 / 图

本阶段 UI 只要求最小可用，不要求做复杂解释面板。

---

## 十、文件变更清单

| 文件                                                  | 动作                                                                |
| --------------------------------------------------- | ----------------------------------------------------------------- |
| `domain/backtest/models.py`                         | 新增 `PortfolioSignal`、`PortfolioBacktestResult`；扩展 `ExecutedTrade` |
| `domain/backtest/strategies/portfolio_base.py`      | 新增 `PortfolioStrategy` 基类                                         |
| `domain/backtest/strategies/portfolio_momentum.py`  | 新增 `PortfolioMomentumStrategy`                                    |
| `domain/backtest/strategies/rebalance/policy.py`    | 修订接口为 `apply()`                                                   |
| `domain/backtest/strategies/rebalance/threshold.py` | 完整实现 `ThresholdRebalancePolicy`                                   |
| `domain/backtest/strategies/__init__.py`            | 导出 `PortfolioStrategy`                                            |
| `domain/backtest/engine.py`                         | 新增 `PortfolioBacktestEngine`                                      |
| `service/portfolio_backtest_service.py`             | 新增                                                                |
| `ui/pages/3_strategy_lab.py`                        | 新增组合回测区块                                                          |

---

### 10.1 接口变更迁移说明

原接口（Phase 3A 存根）：

```python
def rebalance(
    self,
    current_positions: list[dict],
    target_weights: dict[str, float],
    context: SignalContext
) -> list[Signal]
```

新接口（Phase 3C）：

```python
def apply(
    self,
    signal: PortfolioSignal,
    current_positions: list[dict],
    context: SignalContext,
) -> PortfolioSignal | None
```

**说明：**

* `CompositeStrategy` 的 guard code 不动
* 再平衡型组合不走 `CompositeStrategy`
* 使用独立的 `PortfolioBacktestEngine`

---

## 十一、测试覆盖

### 11.1 数据模型测试

* `PortfolioSignal` 构造与权重校验
* 缺少 `"CASH"` 报错
* 权重和不为 1 报错
* 权重越界报错
* `PortfolioBacktestResult` 默认值

---

### 11.2 策略测试

* `PortfolioMomentumStrategy.generate_portfolio_signals()` 返回有效信号
* `lookback_periods` 基于交易点工作正常
* `signal_interval_periods` 基于交易点工作正常
* 前 `top_n` 等权 + `CASH` 配仓正确
* 同日不生成多条信号

---

### 11.3 RebalancePolicy 测试

* `ThresholdRebalancePolicy.apply()` 在偏差超过阈值时放行
* 在偏差低于阈值时拦截
* `CASH` 权重参与偏差判断

---

### 11.4 Engine 测试

* 时间轴交集对齐正确
* lookback 裁剪正确
* `T` 日信号、`T+1` 日执行正确
* 真正做到“先卖后买”
* 最后一天信号丢弃
* 现金不被强制重置
* 单基金池 / 多基金池都可运行

---

### 11.5 Service 测试

* 策略创建正确
* 再平衡策略创建正确
* warmup 抓数逻辑生效
* 端到端返回 `PortfolioBacktestResult`

---

## 十二、实现顺序建议

1. 数据模型：`PortfolioSignal`、`PortfolioBacktestResult`、`ExecutedTrade` 扩展
2. `PortfolioStrategy` 基类
3. `PortfolioMomentumStrategy`
4. `RebalancePolicy.apply()` 接口修订
5. `ThresholdRebalancePolicy`
6. `PortfolioBacktestEngine`
7. `PortfolioBacktestService`
8. UI 组合回测区块
9. 全量测试

---

## 十三、后续扩展

| Phase    | 内容                  |
| -------- | ------------------- |
| Phase 3C | 多基金轮动与再平衡（本设计）      |
| Phase 3D | 回测统计精细化             |
| 后续       | 与虚拟账户打通、税费/滑点、动态基金池 |
